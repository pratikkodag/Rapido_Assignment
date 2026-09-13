"""
A4: Ranked Recommendations
=============================
Rapido captain onboarding take home, Part A4.

Synthesizes A2 (RC leak segmentation) and A3 (campaign evaluation) into
three ranked recommendations.

Run with: python recommendations.py
Expects captains.csv, approvals.csv, doc_events.csv, nudges.csv,
funnel_building.py in the same folder.
"""

import pandas as pd
from funnel_building import (load_data, determine_cohort_cutoff, split_cohort,
                              flag_and_remove_anomalies, classify_outcomes)

pd.set_option('display.width', 120)

RC_LOCAL_POS = 1
MONTHS = 5
RULE_WIDTH = 70


def header(title: str):
    print("=" * RULE_WIDTH)
    print(title)
    print("=" * RULE_WIDTH)


def build_cohort():
    """Same clean mature cohort used in A1/A2/A3."""
    captains, approvals = load_data()
    cutoff = determine_cohort_cutoff(captains, approvals)
    mature_captains, _ = split_cohort(captains, cutoff)
    mature = mature_captains.merge(approvals, on='captain_id', how='left')
    mature, _ = flag_and_remove_anomalies(mature)
    mature = classify_outcomes(mature)
    return mature


def conversion_rate_after_rc(mature: pd.DataFrame) -> float:
    """Of captains who clear RC, the share that go on to final approval."""
    cleared = mature[mature['stuck_idx'] > RC_LOCAL_POS]
    return (cleared['final_status'] == 'approved').mean()


def recommendation_device_tier(mature: pd.DataFrame, conv_rate: float) -> dict:
    """
    A2, Finding 1: low-tier devices produce blurred RC photos.
    """
    reached = mature[mature['stuck_idx'] >= RC_LOCAL_POS].copy()
    reached['stuck_here'] = reached['stuck_idx'] == RC_LOCAL_POS
    rates = reached.groupby('device_tier')['stuck_here'].mean()
    counts = reached.groupby('device_tier').size()

    observed, benchmark = rates['low'], rates['mid']
    recoverable = counts['low'] * (observed - benchmark)
    monthly_impact = recoverable * conv_rate / MONTHS

    return {
        'rank_input': monthly_impact,
        'what': "Add a photo-quality check in the app before a Registration Certificate "
                "photo is submitted, prompting a retake before it reaches verification.",
        'impact': monthly_impact,
        'working': f"{counts['low']:,} low-tier-device captains reach the RC step. Of them, "
                   f"{observed:.1%} get stuck there, compared with {benchmark:.1%} for mid-tier "
                   f"devices. {conv_rate:.1%} of captains who clear RC go on to full approval.",
        'cost_risk': "Moderate effort, needs a small product build and testing. Main risk is "
                     "an overly strict check rejecting genuinely good photos.",
        'metric': f"RC stuck-rate for low-tier devices, expected to move from {observed:.1%} "
                  f"toward the {benchmark:.1%} mid-tier level.",
        'confidence': "Mechanism is well supported by the failure-reason data, though the "
                      "impact hasn't been confirmed with a live test yet.",
    }

def recommendation_channel_abandonment(mature: pd.DataFrame, doc: pd.DataFrame,
                                        conv_rate: float) -> dict:
    """
    A2, Finding 2: paid_digital captains abandon RC before ever uploading.
    """
    reached = mature[mature['stuck_idx'] >= RC_LOCAL_POS].copy()
    uploaded_ids = set(doc[(doc['doc_type'] == 'RC') &
                           (doc['event_type'] == 'upload_success')]['captain_id'])
    reached['never_uploaded'] = ~reached['captain_id'].isin(uploaded_ids)

    rates = reached.groupby('acquisition_channel')['never_uploaded'].mean()
    counts = reached.groupby('acquisition_channel').size()

    observed, benchmark = rates['paid_digital'], rates['organic_app']
    recoverable = counts['paid_digital'] * (observed - benchmark)
    monthly_impact = recoverable * conv_rate / MONTHS

    return {
        'rank_input': monthly_impact,
        'what': "Send a reminder message to paid_digital captains who reach the RC step "
                "but haven't uploaded within 24 to 48 hours.",
        'impact': monthly_impact,
        'working': f"{counts['paid_digital']:,} paid_digital captains reach RC. Of them, "
                   f"{observed:.1%} never upload a document at all, compared with {benchmark:.1%} "
                   f"for organic_app signups. {conv_rate:.1%} conversion to final approval applied.",
        'cost_risk': "Low effort, reuses the existing messaging system already in place. "
                     "Small risk of message fatigue if sent too often.",
        'metric': f"Share of paid_digital captains who never upload, expected to move from "
                  f"{observed:.1%} toward the {benchmark:.1%} organic_app level.",
        'confidence': "The underlying behaviour (abandonment, not poor photo quality) is "
                      "confirmed, but this specific fix hasn't been tested live yet.",
    }


def recommendation_campaign_coverage(mature: pd.DataFrame, nudges: pd.DataFrame) -> dict:
    """
    A3: CAMP_WA_002 shows a real, validated +4.1pp lift among RC clearers,
    but only reaches 54.9% of that eligible population.
    """
    camp = nudges[nudges['campaign_id'] == 'CAMP_WA_002'][['captain_id', 'sent_ts']]
    m = mature.merge(camp, on='captain_id', how='left')
    m['got_message'] = m['sent_ts'].notna()

    eligible = m[m['stuck_idx'] > RC_LOCAL_POS].copy()
    rates = eligible.groupby('got_message')['final_status'].apply(lambda s: (s == 'approved').mean())
    counts = eligible.groupby('got_message').size()

    lift = rates[True] - rates[False]
    n_gap = counts[False]
    monthly_impact = (n_gap / MONTHS) * lift

    return {
        'rank_input': monthly_impact,
        'what': "Extend the CAMP_WA_002 message from its current 54.9% coverage to all "
                "captains who have cleared RC. Note: a full 5x increase isn't possible, "
                "since the eligible group isn't nearly that large.",
        'impact': monthly_impact,
        'working': f"{n_gap:,} eligible captains haven't received the message yet. The measured "
                   f"lift is {lift:.1%}, statistically significant, and consistent across all "
                   f"5 months of the cohort.",
        'cost_risk': "Low effort, reuses the existing send system. Some risk of message fatigue "
                     "at higher volume, and a small chance the estimate is slightly optimistic "
                     "if non-recipients differ from recipients in some unmeasured way.",
        'metric': f"Approval rate of the newly-covered group, expected to converge toward the "
                  f"{rates[True]:.1%} rate already seen among recipients.",
        'confidence': "Highest of the three, since this is a measured real-world effect "
                      "rather than a projected one.",
    }


def print_recommendations(recs: list[dict], baseline_monthly_approved: float):
    ranked = sorted(recs, key=lambda r: r['rank_input'], reverse=True)
    
    for i, r in enumerate(ranked, 1):
        r['rank'] = i

    campaign_rank = next(r['rank'] for r in ranked if 'CAMP_WA_002' in r['what'])
    device_rank = next(r['rank'] for r in ranked if 'photo-quality check' in r['what'])

    for i, r in enumerate(ranked, 1):
        header(f"RECOMMENDATION {i}")
        print(f"What to do      : {r['what']}")
        print(f"Expected impact : +{r['impact']:.0f} approved captains per month "
              f"({r['impact']/baseline_monthly_approved*100:.1f}% of the current baseline)")
        print(f"Working shown : {r['working']}")
        print(f"Cost and risk   : {r['cost_risk']}")
        print(f"Metric to watch : {r['metric']}")
        print("=" * RULE_WIDTH + "\n")

    total = sum(r['impact'] for r in ranked)
    header("COMBINED IMPACT")
    print(f"Together, all three are projected to add +{total:.0f} approved captains per month, "
          f"about {total/baseline_monthly_approved*100:.1f}% above the current "
          f"{baseline_monthly_approved:.0f}-per-month baseline.")
    print()
    print("A note on overlap:")
    print(f"  Recommendations {campaign_rank} and {device_rank} interact rather than operate independently.")
    print(f"  Recommendation {device_rank} increases the number of captains who clear RC, and")
    print(f"  Recommendation {campaign_rank} is targeted at exactly that population. As a result, some")
    print(f"  captains recovered by Recommendation {device_rank} would also benefit from Recommendation")
    print(f"  {campaign_rank}. The combined total above should be read as a reasonable estimate rather")
    print("  than the sum of two fully independent effects.")
    print("=" * RULE_WIDTH)

def main():
    mature = build_cohort()
    doc = pd.read_csv('doc_events.csv', parse_dates=['event_ts'])
    nudges = pd.read_csv('nudges.csv', parse_dates=['sent_ts'])

    baseline_monthly_approved = (mature['final_status'] == 'approved').sum() / MONTHS
    conv_rate = conversion_rate_after_rc(mature)

    header("A4 -- RANKED RECOMMENDATIONS")
    print(f"Baseline: {baseline_monthly_approved:.0f} approved captains per month")
    print("Recommendations are ranked by projected monthly impact, largest first.")
    print("=" * RULE_WIDTH + "\n")

    recs = [
        recommendation_campaign_coverage(mature, nudges),
        recommendation_device_tier(mature, conv_rate),
        recommendation_channel_abandonment(mature, doc, conv_rate),
    ]
    print_recommendations(recs, baseline_monthly_approved)


if __name__ == '__main__':
    main()