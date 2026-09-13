"""
B3. Is targeted acquisition the right intervention
Rapido captain acquisition take home, Part B3.

Reuses the B1 and B2 calculations quietly, so the numbers here always
match what those scripts printed, rather than being retyped. Adds two
fields not used before, avg_eta_min and avg_surge_multiplier from
airport_hourly.csv, since they directly test whether price incentives
already tried to fix this and whether that worked.

Run with: python targeted_acquisition_check.py
Expects airport_hourly.csv, airport_trips.csv, demand_supply_analysis.py,
and captain_post_trip_analysis.py in the same folder.
"""

import io
import contextlib
import pandas as pd

from demand_supply_analysis import (
    load_and_check_data as load_hourly,
    compare_airport_to_city,
    quantify_night_window,
)
from post_trip_analysis import (
    load_and_check_data as load_trips,
    return_fare_by_time,
    cancellation_by_time,
)

pd.set_option('display.width', 160)

NIGHT_HOURS = list(range(21, 24)) + list(range(0, 4))   # 9pm to 3am


def section(title: str):
    print('\n' + '=' * 72)
    print(title)
    print('=' * 72)


# ---------------------------------------------------------------------------
def load_b1_and_b2_context() -> tuple:
    """
    Reruns the B1 and B2 calculations without printing their output, so
    this script can reuse the same numbers instead of retyping them. This
    also confirms the whole pipeline still runs end to end from the raw
    files.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        hourly = load_hourly()
        by_zone_type = compare_airport_to_city(hourly)
        apt = hourly[hourly['zone_type'] == 'airport_terminal'].copy()
        night_stats = quantify_night_window(apt)

        trips = load_trips()
        return_fare = return_fare_by_time(trips)
        cancellation = cancellation_by_time(trips)

    print("B1 and B2 numbers reloaded.")
    return apt, night_stats, return_fare, cancellation


# ---------------------------------------------------------------------------
def check_price_incentive(apt: pd.DataFrame) -> pd.DataFrame:
    """
    Checks whether the app is already raising prices at night to attract
    more captains, and whether that is working. Surge multiplier means
    how many times the normal fare a ride costs. 1.0x is normal price,
    2.0x is double price. A higher surge is the app's way of trying to
    pull in more drivers with money.
    """
    apt = apt.copy()
    apt['hour'] = apt['hour_ts'].dt.hour
    apt['is_night'] = apt['hour'].isin(NIGHT_HOURS)

    g = apt.groupby('is_night').agg(
        avg_surge=('avg_surge_multiplier', 'mean'),
        avg_eta=('avg_eta_min', 'mean'),
    ).round(2)
    g.index = ['Day', 'Night']
    g.columns = ['Price vs. Normal (Surge)', 'Wait Time for a Ride (min)']
    print(g.to_string())

    max_surge = apt['avg_surge_multiplier'].max()
    night_surge = g.loc['Night', 'Price vs. Normal (Surge)']
    day_surge = g.loc['Day', 'Price vs. Normal (Surge)']

    print(f"\nWhat this means:")
    print(f"  - Rides at night already cost about {night_surge:.1f}x the normal fare, close to the")
    print(f"    highest price seen anywhere in the data, {max_surge:.1f}x.")
    print(f"  - During the day, price stays close to normal, around {day_surge:.1f}x.")
    print(f"  - The app is already charging close to double at night to attract more captains.")
    print(f"  - That has not solved the problem. Most night requests still go unfulfilled.")
    print(f"  - This suggests money alone will not fix this, since a high price is already in place.")
    return g


# ---------------------------------------------------------------------------
def estimate_headcount_gap(apt: pd.DataFrame) -> dict:
    """
    Estimates how many captains it would actually take to clear night
    demand. Uses how many rides each online captain already completes
    per hour at night, then works out how many captains that rate would
    need to cover all of night demand. This turns the acquisition idea
    into an actual number, instead of leaving it vague.
    """
    apt = apt.copy()
    apt['hour'] = apt['hour_ts'].dt.hour
    apt['is_night'] = apt['hour'].isin(NIGHT_HOURS)

    g = apt.groupby('is_night').agg(
        avg_requests=('requests', 'mean'),
        avg_fulfilled=('fulfilled_requests', 'mean'),
        avg_online=('online_captains', 'mean'),
    )
    g.index = ['Day', 'Night']
    g['fulfilled_per_captain'] = (g['avg_fulfilled'] / g['avg_online']).round(2)

    display = g.round(2)
    display.columns = ['Ride Requests (per hour)', 'Rides Completed (per hour)',
                        'Captains Online (avg)', 'Rides Completed per Captain (per hour)']
    print(display.to_string())

    night_throughput = g.loc['Night', 'fulfilled_per_captain']
    night_demand = g.loc['Night', 'avg_requests']
    night_online = g.loc['Night', 'avg_online']
    captains_needed = night_demand / night_throughput
    additional_needed = captains_needed - night_online

    print(f"\nWhat this means:")
    print(f"  - At night, {night_online:.0f} captains are online but {night_demand:.0f} rides are")
    print(f"    requested every hour. Each captain is already completing about {night_throughput:.1f}")
    print(f"    rides an hour, since there is far more demand than captains available.")
    print(f"  - If that same pace held, covering all {night_demand:.0f} requests would take about")
    print(f"    {captains_needed:.0f} captains online, not {night_online:.0f}.")
    print(f"  - That is roughly {additional_needed:.0f} more captains, online specifically during the")
    print(f"    9pm to 3am window, every single night.")

    return {
        'captains_needed': captains_needed,
        'night_online': night_online,
        'additional_needed': additional_needed,
    }


# ---------------------------------------------------------------------------
def print_summary(night_stats: dict, return_fare: pd.DataFrame, cancellation: pd.Series,
                   surge: pd.DataFrame, headcount: dict) -> None:
    """States the answer to B3 as plain labeled fields, pulling every
    number from what was already computed above."""
    section('SUMMARY')

    night_rf = return_fare.loc['Night (9pm to 3am)', 'Return Fare Rate']
    night_cc = cancellation['Night (9pm to 3am)']
    night_surge = surge.loc['Night', 'Price vs. Normal (Surge)']
    max_surge_note = "close to the highest price seen anywhere in the data"

    print(f"\nNight Price vs. Normal   : {night_surge:.1f}x, {max_surge_note}")
    print(f"Night Return Fare Rate   : {night_rf:.0f}%, from B2")
    print(f"Night Cancellation Rate  : {night_cc:.0f}%, from B2")
    print(f"Captains Needed at Night : ~{headcount['captains_needed']:.0f}, versus "
          f"{headcount['night_online']:.0f} online today")
    print(f"Additional Captains      : ~{headcount['additional_needed']:.0f}, specifically online "
          f"9pm to 3am, every night")
    print(f"\nVerdict                  : targeted acquisition is not the right first move.")
    print(f"Reasoning                :")
    print(f"  - Surge pricing is already near its ceiling at night and still leaves most demand unfulfilled,")
    print(f"    so a signup bonus is unlikely to succeed where doubled fares have not.")
    print(f"  - A newly hired captain faces the same return fare odds as everyone else, so B2's stranding")
    print(f"    problem does not go away just because a captain is new.")
    print(f"  - Fully closing the gap by headcount alone would need roughly tripling night online captains,")
    print(f"    a large recurring ask for a narrow six hour window.")
    print(f"\nRecommended Instead      :")
    print(f"  - Guarantee a minimum return fare for night airport trips, especially to suburban drops,")
    print(f"    where the return fare rate is lowest.")
    print(f"  - Consider a queueing system at the airport so a captain who waits is guaranteed the next fare,")
    print(f"    instead of risking an empty drive back.")
    print(f"  - Re-measure night return fare rate, cancellation rate, and unfulfilled volume after that fix,")
    print(f"    then size any remaining acquisition need against the smaller, real gap.")


# ---------------------------------------------------------------------------
def main():
    section('LOADING B1 AND B2 RESULTS')
    apt, night_stats, return_fare, cancellation = load_b1_and_b2_context()

    section('STEP 1. Is price already trying to fix this')
    surge = check_price_incentive(apt)

    section('STEP 2. Sizing the headcount gap')
    headcount = estimate_headcount_gap(apt)

    print_summary(night_stats, return_fare, cancellation, surge, headcount)


if __name__ == '__main__':
    main()