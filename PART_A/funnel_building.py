"""
A1 Signup -> Approved funnel
=================================================
Rapido captain onboarding take home, Part A1.

Run with: python funnel_building.py
Expects captains.csv and approvals.csv in the same folder.

"""

import pandas as pd

pd.set_option('display.width', 160)

REJECT_REASONS_NON_DOC = {
    'background_check_failed', 'vehicle_age_policy',
    'doc_authenticity_flag', 'duplicate_captain',
}
# These values show up in last_stage_reached for REJECTED captains who
# actually cleared every document,they failed a check that isn't part
# of the document sequence at all, so they must NOT be counted as
# "stuck in docs".

STAGES = ['DL', 'RC', 'AADHAAR', 'PERMIT', 'FITNESS', 'INSURANCE']


def load_data(captains_path: str = 'captains.csv',
              approvals_path: str = 'approvals.csv') -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load the two raw files this funnel needs.
    Returns
    -------
    (captains, approvals) : tuple of DataFrames, timestamps already parsed.
    """
    captains = pd.read_csv(captains_path, parse_dates=['signup_ts'])
    approvals = pd.read_csv(approvals_path, parse_dates=['decision_ts'])
    return captains, approvals


def determine_cohort_cutoff(captains: pd.DataFrame, approvals: pd.DataFrame) -> pd.Timestamp:
    """
    Work out where to cut off the signup cohort so we don't mistake
    "hasn't had time to finish onboarding yet" for "dropped out".
    Method
    ------
    1. Measure how long captains who reached approved/rejected actually
       took, from signup to decision.
    2. Independently confirm by checking which signup month(s) the
       'in_progress' (unresolved) status appears in.

    Returns
    -------
    pd.Timestamp(signups strictly before this date form the mature cohort).
    """
    merged = captains.merge(approvals, on='captain_id', how='left')

    decided = merged.dropna(subset=['decision_ts'])
    decided = decided[decided['final_status'].isin(['approved', 'rejected'])]
    days_to_decision = (decided['decision_ts'] - decided['signup_ts']).dt.total_seconds() / 86400

    print("Time-to-decision stats (days), approved/rejected captains only:")
    print(days_to_decision.describe())

    in_progress_months = merged.loc[
        merged['final_status'] == 'in_progress', 'signup_ts'
    ].dt.to_period('M').unique()
    print("\n'in_progress' status appears ONLY for signup months:", in_progress_months)

    # DECISION: use a full calendar-month cutoff for clarity/defensibility,
    # rather than an arbitrary day-count buffer. The observed max time-to-
    # decision (~14 days) comfortably fits inside "one full month before
    # the extract date", so cutting the cohort at the start of the most
    # recent signup month is a safe, round, easy-to-explain choice.
    latest_signup_month_start = captains['signup_ts'].max().to_period('M').start_time
    return latest_signup_month_start


def split_cohort(captains: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split all signups into a 'mature' cohort (safe to judge) and a
    'too recent' cohort (excluded, reported separately).

    Returns
    -------
    (mature_captains, recent_captains)
    """
    mature_captains = captains[captains['signup_ts'] < cutoff].copy()
    recent_captains = captains[captains['signup_ts'] >= cutoff].copy()

    print(f"\nMature cohort (signups before {cutoff.date()}): {len(mature_captains)}")
    print(f"Excluded — too recent to have a resolved outcome: {len(recent_captains)}")
    return mature_captains, recent_captains


def flag_and_remove_anomalies(mature: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Remove records that contradict the stated onboarding rules, instead of
    silently absorbing them into the funnel.

    Known anomaly: some ERickshaw captains have last_stage_reached ==
    'PERMIT', despite Permit only applying to Auto/Cab per the requirement
    table.

    Returns
    -------
    (clean_mature, anomalies)
    """
    anomaly_mask = (mature['vehicle_type'] == 'ERickshaw') & (mature['last_stage_reached'] == 'PERMIT')
    anomalies = mature[anomaly_mask].copy()
    clean_mature = mature[~anomaly_mask].copy()

    print(f"Excluded — anomalous PERMIT record on a non-Permit vehicle type: {len(anomalies)}")
    return clean_mature, anomalies


def required_sequence(vehicle_type: str) -> list[str]:
    """
    Return the ordered list of document stages this vehicle type must clear.
    Permit is conditional: only Auto and Cab require it.
    """
    base = ['DL', 'RC', 'AADHAAR']
    if vehicle_type in ('Auto', 'Cab'):
        base.append('PERMIT')
    base += ['FITNESS', 'INSURANCE']
    return base


def stuck_local_index(row: pd.Series) -> int | None:
    """
    For one captain, return the position (0-indexed, within THEIR OWN
    required sequence) at which they got stuck.

    """
    seq = row['seq']

    if row['final_status'] == 'approved':
        return len(seq)

    if row['final_status'] == 'rejected' and row['last_stage_reached'] in REJECT_REASONS_NON_DOC:
        return len(seq)  # cleared every document, rejected for an unrelated reason

    lsr = row['last_stage_reached']
    if pd.notna(lsr) and lsr in seq:
        return seq.index(lsr)

    return None


def classify_outcomes(mature: pd.DataFrame) -> pd.DataFrame:
    """
    Attach each captain's required sequence and their stuck_idx (how far
    they got, in their own sequence) to the mature cohort dataframe.

    Raises
    ------
    AssertionError if any captain's outcome can't be explained.
    """
    mature = mature.copy()
    mature['seq'] = mature['vehicle_type'].apply(required_sequence)
    mature['stuck_idx'] = mature.apply(stuck_local_index, axis=1)

    unresolved = mature['stuck_idx'].isna().sum()
    assert unresolved == 0, (
        f"{unresolved} captains have no explainable outcome — "
        "investigate before trusting the funnel."
    )
    return mature


def report_permit_branch(mature: pd.DataFrame) -> dict:
    """
    Make the Permit branch point explicit and auditable, right where the
    split actually happens
    Everyone who clears AADHAAR (local position 2, since DL/RC/AADHAAR are
    always the first three stages for every vehicle type) splits into:
      - Auto/Cab  -> proceed to PERMIT
      - ERickshaw -> no Permit required, proceed straight to FITNESS

    Returns
    -------
    dict with the branch counts, for reuse.
    """
    cleared_aadhaar = mature[mature['stuck_idx'] > 2]
    needs_permit_ct = cleared_aadhaar['vehicle_type'].isin(['Auto', 'Cab']).sum()
    skips_permit_ct = (cleared_aadhaar['vehicle_type'] == 'ERickshaw').sum()

    assert needs_permit_ct + skips_permit_ct == len(cleared_aadhaar), \
        "Branch counts don't add up to Aadhaar-clearers — investigate."

    print("\n--- PERMIT BRANCH POINT (right after Aadhaar) ---")
    print(f"Total cleared Aadhaar: {len(cleared_aadhaar)}")
    print(cleared_aadhaar['vehicle_type'].value_counts().to_string())
    print(f"  -> Auto + Cab (require Permit, proceed to Permit stage): {needs_permit_ct}")
    print(f"  -> ERickshaw (no Permit required, proceed straight to Fitness): {skips_permit_ct}")

    return {
        'total_cleared_aadhaar': len(cleared_aadhaar),
        'needs_permit': needs_permit_ct,
        'skips_permit': skips_permit_ct,
    }

def build_stage_funnel(mature: pd.DataFrame) -> pd.DataFrame:
    """
    Build the stage by stage reached / cleared / lost-here / pass-rate table.

    Returns
    -------
    pd.DataFrame with one row per stage.
    """
    rows = []
    for stage in STAGES:
        applies = mature[mature['seq'].apply(lambda s: stage in s)].copy()
        applies['local_pos'] = applies['seq'].apply(lambda s: s.index(stage))

        reached = (applies['stuck_idx'] >= applies['local_pos']).sum()
        lost_here = (applies['stuck_idx'] == applies['local_pos']).sum()
        cleared = reached - lost_here

        rows.append({
            'stage': stage,
            'reached': reached,
            'cleared': cleared,
            'lost_here': lost_here,
            'pass_rate': cleared / reached if reached else float('nan'),
        })

    return pd.DataFrame(rows)



def compute_topline(mature: pd.DataFrame, n: int) -> dict:
    """
    Compute the headline funnel numbers: cleared-all-docs, and A2O
    (signup -> approved).

    Returns
    -------
    dict with approved_ct, rejected_postdoc_ct, cleared_all_ct, a2o_rate.
    """
    approved_ct = (mature['final_status'] == 'approved').sum()
    rejected_postdoc_ct = (
        (mature['final_status'] == 'rejected') &
        mature['last_stage_reached'].isin(REJECT_REASONS_NON_DOC)
    ).sum()
    cleared_all_ct = approved_ct + rejected_postdoc_ct
    a2o_rate = approved_ct / n

    print(f"\nCleared ALL required documents: {cleared_all_ct} ({cleared_all_ct/n:.1%})")
    print(f"  of which rejected post-docs (background/policy/duplicate): {rejected_postdoc_ct}")
    print(f"  of which APPROVED: {approved_ct} ({a2o_rate:.1%})  <-- A2O")

    return {
        'approved_ct': approved_ct,
        'rejected_postdoc_ct': rejected_postdoc_ct,
        'cleared_all_ct': cleared_all_ct,
        'a2o_rate': a2o_rate,
    }


def reconcile(funnel: pd.DataFrame, cleared_all_ct: int, n: int) -> None:
    """
    Hard sanity check: (total lost across all stages) + (cleared all docs)
    must equal the full cohort denominator.
    Raises AssertionError if the numbers don't reconcile exactly.
    """
    total_lost = funnel['lost_here'].sum()
    reconciled_total = total_lost + cleared_all_ct

    print(f"\nReconciliation check: {total_lost} (lost across stages) + {cleared_all_ct} (cleared all) "
          f"= {reconciled_total}  vs.  N = {n}")
    assert reconciled_total == n, "Funnel does not reconcile."
    print("Reconciliation OK.")


def main():
    """Run the full A1 funnel build, end to end, printing every step."""
    captains, approvals = load_data()

    cutoff = determine_cohort_cutoff(captains, approvals)
    mature_captains, recent_captains = split_cohort(captains, cutoff)

    # Join outcome data onto the mature cohort only (left join preserves
    # every signup even if a future data pull ever has a missing match).
    mature = mature_captains.merge(approvals, on='captain_id', how='left')

    mature, anomalies = flag_and_remove_anomalies(mature)
    n = len(mature)
    print(f"\nFINAL DENOMINATOR (clean mature cohort): {n}")

    mature = classify_outcomes(mature)

    report_permit_branch(mature)

    funnel = build_stage_funnel(mature)
    print("\n--- STAGE-BY-STAGE FUNNEL ---")
    print(funnel.to_string(index=False))

    topline = compute_topline(mature, n)

    reconcile(funnel, topline['cleared_all_ct'], n)

    return {
        'mature': mature,
        'funnel': funnel,
        'topline': topline,
        'recent_captains': recent_captains,
        'anomalies': anomalies,
    }


if __name__ == '__main__':
    main()