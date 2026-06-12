# Pre-Match Manual Final And Post-Match Auto Learning Design

## Overview

This design reshapes the World Cup intelligence workflow around two user habits:

- post-match learning should happen automatically after each finished match
- pre-match final analysis should happen when the user sends one batch of late information

The system will stop acting like it must collect or send updates every hour. Instead, it will use one automatic fallback pre-match email, one optional manual-triggered final email, and one automatic post-match learning pass per finished match.

## Goals

- Run post-match learning automatically after each finished match.
- Let the user send late match materials once, close to kickoff, instead of drip-feeding updates.
- Send a final pre-match email immediately after late materials are provided.
- Preserve an automatic fallback pre-match email when the user does not send late materials.
- Prevent duplicate or noisy pre-match emails.
- Make automation status clearer so `0 refreshed` means `nothing new` rather than `nothing works`.

## Non-Goals

- Automatic live scraping of every starting lineup, odds move, or weather update.
- Multi-version email chains beyond one fallback email and one final email.
- In-match halftime automation.
- Rebuilding the prediction model into a black-box system.

## User Workflow

### Post-match

1. A match becomes `finished`.
2. The post-match automation checks for finished matches that have not yet been learned.
3. For each new finished match, the system creates reviews, learning snapshots, and next-match prediction refreshes.
4. The automation records that the match has already been processed so it is not refreshed again by default.

### Pre-match

1. The system watches upcoming scheduled matches.
2. Before kickoff, a fallback time is defined for the match.
3. If the user has not sent late materials by that fallback time, the system sends one `basic` pre-match email.
4. If the user later sends late materials before kickoff, the system updates the match intelligence and sends one `final` pre-match email immediately.
5. After a `final` email has been sent, no more automatic pre-match emails are sent for that match.

## Match Phases And Timing

### Post-match auto learning

- Trigger window: approximately 10 to 20 minutes after full time
- Source condition: only matches with `status = finished`
- Processing rule: one automatic learning pass per match by default
- Manual enhancement rule: additional user-provided screenshots or notes may trigger a manual enrichment refresh without changing the core one-pass automatic design

### Pre-match fallback email

- Trigger window: one fixed fallback time before kickoff
- Purpose: avoid missing a match when the user does not send late materials
- Output: one `basic` pre-match email

### Pre-match final email

- Trigger event: the user sends a late information batch
- Recommended user batch contents:
  - starting lineup
  - latest odds and handicap
  - weather
  - injuries or suspensions
  - late news
  - referee if available
- Output: one `final` pre-match email sent immediately after analysis

## Email Modes

The system will treat pre-match emails as distinct delivery modes instead of one generic report.

### Basic mode

Used when the fallback trigger fires and no final late-material analysis has been sent.

Content should include:

- win, draw, loss lean
- handicap lean
- totals lean
- three likely scorelines
- core reasoning from current power, known odds, injuries, weather, venue, and group context
- risk reminders

Suggested subject format:

- `[世界杯基础版] <home> vs <away> 赛前分析`

### Final mode

Used when the user sends late materials and wants the strongest possible pre-match conclusion.

Content should include everything from `basic` mode plus:

- lineup and shape impact
- late market movement interpretation
- model versus market disagreement explanation
- late weather and environment effect
- injury, card, and availability impact
- motivation and scenario adjustments
- final conclusion with explicit reason for any change from the earlier lean

Suggested subject format:

- `[世界杯最终版] <home> vs <away> 临场分析`

## Pre-Match Delivery Rules

### Rule set

1. Each match may send at most one `basic` email.
2. Each match may send at most one `final` email.
3. If a `final` email already exists, do not send a `basic` email later.
4. If a `basic` email exists and the user later provides late materials, sending one `final` email is allowed.
5. A `final` email supersedes the `basic` email for decision-making, but both remain in history for auditability.

### Why this design

- It avoids spam.
- It protects against missed matches.
- It matches the user's real workflow: one late information drop, then one decisive output.

## Data Model Changes

The existing `sent_reports` table currently records generic pre-match report delivery. The new design needs enough state to distinguish fallback and final deliveries.

### Minimum change option

Extend sent-report delivery records with:

- `report_mode` with values such as `basic` and `final`
- `trigger_source` with values such as `automatic_fallback` and `manual_late_material`

This allows current report history to stay usable while supporting the new delivery rules.

### Optional support records

If needed for clarity and future debugging, add a lightweight per-match status view or helper logic that derives:

- whether a basic email has been sent
- whether a final email has been sent
- whether late materials have been attached

## Late Material Intake

Late material intake does not require full autonomous scraping. The design assumes the user sends the final data bundle manually.

### Intake behavior

When the user sends late materials:

1. attach or persist the late intelligence for the target match
2. refresh or regenerate the prediction
3. render the final email
4. record a `final` sent-report entry

### Match intelligence sources

The late intake path should be able to update or reuse:

- lineup and tactical context
- odds markets
- weather snapshot
- referee snapshot
- availability and injury context
- match context snapshot for motivation, fatigue, and scenario notes

## Post-Match Learning Behavior

The existing post-match learning loop is conceptually correct but should present its status more clearly.

### Required behavior

- keep the current one-pass safeguard for already learned finished matches
- continue producing reviews and team learning snapshots
- continue refreshing relevant next-match predictions
- improve operator output so it reports:
  - total finished matches seen
  - newly refreshed matches
  - already learned matches
  - refreshed next-match prediction ids
  - concrete errors if any

### Why this matters

Today, `refreshed 0 matches` is technically correct but easy to misread as a failure. The new output should make it obvious that `0 new` can coexist with `already learned 2`.

## Prediction And Report Inputs

The final pre-match analysis should continue using the richer signal set already discussed with the user:

- base team strength
- tactical profile
- player availability and start risk
- odds and handicap
- venue and environment
- weather
- schedule fatigue and travel
- group table motivation and knockout path
- referee tendencies when available
- post-match learning from the teams' most recent games

The design does not require all of these to be present every time. Missing late signals should gracefully fall back to the current stored data.

## Error Handling

### Pre-match

- If fallback email sending fails, record the failure and allow a retry before kickoff.
- If final email sending fails after late material intake, preserve the late materials and report the exact delivery error.
- If odds, lineup, or weather updates are partial, still generate the best possible final email rather than aborting the whole flow.

### Post-match

- If one finished match fails to refresh, do not block other finished matches in the same batch.
- Record which match failed and why.
- Never duplicate learning snapshots for a match already marked as processed unless a separate manual enrichment path explicitly requests it.

## Testing Strategy

Use test-driven development for all behavior changes.

### Delivery tests

- fallback sends one `basic` email when no prior delivery exists
- fallback skips a match when a `final` email already exists
- fallback does not send a second `basic` email
- manual late-material flow sends one `final` email
- manual late-material flow can send `final` after `basic`
- manual late-material flow cannot send a second `final`

### CLI and operator output tests

- refreshed post-match output shows `new`, `already learned`, and affected matches
- pre-match fallback command reports which matches were sent versus skipped

### Learning safety tests

- already processed finished matches are skipped
- a new finished match creates review, learning, and next-match prediction refreshes

## Implementation Areas

- `src/world_cup_intel/schema.py`
  - extend delivery state to distinguish `basic` and `final`
- `src/world_cup_intel/delivery/email_reports.py`
  - render subject and body for two pre-match modes
- `src/world_cup_intel/delivery/scheduler.py`
  - enforce fallback-versus-final delivery rules
- `src/world_cup_intel/cli.py`
  - expose clearer operator output
  - add or adapt a manual late-material final-send entrypoint
- `src/world_cup_intel/analysis/reviews.py`
  - keep current learning flow, but improve reporting surfaces
- tests in `tests/test_delivery_and_cli.py`, `tests/test_reviews.py`, and `tests/test_schema.py`

## Risks

- If the fallback trigger time is too early, the basic email may feel stale.
- If the fallback trigger time is too late, there may be less time to recover from email delivery failure.
- If late-material targeting is ambiguous, a final email could attach to the wrong match; the intake path must identify the match explicitly.
- If operator output stays vague, user trust will remain lower even when the automation is working.

## Recommendation

Adopt `manual final + automatic fallback + automatic post-match learning` as the default operating model.

This gives the user a practical workflow:

- no constant hourly collection burden
- no missed matches
- no excessive email spam
- consistent post-match learning that improves the next analysis
