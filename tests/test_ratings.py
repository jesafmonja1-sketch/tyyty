from datetime import datetime

from world_cup_intel.analysis.ratings import build_team_snapshot
from world_cup_intel.schema import Match, MatchTeamStat, NationalTeam, Player, PlayerAvailability, TeamPowerSnapshot


def test_build_team_snapshot_raises_attack_score_for_strong_recent_results(session):
    team = NationalTeam(fifa_code="ARG", name="Argentina", confederation="CONMEBOL", tactical_labels=[], common_formations=["4-3-3"], is_supported=True)
    opponent = NationalTeam(fifa_code="FRA", name="France", confederation="UEFA", tactical_labels=[], common_formations=["4-2-3-1"], is_supported=True)
    session.add_all([team, opponent])
    session.flush()

    session.add(Player(full_name="Lionel Messi", national_team_id=team.id, position="FW", age=39, club_name="Inter Miami", role_tags=["creator", "set-piece"]))
    match_row = Match(
        external_id="wc-1",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 14, 18, 0, 0),
        home_team_id=team.id,
        away_team_id=opponent.id,
        is_neutral_site=True,
        home_score=2,
        away_score=0,
        half_time_score="1-0",
        status="finished",
    )
    session.add(match_row)
    session.flush()
    session.add(MatchTeamStat(match_id=match_row.id, national_team_id=team.id, possession=58.0, shots=14, shots_on_target=6, corners=5, fouls=9, yellow_cards=1, red_cards=0, expected_goals=1.9))
    session.add(PlayerAvailability(player_id=1, match_id=match_row.id, status="available", details="", expected_to_start=True, minutes_risk=0.0))

    snapshot = build_team_snapshot(session, team.id, datetime(2026, 6, 14, 21, 0, 0))
    session.commit()

    assert snapshot.attack_score > 60.0
    assert snapshot.overall_score >= snapshot.attack_score - 10.0
    assert session.query(TeamPowerSnapshot).count() == 1
