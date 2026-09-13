# Data Scientist (Intern / Associate) — Take-Home Exercise
### Captain Acquisition, Supply

---

## Before you start

- **Time budget:** ~5 focused hours. You have **5 calendar days**.
- **Do not gold-plate.** We would rather see three questions answered well than nine answered thinly. Telling us what you *chose not to do, and why* scores points.
- **Use whatever tools you like** — Python, R, SQL, dbt, notebooks, BI tools, and AI assistants are all fair game. We use them too. The debrief is where we find out how well you understand your own work, so don't ship anything you can't defend line by line.
- **The data is synthetic.** It is shaped like ours but contains no real captain or customer information.

---

## Context you need

Rapido's supply side runs on **captains** — the drivers who fulfil rides. Before a captain can take a single order, they must get through **onboarding**: uploading and passing verification on a sequence of documents.

The required document sequence is:

| Order | Document | Applies to |
|---|---|---|
| 1 | Driving Licence (DL) | all |
| 2 | Registration Certificate (RC) | all |
| 3 | Aadhaar | all |
| 4 | Permit | Auto, Cab |
| 5 | Fitness Certificate | all |
| 6 | Insurance | all |

Each document can be uploaded, then either **passes** or **fails** verification. A failed document can be re-uploaded (up to 3 attempts). A captain who clears all documents goes to a final **approval** decision. Approved captains may or may not ever take a first order.

Two vocabulary items we use internally, so you can use them too:

- **A2O** — *Acquisition to Onboarded*: signup → approved.
- **R2A** — *Registered to Active*: signup → first order completed.

We care about A2O and R2A, in that order, and about the cost of everything in between.

---

## The data

Seven files, extracted at **2026-06-30 23:59 IST**. Read that sentence again — it matters.

**`captains.csv`** — one row per signup
`captain_id, signup_ts, city, vehicle_type, acquisition_channel, signup_zone_id, device_tier, app_language, age_band`

**`doc_events.csv`** — one row per document event
`event_id, captain_id, doc_type, attempt_no, event_type, event_ts, failure_reason`
`event_type` ∈ {`upload_success`, `verification_pass`, `verification_fail`}

**`approvals.csv`** — terminal onboarding outcome
`captain_id, decision_ts, final_status, last_stage_reached, docs_cleared`
`final_status` ∈ {`approved`, `rejected`, `dropped_in_docs`, `in_progress`}

**`activation.csv`** — post-approval activity, approved captains only
`captain_id, first_order_ts, orders_d7, orders_d30, online_hours_d30`

**`nudges.csv`** — onboarding comms
`captain_id, campaign_id, channel, sent_ts, delivered, clicked`

**`airport_hourly.csv`** — hourly marketplace state by zone, May–June 2026
`zone_id, zone_type, hour_ts, requests, fulfilled_requests, unfulfilled_requests, online_captains, avg_eta_min, avg_surge_multiplier`

**`airport_trips.csv`** — sampled airport-origin trips
`trip_id, pickup_zone_id, drop_zone_id, drop_zone_type, request_ts, trip_distance_km, captain_cancelled, got_return_fare_within_20min, fare_inr`

Nothing here has been cleaned for you.

---

## Part A — The onboarding funnel *(required)*

You have been asked by the Head of Supply for a read on captain onboarding health, with recommendations.

**A1. Build the funnel.**
Define and compute the signup → approved funnel, stage by stage. State your denominator and your cohorting rule explicitly, and say why you chose them. Show where the volume is actually being lost — not just the percentages.

**A2. Find the biggest fixable leak.**
Segment the drop-off. Cities, vehicle types, channels, devices, time, document, failure reason — you decide which cuts are worth making. We are looking for the leaks that are (a) large, (b) explicable, and (c) something a product or ops team could actually do something about. Quantify each one: *if we fixed this, how many more approved captains per month?*

**A3. Evaluate a campaign.**
Someone on the growth team is claiming that `CAMP_WA_002` is a big win for onboarding completion and wants budget to scale it 5x. Assess that claim. Give us a number you would be willing to put in a deck with your name on it, and tell us how confident you are in it.

**A4. Recommend.**
Three recommendations, ranked. For each: what to do, expected impact with your working shown, what it would cost or risk, and what you would measure to know if it worked.

---

## Part B — Airport supply *(required for Associate, optional for Intern)*

Regional leadership wants to fund a **captain acquisition push targeted at the airport catchment area** — hiring more captains who live near the airport, plus a sign-up bonus for them.

Using `airport_hourly.csv` and `airport_trips.csv`:

**B1.** Characterise the demand–supply mismatch at the airport terminals. Be specific about *when* and *how much*.

**B2.** Airport supply is not only a headcount question. Look at what happens to a captain *after* an airport trip. Does that change the diagnosis?

**B3.** Answer the actual business question: **is targeted acquisition the right intervention here?** If yes, size it. If no, say so plainly and propose what you would do instead, with the same rigour. "No" is an acceptable answer if you can defend it.

---

## Deliverables

Submit three things:

1. **A memo — max 2 pages.** Written for the Head of Supply, who is smart, busy, and not a statistician. Findings and recommendations, not methodology. No code, no unexplained jargon.
2. **Your working** — notebook, scripts, or repo. It should run end to end from the raw CSVs. A short README on how to run it.
3. **A deck — max 6 slides.** What you would actually present. Assume you get 10 minutes and are interrupted twice.

Then a **30-minute live debrief**: 10 minutes presenting, 20 minutes of us asking questions.

---

## What we are actually assessing

To be completely transparent about the bar:

- **Framing.** Did you decide what mattered before you started computing things?
- **Rigour.** Do your numbers survive being poked? Do you know the difference between a difference and an effect?
- **Product sense.** Do your recommendations pass the "an ops manager could start this on Monday" test?
- **Ownership.** Did you notice the things we didn't ask about? Did you flag what's wrong with the data instead of quietly working around it?
- **Communication.** Could a busy exec read your memo once and make a decision?

Assumptions are fine. **Undeclared** assumptions are not. There is a section at the end of a good memo titled "What I assumed and what would change my answer."

Good luck — we're genuinely looking forward to reading it.
