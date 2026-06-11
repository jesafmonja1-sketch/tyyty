from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from world_cup_intel.ingest.base import record_source_run
from world_cup_intel.schema import NationalTeam, TeamRanking


def ingest_fifa_rankings(session, payload: dict, captured_at: datetime) -> None:
    record_source_run(
        session,
        source_name="fifa-rankings",
        endpoint="/rankings/men",
        captured_at=captured_at,
        payload=payload,
    )

    ranking_date = datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
    for row in payload["rankings"]:
        team = session.scalar(select(NationalTeam).where(NationalTeam.fifa_code == row["fifa_code"]))
        if team is None:
            team = NationalTeam(
                fifa_code=row["fifa_code"],
                name=row["team_name"],
                confederation=row["confederation"],
                tactical_labels=[],
                common_formations=[],
                is_supported=True,
            )
            session.add(team)
            session.flush()
        else:
            team.name = row["team_name"]
            team.confederation = row["confederation"]

        ranking = session.scalar(
            select(TeamRanking).where(
                TeamRanking.national_team_id == team.id,
                TeamRanking.ranking_date == ranking_date,
            )
        )
        if ranking is None:
            ranking = TeamRanking(national_team_id=team.id, ranking_date=ranking_date)
            session.add(ranking)
        ranking.fifa_rank = row["rank"]
        ranking.ranking_points = row["points"]
