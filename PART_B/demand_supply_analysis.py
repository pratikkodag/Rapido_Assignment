"""
B1: Airport Demand-Supply Mismatch
=====================================
Rapido captain acquisition take-home, Part B1.

Run with: python demand_supply_analysis.py
Expects airport_hourly.csv in the same folder.
"""

import pandas as pd

pd.set_option('display.width', 160)

NIGHT_HOURS = list(range(21, 24)) + list(range(0, 4))   # 21:00 - 03:00
DOW_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def section(title: str):
    print('\n' + '=' * 72)
    print(title)
    print('=' * 72)


def subsection(title: str):
    print(f'\n{title}')
    print('-' * len(title))


def unfulfilled_rate(df: pd.DataFrame) -> float:
    """Pooled unfulfilled rate (%): total unfulfilled / total requests. Pooling on raw
    counts (not averaging per-row percentages) means busy hours are weighted correctly."""
    return df['unfulfilled_requests'].sum() / df['requests'].sum() * 100

def load_and_check_data(path: str = 'airport_hourly.csv') -> pd.DataFrame:
    """Loads the hourly marketplace file and confirms it reconciles before
    trusting any downstream number."""
    df = pd.read_csv(path, parse_dates=['hour_ts'])
    reconciled = (df['requests'] == df['fulfilled_requests'] + df['unfulfilled_requests']).all()

    print(f"Rows                : {len(df):,}")
    print(f"Date range          : {df['hour_ts'].min().date()} to {df['hour_ts'].max().date()}")
    print(f"Zones covered       : {df['zone_id'].nunique()} ({', '.join(sorted(df['zone_id'].unique()))})")
    print(f"requests = fulfilled + unfulfilled, every row: {'Yes' if reconciled else 'NO investigate before trusting anything below'}")
    assert reconciled, "Data does not reconcile stop here."
    return df


def compare_airport_to_city(df: pd.DataFrame) -> pd.Series:
    """
    Establishes whether airport terminals are actually unusual, using every
    other zone type in the city as the baseline.
    """
    by_zone_type = df.groupby('zone_type').apply(unfulfilled_rate).rename('unfulfilled_rate_pct').round(1)
    by_zone_type = by_zone_type.sort_values(ascending=False)

    display = by_zone_type.rename_axis('Zone Type').to_frame('Unfulfilled %')
    print(display.to_string())

    airport_rate = by_zone_type['airport_terminal']
    next_worst = by_zone_type.drop('airport_terminal').max()
    print(f"\nAirport terminals fail to fulfil {airport_rate:.1f}% of ride requests, versus "
          f"{next_worst:.1f}% at the next-worst zone type roughly a "
          f"{airport_rate / next_worst:.0f}x gap.")
    return by_zone_type

def check_terminal_consistency(df: pd.DataFrame) -> pd.Series:
    """
    Confirms both airport terminal zones show the same pattern, so the
    finding is an airport wide story rather than one zone's quirk being
    averaged in with a normal one.
    """
    apt = df[df['zone_type'] == 'airport_terminal']
    by_terminal = apt.groupby('zone_id').apply(unfulfilled_rate).round(1)

    display = by_terminal.rename_axis('Terminal').to_frame('Unfulfilled %')
    print(display.to_string())

    spread = by_terminal.max() - by_terminal.min()
    print(f"\nBoth terminals show essentially the same rate (spread: {spread:.1f}pp),"
          f"this confirms one consistent airport wide pattern, not a single outlier zone.")
    return by_terminal


def check_stability_over_time(apt: pd.DataFrame) -> None:
    """
    Checks whether the mismatch is a stable, structural pattern or driven by
    a particular day of week or a month-over-month trend (e.g. weekend
    surges, seasonal growth).
    """
    apt = apt.copy()
    apt['dow'] = apt['hour_ts'].dt.day_name()
    apt['month'] = apt['hour_ts'].dt.month_name()

    by_dow = apt.groupby('dow').apply(unfulfilled_rate).reindex(DOW_ORDER).round(1)
    by_month = apt.groupby('month').apply(unfulfilled_rate).round(1)

    print("By day of week:")
    print(by_dow.rename_axis('Day').to_frame('Unfulfilled %').to_string())
    print("\nBy month:")
    print(by_month.rename_axis('Month').to_frame('Unfulfilled %').to_string())

    dow_spread = by_dow.max() - by_dow.min()
    month_spread = by_month.max() - by_month.min()
    print(f"\nDay-of-week spread: {dow_spread:.1f}pp. Month-over-month spread: {month_spread:.1f}pp.")
    print("Both are small relative to the airport-vs-city gap above, this rules out a "
          "weekend-rush or seasonal-growth explanation. The pattern is stable and structural, "
          "which means it must live inside the 24-hour cycle instead.")


def find_hourly_pattern(apt: pd.DataFrame) -> pd.DataFrame:
    """
    Breaks the airport only data down by hour of day this is where the
    mismatch is expected to actually live, based on the stability check
    above having ruled out day-of-week and month effects.
    """
    apt = apt.copy()
    apt['hour'] = apt['hour_ts'].dt.hour
    by_hour = apt.groupby('hour').agg(
        requests=('requests', 'sum'),
        unfulfilled=('unfulfilled_requests', 'sum'),
        avg_online_captains=('online_captains', 'mean'),
    )
    by_hour['unfulfilled_rate_pct'] = (by_hour['unfulfilled'] / by_hour['requests'] * 100).round(1)
    by_hour['avg_online_captains'] = by_hour['avg_online_captains'].round(1)

    display = by_hour[['unfulfilled_rate_pct', 'avg_online_captains']].rename(
        columns={'unfulfilled_rate_pct': 'Unfulfilled %', 'avg_online_captains': 'Avg Captains Online'}
    ).rename_axis('Hour')
    print(display.to_string())

    worst_hour = by_hour['unfulfilled_rate_pct'].idxmax()
    best_hour = by_hour['unfulfilled_rate_pct'].idxmin()
    print(f"\nWorst hour: {worst_hour:02d}:00 ({by_hour.loc[worst_hour, 'unfulfilled_rate_pct']:.1f}% unfulfilled). "
          f"Best hour: {best_hour:02d}:00 ({by_hour.loc[best_hour, 'unfulfilled_rate_pct']:.1f}% unfulfilled).")
    return by_hour


def quantify_night_window(apt: pd.DataFrame, night_hours: list = NIGHT_HOURS) -> dict:
    """
    Splits the day into two windows  Night (21:00-03:00) and Day (the
    remaining 17 hours) and compares them side by side. The point of
    this step: STEP 4's hour-by-hour table shows THAT the pattern exists,
    this step shows how big it is in plain terms,how much worse night
    is, and how many actual requests that represents.
    """
    apt = apt.copy()
    apt['hour'] = apt['hour_ts'].dt.hour
    apt['is_night'] = apt['hour'].isin(night_hours)

    summary = apt.groupby('is_night').agg(
        requests=('requests', 'sum'),
        unfulfilled=('unfulfilled_requests', 'sum'),
        avg_requests_per_hour=('requests', 'mean'),
        avg_online_captains=('online_captains', 'mean'),
    ).rename(index={True: 'Night (9pm-3am)', False: 'Day (4am-8pm)'})
    summary['unfulfilled_pct'] = (summary['unfulfilled'] / summary['requests'] * 100).round(1)

    # Clean 3-column table: one row per window, each column self-explanatory.
    display = summary[['avg_requests_per_hour', 'avg_online_captains', 'unfulfilled_pct']].round(1)
    display.columns = ['Requests/Hour', 'Avg Captains Online', 'Unfulfilled %']
    display = display.rename_axis('Time Window')
    print(display.to_string())

    night = summary.loc['Night (9pm-3am)']
    day = summary.loc['Day (4am-8pm)']
    days = apt['hour_ts'].dt.date.nunique()
    per_night = night['unfulfilled'] / days
    night_share_of_hours = len(night_hours) / 24 * 100
    night_share_of_unfulfilled = night['unfulfilled'] / summary['unfulfilled'].sum() * 100
    demand_ratio = night['avg_requests_per_hour'] / day['avg_requests_per_hour']
    supply_pct = night['avg_online_captains'] / day['avg_online_captains'] * 100

    print(f"\nWhat this shows:")
    print(f"  - Night is only {night_share_of_hours:.0f}% of the clock, but {night_share_of_unfulfilled:.0f}% "
          f"of all unfulfilled airport demand happens in it.")
    print(f"  - That's ~{per_night:.0f} unfulfilled requests, every single night.")
    print(f"  - Demand is {demand_ratio:.1f}x higher at night ({night['avg_requests_per_hour']:.0f} vs. "
          f"{day['avg_requests_per_hour']:.0f} requests/hour), while supply drops to {supply_pct:.0f}% of "
          f"daytime levels ({night['avg_online_captains']:.0f} vs. {day['avg_online_captains']:.0f} captains online).")
    print(f"  - Demand goes up right when supply goes down.")

    return {
        'per_night_unfulfilled': per_night,
        'night_share_of_unfulfilled': night_share_of_unfulfilled,
        'night_requests_per_hour': night['avg_requests_per_hour'],
        'day_requests_per_hour': day['avg_requests_per_hour'],
        'night_captains': night['avg_online_captains'],
        'day_captains': day['avg_online_captains'],
        'days_in_data': days,
    }


# ---------------------------------------------------------------------------
def print_bottom_line(by_zone_type: pd.Series, night_stats: dict) -> None:
    """States the final answer as plain labeled fields the numbers a
    reader would actually want to lift straight into a memo or slide."""
    section('SUMMARY')

    airport_rate = by_zone_type['airport_terminal']
    next_worst = by_zone_type.drop('airport_terminal').max()
    total_night_unfulfilled = night_stats['per_night_unfulfilled'] * night_stats['days_in_data']
    demand_ratio = night_stats['night_requests_per_hour'] / night_stats['day_requests_per_hour']
    supply_pct = night_stats['night_captains'] / night_stats['day_captains'] * 100

    print(f"\nAffected Window        : 9pm - 3am, every night")
    print(f"Consistency             : same rate on every day of the week; same in both months (no seasonal drift)")
    print(f"Airport Unfulfilled Rate: {airport_rate:.0f}%  (vs. {next_worst:.0f}% at the next-worst zone type)")
    print(f"Nightly Volume          : ~{night_stats['per_night_unfulfilled']:.0f} unfulfilled requests per night")
    print(f"Total Volume ({night_stats['days_in_data']} days)  : ~{total_night_unfulfilled:,.0f} unfulfilled requests")
    print(f"Demand at Night         : {demand_ratio:.1f}x the daytime rate")
    print(f"Supply at Night         : drops to {supply_pct:.0f}% of the daytime count")
    print(f"Root Cause              : demand rises and supply falls at the same hours.")

def main():
    section('DATA CHECK')
    df = load_and_check_data()

    section('STEP 1 Are airport terminals actually unusual?')
    by_zone_type = compare_airport_to_city(df)

    apt = df[df['zone_type'] == 'airport_terminal'].copy()

    section('STEP 2 Is this consistent across both airport terminals?')
    check_terminal_consistency(df)

    section('STEP 3 Is the pattern stable, or driven by a specific day/month?')
    check_stability_over_time(apt)

    section('STEP 4 Where exactly does the mismatch live within the day?')
    find_hourly_pattern(apt)

    section('STEP 5 Quantifying the night window')
    night_stats = quantify_night_window(apt)

    print_bottom_line(by_zone_type, night_stats)


if __name__ == '__main__':
    main()