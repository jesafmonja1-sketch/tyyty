from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner

from world_cup_intel.cli import app
from world_cup_intel.config import EmailSettings, Settings
from world_cup_intel.delivery.email_reports import render_match_report, send_match_report
from world_cup_intel.delivery.scheduler import select_matches_needing_report, send_due_reports
from world_cup_intel.schema import Match, MatchPrediction, MatchReview, NationalTeam, PredictionFactor, PredictionRun, SentReport


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
