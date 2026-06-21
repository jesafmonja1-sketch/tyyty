# CLI Match Analysis Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `analyze-match` CLI command that prints a human-readable single-match betting summary for direct daily use.

**Architecture:** Keep `predictions.py` responsible for football and recommendation logic, add a narrow CLI formatter helper under `delivery/`, and wire a new Typer command in `cli.py`. Reuse the latest `PredictionDiagnostic` plus the latest persisted `MatchPrediction` row for the same match so the command can show both raw and calibrated probabilities without re-deriving model outputs.

**Tech Stack:** Python 3.12, Typer, SQLAlchemy ORM, pytest

---

### Task 1: Add Failing CLI Tests For `analyze-match`

**Files:**
- Modify: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_delivery_and_cli.py`
- Read for fixture reuse: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\analysis\predictions.py`

- [ ] **Step 1: Write the failing success-path CLI test**

Add this test near the other CLI tests in `tests/test_delivery_and_cli.py`:

```python
def test_cli_analyze_match_prints_readable_summary(session, monkeypatch, tmp_path):
    kickoff = _utcnow() + timedelta(hours=2)
    match_row = _seed_prediction(session, kickoff, external_id="wc-analyze-1")
    session.add(
        MatchPrediction(
            prediction_run_id=session.query(PredictionRun).filter_by(match_id=match_row.id).one().id,
            home_win_probability=0.48,
            draw_probability=0.27,
            away_win_probability=0.25,
            calibrated_home_win_probability=0.46,
            calibrated_draw_probability=0.28,
            calibrated_away_win_probability=0.26,
            expected_home_goals=1.42,
            expected_away_goals=1.03,
            over_2_5_probability=0.44,
            under_2_5_probability=0.56,
            handicap_cover_probability=0.41,
            handicap_push_probability=0.22,
            handicap_fail_probability=0.37,
            totals_over_probability=0.39,
            totals_push_probability=0.17,
            totals_under_probability=0.44,
            fair_handicap_line=-0.25,
            fair_total_line=2.25,
            market_handicap_line=-0.5,
            recommended_handicap_side="away",
            recommended_totals_side="under",
            totals_tendency="under 2.5",
            likely_scorelines="1-0,1-1,2-1",
            confidence_level="medium",
            summary_conclusion="home side slight edge but market line is deeper",
            calibration_summary_json={},
        )
    )
    session.commit()

    db_path = tmp_path / "analyze-match.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")
```

- [ ] **Step 2: Complete the test by cloning the seeded match into the CLI database and asserting summary sections**

Continue the same test body with:

```python
    from sqlalchemy.orm import sessionmaker
    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        cloned_home = NationalTeam(
            fifa_code="BRA",
            name="Brazil",
            confederation="CONMEBOL",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        cloned_away = NationalTeam(
            fifa_code="POR",
            name="Portugal",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        db_session.add_all([cloned_home, cloned_away])
        db_session.flush()
        cloned_match = Match(
            external_id="wc-analyze-1",
            competition="FIFA World Cup",
            stage="Quarterfinal",
            kickoff_at=kickoff,
            home_team_id=cloned_home.id,
            away_team_id=cloned_away.id,
            is_neutral_site=True,
            home_score=None,
            away_score=None,
            half_time_score=None,
            status="scheduled",
        )
        db_session.add(cloned_match)
        db_session.flush()
        cloned_run = PredictionRun(
            match_id=cloned_match.id,
            captured_at=_utcnow(),
            model_version="v1-rules",
        )
        db_session.add(cloned_run)
        db_session.flush()
        db_session.add(
            MatchPrediction(
                prediction_run_id=cloned_run.id,
                home_win_probability=0.48,
                draw_probability=0.27,
                away_win_probability=0.25,
                calibrated_home_win_probability=0.46,
                calibrated_draw_probability=0.28,
                calibrated_away_win_probability=0.26,
                expected_home_goals=1.42,
                expected_away_goals=1.03,
                over_2_5_probability=0.44,
                under_2_5_probability=0.56,
                handicap_cover_probability=0.41,
                handicap_push_probability=0.22,
                handicap_fail_probability=0.37,
                totals_over_probability=0.39,
                totals_push_probability=0.17,
                totals_under_probability=0.44,
                fair_handicap_line=-0.25,
                fair_total_line=2.25,
                market_handicap_line=-0.5,
                recommended_handicap_side="away",
                recommended_totals_side="under",
                totals_tendency="under 2.5",
                likely_scorelines="1-0,1-1,2-1",
                confidence_level="medium",
                summary_conclusion="home side slight edge but market line is deeper",
                calibration_summary_json={},
            )
        )
        db_session.add_all(
            [
                PredictionFactor(
                    prediction_run_id=cloned_run.id,
                    factor_name="market_home_probability",
                    factor_value=0.44,
                    explanation="de-vigged 1X2 market probability for home win",
                ),
                PredictionFactor(
                    prediction_run_id=cloned_run.id,
                    factor_name="market_draw_probability",
                    factor_value=0.29,
                    explanation="de-vigged 1X2 market probability for draw",
                ),
                PredictionFactor(
                    prediction_run_id=cloned_run.id,
                    factor_name="market_away_probability",
                    factor_value=0.27,
                    explanation="de-vigged 1X2 market probability for away win",
                ),
            ]
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["analyze-match", "1"])

    assert result.exit_code == 0
    assert "比赛结论" in result.stdout
    assert "胜平负" in result.stdout
    assert "让球" in result.stdout
    assert "大小球" in result.stdout
    assert "比分" in result.stdout
    assert "风险点" in result.stdout
    assert "核心理由" in result.stdout
```

- [ ] **Step 3: Add a failing fallback-line rendering test**

Add this second test in the same file:

```python
def test_cli_analyze_match_uses_fair_total_line_when_market_total_missing(monkeypatch, tmp_path):
    db_path = tmp_path / "analyze-match-fallback.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")
```

- [ ] **Step 4: Complete the fallback test with exact seeded data and expected output**

Continue that test with:

```python
    from sqlalchemy.orm import sessionmaker
    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        home = NationalTeam(
            fifa_code="ARG",
            name="Argentina",
            confederation="CONMEBOL",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away = NationalTeam(
            fifa_code="MEX",
            name="Mexico",
            confederation="CONCACAF",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        db_session.add_all([home, away])
        db_session.flush()
        match_row = Match(
            external_id="wc-analyze-2",
            competition="FIFA World Cup",
            stage="Group Stage",
            kickoff_at=_utcnow() + timedelta(hours=2),
            home_team_id=home.id,
            away_team_id=away.id,
            is_neutral_site=True,
            home_score=None,
            away_score=None,
            half_time_score=None,
            status="scheduled",
        )
        db_session.add(match_row)
        db_session.flush()
        run = PredictionRun(
            match_id=match_row.id,
            captured_at=_utcnow(),
            model_version="v1-rules",
        )
        db_session.add(run)
        db_session.flush()
        db_session.add(
            MatchPrediction(
                prediction_run_id=run.id,
                home_win_probability=0.51,
                draw_probability=0.26,
                away_win_probability=0.23,
                calibrated_home_win_probability=0.49,
                calibrated_draw_probability=0.27,
                calibrated_away_win_probability=0.24,
                expected_home_goals=1.61,
                expected_away_goals=0.92,
                over_2_5_probability=0.47,
                under_2_5_probability=0.53,
                handicap_cover_probability=0.49,
                handicap_push_probability=0.21,
                handicap_fail_probability=0.30,
                totals_over_probability=0.46,
                totals_push_probability=0.18,
                totals_under_probability=0.36,
                fair_handicap_line=-0.5,
                fair_total_line=2.25,
                market_handicap_line=-0.5,
                recommended_handicap_side="home",
                recommended_totals_side="under",
                totals_tendency="under 2.5",
                likely_scorelines="1-0,2-0,1-1",
                confidence_level="medium",
                summary_conclusion="Argentina edge with a cautious totals profile",
                calibration_summary_json={
                    "totals": {
                        "market_family": "totals",
                        "market_line": 2.25,
                        "line_source": "fair_total_line",
                        "source": "fallback",
                    }
                },
            )
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["analyze-match", "1"])

    assert result.exit_code == 0
    assert "fair total line" in result.stdout.lower()
    assert "2.25" in result.stdout
```

- [ ] **Step 5: Run the CLI test file to verify failure**

Run:

```bash
python -m pytest tests/test_delivery_and_cli.py -q
```

Expected:

- FAIL because `analyze-match` command does not exist yet
- or FAIL because expected summary sections are missing

- [ ] **Step 6: Commit the failing tests**

```bash
git add tests/test_delivery_and_cli.py
git commit -m "test: add analyze-match cli coverage"
```

### Task 2: Add A Focused CLI Summary Formatter

**Files:**
- Create: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\delivery\cli_match_analysis.py`
- Test through: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_delivery_and_cli.py`

- [ ] **Step 1: Create a small presentation dataclass**

Create `src/world_cup_intel/delivery/cli_match_analysis.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass

from world_cup_intel.analysis.predictions import PredictionDiagnostic
from world_cup_intel.schema import MatchPrediction


@dataclass(frozen=True)
class CliMatchAnalysisPayload:
    match_label: str
    prediction: MatchPrediction
    diagnostic: PredictionDiagnostic
```

- [ ] **Step 2: Add helper functions for percentage and line formatting**

Continue the same file with:

```python
def _pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _line(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _first_matching_line(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return "N/A"
```

- [ ] **Step 3: Add the summary renderer**

Finish the file with:

```python
def render_cli_match_analysis(payload: CliMatchAnalysisPayload) -> str:
    prediction = payload.prediction
    diagnostic = payload.diagnostic

    score_parts = [part.strip() for part in prediction.likely_scorelines.split(",") if part.strip()]
    primary_scores = ", ".join(score_parts[:3]) if score_parts else "N/A"
    defensive_score = score_parts[3] if len(score_parts) > 3 else (score_parts[-1] if score_parts else "N/A")

    match_suitability = _first_matching_line(diagnostic.toto_recommendation_lines, "适合下球判断")
    match_suitability_reason = _first_matching_line(diagnostic.toto_recommendation_lines, "适合度理由")
    handicap_suitability = _first_matching_line(diagnostic.toto_recommendation_lines, "让球适合度判断")
    handicap_suitability_reason = _first_matching_line(diagnostic.toto_recommendation_lines, "让球适合度理由")
    totals_suitability = _first_matching_line(diagnostic.toto_recommendation_lines, "大小球适合度判断")
    totals_suitability_reason = _first_matching_line(diagnostic.toto_recommendation_lines, "大小球适合度理由")

    market_probability_lines = diagnostic.market_probability_summary or "N/A"
    value_edge_summary = diagnostic.value_edge_summary or "N/A"
    risk_lines = diagnostic.issue_hints[:4] if diagnostic.issue_hints else ["N/A"]

    totals_summary = prediction.calibration_summary_json.get("totals", {}) if prediction.calibration_summary_json else {}
    totals_market_line = totals_summary.get("market_line", prediction.fair_total_line)
    totals_line_source = totals_summary.get("line_source", "market_total_line")

    lines = [
        f"比赛结论 | {payload.match_label}",
        f"总结: {diagnostic.summary_conclusion}",
        f"是否建议下: {match_suitability}",
        f"原因: {match_suitability_reason}",
        "",
        "胜平负",
        f"原始概率: 主胜 {_pct(prediction.home_win_probability)} / 平 {_pct(prediction.draw_probability)} / 客胜 {_pct(prediction.away_win_probability)}",
        f"校准概率: 主胜 {_pct(prediction.calibrated_home_win_probability)} / 平 {_pct(prediction.calibrated_draw_probability)} / 客胜 {_pct(prediction.calibrated_away_win_probability)}",
        f"市场概率: {market_probability_lines}",
        f"市场分歧: {value_edge_summary}",
        "",
        "让球",
        f"市场线: {_line(prediction.market_handicap_line)}",
        f"公平线: {_line(prediction.fair_handicap_line)}",
        f"cover / push / fail: {_pct(prediction.handicap_cover_probability)} / {_pct(prediction.handicap_push_probability)} / {_pct(prediction.handicap_fail_probability)}",
        f"推荐方向: {diagnostic.recommended_handicap_side}",
        f"是否建议碰: {handicap_suitability}",
        f"原因: {handicap_suitability_reason}",
        "",
        "大小球",
        f"当前线: {_line(totals_market_line)} ({totals_line_source})",
        f"fair total line: {_line(prediction.fair_total_line)}",
        f"over / push / under: {_pct(prediction.totals_over_probability)} / {_pct(prediction.totals_push_probability)} / {_pct(prediction.totals_under_probability)}",
        f"推荐方向: {prediction.recommended_totals_side or 'N/A'}",
        f"是否建议碰: {totals_suitability}",
        f"原因: {totals_suitability_reason}",
        "",
        "比分",
        f"主比分: {primary_scores}",
        f"防冷比分: {defensive_score}",
        "",
        "风险点",
    ]
    lines.extend(f"- {line}" for line in risk_lines)
    lines.extend(
        [
            "",
            "核心理由",
            f"- {diagnostic.summary_conclusion}",
            f"- 让球: {handicap_suitability_reason}",
            f"- 大小球: {totals_suitability_reason}",
        ]
    )
    return "\n".join(lines)
```

- [ ] **Step 4: Run the CLI tests again**

Run:

```bash
python -m pytest tests/test_delivery_and_cli.py -q
```

Expected:

- still FAIL because `cli.py` does not yet expose `analyze-match`
- formatter-related assertions may start passing once the command is added

- [ ] **Step 5: Commit the formatter**

```bash
git add src/world_cup_intel/delivery/cli_match_analysis.py
git commit -m "feat: add cli match analysis formatter"
```

### Task 3: Add `analyze-match` Command Wiring

**Files:**
- Modify: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\cli.py`
- Modify: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_delivery_and_cli.py`
- Reuse: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\analysis\predictions.py`

- [ ] **Step 1: Import the needed helpers in `cli.py`**

Update imports near the top of `src/world_cup_intel/cli.py` to include:

```python
from sqlalchemy import desc
from sqlalchemy import select

from world_cup_intel.analysis.predictions import diagnose_prediction
from world_cup_intel.delivery.cli_match_analysis import CliMatchAnalysisPayload
from world_cup_intel.delivery.cli_match_analysis import render_cli_match_analysis
from world_cup_intel.schema import Match
from world_cup_intel.schema import MatchPrediction
from world_cup_intel.schema import PredictionRun
```

- [ ] **Step 2: Add a helper for loading the latest prediction row**

Add this helper above the CLI commands:

```python
def _latest_prediction_for_match(session, match_id: int) -> tuple[Match, MatchPrediction]:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    row = session.execute(
        select(MatchPrediction, PredictionRun)
        .join(PredictionRun, PredictionRun.id == MatchPrediction.prediction_run_id)
        .where(PredictionRun.match_id == match_id)
        .order_by(desc(PredictionRun.captured_at), desc(PredictionRun.id))
    ).first()
    if row is None:
        raise ValueError(f"Prediction not found for match_id={match_id}")

    prediction, _ = row
    return match_row, prediction
```

- [ ] **Step 3: Add the new Typer command**

Add this command below `preview-report`:

```python
@app.command("analyze-match")
def analyze_match_command(match_id: int) -> None:
    with _session() as session:
        match_row, prediction = _latest_prediction_for_match(session, match_id)
        diagnostic = diagnose_prediction(session, match_id)
        payload = CliMatchAnalysisPayload(
            match_label=f"{diagnostic.home_team} vs {diagnostic.away_team}",
            prediction=prediction,
            diagnostic=diagnostic,
        )
        typer.echo(render_cli_match_analysis(payload))
```

- [ ] **Step 4: Run the CLI test file to verify it passes**

Run:

```bash
python -m pytest tests/test_delivery_and_cli.py -q
```

Expected:

- PASS for the new `analyze-match` CLI tests
- existing `preview-report`, delivery, and rebuild tests still PASS

- [ ] **Step 5: Commit the command wiring**

```bash
git add src/world_cup_intel/cli.py tests/test_delivery_and_cli.py
git commit -m "feat: add analyze-match cli command"
```

### Task 4: Final Verification Sweep

**Files:**
- Verify: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\cli.py`
- Verify: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\src\world_cup_intel\delivery\cli_match_analysis.py`
- Verify: `C:\Users\Administrator\Documents\球赛\.worktrees\codex-dixon-coles\tests\test_delivery_and_cli.py`

- [ ] **Step 1: Run the focused verification suite**

Run:

```bash
python -m pytest tests/test_delivery_and_cli.py tests/test_predictions.py -q
```

Expected:

- PASS with the new CLI tests and the existing prediction regressions

- [ ] **Step 2: Run one smoke check through the module entrypoint**

Run:

```bash
$env:PYTHONPATH='C:/Users/Administrator/Documents/球赛/.worktrees/codex-dixon-coles/src'
$env:WCI_DATABASE_URL='sqlite:///C:/Users/Administrator/Documents/球赛/.worktrees/codex-dixon-coles/.tmp-analyze-smoke.db'
$env:WCI_EMAIL_SMTP_HOST='smtp.qq.com'
$env:WCI_EMAIL_SMTP_PORT='465'
$env:WCI_EMAIL_USERNAME='sender@qq.com'
$env:WCI_EMAIL_PASSWORD='smtp-auth-code'
$env:WCI_EMAIL_RECIPIENT='receiver@example.com'
python -m world_cup_intel.cli --help
```

Expected:

- PASS
- help output lists `analyze-match`

- [ ] **Step 3: Review scope drift**

Check that:

- no email wording changed
- no JSON output mode was added
- no new model logic was added to `predictions.py`
- `diagnose-prediction` remains a technical path, not the final readable summary command

- [ ] **Step 4: Commit any final cleanup**

```bash
git add src/world_cup_intel/cli.py src/world_cup_intel/delivery/cli_match_analysis.py tests/test_delivery_and_cli.py
git commit -m "test: verify analyze-match cli rollout"
```
