from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from world_cup_intel.schema import (
    MatchKeyEvent,
    MatchReview,
    Player,
    PlayerAvailability,
    TeamChangeLog,
    TeamPowerSnapshot,
    TeamTacticalProfile,
)


def _latest_two(session, model, team_id: int):
    return session.scalars(
        select(model)
        .where(model.national_team_id == team_id)
        .order_by(desc(model.captured_at))
    ).all()[:2]


def build_match_review(session, match_id: int, team_id: int, captured_at: datetime) -> MatchReview:
    power_rows = _latest_two(session, TeamPowerSnapshot, team_id)
    tactical_rows = _latest_two(session, TeamTacticalProfile, team_id)
    if len(power_rows) < 2:
        raise ValueError(f"Need at least two power snapshots for team_id={team_id}")
    if len(tactical_rows) < 2:
        raise ValueError(f"Need at least two tactical profiles for team_id={team_id}")

    availability_rows = session.execute(
        select(PlayerAvailability, Player.full_name)
        .join(Player, Player.id == PlayerAvailability.player_id)
        .where(PlayerAvailability.match_id == match_id, Player.national_team_id == team_id)
    ).all()
    events = session.scalars(
        select(MatchKeyEvent).where(
            MatchKeyEvent.match_id == match_id,
            MatchKeyEvent.national_team_id == team_id,
        )
    ).all()

    injured_names = []
    for availability, player_name in availability_rows:
        if availability.status != "available":
            injured_names.append(f"{player_name}: {availability.details}")

    current_power, previous_power = power_rows[0], power_rows[1]
    power_delta = current_power.overall_score - previous_power.overall_score
    strength_text = "improved overall strength" if power_delta >= 0 else "dropped overall strength"
    tactical_text = f"{tactical_rows[1].main_formation} -> {tactical_rows[0].main_formation}"
    event_text = "; ".join(event.details for event in events) if events else "no high-leverage events recorded"
    injury_text = ", ".join(injured_names) if injured_names else "no fresh absences flagged"

    review = MatchReview(
        match_id=match_id,
        national_team_id=team_id,
        created_at=captured_at,
        summary_text=f"{injury_text}; {event_text}",
        tactical_change_summary=tactical_text,
        strength_change_summary=f"{strength_text} ({power_delta:+.2f})",
        next_match_impact_summary="starting eleven risk elevated" if injured_names else "baseline availability outlook",
    )
    session.add(review)
    session.add(
        TeamChangeLog(
            national_team_id=team_id,
            match_id=match_id,
            created_at=captured_at,
            change_type="tactical",
            details=tactical_text,
        )
    )
    session.add(
        TeamChangeLog(
            national_team_id=team_id,
            match_id=match_id,
            created_at=captured_at,
            change_type="strength",
            details=f"{power_delta:+.2f}",
        )
    )
    return review
