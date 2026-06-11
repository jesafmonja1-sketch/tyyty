from datetime import datetime, timedelta

from typer.testing import CliRunner

from world_cup_intel.cli import app
from world_cup_intel.delivery.email_reports import render_match_report
from world_cup_intel.delivery.scheduler import select_matches_needing_report
from world_cup_intel.schema import Match, MatchPrediction, NationalTeam, PredictionFactor, PredictionRun


def test_render_match_report_and_cli_preview(session, monkeypatch, tmp_path):
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
    session.add_all([home, away])
    session.flush()

    kickoff = datetime.utcnow() + timedelta(hours=2)
    match_row = Match(
        external_id="wc-4",
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

    run = PredictionRun(match_id=match_row.id, captured_at=datetime.utcnow(), model_version="v1-rules")
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

    report = render_match_report(session, match_row.id)
    assert "Brazil vs Portugal" in report.subject
    assert "under 2.5" in report.body
    assert "分析理由" in report.body

    due_matches = select_matches_needing_report(session, datetime.utcnow(), timedelta(hours=2, minutes=5))
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
            captured_at=datetime.utcnow(),
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
