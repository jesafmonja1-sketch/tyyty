from datetime import datetime

from world_cup_intel.analysis.reviews import build_match_review
from world_cup_intel.schema import (
    Match,
    MatchKeyEvent,
    MatchReview,
    NationalTeam,
    Player,
    PlayerAvailability,
    TeamChangeLog,
    TeamPowerSnapshot,
    TeamTacticalProfile,
)


def test_build_match_review_flags_injuries_and_strength_change(session):
    team = NationalTeam(
        fifa_code="ENG",
        name="England",
        confederation="UEFA",
        tactical_labels=["high-press"],
        common_formations=["4-2-3-1"],
        is_supported=True,
    )
    opponent = NationalTeam(
        fifa_code="ESP",
        name="Spain",
        confederation="UEFA",
        tactical_labels=["possession"],
        common_formations=["4-3-3"],
        is_supported=True,
    )
    session.add_all([team, opponent])
    session.flush()

    player = Player(
        full_name="Bukayo Saka",
        national_team_id=team.id,
        position="FW",
        age=25,
        club_name="Arsenal",
        role_tags=["creator"],
    )
    session.add(player)
    session.flush()

    match_row = Match(
        external_id="wc-3",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 20, 18, 0, 0),
        home_team_id=team.id,
        away_team_id=opponent.id,
        is_neutral_site=True,
        home_score=1,
        away_score=0,
        half_time_score="0-0",
        status="finished",
    )
    session.add(match_row)
    session.flush()

    session.add(
        TeamPowerSnapshot(
            national_team_id=team.id,
            captured_at=datetime(2026, 6, 16, 18, 0, 0),
            overall_score=78.0,
            attack_score=76.0,
            defense_score=77.0,
            midfield_control_score=75.0,
            set_piece_score=70.0,
            squad_completeness_score=95.0,
            recent_form_score=79.0,
        )
    )
    session.add(
        TeamPowerSnapshot(
            national_team_id=team.id,
            captured_at=datetime(2026, 6, 20, 21, 0, 0),
            overall_score=81.0,
            attack_score=79.0,
            defense_score=80.0,
            midfield_control_score=78.0,
            set_piece_score=71.0,
            squad_completeness_score=82.0,
            recent_form_score=84.0,
        )
    )
    session.add(
        TeamTacticalProfile(
            national_team_id=team.id,
            captured_at=datetime(2026, 6, 16, 18, 0, 0),
            main_formation="4-2-3-1",
            pressing_intensity="medium",
            possession_tendency="balanced",
            transition_reliance="medium",
            progression_focus="wide",
            tactical_stability_score=66.0,
        )
    )
    session.add(
        TeamTacticalProfile(
            national_team_id=team.id,
            captured_at=datetime(2026, 6, 20, 21, 0, 0),
            main_formation="4-3-3",
            pressing_intensity="high",
            possession_tendency="balanced",
            transition_reliance="high",
            progression_focus="wide",
            tactical_stability_score=71.0,
        )
    )
    session.add(
        PlayerAvailability(
            player_id=player.id,
            match_id=match_row.id,
            status="injured",
            details="hamstring tightness",
            expected_to_start=False,
            minutes_risk=0.9,
        )
    )
    session.add(
        MatchKeyEvent(
            match_id=match_row.id,
            national_team_id=team.id,
            minute=67,
            event_type="injury_substitution",
            details="Saka left with hamstring tightness",
        )
    )

    review = build_match_review(session, match_row.id, team.id, datetime(2026, 6, 20, 22, 0, 0))
    session.commit()

    assert "hamstring" in review.summary_text.lower()
    assert "4-2-3-1 -> 4-3-3" in review.tactical_change_summary
    assert "improved" in review.strength_change_summary.lower()
    assert session.query(MatchReview).count() == 1
    assert session.query(TeamChangeLog).count() >= 2
