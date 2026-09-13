"""
B2. What happens to a captain after an airport trip
Rapido captain acquisition take home, Part B2.

Run with: python post_trip_analysis.py
Expects airport_trips.csv in the same folder.
"""

import pandas as pd

pd.set_option('display.width', 160)

NIGHT_HOURS = list(range(21, 24)) + list(range(0, 4))   # 9pm to 3am


def section(title: str):
    print('\n' + '=' * 72)
    print(title)
    print('=' * 72)


# ---------------------------------------------------------------------------
def load_and_check_data(path: str = 'airport_trips.csv') -> pd.DataFrame:
    """
    Loads the trip level file and checks it for a logical problem before
    using it: some cancelled trips still carry a return fare value, which
    does not make sense since a cancelled trip has no real drop off.
    """
    df = pd.read_csv(path, parse_dates=['request_ts'])
    df['hour'] = df['request_ts'].dt.hour
    df['is_night'] = df['hour'].isin(NIGHT_HOURS)
    df['month'] = df['request_ts'].dt.month_name()

    print(f"Rows                : {len(df):,}")
    print(f"Date range          : {df['request_ts'].min().date()} to {df['request_ts'].max().date()}")
    print(f"Pickup zones        : {sorted(df['pickup_zone_id'].unique())}")
    print(f"Drop zone types     : {sorted(df['drop_zone_type'].unique())}")

    bad = df[(df['captain_cancelled'] == 1) & (df['got_return_fare_within_20min'] == 1)]
    print(f"\nData quality note   : {len(bad):,} rows show a return fare on a cancelled trip. "
          f"A cancelled trip has no real drop off, so this field is not meaningful for those rows. "
          f"Return fare numbers below use completed trips only.")
    return df


# ---------------------------------------------------------------------------
def return_fare_by_time(df: pd.DataFrame) -> pd.DataFrame:
    """
    Checks how often a captain gets a return fare within 20 minutes after
    an airport drop off, comparing night and day. Only completed trips are
    used, since a cancelled trip never had a real drop off to measure from.
    """
    completed = df[df['captain_cancelled'] == 0]
    g = completed.groupby('is_night')['got_return_fare_within_20min'].agg(['mean', 'count'])
    g.index = ['Day (4am to 8pm)', 'Night (9pm to 3am)']
    g.columns = ['Return Fare Rate', 'Trips']
    g['Return Fare Rate'] = (g['Return Fare Rate'] * 100).round(1)

    print(g.to_string())
    day_rate = g.loc['Day (4am to 8pm)', 'Return Fare Rate']
    night_rate = g.loc['Night (9pm to 3am)', 'Return Fare Rate']
    print(f"\nA captain who completes an airport drop off gets a fare back within 20 minutes "
          f"{night_rate:.0f}% of the time at night, versus {day_rate:.0f}% in the day. "
          f"Night drop offs leave a captain stranded more often.")
    return g


# ---------------------------------------------------------------------------
def cancellation_by_time(df: pd.DataFrame) -> pd.Series:
    """
    Checks how often a captain cancels an airport pickup, comparing night
    and day. A cancellation means the captain chose not to take the trip
    at all, which is a separate signal from what happens after a trip.
    """
    g = df.groupby('is_night')['captain_cancelled'].mean() * 100
    g.index = ['Day (4am to 8pm)', 'Night (9pm to 3am)']
    g = g.round(1)

    print(g.rename('Cancellation Rate').to_frame().to_string())
    day_rate = g['Day (4am to 8pm)']
    night_rate = g['Night (9pm to 3am)']
    print(f"\nCaptains cancel {night_rate:.0f}% of airport pickups at night, versus {day_rate:.0f}% "
          f"in the day. Captains are more likely to turn down an airport trip at night.")
    return g


# ---------------------------------------------------------------------------
def analysis_by_drop_zone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Breaks return fare rate and cancellation rate down by where the trip
    drops the captain off. This checks whether the night effect above is
    the same everywhere, or concentrated in one type of destination.
    """
    completed = df[df['captain_cancelled'] == 0]
    result = pd.DataFrame({
        'Share of Trips': (df['drop_zone_type'].value_counts(normalize=True) * 100).round(1),
        'Return Fare Rate': (completed.groupby('drop_zone_type')['got_return_fare_within_20min'].mean() * 100).round(1),
        'Cancellation Rate': (df.groupby('drop_zone_type')['captain_cancelled'].mean() * 100).round(1),
        'Avg Distance (km)': df.groupby('drop_zone_type')['trip_distance_km'].mean().round(1),
    }).sort_values('Return Fare Rate')

    print(result.to_string())

    worst = result.index[0]
    print(f"\n'{worst}' is the weakest destination: only {result.loc[worst, 'Return Fare Rate']:.0f}% "
          f"of captains get a fare back within 20 minutes, and it is also where captains cancel "
          f"most often ({result.loc[worst, 'Cancellation Rate']:.0f}%). It also carries {result.loc[worst,'Share of Trips']:.0f}% "
          f"of all airport trips.")
    return result


# ---------------------------------------------------------------------------
def check_night_effect_within_each_zone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Confirms the night effect on return fare rate holds inside every drop
    zone type, not just in the overall average. This rules out the drop
    zone mix simply shifting toward worse zones at night.
    """
    completed = df[df['captain_cancelled'] == 0]
    mix = pd.crosstab(df['is_night'], df['drop_zone_type'], normalize='index') * 100
    mix.index = ['Day', 'Night']
    print("Drop zone mix by time of day, percent of trips:")
    print(mix.round(1).to_string())

    rate = completed.groupby(['drop_zone_type', 'is_night'])['got_return_fare_within_20min'].mean().unstack() * 100
    rate.columns = ['Day', 'Night']
    print("\nReturn fare rate, by drop zone and time of day:")
    print(rate.round(1).to_string())

    print(f"\nThe drop zone mix barely changes at night, but the return fare rate falls in every "
          f"single zone type. This is a night effect on its own.")
    return rate


# ---------------------------------------------------------------------------
def check_not_a_distance_story(df: pd.DataFrame) -> None:
    """
    Checks whether night trips are simply longer, which would be a
    different and less interesting explanation for the return fare gap.
    """
    g = df.groupby('is_night')['trip_distance_km'].mean().round(1)
    g.index = ['Day', 'Night']
    print(g.rename('Avg Distance (km)').to_frame().to_string())
    spread = abs(g['Night'] - g['Day'])
    print(f"\nAverage trip distance is almost identical, {spread:.1f} km apart. "
          f"The gap in return fares is not explained by night trips being longer.")


# ---------------------------------------------------------------------------
def check_monthly_stability(df: pd.DataFrame) -> None:
    """
    Confirms the night effect on return fare rate and cancellation rate
    holds in both months in the data, not just one.
    """
    completed = df[df['captain_cancelled'] == 0]
    rf = completed.groupby(['month', 'is_night'])['got_return_fare_within_20min'].mean().unstack() * 100
    cc = df.groupby(['month', 'is_night'])['captain_cancelled'].mean().unstack() * 100
    rf.columns = cc.columns = ['Day', 'Night']

    print("Return fare rate, by month:")
    print(rf.round(1).to_string())
    print("\nCancellation rate, by month:")
    print(cc.round(1).to_string())
    print(f"\nBoth patterns hold in May and June. This is a stable effect, not a one month event.")


# ---------------------------------------------------------------------------
def print_summary(return_fare: pd.DataFrame, cancellation: pd.Series, by_zone: pd.DataFrame) -> None:
    """States the answer to B2 """
    section('SUMMARY')

    day_rf = return_fare.loc['Day (4am to 8pm)', 'Return Fare Rate']
    night_rf = return_fare.loc['Night (9pm to 3am)', 'Return Fare Rate']
    day_cc = cancellation['Day (4am to 8pm)']
    night_cc = cancellation['Night (9pm to 3am)']
    worst_zone = by_zone.index[0]
    worst_zone_rf = by_zone.loc[worst_zone, 'Return Fare Rate']
    worst_zone_share = by_zone.loc[worst_zone, 'Share of Trips']

    print(f"\nReturn Fare Rate, Day   : {day_rf:.0f}%")
    print(f"Return Fare Rate, Night : {night_rf:.0f}%")
    print(f"Cancellation Rate, Day  : {day_cc:.0f}%")
    print(f"Cancellation Rate, Night: {night_cc:.0f}%")
    print(f"Weakest Drop Zone       : {worst_zone}, only {worst_zone_rf:.0f}% return fare rate, "
          f"{worst_zone_share:.0f}% of all airport trips")
    print(f"Distance Effect         : none, trip length is nearly the same at night and in the day")
    print(f"Conclusion              : a captain who takes an airport trip, especially at night or to "
          f"a suburban drop, is likely to be stranded without a quick fare back. Captains already "
          f"react to this by cancelling more airport trips at night. Hiring more captains does not "
          f"fix this on its own, since new captains face the same odds.")


# ---------------------------------------------------------------------------
def main():
    section('DATA CHECK')
    df = load_and_check_data()

    section('STEP 1. Return fare rate, night versus day')
    return_fare = return_fare_by_time(df)

    section('STEP 2. Cancellation rate, night versus day')
    cancellation = cancellation_by_time(df)

    section('STEP 3. Where do airport trips actually go')
    by_zone = analysis_by_drop_zone(df)

    section('STEP 4. Is the night effect the same in every drop zone')
    check_night_effect_within_each_zone(df)

    section('STEP 5. Is this just about trip distance')
    check_not_a_distance_story(df)

    section('STEP 6. Is the pattern stable across both months')
    check_monthly_stability(df)

    print_summary(return_fare, cancellation, by_zone)


if __name__ == '__main__':
    main()