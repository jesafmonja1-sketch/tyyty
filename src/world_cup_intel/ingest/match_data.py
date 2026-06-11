from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from world_cup_intel.ingest.base import record_source_run
from world_cup_intel.schema import Match, NationalTeam


def _get_or_create_team(session, team_payload: dict) -> NationalTeam:
    team = session.scalar(select(NationalTeam).where(NationalTeam.fifa_code == team_payload["fifa_code"]))
    if team is None:
        team = NationalTeam(
            fifa_code=team_payload["fifa_code"],
            name=team_payload["name"],
            confederation=team_payload["confederation"],
            tactical_labels=[],
            common_formations=[],
            is_supported=True,
        )
        session.add(team)
        session.flush()
    else:
        team.name = team_payload["name"]
        team.confederation = team_payload["confederation"]
    return team


def ingest_match_bundle(session, payload: dict, captured_at: datetime) -> Match:
    record_source_run(
        session,
        source_name="match-data",
        endpoint="/matches",
        captured_at=captured_at,
        payload=payload,
    )

    match_data = payload["match"]
    home_team = _get_or_create_team(session, match_data["home_team"])
    away_team = _get_or_create_team(session, match_data["away_team"])

    match_row = session.scalar(select(Match).where(Match.external_id == match_data["id"]))
    if match_row is None:
        match_row = Match(external_id=match_data["id"])
        session.add(match_row)

    match_row.competition = match_data["competition"]
    match_row.stage = match_data["stage"]
    match_row.kickoff_at = datetime.fromisoformat(match_data["kickoff_at"].replace("Z", "+00:00"))
    match_row.home_team_id = home_team.id
    match_row.away_team_id = away_team.id
    match_row.is_neutral_site = match_data["neutral_site"]
    match_row.status = match_data["status"]
    match_row.home_score = match_data.get("home_score")
    match_row.away_score = match_data.get("away_score")
    match_row.half_time_score = match_data.get("half_time_score")
    return match_row
