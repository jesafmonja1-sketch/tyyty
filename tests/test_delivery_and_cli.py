from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import subprocess
import sys

from typer.testing import CliRunner

from world_cup_intel.analysis.market_calibration import rebuild_market_calibration_profiles
from world_cup_intel.cli import app
from world_cup_intel.config import EmailSettings, Settings
from world_cup_intel.delivery.email_reports import render_match_report, send_match_report
from world_cup_intel.delivery.scheduler import select_matches_needing_report, send_due_reports
from world_cup_intel.schema import (
    Match,
    MatchFeatureSnapshot,
    MatchPrediction,
    MatchReview,
    MarketCalibrationProfile,
    NationalTeam,
    PredictionFactor,
    PredictionRun,
    SentReport,
)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_prediction(
    session,
    kickoff: datetime,
    external_id: str = "wc-4",
    home_code: str = "BRA",
    home_name: str = "Brazil",
    away_code: str = "POR",
    away_name: str = "Portugal",
) -> Match:
    home = NationalTeam(
        fifa_code=home_code,
        name=home_name,
        confederation="CONMEBOL",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code=away_code,
        name=away_name,
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id=external_id,
        competition="FIFA World Cup",
        stage="Quarterfinal",
        kickoff_at=kickoff,
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        home_score=None,
        away_score=None,
        half_time_score=None,
        status="scheduled",
    )
    session.add(match_row)
    session.flush()

    run = PredictionRun(match_id=match_row.id, captured_at=_utcnow(), model_version="v1-rules")
    session.add(run)
    session.flush()
    session.add(
        MatchPrediction(
            prediction_run_id=run.id,
            home_win_probability=0.44,
            draw_probability=0.29,
            away_win_probability=0.27,
            fair_handicap_line=-0.25,
            market_handicap_line=-0.5,
            recommended_handicap_side="away",
            totals_tendency="under 2.5",
            likely_scorelines="1-0,1-1,2-1",
            confidence_level="medium",
            summary_conclusion="Brazil slightly ahead but market is deeper than model",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="rating_gap",
            factor_value=5.0,
            explanation="overall team power difference",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="market_handicap",
            factor_value=-0.5,
            explanation="latest available handicap line",
        )
    )
    session.commit()
    return match_row


def _settings() -> Settings:
    return Settings(
        database_url="sqlite:///unused.db",
        email=EmailSettings(
            smtp_host="smtp.qq.com",
            smtp_port=465,
            username="sender@qq.com",
            password="smtp-auth-code",
            recipient="receiver@example.com",
        ),
    )


def test_render_match_report_and_cli_preview(session, monkeypatch, tmp_path):
    kickoff = _utcnow() + timedelta(hours=2)
    match_row = _seed_prediction(session, kickoff)
    session.add(
        MatchReview(
            match_id=match_row.id,
            national_team_id=1,
            created_at=_utcnow(),
            summary_text="主力边锋腿筋紧张，上一场第67分钟被换下。",
            tactical_change_summary="4-2-3-1 -> 4-3-3，边路推进更直接。",
            strength_change_summary="整体实力较上一场提升（+2.10）。",
            next_match_impact_summary="首发风险抬升，若边锋缺席将削弱左路爆点和反击推进。",
        )
    )
    session.commit()

    report = render_match_report(session, match_row.id)
    assert "Brazil vs Portugal" in report.subject
    assert "under 2.5" in report.body
    assert "分析理由" in report.body
    assert "实力差来源" in report.body
    assert "盘口差异" in report.body
    assert "战术变化" in report.body
    assert "伤停影响" in report.body
    assert "主力边锋腿筋紧张" in report.body

    due_matches = select_matches_needing_report(session, _utcnow(), timedelta(hours=2, minutes=5))
    assert match_row.id in [item.id for item in due_matches]

    db_path = tmp_path / "cli-preview.db"
    cli_session = session.get_bind()
    cli_session.dispose()

    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")

    from world_cup_intel.db import build_engine, create_schema
    from sqlalchemy.orm import sessionmaker

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
            external_id="wc-4",
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
                home_win_probability=0.44,
                draw_probability=0.29,
                away_win_probability=0.27,
                fair_handicap_line=-0.25,
                market_handicap_line=-0.5,
                recommended_handicap_side="away",
                totals_tendency="under 2.5",
                likely_scorelines="1-0,1-1,2-1",
                confidence_level="medium",
                summary_conclusion="Brazil slightly ahead but market is deeper than model",
            )
        )
        db_session.add(
            PredictionFactor(
                prediction_run_id=cloned_run.id,
                factor_name="rating_gap",
                factor_value=5.0,
                explanation="overall team power difference",
            )
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["preview-report", str(1)])
    assert result.exit_code == 0
    assert "Brazil vs Portugal" in result.stdout


def test_send_match_report_records_delivery_without_repeating_network(session, monkeypatch):
    class FakeSMTP:
        sent_messages = []
        logins = []

        def __init__(self, host, port):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            self.logins.append((username, password))

        def send_message(self, message):
            self.sent_messages.append(message)

    kickoff = _utcnow() + timedelta(hours=2)
    match_row = _seed_prediction(session, kickoff, external_id="wc-5")
    monkeypatch.setattr("world_cup_intel.delivery.email_reports.smtplib.SMTP_SSL", FakeSMTP)

    sent_report = send_match_report(session, _settings(), match_row.id, _utcnow())
    session.commit()

    assert sent_report.match_id == match_row.id
    assert session.query(SentReport).count() == 1
    assert len(FakeSMTP.sent_messages) == 1
    assert FakeSMTP.sent_messages[0]["To"] == "receiver@example.com"


def test_send_due_reports_sends_due_match_once_and_skips_already_sent(session, monkeypatch):
    class FakeSMTP:
        sent_messages = []

        def __init__(self, host, port):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            self.sent_messages.append(message)

    monkeypatch.setattr("world_cup_intel.delivery.email_reports.smtplib.SMTP_SSL", FakeSMTP)
    now = _utcnow()
    due_match = _seed_prediction(session, now + timedelta(hours=2), external_id="wc-6")
    later_match = _seed_prediction(
        session,
        now + timedelta(hours=5),
        external_id="wc-7",
        home_code="ARG",
        home_name="Argentina",
        away_code="FRA",
        away_name="France",
    )

    sent_ids = send_due_reports(session, _settings(), now, timedelta(hours=2, minutes=5))
    resent_ids = send_due_reports(session, _settings(), now, timedelta(hours=2, minutes=5))

    assert due_match.id in sent_ids
    assert later_match.id not in sent_ids
    assert resent_ids == []
    assert session.query(SentReport).count() == 1
    assert len(FakeSMTP.sent_messages) == 1


def test_cli_send_due_reports_uses_configured_database(monkeypatch, tmp_path):
    class FakeSMTP:
        sent_messages = []

        def __init__(self, host, port):
            self.host = host
            self.port = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, username, password):
            return None

        def send_message(self, message):
            self.sent_messages.append(message)

    monkeypatch.setattr("world_cup_intel.delivery.email_reports.smtplib.SMTP_SSL", FakeSMTP)

    db_path = tmp_path / "send-due.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")

    from sqlalchemy.orm import sessionmaker

    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        _seed_prediction(db_session, _utcnow() + timedelta(hours=2), external_id="wc-8")

    runner = CliRunner()
    result = runner.invoke(app, ["send-due-reports"])

    assert result.exit_code == 0
    assert "Sent 1 report(s)." in result.stdout
    assert len(FakeSMTP.sent_messages) == 1


def test_cli_analyze_match_prints_readable_summary(monkeypatch, tmp_path):
    db_path = tmp_path / "analyze-match.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")

    from sqlalchemy.orm import sessionmaker

    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        home = NationalTeam(
            fifa_code="BRA",
            name="Brazil",
            confederation="CONMEBOL",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away = NationalTeam(
            fifa_code="POR",
            name="Portugal",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        db_session.add_all([home, away])
        db_session.flush()
        match_row = Match(
            external_id="wc-analyze-1",
            competition="FIFA World Cup",
            stage="Quarterfinal",
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
                    prediction_run_id=run.id,
                    factor_name="market_home_probability",
                    factor_value=0.44,
                    explanation="de-vigged 1X2 market probability for home win",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="market_draw_probability",
                    factor_value=0.29,
                    explanation="de-vigged 1X2 market probability for draw",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="market_away_probability",
                    factor_value=0.27,
                    explanation="de-vigged 1X2 market probability for away win",
                ),
            ]
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["analyze-match", str(match_row.id)])

    assert result.exit_code == 0
    assert "比赛结论" in result.stdout
    assert "Brazil vs Portugal" in result.stdout
    assert "home side slight edge but market line is deeper" in result.stdout
    assert "胜平负" in result.stdout
    assert "市场概率: 市场概率:" not in result.stdout
    assert "市场分歧: 价值差:" not in result.stdout
    assert "让球" in result.stdout
    assert "推荐方向: away" in result.stdout
    assert "大小球" in result.stdout
    assert "推荐方向: under" in result.stdout
    assert "比分" in result.stdout
    assert "1-0, 1-1, 2-1" in result.stdout
    assert "防冷比分: N/A" in result.stdout
    assert "风险点" in result.stdout
    assert "核心理由" in result.stdout


def test_cli_analyze_match_does_not_require_email_env(monkeypatch, tmp_path):
    db_path = tmp_path / "analyze-match-no-email.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.delenv("WCI_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("WCI_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("WCI_EMAIL_USERNAME", raising=False)
    monkeypatch.delenv("WCI_EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("WCI_EMAIL_RECIPIENT", raising=False)

    from sqlalchemy.orm import sessionmaker

    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        home = NationalTeam(
            fifa_code="GER",
            name="Germany",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away = NationalTeam(
            fifa_code="JPN",
            name="Japan",
            confederation="AFC",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        db_session.add_all([home, away])
        db_session.flush()
        match_row = Match(
            external_id="wc-analyze-no-email",
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
                home_win_probability=0.47,
                draw_probability=0.28,
                away_win_probability=0.25,
                calibrated_home_win_probability=0.45,
                calibrated_draw_probability=0.29,
                calibrated_away_win_probability=0.26,
                expected_home_goals=1.35,
                expected_away_goals=0.97,
                over_2_5_probability=0.42,
                under_2_5_probability=0.58,
                handicap_cover_probability=0.44,
                handicap_push_probability=0.21,
                handicap_fail_probability=0.35,
                totals_over_probability=0.38,
                totals_push_probability=0.18,
                totals_under_probability=0.44,
                fair_handicap_line=-0.25,
                fair_total_line=2.25,
                market_handicap_line=-0.5,
                recommended_handicap_side="away",
                recommended_totals_side="under",
                totals_tendency="under 2.5",
                likely_scorelines="1-0,1-1,2-0",
                confidence_level="medium",
                summary_conclusion="Germany slight edge with a cautious goal profile",
                calibration_summary_json={},
            )
        )
        db_session.add(
            PredictionFactor(
                prediction_run_id=run.id,
                factor_name="market_home_probability",
                factor_value=0.46,
                explanation="de-vigged 1X2 market probability for home win",
            )
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["analyze-match", str(match_row.id)])

    assert result.exit_code == 0
    assert "Germany vs Japan" in result.stdout


def test_cli_analyze_match_uses_fair_total_line_when_market_total_missing(monkeypatch, tmp_path):
    db_path = tmp_path / "analyze-match-fallback.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")

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
    result = runner.invoke(app, ["analyze-match", str(match_row.id)])

    assert result.exit_code == 0
    assert "Argentina vs Mexico" in result.stdout
    assert "Argentina edge with a cautious totals profile" in result.stdout
    assert "当前线: 2.25 (fair_total_line)" in result.stdout
    assert "fair total line: 2.25" in result.stdout
    assert "防冷比分: N/A" in result.stdout


def test_cli_list_matches_prints_recent_matches(monkeypatch, tmp_path):
    db_path = tmp_path / "list-matches.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.delenv("WCI_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("WCI_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("WCI_EMAIL_USERNAME", raising=False)
    monkeypatch.delenv("WCI_EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("WCI_EMAIL_RECIPIENT", raising=False)

    from sqlalchemy.orm import sessionmaker

    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        home_one = NationalTeam(
            fifa_code="BRA",
            name="Brazil",
            confederation="CONMEBOL",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away_one = NationalTeam(
            fifa_code="POR",
            name="Portugal",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        home_two = NationalTeam(
            fifa_code="GER",
            name="Germany",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away_two = NationalTeam(
            fifa_code="JPN",
            name="Japan",
            confederation="AFC",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        db_session.add_all([home_one, away_one, home_two, away_two])
        db_session.flush()
        db_session.add_all(
            [
                Match(
                    external_id="wc-list-1",
                    competition="FIFA World Cup",
                    stage="Group Stage",
                    kickoff_at=_utcnow() + timedelta(hours=2),
                    home_team_id=home_one.id,
                    away_team_id=away_one.id,
                    is_neutral_site=True,
                    home_score=None,
                    away_score=None,
                    half_time_score=None,
                    status="scheduled",
                ),
                Match(
                    external_id="wc-list-2",
                    competition="FIFA World Cup",
                    stage="Group Stage",
                    kickoff_at=_utcnow() + timedelta(hours=4),
                    home_team_id=home_two.id,
                    away_team_id=away_two.id,
                    is_neutral_site=True,
                    home_score=None,
                    away_score=None,
                    half_time_score=None,
                    status="scheduled",
                ),
            ]
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["list-matches", "--limit", "2"])

    assert result.exit_code == 0
    assert "Germany vs Japan" in result.stdout
    assert "Brazil vs Portugal" in result.stdout
    assert "Group Stage" in result.stdout
    assert "scheduled" in result.stdout


def test_cli_find_match_filters_by_team_name(monkeypatch, tmp_path):
    db_path = tmp_path / "find-match.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.delenv("WCI_EMAIL_SMTP_HOST", raising=False)
    monkeypatch.delenv("WCI_EMAIL_SMTP_PORT", raising=False)
    monkeypatch.delenv("WCI_EMAIL_USERNAME", raising=False)
    monkeypatch.delenv("WCI_EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("WCI_EMAIL_RECIPIENT", raising=False)

    from sqlalchemy.orm import sessionmaker

    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        home_one = NationalTeam(
            fifa_code="NED",
            name="Netherlands",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away_one = NationalTeam(
            fifa_code="SWE",
            name="Sweden",
            confederation="UEFA",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        home_two = NationalTeam(
            fifa_code="USA",
            name="United States",
            confederation="CONCACAF",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        away_two = NationalTeam(
            fifa_code="AUS",
            name="Australia",
            confederation="AFC",
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        db_session.add_all([home_one, away_one, home_two, away_two])
        db_session.flush()
        db_session.add_all(
            [
                Match(
                    external_id="wc-find-1",
                    competition="FIFA World Cup",
                    stage="Group Stage",
                    kickoff_at=_utcnow() + timedelta(hours=6),
                    home_team_id=home_one.id,
                    away_team_id=away_one.id,
                    is_neutral_site=True,
                    home_score=None,
                    away_score=None,
                    half_time_score=None,
                    status="scheduled",
                ),
                Match(
                    external_id="wc-find-2",
                    competition="FIFA World Cup",
                    stage="Group Stage",
                    kickoff_at=_utcnow() + timedelta(hours=8),
                    home_team_id=home_two.id,
                    away_team_id=away_two.id,
                    is_neutral_site=True,
                    home_score=None,
                    away_score=None,
                    half_time_score=None,
                    status="scheduled",
                ),
            ]
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["find-match", "--team", "nether", "--limit", "5"])

    assert result.exit_code == 0
    assert "Netherlands vs Sweden" in result.stdout
    assert "United States vs Australia" not in result.stdout


def test_rebuild_market_calibration_command_runs_successfully(monkeypatch, tmp_path):
    db_path = tmp_path / "rebuild-market-calibration.db"
    monkeypatch.setenv("WCI_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WCI_EMAIL_SMTP_HOST", "smtp.qq.com")
    monkeypatch.setenv("WCI_EMAIL_SMTP_PORT", "465")
    monkeypatch.setenv("WCI_EMAIL_USERNAME", "sender@qq.com")
    monkeypatch.setenv("WCI_EMAIL_PASSWORD", "smtp-auth-code")
    monkeypatch.setenv("WCI_EMAIL_RECIPIENT", "receiver@example.com")

    from sqlalchemy.orm import sessionmaker

    from world_cup_intel.db import build_engine, create_schema

    engine = build_engine(f"sqlite:///{db_path.as_posix()}")
    create_schema(engine)
    local_session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with local_session() as db_session:
        match_row = _seed_prediction(
            db_session,
            _utcnow() - timedelta(hours=2),
            external_id="wc-rebuild-cli",
            home_code="GER",
            home_name="Germany",
            away_code="CRC",
            away_name="Costa Rica",
        )
        match_row.status = "finished"
        match_row.home_score = 3
        match_row.away_score = 1
        match_row.half_time_score = "2-0"
        run = db_session.query(PredictionRun).filter_by(match_id=match_row.id).one()
        db_session.add(
            MatchFeatureSnapshot(
                prediction_run_id=run.id,
                match_id=match_row.id,
                captured_at=run.captured_at,
                model_version="v1-rules",
                home_overall_score=88.0,
                away_overall_score=72.0,
                home_attack_score=86.0,
                away_attack_score=69.0,
                home_defense_score=81.0,
                away_defense_score=66.0,
                home_recent_form_score=84.0,
                away_recent_form_score=63.0,
                power_delta=16.0,
                attack_delta=17.0,
                defense_delta=15.0,
                form_delta=21.0,
                home_learning_readiness_score=0.0,
                away_learning_readiness_score=0.0,
                home_learning_momentum_score=0.0,
                away_learning_momentum_score=0.0,
                home_tactical_continuity_score=0.0,
                away_tactical_continuity_score=0.0,
                learning_delta=0.0,
                tactical_continuity_delta=0.0,
                home_availability_alert_count=0,
                away_availability_alert_count=0,
                home_minutes_risk_score=0.0,
                away_minutes_risk_score=0.0,
                discipline_delta=0.0,
                environment_delta=0.0,
                weather_delta=0.0,
                referee_delta=0.0,
                motivation_delta=0.0,
                fatigue_delta=0.0,
                scenario_pressure_delta=0.0,
                goal_difference_pressure_delta=0.0,
                market_handicap_line=-0.5,
                market_total_line=2.5,
                market_home_probability=0.6,
                market_draw_probability=0.25,
                market_away_probability=0.15,
                market_over_price=1.92,
                market_under_price=1.94,
                lambda_home=1.8,
                lambda_away=0.9,
                projected_tempo_score=0.0,
                learning_adjustment=0.0,
                feature_payload_json={},
            )
        )
        db_session.commit()

    runner = CliRunner()
    result = runner.invoke(app, ["rebuild-market-calibration"])

    assert result.exit_code == 0
    assert "rebuilt market calibration profiles" in result.stdout.lower()
    with local_session() as db_session:
        profiles = db_session.query(MarketCalibrationProfile).all()
    assert profiles
    assert {profile.market_family for profile in profiles} >= {"1x2", "handicap", "totals"}


def test_rebuild_market_calibration_command_persists_profiles(session):
    match_row = _seed_prediction(
        session,
        _utcnow() - timedelta(hours=2),
        external_id="wc-rebuild-session",
        home_code="ESP",
        home_name="Spain",
        away_code="JPN",
        away_name="Japan",
    )
    match_row.status = "finished"
    match_row.home_score = 2
    match_row.away_score = 1
    match_row.half_time_score = "1-0"
    run = session.query(PredictionRun).filter_by(match_id=match_row.id).one()
    session.add(
        MatchFeatureSnapshot(
            prediction_run_id=run.id,
            match_id=match_row.id,
            captured_at=run.captured_at,
            model_version="v1-rules",
            home_overall_score=83.0,
            away_overall_score=78.0,
            home_attack_score=81.0,
            away_attack_score=76.0,
            home_defense_score=80.0,
            away_defense_score=75.0,
            home_recent_form_score=82.0,
            away_recent_form_score=77.0,
            power_delta=5.0,
            attack_delta=5.0,
            defense_delta=5.0,
            form_delta=5.0,
            home_learning_readiness_score=0.0,
            away_learning_readiness_score=0.0,
            home_learning_momentum_score=0.0,
            away_learning_momentum_score=0.0,
            home_tactical_continuity_score=0.0,
            away_tactical_continuity_score=0.0,
            learning_delta=0.0,
            tactical_continuity_delta=0.0,
            home_availability_alert_count=0,
            away_availability_alert_count=0,
            home_minutes_risk_score=0.0,
            away_minutes_risk_score=0.0,
            discipline_delta=0.0,
            environment_delta=0.0,
            weather_delta=0.0,
            referee_delta=0.0,
            motivation_delta=0.0,
            fatigue_delta=0.0,
            scenario_pressure_delta=0.0,
            goal_difference_pressure_delta=0.0,
            market_handicap_line=-0.5,
            market_total_line=2.5,
            market_home_probability=0.52,
            market_draw_probability=0.27,
            market_away_probability=0.21,
            market_over_price=1.9,
            market_under_price=1.96,
            lambda_home=1.5,
            lambda_away=1.0,
            projected_tempo_score=0.0,
            learning_adjustment=0.0,
            feature_payload_json={},
        )
    )
    session.commit()

    built = rebuild_market_calibration_profiles(
        session,
        captured_at=_utcnow(),
    )
    session.commit()

    profiles = session.query(MarketCalibrationProfile).all()

    assert built["1x2"] >= 1
    assert built["handicap"] >= 1
    assert built["totals"] >= 1
    assert profiles
    assert {profile.market_family for profile in profiles} >= {"1x2", "handicap", "totals"}


def test_python_module_cli_entrypoint_runs_rebuild_command(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "module-entrypoint.db"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + str(repo_root / "src")
    env["WCI_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["WCI_EMAIL_SMTP_HOST"] = "smtp.qq.com"
    env["WCI_EMAIL_SMTP_PORT"] = "465"
    env["WCI_EMAIL_USERNAME"] = "sender@qq.com"
    env["WCI_EMAIL_PASSWORD"] = "smtp-auth-code"
    env["WCI_EMAIL_RECIPIENT"] = "receiver@example.com"

    result = subprocess.run(
        [sys.executable, "-m", "world_cup_intel.cli", "rebuild-market-calibration"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "rebuilt market calibration profiles" in result.stdout.lower()


def test_python_module_cli_entrypoint_help_lists_analyze_match(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "module-entrypoint-help.db"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + str(repo_root / "src")
    env["WCI_DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["WCI_EMAIL_SMTP_HOST"] = "smtp.qq.com"
    env["WCI_EMAIL_SMTP_PORT"] = "465"
    env["WCI_EMAIL_USERNAME"] = "sender@qq.com"
    env["WCI_EMAIL_PASSWORD"] = "smtp-auth-code"
    env["WCI_EMAIL_RECIPIENT"] = "receiver@example.com"

    result = subprocess.run(
        [sys.executable, "-m", "world_cup_intel.cli", "--help"],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "analyze-match" in result.stdout


def test_dev_shell_script_exists():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "dev-shell.ps1"

    assert script_path.exists()


def test_dev_shell_script_contains_required_environment_variables():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "dev-shell.ps1"

    contents = script_path.read_text(encoding="utf-8")

    assert "PYTHONPATH" in contents
    assert "WCI_DATABASE_URL" in contents
    assert "WCI_EMAIL_SMTP_HOST" in contents
    assert "WCI_EMAIL_SMTP_PORT" in contents
    assert "WCI_EMAIL_USERNAME" in contents
    assert "WCI_EMAIL_PASSWORD" in contents
    assert "WCI_EMAIL_RECIPIENT" in contents
