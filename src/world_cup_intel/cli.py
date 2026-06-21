from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path

import typer
from click.core import Parameter
from typer.core import TyperArgument

from world_cup_intel.analysis.market_calibration import rebuild_market_calibration_profiles
from world_cup_intel.analysis.predictions import diagnose_prediction
from world_cup_intel.config import Settings
from world_cup_intel.db import SessionLocal, build_engine, create_schema
from world_cup_intel.delivery.cli_match_analysis import CliMatchAnalysisPayload
from world_cup_intel.delivery.cli_match_analysis import render_cli_match_analysis
from world_cup_intel.delivery.email_reports import render_match_report
from world_cup_intel.delivery.scheduler import send_due_reports
from world_cup_intel.seed.upcoming_world_cup import seed_upcoming_world_cup_matches
from world_cup_intel.schema import Match
from world_cup_intel.schema import MatchPrediction
from world_cup_intel.schema import PredictionRun
from world_cup_intel.schema import NationalTeam
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import aliased


def _patch_typer_click_compat() -> None:
    if TyperArgument.make_metavar.__code__.co_argcount == 1:
        def _compat_make_metavar(self, ctx=None):
            if self.metavar is not None:
                return self.metavar

            var = (self.name or "").upper()
            if not self.required:
                var = f"[{var}]"
            try:
                type_var = self.type.get_metavar(param=self, ctx=ctx)
            except TypeError:
                type_var = self.type.get_metavar(self)
            if type_var:
                var += f":{type_var}"
            if self.nargs != 1:
                var += "..."
            return var

        TyperArgument.make_metavar = _compat_make_metavar

    if Parameter.make_metavar.__code__.co_argcount == 2:
        _original_make_metavar = Parameter.make_metavar

        def _compat_parameter_make_metavar(self, ctx=None):
            if ctx is None:
                class _CompatCtx:
                    resilient_parsing = False

                ctx = _CompatCtx()
            return _original_make_metavar(self, ctx)

        Parameter.make_metavar = _compat_parameter_make_metavar


_patch_typer_click_compat()
app = typer.Typer()


@app.callback()
def main() -> None:
    """World Cup intelligence commands."""


def _load_local_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _session():
    _load_local_env()
    engine = build_engine(Settings.database_url_from_env())
    create_schema(engine)
    SessionLocal.configure(bind=engine)
    return SessionLocal()


def _latest_prediction_for_match(session, match_id: int) -> tuple[Match, MatchPrediction]:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    row = session.execute(
        select(MatchPrediction, PredictionRun)
        .join(PredictionRun, PredictionRun.id == MatchPrediction.prediction_run_id)
        .where(PredictionRun.match_id == match_id)
        .order_by(desc(PredictionRun.captured_at), desc(PredictionRun.id), desc(MatchPrediction.id))
    ).first()
    if row is None:
        raise ValueError(f"Prediction not found for match_id={match_id}")
    prediction, _ = row
    return match_row, prediction


def _render_match_rows(rows: list[tuple[Match, NationalTeam, NationalTeam]]) -> str:
    if not rows:
        return "No matches found."

    rendered_rows = []
    for match_row, home_team, away_team in rows:
        kickoff = match_row.kickoff_at.isoformat(sep=" ", timespec="minutes")
        rendered_rows.append(
            f"{match_row.id} | {home_team.name} vs {away_team.name} | "
            f"{kickoff} | {match_row.stage} | {match_row.status}"
        )
    return "\n".join(rendered_rows)


def _parse_cli_option(
    args: list[str],
    option_name: str,
    *,
    default=None,
    required: bool = False,
    cast=str,
):
    if option_name not in args:
        if required:
            raise typer.BadParameter(f"{option_name} requires a value")
        return default

    option_index = args.index(option_name)
    try:
        option_value = args[option_index + 1]
    except IndexError as exc:
        raise typer.BadParameter(f"{option_name} requires a value") from exc

    if option_value.startswith("--"):
        raise typer.BadParameter(f"{option_name} requires a value")
    return cast(option_value)


def _match_listing_query():
    home_team = aliased(NationalTeam)
    away_team = aliased(NationalTeam)
    query = (
        select(Match, home_team, away_team)
        .join(home_team, home_team.id == Match.home_team_id)
        .join(away_team, away_team.id == Match.away_team_id)
    )
    return query, home_team, away_team


@app.command("preview-report")
def preview_report(match_id: int) -> None:
    with _session() as session:
        report = render_match_report(session, match_id)
        typer.echo(report.subject)
        typer.echo(report.body)


@app.command("analyze-match")
def analyze_match(match_id: int) -> None:
    with _session() as session:
        match_row, prediction = _latest_prediction_for_match(session, match_id)
        diagnostic = diagnose_prediction(session, match_id)
        home_team = session.get(NationalTeam, match_row.home_team_id) if match_row.home_team_id else None
        away_team = session.get(NationalTeam, match_row.away_team_id) if match_row.away_team_id else None
        if home_team is None or away_team is None:
            raise ValueError(f"Teams missing for match_id={match_id}")
        payload = CliMatchAnalysisPayload(
            match_label=f"{home_team.name} vs {away_team.name}",
            prediction=prediction,
            diagnostic=diagnostic,
        )
        typer.echo(render_cli_match_analysis(payload))


@app.command(
    "list-matches",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def list_matches(ctx: typer.Context) -> None:
    limit = _parse_cli_option(ctx.args, "--limit", default=20, cast=int)
    with _session() as session:
        query, _, _ = _match_listing_query()
        rows = session.execute(
            query.order_by(desc(Match.kickoff_at), desc(Match.id)).limit(limit)
        ).all()
        typer.echo(_render_match_rows(rows))


@app.command(
    "find-match",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def find_match(ctx: typer.Context) -> None:
    team = _parse_cli_option(ctx.args, "--team", required=True)
    limit = _parse_cli_option(ctx.args, "--limit", default=20, cast=int)
    with _session() as session:
        team_pattern = f"%{team}%"
        query, home_team, away_team = _match_listing_query()
        rows = session.execute(
            query
            .where(
                or_(
                    home_team.name.ilike(team_pattern),
                    away_team.name.ilike(team_pattern),
                )
            )
            .order_by(desc(Match.kickoff_at), desc(Match.id))
            .limit(limit)
        ).all()
        typer.echo(_render_match_rows(rows))


@app.command("send-due-reports")
def send_due_reports_command(window_minutes: int = 125) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    _load_local_env()
    settings = Settings(
        database_url=Settings.database_url_from_env(),
        email=Settings.email_from_env(),
    )
    with _session() as session:
        sent_ids = send_due_reports(
            session,
            settings,
            now,
            timedelta(minutes=window_minutes),
        )
        session.commit()
        typer.echo(f"Sent {len(sent_ids)} report(s).")


@app.command("seed-upcoming-world-cup")
def seed_upcoming_world_cup_command() -> None:
    captured_at = datetime.now(UTC).replace(tzinfo=None)
    with _session() as session:
        seeded = seed_upcoming_world_cup_matches(session, captured_at)
        session.commit()
        typer.echo(f"Seeded {len(seeded)} upcoming World Cup match(es).")


@app.command("rebuild-market-calibration")
def rebuild_market_calibration_command() -> None:
    captured_at = datetime.now(UTC).replace(tzinfo=None)
    with _session() as session:
        built = rebuild_market_calibration_profiles(session, captured_at=captured_at)
        session.commit()
        typer.echo(
            "Rebuilt market calibration profiles: "
            f"1x2={built['1x2']} handicap={built['handicap']} totals={built['totals']}"
        )


if __name__ == "__main__":
    app()
