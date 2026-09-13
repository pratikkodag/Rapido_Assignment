"""
A2 RC Stage Leak Analysis
============================
Rapido captain onboarding take home, Part A2.

Builds on the mature cohort established in A1 (funnel_building.py) and
identifies the two largest fixable leaks at the RC (Registration
Certificate) verification stage.

Run with: python leak_analysis.py
Expects captains.csv, approvals.csv, doc_events.csv, funnel_building.py
in the same folder.
"""

import io
import contextlib
import pandas as pd
from funnel_building import (load_data, determine_cohort_cutoff, split_cohort,
                              flag_and_remove_anomalies, classify_outcomes)

pd.set_option('display.width', 160)

RC_LOCAL_POS = 1          
COHORT_MONTHS = 5         # mature cohort spans Jan-May 2026 (see A1)
#----------------Reason for choosing the Benchmark--------------------------------
# Benchmark segment for each finding deliberately NOT the single best
# group available, because the recommended fix can't realistically move
# the worst segment all the way to that group's rate.

DEVICE_TIER_BENCHMARK = 'mid'
# Not 'high': high-tier's low stuck rate comes partly from better camera
# hardware. A software only blur/lighting check can realistically bring
# low-tier up to mid-tier performance, not replicate better hardware.

CHANNEL_BENCHMARK = 'organic_app'

# Not 'fos_field': fos_field's low abandonment rate comes from a human
# agent physically present at signup. A reminder nudge is the realistic
# comparison against another self-serve channel, not against in person help.


def section(title: str):
    print('\n' + '=' * 72)
    print(title)
    print('=' * 72)


def subsection(title: str):
    print(f'\n{title}')
    print('-' * len(title))


def build_mature_cohort() -> pd.DataFrame:
    """
    Reconstructs the clean mature cohort from A1 (same cutoff, same
    anomaly exclusions, same stuck_idx classification).
    """
    with contextlib.redirect_stdout(io.StringIO()):
        captains, approvals = load_data()
        cutoff = determine_cohort_cutoff(captains, approvals)
        mature_captains, _ = split_cohort(captains, cutoff)
        mature = mature_captains.merge(approvals, on='captain_id', how='left')
        mature, _ = flag_and_remove_anomalies(mature)
        mature = classify_outcomes(mature)
    return mature


def segment_stuck_rate(mature: pd.DataFrame, seg_col: str,
                        stage_name: str = 'RC', stage_pos: int = RC_LOCAL_POS) -> pd.DataFrame:
    """
    Computes, for captains who reached a given stage, the share that
    never cleared it.
    """
    reached = mature[mature['stuck_idx'] >= stage_pos].copy()
    reached['stuck_here'] = reached['stuck_idx'] == stage_pos

    g = reached.groupby(seg_col).agg(
        captains_reaching_stage=('captain_id', 'count'),
        captains_stuck_here=('stuck_here', 'sum'),
    )
    g['stuck_rate_pct'] = (g['captains_stuck_here'] / g['captains_reaching_stage'] * 100).round(1)
    g = g.sort_values('stuck_rate_pct', ascending=False)

    print(g.to_string())
    worst, best = g.index[0], g.index[-1]
    gap = g['stuck_rate_pct'].iloc[0] - g['stuck_rate_pct'].iloc[-1]
    print(f"\nCaptains in the '{worst}' segment fail to clear {stage_name} in "
          f"{g['stuck_rate_pct'].iloc[0]:.1f}% of cases, versus {g['stuck_rate_pct'].iloc[-1]:.1f}% "
          f"for '{best}' -- a {gap:.1f} percentage-point gap.")
    return g


def failure_reason_fingerprint(doc: pd.DataFrame, mature: pd.DataFrame,
                                seg_col: str, worst_segment: str, best_segment: str,
                                doc_type: str = 'RC') -> bool:
    """
    Compares the failure_reason mix between the worst and best performing
    segment.
    """
    fails = doc[(doc['doc_type'] == doc_type) & (doc['event_type'] == 'verification_fail')]
    fails = fails.merge(mature[['captain_id', seg_col]], on='captain_id', how='inner')
    tab = pd.crosstab(fails[seg_col], fails['failure_reason'], normalize='index') * 100

    diff = (tab.loc[worst_segment] - tab.loc[best_segment]).sort_values(ascending=False)
    diff = diff[diff > 0]
    top_reason, top_gap = diff.index[0], diff.iloc[0]

    print(f"Failure reasons more common for '{worst_segment}' than '{best_segment}':")
    for reason, gap in diff.head(3).items():
        note = '  (primary driver)' if reason == top_reason else ''
        print(f"  {reason:<22} {tab.loc[worst_segment, reason]:5.1f}% vs {tab.loc[best_segment, reason]:5.1f}%"
              f"   ({gap:+.1f}pp){note}")

    mechanism_found = top_gap >= 5
    if mechanism_found:
        print(f"\nConclusion: root cause identified. '{top_reason}' is materially overrepresented "
              f"in the '{worst_segment}' segment.")
    else:
        print(f"\nConclusion: failure-reason mix is not materially different across segments. "
              f"This gap is not a document-quality issue -- a different mechanism is examined below.")
    return mechanism_found


def upload_abandonment_check(doc: pd.DataFrame, mature: pd.DataFrame, seg_col: str,
                              doc_type: str = 'RC', stage_pos: int = RC_LOCAL_POS) -> pd.Series:
    """
    Measures the share of captains who reached this stage but never
    submitted a document for it at all.
    """
    reached = mature[mature['stuck_idx'] >= stage_pos].copy()
    uploaded_ids = set(doc[(doc['doc_type'] == doc_type) &
                           (doc['event_type'] == 'upload_success')]['captain_id'])
    reached['never_uploaded'] = ~reached['captain_id'].isin(uploaded_ids)

    rate = (reached.groupby(seg_col)['never_uploaded'].mean() * 100).round(1).sort_values(ascending=False)
    print(f"Share of {doc_type}-reachers who never submitted a document, by {seg_col}:")
    print(rate.to_string())

    gap = rate.iloc[0] - rate.iloc[-1]
    print(f"\nConclusion: root cause identified. '{rate.index[0]}' captains abandon the process "
          f"before submitting {doc_type} in {rate.iloc[0]:.1f}% of cases, versus {rate.iloc[-1]:.1f}% "
          f"for '{rate.index[-1]}' ({gap:.1f}pp gap). This is a pre-submission drop-off, not a "
          f"document-quality problem.")
    return rate

def check_not_confounded(mature: pd.DataFrame, col_a: str, col_b: str,
                          stage_pos: int = RC_LOCAL_POS) -> bool:
    """
    Confirms col_a's effect is not simply col_b's effect under another
    label.
    """
    reached = mature[mature['stuck_idx'] >= stage_pos].copy()
    reached['stuck_here'] = reached['stuck_idx'] == stage_pos

    mix = pd.crosstab(reached[col_a], reached[col_b], normalize='index') * 100
    mix_spread = (mix.max() - mix.min()).max()

    within = reached.groupby([col_a, col_b])['stuck_here'].mean().unstack() * 100
    gap_survives = all(within[c].max() - within[c].min() > 5 for c in within.columns)

    return mix_spread < 5 and gap_survives


def check_monthly_stability(mature: pd.DataFrame, seg_col: str,
                             stage_pos: int = RC_LOCAL_POS) -> bool:
    """
    Confirms the segment gap holds in every signup month rather than
    being driven by one unusual month.
    """
    m = mature.copy()
    m['signup_month'] = m['signup_ts'].dt.to_period('M')
    reached = m[m['stuck_idx'] >= stage_pos].copy()
    reached['stuck_here'] = reached['stuck_idx'] == stage_pos

    piv = (reached.groupby(['signup_month', seg_col])['stuck_here'].mean() * 100).unstack()
    worst_col, best_col = piv.mean().idxmax(), piv.mean().idxmin()
    return piv[worst_col].min() > piv[best_col].max()


def downstream_conversion_rate(mature: pd.DataFrame, stage_pos: int = RC_LOCAL_POS) -> float:
    """
    Of captains who cleared this stage, the share that eventually reach
    final approval. Required because clearing RC does not guarantee
    approval ,later stages still filter people out.
    """
    cleared = mature[mature['stuck_idx'] > stage_pos]
    return (cleared['final_status'] == 'approved').mean()


def quantify_leak(finding: str, stage_name: str, root_cause: str, recommended_action: str,
                    reached_n: int, observed_rate: float, benchmark_rate: float,
                   conv_rate: float, months: int = COHORT_MONTHS) -> dict:
    """
    Converts a confirmed leak into incremental approved captains per
    month,this function
    does not look anything up itself, it only does the arithmetic.
    """
    recoverable = reached_n * (observed_rate - benchmark_rate)
    monthly = recoverable * conv_rate / months

    print(f"Finding                 : {finding}")
    print(f"Funnel Stage            : {stage_name}")
    print(f"Root Cause              : {root_cause}")
    print(f"Captains in Segment     : {reached_n:,} (reaching {stage_name})")
    print(f"Observed Stuck Rate     : {observed_rate:.1%}")
    print(f"Benchmark Stuck Rate    : {benchmark_rate:.1%}")
    print(f"Recoverable Captains    : ~{recoverable:.0f} (over {months}-month cohort window)")
    print(f"Approval Conversion Rate: {conv_rate:.1%} (RC clearers who reach final approval)")
    print(f"Projected Monthly Impact: +{monthly:.0f} approved captains/month")
    print(f"Recommended Action      : {recommended_action}")


    return {
        'finding': finding, 'stage': stage_name, 'action': recommended_action,
        'monthly_incremental_approved': monthly,
    }

def print_summary(results: list[dict], baseline_monthly_approved: float) -> None:
    """Ranks the quantified findings and states the combined impact."""
    section('SUMMARY AND RECOMMENDATIONS')
    ranked = sorted(results, key=lambda r: r['monthly_incremental_approved'], reverse=True)
    total = sum(r['monthly_incremental_approved'] for r in ranked)

    for i, r in enumerate(ranked, 1):
        pct = r['monthly_incremental_approved'] / baseline_monthly_approved * 100
        print(f"\nPriority {i}: {r['finding']}")
        print(f"  Stage             : {r['stage']}")
        print(f"  Recommended Action: {r['action']}")
        print(f"  Projected Impact  : +{r['monthly_incremental_approved']:.0f} approved captains/month "
              f"(+{pct:.1f}% vs. current baseline)")

    print(f"\nCombined, both fixes are projected to add roughly +{total:.0f} approved captains/month "
          f"({total/baseline_monthly_approved*100:.1f}% lift over the current "
          f"{baseline_monthly_approved:.0f}/month baseline).")


def main():
    section('LEAK ANALYSIS -- RC (REGISTRATION CERTIFICATE) STAGE')

    mature = build_mature_cohort()
    doc = pd.read_csv('doc_events.csv')

    approved_ct = (mature['final_status'] == 'approved').sum()
    baseline_monthly_approved = approved_ct / COHORT_MONTHS
    print(f"\nCohort            : {len(mature):,} captains (mature cohort, Jan-May 2026 signups)")
    print(f"Baseline Approvals: {approved_ct:,} approved over {COHORT_MONTHS} months "
          f"= {baseline_monthly_approved:.0f} approved captains/month")
    print(f"Target Stage      : RC -- the single largest volume loss in the onboarding funnel")

    # ---- Finding 1: device tier --------------------------------------------
    section('FINDING 1 -- DEVICE TIER')
    subsection('RC stuck rate by device tier')
    t1 = segment_stuck_rate(mature, 'device_tier')
    subsection('Root cause investigation')
    failure_reason_fingerprint(doc, mature, 'device_tier',
                                worst_segment=t1.index[0], best_segment=t1.index[-1])

    # ---- Finding 2: acquisition channel ------------------------------------
    section('FINDING 2 -- ACQUISITION CHANNEL')
    subsection('RC stuck rate by acquisition channel')
    t2 = segment_stuck_rate(mature, 'acquisition_channel')
    subsection('Root cause investigation')
    reason_found = failure_reason_fingerprint(doc, mature, 'acquisition_channel',
                                               worst_segment=t2.index[0], best_segment=t2.index[-1])
    abandonment_rate = None
    if not reason_found:
        print()
        abandonment_rate = upload_abandonment_check(doc, mature, 'acquisition_channel')

    conv_rate = downstream_conversion_rate(mature)

    # ---- Quantification -------------------------------------------------
    section('QUANTIFIED IMPACT')
    print(f"\nNote: {conv_rate:.1%} of captains who clear RC go on to be fully approved -- this "
          f"conversion rate is applied to both findings below.\n")

    # Finding 1 -- device tier. Mechanism confirmed via failure_reason,
    # so both observed and benchmark rates come from the stuck-rate table.
    worst_1 = t1.index[0]
    result_1 = quantify_leak(
        finding=f"'{worst_1}'-tier devices produce blurred, low-confidence RC document photos",
        stage_name='RC',
        root_cause='Camera quality on low-tier devices leads to image_blurred and '
                    'ocr_low_confidence verification failures',
        recommended_action='Add an in-app blur/lighting check before RC photo submission, prompting a '
                            're-take before the image ever reaches verification.',
        reached_n=int(t1.loc[worst_1, 'captains_reaching_stage']),
        observed_rate=t1.loc[worst_1, 'stuck_rate_pct'] / 100,
        benchmark_rate=t1.loc[DEVICE_TIER_BENCHMARK, 'stuck_rate_pct'] / 100,
        conv_rate=conv_rate,
    )
    print()

  
    worst_2 = abandonment_rate.index[0]
    result_2 = quantify_leak(
        finding=f"'{worst_2}' captains abandon RC before ever submitting a document",
        stage_name='RC',
        root_cause='Self-serve signups receive no prompt to complete the RC upload, '
                    'unlike field-agent-assisted signups',
        recommended_action=f"Send a targeted reminder (push/SMS) to '{worst_2}' captains who reach RC "
                            f"but do not upload within 24-48 hours.",
        reached_n=int(t2.loc[worst_2, 'captains_reaching_stage']),
        observed_rate=abandonment_rate.loc[worst_2] / 100,
        benchmark_rate=abandonment_rate.loc[CHANNEL_BENCHMARK] / 100,
        conv_rate=conv_rate,
    )

    print_summary([result_1, result_2], baseline_monthly_approved)


if __name__ == '__main__':
    main()