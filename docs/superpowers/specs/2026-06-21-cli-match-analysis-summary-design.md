# CLI Match Analysis Summary Design

## Overview

This design adds a dedicated human-readable CLI output for single-match betting analysis.

The current system already has:

- context-aware match prediction
- Dixon-Coles score distribution
- calibrated `1X2`, handicap, and totals probabilities
- diagnostic output for debugging
- recommendation fragments inside `PredictionDiagnostic`

What is still missing is a stable CLI command for direct day-to-day use.

The user is currently reading results directly inside the terminal conversation rather than relying on email delivery or machine-readable JSON. That means the next valuable step is not more model depth first. The next valuable step is a clear final-output command that turns the existing prediction state into one compact, readable match-analysis summary.

## Goal

Add a dedicated CLI command for direct match reading, shaped for practical pre-match use.

The command should:

- show the final match lean in one place
- summarize win/draw/loss probabilities
- summarize handicap cover/push/fail probabilities
- summarize totals over/push/under probabilities
- compare model fair lines against market lines
- surface whether the match is suitable to play
- show the main scoreline range and core risks

This is an output-layer feature, not a model-redesign feature.

## Non-Goals

This phase will not include:

- email output changes
- JSON mode
- frontend or web UI
- new calibration families
- group qualification Monte Carlo
- new hidden betting heuristics beyond current structured recommendation logic
- reworking the raw prediction engine

## Existing System Context

The current codebase already contains two important layers:

1. prediction generation in [C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\analysis\predictions.py](C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\analysis\predictions.py)
2. CLI command registration in [C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\cli.py](C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\cli.py)

`predictions.py` already exposes:

- `generate_match_prediction(...)`
- `diagnose_prediction(...)`
- `PredictionDiagnostic`
- `TotoRecommendation`

`PredictionDiagnostic` already contains most of the ingredients needed for a direct-reading CLI:

- summary conclusion
- recommended handicap side
- fair handicap line
- expected goals
- totals tendency
- likely scorelines
- factor lines
- issue hints
- toto recommendation lines

So the missing piece is not data generation. The missing piece is a formatter and command boundary that present the right information for human reading.

## Approaches Considered

### Option 1: Expand `diagnose-prediction`

Pros:

- smallest code diff
- reuses an existing command concept

Cons:

- mixes technical debugging with final human-facing analysis
- makes the diagnosis command harder to maintain
- causes future output growth to become messy

### Option 2: Add a dedicated `analyze-match` command

Pros:

- clean separation of responsibilities
- directly matches the user’s current workflow
- allows stable human-readable formatting without polluting debug output

Cons:

- adds one new CLI command

### Option 3: Build a shared formatter abstraction for every output surface

Pros:

- cleanest long-term reuse path
- could later feed CLI, email, and other surfaces

Cons:

- too large for the current phase
- creates unnecessary scope expansion before the direct CLI use case is stable

## Recommendation

Use **Option 2**:

- keep `diagnose-prediction` as the technical/debug command
- add a new `analyze-match <match_id>` CLI command
- keep output human-readable only
- use a small formatter helper rather than building a general rendering framework

This gives the best trade-off between correctness, clarity, and delivery speed.

## Proposed Command

### Command shape

```text
python -m world_cup_intel.cli analyze-match <match_id>
```

### Primary behavior

The command should:

1. open a session through the existing CLI session path
2. load the latest prediction through `diagnose_prediction(...)`
3. format the result into a single readable terminal summary
4. print the summary to stdout

### Error behavior

If the match or prediction is missing:

- keep the current exception behavior style consistent with existing CLI commands
- do not silently swallow missing data

The first version does not need a custom multi-layer exception formatting system.

## Output Structure

The new command should print seven stable sections in this order.

### Section 1: Match conclusion

Fields:

- match name
- summary conclusion
- whether the match is recommended to play
- confidence level if available from the underlying prediction

Purpose:

- give the user the one-screen bottom line first

### Section 2: Win / draw / loss

Fields:

- raw home / draw / away probability
- calibrated home / draw / away probability
- market implied home / draw / away probability when available
- strongest side

Purpose:

- distinguish the base football lean from the calibrated output
- show whether market pricing agrees or disagrees

### Section 3: Handicap

Fields:

- current market handicap line
- model fair handicap line
- cover / push / fail probability for the current line
- recommended handicap side
- whether handicap is suitable to play
- short reason

Purpose:

- answer the user’s most common “让球怎么选” question directly

### Section 4: Totals

Fields:

- current market total line when available
- model fair total line
- over / push / under probability for the current line
- recommended totals side
- whether totals are suitable to play
- short reason

Purpose:

- answer the user’s common “大小球怎么选” question directly

### Section 5: Scorelines

Fields:

- top three main scorelines
- one defensive upset / cold-risk scoreline

Purpose:

- give a compact score range rather than only one exact score

### Section 6: Risks

Fields should be selected from the existing diagnostics and recommendation text, with emphasis on:

- injury / rotation risk
- group-stage motivation or control-game risk
- old-data risk
- handicap too deep / card risk / path incentive / draw value

Purpose:

- explain why a theoretically good angle may still be unsuitable

### Section 7: Core reasons

Fields:

- 2 to 5 short lines combining the most important directional logic

Examples of source inputs:

- `summary_conclusion`
- selected `toto_recommendation_lines`
- the highest-signal `issue_hints`

Purpose:

- end with the short reasoning chain the user will actually remember

## Formatting Strategy

The first version should stay plain text and terminal-friendly.

Formatting rules:

- short titled sections
- one line per key statement
- no nested structures
- no raw diagnostic dump by default
- no JSON
- no decorative formatting requirements beyond readable markdown-like text

This should read like a compact analyst note, not like a raw database printout.

## Module Boundaries

### `predictions.py`

Keep responsibility for:

- probability generation
- calibrated values
- diagnostic assembly
- recommendation logic

Do not move CLI formatting into this file.

### New CLI formatter helper

Add a small helper module, recommended path:

- [C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\delivery\cli_match_analysis.py](C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\delivery\cli_match_analysis.py)

Suggested responsibility:

- accept `PredictionDiagnostic`
- accept the latest `MatchPrediction` row when needed for raw versus calibrated display
- return one final formatted string

This helper should stay focused on rendering only.

### `cli.py`

Keep responsibility for:

- command registration
- session setup
- calling analysis helpers
- printing final output

Do not duplicate formatting logic inline beyond minimal orchestration.

## Data Flow

Recommended flow:

1. `analyze-match <match_id>` command starts
2. CLI session opens
3. load latest `PredictionDiagnostic`
4. load latest `MatchPrediction` + `PredictionRun` row for the same match
5. build a presentation payload
6. pass payload to the CLI formatter
7. print final text

This keeps data retrieval explicit and avoids hiding presentation lookups inside the formatter.

## Presentation Payload Direction

The formatter will likely need more than `PredictionDiagnostic` alone because the final summary should show both:

- raw probabilities
- calibrated probabilities

`PredictionDiagnostic` currently focuses on derived text and diagnostic output, while `MatchPrediction` stores the raw/calibrated fields directly.

So the presentation layer should consume a small composed payload with:

- match identity
- latest prediction row
- prediction diagnostic

This can be a light dataclass or narrow dict.

## Suitability Rules

The existing recommendation layer already contains:

- match suitability
- handicap suitability
- totals suitability

The first version of `analyze-match` should not invent a second recommendation engine.

Instead it should:

- reuse the existing suitability outputs
- present them more clearly
- only add light wording normalization if necessary

## Testing Strategy

This phase must stay test-first.

Primary test file:

- [C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_delivery_and_cli.py](C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_delivery_and_cli.py)

Secondary test coverage may stay in:

- [C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_predictions.py](C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_predictions.py)

### Required failing-test coverage

1. `analyze-match` command runs successfully for a seeded match
2. output includes final conclusion, handicap section, totals section, and scorelines
3. output includes both raw and calibrated `1X2` probabilities
4. output includes market line versus fair line for handicap and totals
5. output includes suitability wording rather than only raw diagnostic fragments
6. missing market totals line still renders correctly using the fallback fair total line path

## Risks

Main risks:

1. overloading one command with too much diagnostic noise
2. duplicating recommendation logic inside CLI rendering
3. coupling formatter directly to ORM state
4. growing `cli.py` into a rendering file

Mitigations:

- dedicate a separate CLI formatter helper
- reuse current recommendation outputs
- keep the formatter input narrow
- keep `diagnose-prediction` separate from `analyze-match`

## Rollout Recommendation

Ship this in one small bounded phase:

1. add tests for the new CLI command
2. add a presentation helper
3. add `analyze-match` command
4. verify output against seeded prediction fixtures

Do not mix this phase with:

- email redesign
- JSON API work
- new model mathematics

## Success Criteria

This phase is successful when:

- the user can run one command and get a readable single-match summary
- handicap and totals decisions are shown clearly
- fair line versus market line is visible
- the command reuses existing model outputs instead of re-deriving them
- technical diagnostic output remains available separately

## Recommendation

Implement a dedicated human-readable `analyze-match` CLI command with a narrow formatter helper, reusing existing prediction and recommendation outputs while keeping diagnosis and rendering responsibilities separated.
