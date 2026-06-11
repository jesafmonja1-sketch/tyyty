from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from world_cup_intel.schema import (
    Match,
    MatchTeamStat,
    NationalTeam,
    Player,
    PlayerAvailability,
    PlayerImpactRating,
    TeamFormSnapshot,
    TeamPowerSnapshot,
    TeamTacticalProfile,
)


def _average(values: list[float], default: float = 0.0) -> float:
    return sum(values) / len(values) if values else default


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _team_result(match: Match, team_id: int) -> str | None:
    if match.home_score is None or match.away_score is None:
        return None

    team_score = match.home_score if match.home_team_id == team_id else match.away_score
    opponent_score = match.away_score if match.home_team_id == team_id else match.home_score
    if team_score > opponent_score:
        return "W"
    if team_score < opponent_score:
        return "L"
    return "D"


def build_team_snapshot(session, team_id: int, captured_at: datetime) -> TeamPowerSnapshot:
    stats = session.scalars(
        select(MatchTeamStat).where(MatchTeamStat.national_team_id == team_id)
    ).all()
    players = session.scalars(select(Player).where(Player.national_team_id == team_id)).all()
    availability_rows = session.scalars(
        select(PlayerAvailability)
        .join(Player, Player.id == PlayerAvailability.player_id)
        .where(Player.national_team_id == team_id)
    ).all()

    avg_xg = _average([(row.expected_goals or 0.0) for row in stats])
    avg_shots_on_target = _average([float(row.shots_on_target or 0) for row in stats])
    avg_red_cards = _average([float(row.red_cards or 0) for row in stats])
    avg_possession = _average([(row.possession or 50.0) for row in stats], default=50.0)
    avg_corners = _average([float(row.corners or 0) for row in stats])
    availability_score = _clamp_score(
        100.0 - sum(row.minutes_risk for row in availability_rows) * 10.0
    )

    attack_score = _clamp_score(45.0 + avg_xg * 12.0 + avg_shots_on_target * 2.0)
    defense_score = _clamp_score(72.0 - avg_red_cards * 8.0)
    midfield_control_score = _clamp_score(40.0 + avg_possession * 0.7)
    set_piece_score = _clamp_score(35.0 + avg_corners * 4.0)
    recent_form_score = _clamp_score(50.0 + avg_xg * 10.0)
    overall_score = round(
        (
            attack_score
            + defense_score
            + midfield_control_score
            + set_piece_score
            + availability_score
            + recent_form_score
        )
        / 6.0,
        2,
    )

    power_snapshot = TeamPowerSnapshot(
        national_team_id=team_id,
        captured_at=captured_at,
        overall_score=overall_score,
        attack_score=round(attack_score, 2),
        defense_score=round(defense_score, 2),
        midfield_control_score=round(midfield_control_score, 2),
        set_piece_score=round(set_piece_score, 2),
        squad_completeness_score=round(availability_score, 2),
        recent_form_score=round(recent_form_score, 2),
    )
    session.add(power_snapshot)

    team = session.get(NationalTeam, team_id)
    main_formation = team.common_formations[0] if team and team.common_formations else "4-3-3"
    possession_tendency = "possession" if avg_possession >= 55.0 else "balanced"
    pressing_intensity = "high" if avg_possession >= 58.0 else "medium"
    session.add(
        TeamTacticalProfile(
            national_team_id=team_id,
            captured_at=captured_at,
            main_formation=main_formation,
            pressing_intensity=pressing_intensity,
            possession_tendency=possession_tendency,
            transition_reliance="medium",
            progression_focus="mixed",
            tactical_stability_score=68.0,
        )
    )

    matches_by_id = {
        row.id: row
        for row in session.scalars(
            select(Match)
            .where((Match.home_team_id == team_id) | (Match.away_team_id == team_id))
            .order_by(Match.kickoff_at.desc())
            .limit(5)
        )
    }
    results = [
        result
        for match in matches_by_id.values()
        if (result := _team_result(match, team_id)) is not None
    ]
    recent_record = f"W{results.count('W')}-D{results.count('D')}-L{results.count('L')}"
    session.add(
        TeamFormSnapshot(
            national_team_id=team_id,
            captured_at=captured_at,
            recent_record=recent_record,
            adjusted_form_score=round(recent_form_score, 2),
            scoring_trend=round(avg_xg, 2),
            conceding_trend=0.8,
        )
    )

    for player in players:
        is_creator = "creator" in (player.role_tags or [])
        session.add(
            PlayerImpactRating(
                player_id=player.id,
                captured_at=captured_at,
                impact_score=75.0 if is_creator else 62.0,
                impact_reason="creator bonus applied" if is_creator else "baseline role impact",
            )
        )

    return power_snapshot
