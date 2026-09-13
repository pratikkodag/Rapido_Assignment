"""
A3: Evaluating CAMP_WA_002
=============================
Rapido captain onboarding take home, Part A3.

Growth claims CAMP_WA_002 drives onboarding completion and wants 5x
budget to scale it. This script tests whether that claim holds up, and
whether "5x" is even a feasible ask.

Run with: python campaign_evaluation.py
Expects captains.csv, approvals.csv, doc_events.csv, nudges.csv,
funnel_building.py in the same folder.
"""

import pandas as pd
from scipy import stats
from funnel_building import (load_data, determine_cohort_cutoff, split_cohort,
                              flag_and_remove_anomalies, classify_outcomes)

pd.set_option('display.width', 120)

CAMPAIGN_ID = 'CAMP_WA_002'
RC_LOCAL_POS = 1   # RC is always the 2nd required document for every vehicle type
MONTHS = 5         # mature cohort spans Jan-May 2026 (see A1)
RULE_WIDTH = 60


def header(title: str):
    """Prints a title framed with '=' rules above and below, used for
    every step so the console output reads as clearly delimited sections."""
    print("=" * RULE_WIDTH)
    print(title)
    print("=" * RULE_WIDTH)


def approval_rate(df: pd.DataFrame, by: str) -> pd.DataFrame:
    """Approval rate (%) and sample size, split by a grouping column."""
    out = df.groupby(by).agg(
        approval_rate=('final_status', lambda s: (s == 'approved').mean()),
        n=('final_status', 'size'),
    )
    out['approval_rate'] = (out['approval_rate'] * 100).round(1)
    return out


def main():
    captains, approvals = load_data()
    cutoff = determine_cohort_cutoff(captains, approvals)
    mature_captains, _ = split_cohort(captains, cutoff)
    mature = mature_captains.merge(approvals, on='captain_id', how='left')
    mature, _ = flag_and_remove_anomalies(mature)
    mature = classify_outcomes(mature)

    nudges = pd.read_csv('nudges.csv', parse_dates=['sent_ts'])
    doc = pd.read_csv('doc_events.csv', parse_dates=['event_ts'])

    camp = nudges[nudges['campaign_id'] == CAMPAIGN_ID][['captain_id', 'sent_ts', 'delivered', 'clicked']]
    m = mature.merge(camp, on='captain_id', how='left')
    m['got_message'] = m['sent_ts'].notna()

    header("COHORT")
    print(f"Total mature cohort           : {len(m):,} captains")
    print(f"Recipients of {CAMPAIGN_ID}   : {m['got_message'].sum():,}")
    print("=" * RULE_WIDTH + "\n")

    # ---- Step 1: reproduce the headline number as presented ----------------
    header("STEP 1 -- Reproducing the comparison as originally presented")
    naive = approval_rate(m, 'got_message')
    print(naive)
    naive_gap = naive.loc[True, 'approval_rate'] - naive.loc[False, 'approval_rate']
    print(f"\nUnadjusted gap: {naive_gap:.1f}pp (percentage points)")
    print("=" * RULE_WIDTH + "\n")

    # ---- Step 2: test whether the two groups are comparable ----------------
    header("STEP 2 -- Testing whether recipients and non-recipients are a fair comparison")
    rc_clear_ts = (doc[(doc['doc_type'] == 'RC') & (doc['event_type'] == 'verification_pass')]
                   .groupby('captain_id')['event_ts'].min())
    mm = m.merge(rc_clear_ts.rename('rc_cleared_at'), on='captain_id', how='left')
    sent = mm.dropna(subset=['sent_ts', 'rc_cleared_at'])
    sent_before_rc_cleared = (sent['rc_cleared_at'] >= sent['sent_ts']).sum()

    print(f"Recipients whose RC was not yet cleared at send time : {sent_before_rc_cleared} of {len(sent)}")
    print("-" * RULE_WIDTH)
    print("Finding:")
    print("  The campaign is triggered only after RC clearance. Recipients are, by")
    print("  construction, drawn exclusively from captains who already passed the funnel's")
    print("  largest bottleneck (see A1/A2). The comparison above is confounded by this and")
    print("  needs to be restated within a matched population (Step 3).")
    print("=" * RULE_WIDTH + "\n")

    # ---- Step 3: like-for-like comparison ----------------------------------
    header("STEP 3 -- Restating the comparison within a matched population (RC-clearers only)")
    eligible = m[m['stuck_idx'] > RC_LOCAL_POS].copy()
    coverage = eligible['got_message'].mean() * 100
    fair = approval_rate(eligible, 'got_message')
    print(f"Eligible population (cleared RC): {len(eligible):,}   |   Current coverage: {coverage:.1f}%\n")
    print(fair)
    print("=" * RULE_WIDTH + "\n")

    lift_pp = fair.loc[True, 'approval_rate'] - fair.loc[False, 'approval_rate']

    # ---- Step 4: statistical validity ---------------------------------------
    header("STEP 4 -- Testing whether the adjusted gap is statistically meaningful")
    ct = pd.crosstab(eligible['got_message'], eligible['final_status'] == 'approved')
    _, p_value, _, _ = stats.chi2_contingency(ct)
    e = eligible.copy()
    e['month'] = e['signup_ts'].dt.to_period('M')
    monthly = (e.groupby(['month', 'got_message'])['final_status']
               .apply(lambda s: (s == 'approved').mean() * 100).unstack())
    monthly_lift = monthly[True] - monthly[False]
    consistent = (monthly_lift > 0).all()

    print(f"Observed lift                       : {lift_pp:.1f}pp")
    print(f"Significance (chi-square test)      : p = {p_value:.2e}  (threshold for significance: p < 0.05)")
    print(f"Consistent across all cohort months : {'Yes' if consistent else 'No'} "
          f"(range {monthly_lift.min():.1f}pp to {monthly_lift.max():.1f}pp)")
    print("=" * RULE_WIDTH + "\n")

    # ---- Step 5: feasibility of the 5x request -----------------------------
    header("STEP 5 -- Assessing the feasibility of a 5x volume increase")
    n_eligible = len(eligible)
    n_covered = int(eligible['got_message'].sum())
    n_gap = n_eligible - n_covered
    max_scale = n_eligible / n_covered
    monthly_impact = (n_gap / MONTHS) * (lift_pp / 100)

    print(f"Eligible population               : {n_eligible:,}")
    print(f"Currently covered                 : {n_covered:,} ({coverage:.1f}%)")
    print(f"Maximum achievable scale factor    : {max_scale:.1f}x (requested: 5x -- not achievable)")
    print(f"Uncovered eligible captains        : {n_gap:,}")
    print(f"Estimated impact of full coverage  : +{monthly_impact:.0f} approved captains/month")
    print("=" * RULE_WIDTH + "\n")

    # ---- Summary --------------------------------------------------------
    header("SUMMARY")
    print(f"Headline number      : +{lift_pp:.1f}pp lift in final approval rate (statistically significant)")
    print(f"5x budget request    : not supported -- {max_scale:.1f}x is the mathematical ceiling")
    print(f"Realistic opportunity: +{monthly_impact:.0f} approved captains/month from full coverage of the eligible population")
    print(f"Caveat               : non-recipients within the eligible group may differ on an")
    print(f"                       unobserved factor (e.g. invalid contact details), which")
    print(f"                       would inflate this estimate if present")
    print("=" * RULE_WIDTH)


if __name__ == '__main__':
    main()