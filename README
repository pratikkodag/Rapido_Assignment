# Rapido Captain Acquisition Take-Home Analysis

This repo answers Part A (onboarding funnel) and Part B (airport supply)
of the Data Scientist take home Assignment. Every script runs end to end from
the raw CSVs sitting alongside it.

See [`CANDIDATE_BRIEF.md`](./CANDIDATE_BRIEF.md) for the original problem
statement, and [`Captain_Onboarding_Airport_Supply_Memo.docx`](./Captain_Onboarding_&_Airport_Supply_Memo.docx)
for the 2-page findings memo.

---

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install pandas scipy
```

No other dependencies are required. Tested on Python 3.11.

---

## Repo structure

```
PART_A/
    captains.csv, approvals.csv, doc_events.csv, activation.csv, nudges.csv
    funnel_building.py
    leak_analysis.py
    campaign_evaluation.py
    recommendations.py

PART_B/
    airport_hourly.csv, airport_trips.csv
    demand_supply_analysis.py
    post_trip_analysis.py
    final_recommendation.py

CANDIDATE_BRIEF.md
Captain_Onboarding___Airport_Supply_Memo.docx
```

Data lives in the same folder as the scripts that use it ,nothing needs
to be moved or supplied separately.

---

## How to run

Each script is self-contained: it loads the raw CSVs and computes
everything itself. `leak_analysis.py`, `campaign_evaluation.py`, and
`recommendations.py` import a few shared functions from
`funnel_building.py` (so it needs to exist in the same folder), but they
don't depend on it having been *run* first there's no intermediate
output file being passed between scripts. Likewise, `final_recommendation.py`
imports functions from `demand_supply_analysis.py` and
`post_trip_analysis.py`.

**scripts in a folder can be run in any
order, including on its own:**

```bash
cd PART_A
python funnel_building.py
python leak_analysis.py
python campaign_evaluation.py
python recommendations.py
```

```bash
cd PART_B
python demand_supply_analysis.py
python post_trip_analysis.py
python final_recommendation.py
```

---

## What each file does

### Part A — Onboarding funnel

| File | Question | What it does |
|---|---|---|
| [`funnel_building.py`](./PART_A/funnel_building.py) | **A1** | Builds the signup to approved funnel. Defines the cohort cutoff (excludes recent, unresolved signups), flags a data-quality anomaly, and shows stage-by-stage volume lost, not just percentages. |
| [`leak_analysis.py`](./PART_A/leak_analysis.py) | **A2** | Segments the RC (Registration Certificate) drop-off by device tier and acquisition channel, confirms the root cause using failure-reason data, and converts each leak into incremental approved captains per month. |
| [`campaign_evaluation.py`](./PART_A/campaign_evaluation.py) | **A3** | Tests the growth team's claim about the `CAMP_WA_002` campaign. Shows the naive comparison is confounded by targeting, restates it fairly, and checks whether the requested 5x budget increase is even mathematically possible. |
| [`recommendations.py`](./PART_A/recommendations.py) | **A4** | Pulls the A2 and A3 findings into three ranked recommendations, each with expected impact, cost/risk, and a metric to track. Flags where two recommendations overlap rather than treating them as fully independent. |

### Part B — Airport supply

| File | Question | What it does |
|---|---|---|
| [`demand_supply_analysis.py`](./PART_B/demand_supply_analysis.py) | **B1** | Compares airport terminals to the rest of the city, checks the pattern holds across both terminals, every day of the week, and both months, then isolates and quantifies a nightly 9pm to 3am demand-supply mismatch. |
| [`post_trip_analysis.py`](./PART_B/post_trip_analysis.py) | **B2** | Looks at what happens to a captain after an airport drop-off how often they get a return fare within 20 minutes and how often they cancel broken down by time of day and drop zone. |
| [`final_recommendation.py`](./PART_B/final_recommendation.py) | **B3** | Combines B1 and B2 with surge pricing data to test whether a captain acquisition push is the right fix, sizes the headcount gap directly, and recommends an alternative. |

---

## Note on assumptions

Each script states its own assumptions inline as comments at the point
they're made (cohort cutoff date, benchmark segment choices, night-window
definition, etc.) rather than in a separate document, so the reasoning
sits next to the number it produces. A consolidated list also appears in
the memo under "What I assumed and what would change my answer."