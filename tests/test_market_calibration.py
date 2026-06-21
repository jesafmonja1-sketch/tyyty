from datetime import datetime

import pytest
from sqlalchemy import select

from world_cup_intel.analysis.market_calibration import build_handicap_bucket_key
from world_cup_intel.analysis.market_calibration import build_handicap_profile
from world_cup_intel.analysis.market_calibration import build_one_x_two_profile
from world_cup_intel.analysis.market_calibration import build_probability_band_key
from world_cup_intel.analysis.market_calibration import rebuild_market_calibration_profiles
from world_cup_intel.analysis.market_calibration import build_totals_profile
from world_cup_intel.analysis.market_calibration import build_totals_bucket_key
from world_cup_intel.analysis.market_calibration import choose_profile_with_fallback
from world_cup_intel.analysis.market_calibration import compute_brier_score
from world_cup_intel.analysis.market_calibration import compute_log_loss
from world_cup_intel.analysis.market_calibration import compute_reliability_gap
from world_cup_intel.analysis.market_calibration import settle_handicap_line
from world_cup_intel.analysis.market_calibration import settle_total_line
from world_cup_intel.analysis.market_calibration import split_rows_by_time
from world_cup_intel.schema import Match
from world_cup_intel.schema import MatchFeatureSnapshot
from world_cup_intel.schema import MatchPrediction
from world_cup_intel.schema import MarketCalibrationProfile
from world_cup_intel.schema import NationalTeam
from world_cup_intel.schema import PredictionRun


def test_build_probability_band_key_groups_probability_into_expected_band():
    assert build_probability_band_key(0.62) == "p_0.60_0.75"


def test_build_probability_band_key_groups_low_probability_into_first_plan_band():
    assert build_probability_band_key(0.10) == "p_0.00_0.15"


def test_build_probability_band_key_includes_left_boundary_of_second_band():
    assert build_probability_band_key(0.15) == "p_0.15_0.30"


def test_build_probability_band_key_includes_left_boundary_of_third_band():
    assert build_probability_band_key(0.30) == "p_0.30_0.45"


def test_build_probability_band_key_includes_left_boundary_of_fourth_band():
    assert build_probability_band_key(0.45) == "p_0.45_0.60"


def test_build_probability_band_key_includes_left_boundary_of_fifth_band():
    assert build_probability_band_key(0.60) == "p_0.60_0.75"


def test_build_probability_band_key_includes_left_boundary_of_final_band():
    assert build_probability_band_key(0.75) == "p_0.75_1.00"


def test_build_probability_band_key_groups_mid_probability_into_plan_band():
    assert build_probability_band_key(0.46) == "p_0.45_0.60"


def test_build_probability_band_key_groups_high_probability_into_final_plan_band():
    assert build_probability_band_key(0.90) == "p_0.75_1.00"


def test_build_handicap_bucket_key_groups_quarter_line():
    assert build_handicap_bucket_key(-1.25) == "hcp_-1.00_-1.50"


def test_build_handicap_bucket_key_groups_negative_half_line_into_stable_band():
    assert build_handicap_bucket_key(-0.5) == "hcp_-0.25_-0.75"


def test_build_handicap_bucket_key_groups_two_goal_line_into_deeper_band():
    assert build_handicap_bucket_key(-2.0) == "hcp_-1.75_-2.50"


def test_build_handicap_bucket_key_includes_left_boundary_of_deeper_range():
    assert build_handicap_bucket_key(-1.75) == "hcp_-1.75_-2.50"


def test_build_handicap_bucket_key_includes_upper_boundary_of_mid_range():
    assert build_handicap_bucket_key(-1.50) == "hcp_-1.00_-1.50"


def test_build_handicap_bucket_key_includes_lower_boundary_of_mid_range():
    assert build_handicap_bucket_key(-1.00) == "hcp_-1.00_-1.50"


def test_build_handicap_bucket_key_includes_upper_boundary_of_shallow_range():
    assert build_handicap_bucket_key(-0.75) == "hcp_-0.25_-0.75"


def test_build_handicap_bucket_key_includes_lower_boundary_of_shallow_range():
    assert build_handicap_bucket_key(-0.25) == "hcp_-0.25_-0.75"


def test_build_handicap_bucket_key_marks_deeper_negative_lines():
    assert build_handicap_bucket_key(-3.25) == "hcp_-2.75_deeper"


def test_build_totals_bucket_key_groups_mid_totals_line():
    assert build_totals_bucket_key(2.75) == "totals_2.5_3.0"


def test_build_totals_bucket_key_groups_flat_two_point_five_line():
    assert build_totals_bucket_key(2.5) == "totals_2.5"


def test_build_totals_bucket_key_groups_flat_three_point_zero_line():
    assert build_totals_bucket_key(3.0) == "totals_3.0"


def test_build_totals_bucket_key_marks_high_totals_tail():
    assert build_totals_bucket_key(3.25) == "totals_3.0_3.5_plus"


def test_settle_handicap_line_preserves_half_push_for_negative_three_quarter_line():
    assert settle_handicap_line(home_goals=2, away_goals=1, line=-0.75) == {
        "cover": 0.5,
        "push": 0.5,
        "fail": 0.0,
    }


def test_settle_handicap_line_pushes_when_margin_matches_full_goal_line():
    assert settle_handicap_line(home_goals=2, away_goals=1, line=-1.0) == {
        "cover": 0.0,
        "push": 1.0,
        "fail": 0.0,
    }


def test_settle_handicap_line_preserves_half_push_for_negative_one_point_two_five_line():
    assert settle_handicap_line(home_goals=2, away_goals=1, line=-1.25) == {
        "cover": 0.0,
        "push": 0.5,
        "fail": 0.5,
    }


def test_settle_handicap_line_preserves_half_push_for_positive_quarter_line_draw():
    assert settle_handicap_line(home_goals=1, away_goals=1, line=0.25) == {
        "cover": 0.5,
        "push": 0.5,
        "fail": 0.0,
    }


def test_settle_handicap_line_preserves_half_push_for_positive_three_quarter_line_loss():
    assert settle_handicap_line(home_goals=1, away_goals=2, line=0.75) == {
        "cover": 0.0,
        "push": 0.5,
        "fail": 0.5,
    }


def test_settle_total_line_preserves_half_push_for_two_point_seven_five_line():
    assert settle_total_line(total_goals=3, line=2.75) == {
        "over": 0.5,
        "push": 0.5,
        "under": 0.0,
    }


def test_settle_total_line_pushes_when_total_matches_whole_number_line():
    assert settle_total_line(total_goals=2, line=2.0) == {
        "over": 0.0,
        "push": 1.0,
        "under": 0.0,
    }


def test_settle_total_line_preserves_half_push_for_two_point_two_five_line():
    assert settle_total_line(total_goals=2, line=2.25) == {
        "over": 0.0,
        "push": 0.5,
        "under": 0.5,
    }


def test_settle_total_line_preserves_half_push_for_three_point_two_five_line():
    assert settle_total_line(total_goals=3, line=3.25) == {
        "over": 0.0,
        "push": 0.5,
        "under": 0.5,
    }


def test_choose_profile_with_fallback_uses_wider_bucket_when_exact_bucket_sample_is_thin():
    profiles = {
        "hcp_-1.00_-1.50": {
            "bucket_key": "hcp_-1.00_-1.50",
            "sample_count": 12,
            "fallback_bucket_key": "hcp_-0.50_-1.50",
        },
        "hcp_-0.50_-1.50": {
            "bucket_key": "hcp_-0.50_-1.50",
            "sample_count": 48,
            "fallback_bucket_key": None,
        },
    }

    chosen = choose_profile_with_fallback(
        profiles,
        bucket_key="hcp_-1.00_-1.50",
        minimum_sample_count=30,
    )

    assert chosen["bucket_key"] == "hcp_-0.50_-1.50"
    assert chosen["fallback_level"] == 1


def test_choose_profile_with_fallback_uses_wider_bucket_when_exact_bucket_is_missing():
    profiles = {
        "hcp_-0.25_-0.75": {
            "bucket_key": "hcp_-0.25_-0.75",
            "sample_count": 52,
            "fallback_bucket_key": None,
        },
    }

    chosen = choose_profile_with_fallback(
        profiles,
        bucket_key="hcp_-0.50_exact",
        fallback_bucket_keys=["hcp_-0.25_-0.75"],
        minimum_sample_count=30,
    )

    assert chosen["bucket_key"] == "hcp_-0.25_-0.75"
    assert chosen["fallback_level"] == 1


def test_choose_profile_with_fallback_supports_market_family_and_tuple_profile_keys():
    profiles = {
        ("handicap", "hcp_-0.25_-0.75"): {
            "bucket_key": "hcp_-0.25_-0.75",
            "sample_count": 64,
            "fallback_bucket_key": None,
        },
    }

    chosen = choose_profile_with_fallback(
        market_family="handicap",
        exact_bucket_key="hcp_missing",
        fallback_bucket_keys=["hcp_-0.25_-0.75"],
        profiles=profiles,
        minimum_sample_count=30,
    )

    assert chosen["bucket_key"] == "hcp_-0.25_-0.75"
    assert chosen["fallback_level"] == 1


def test_build_one_x_two_profile_preserves_bucket_and_reports_smoothed_hit_rate():
    profile = build_one_x_two_profile(
        rows=[
            {"outcome_hit": 1.0},
            {"outcome_hit": 0.0},
            {"outcome_hit": 1.0},
            {"outcome_hit": 1.0},
        ],
        bucket_key="p_0.60_0.75",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert profile["market_family"] == "1x2"
    assert profile["bucket_key"] == "p_0.60_0.75"
    assert profile["profile_version"] == "v1"
    assert profile["sample_count"] == 4
    assert profile["captured_at"] == "2026-06-21T18:00:00Z"
    assert 0.5 < profile["calibrated_hit_rate"] < 0.9


def test_build_one_x_two_profile_uses_expected_laplace_binary_value():
    profile = build_one_x_two_profile(
        rows=[
            {"outcome_hit": 1.0},
            {"outcome_hit": 0.0},
            {"outcome_hit": 1.0},
            {"outcome_hit": 1.0},
        ],
        bucket_key="p_0.60_0.75",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert round(profile["calibrated_hit_rate"], 6) == round(4 / 6, 6)


def test_build_one_x_two_profile_defaults_empty_samples_to_even_rate():
    profile = build_one_x_two_profile(
        rows=[],
        bucket_key="p_0.30_0.45",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert profile["sample_count"] == 0
    assert profile["calibrated_hit_rate"] == 0.5


def test_build_handicap_profile_uses_smoothing_and_normalizes_probabilities():
    profile = build_handicap_profile(
        rows=[
            {"cover": 1.0, "push": 0.0, "fail": 0.0},
            {"cover": 1.0, "push": 0.0, "fail": 0.0},
            {"cover": 1.0, "push": 0.0, "fail": 0.0},
        ],
        bucket_key="hcp_-1.00_-1.50",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert profile["market_family"] == "handicap"
    assert profile["cover_probability"] < 1.0
    assert round(
        profile["cover_probability"] + profile["push_probability"] + profile["fail_probability"],
        6,
    ) == 1.0


def test_build_handicap_profile_uses_expected_laplace_trinary_values():
    profile = build_handicap_profile(
        rows=[
            {"cover": 1.0, "push": 0.0, "fail": 0.0},
            {"cover": 1.0, "push": 0.0, "fail": 0.0},
            {"cover": 1.0, "push": 0.0, "fail": 0.0},
        ],
        bucket_key="hcp_-1.00_-1.50",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert round(profile["cover_probability"], 6) == round(4 / 6, 6)
    assert round(profile["push_probability"], 6) == round(1 / 6, 6)
    assert round(profile["fail_probability"], 6) == round(1 / 6, 6)


def test_build_handicap_profile_defaults_empty_samples_to_uniform_trinary_prior():
    profile = build_handicap_profile(
        rows=[],
        bucket_key="hcp_-0.25_-0.75",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert profile["sample_count"] == 0
    assert round(profile["cover_probability"], 6) == round(1 / 3, 6)
    assert round(profile["push_probability"], 6) == round(1 / 3, 6)
    assert round(profile["fail_probability"], 6) == round(1 / 3, 6)


def test_build_totals_profile_normalizes_trinary_probabilities():
    profile = build_totals_profile(
        rows=[
            {"over": 1.0, "push": 0.0, "under": 0.0},
            {"over": 0.0, "push": 1.0, "under": 0.0},
            {"over": 0.0, "push": 0.0, "under": 1.0},
            {"over": 0.0, "push": 0.0, "under": 1.0},
        ],
        bucket_key="totals_2.5_3.0",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert profile["market_family"] == "totals"
    assert round(
        profile["over_probability"] + profile["push_probability"] + profile["under_probability"],
        6,
    ) == 1.0


def test_build_totals_profile_uses_expected_laplace_trinary_values():
    profile = build_totals_profile(
        rows=[
            {"over": 1.0, "push": 0.0, "under": 0.0},
            {"over": 0.0, "push": 1.0, "under": 0.0},
            {"over": 0.0, "push": 0.0, "under": 1.0},
            {"over": 0.0, "push": 0.0, "under": 1.0},
        ],
        bucket_key="totals_2.5_3.0",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert round(profile["over_probability"], 6) == round(2 / 7, 6)
    assert round(profile["push_probability"], 6) == round(2 / 7, 6)
    assert round(profile["under_probability"], 6) == round(3 / 7, 6)


def test_build_totals_profile_defaults_empty_samples_to_uniform_trinary_prior():
    profile = build_totals_profile(
        rows=[],
        bucket_key="totals_2.5",
        profile_version="v1",
        captured_at="2026-06-21T18:00:00Z",
    )

    assert profile["sample_count"] == 0
    assert round(profile["over_probability"], 6) == round(1 / 3, 6)
    assert round(profile["push_probability"], 6) == round(1 / 3, 6)
    assert round(profile["under_probability"], 6) == round(1 / 3, 6)


def test_split_rows_by_time_sends_older_rows_to_fit_set():
    fit_rows, validation_rows = split_rows_by_time(
        [
            {"captured_at": datetime(2026, 6, 10), "value": 1},
            {"captured_at": datetime(2026, 6, 20), "value": 2},
            {"captured_at": datetime(2026, 6, 21), "value": 3},
        ],
        split_at=datetime(2026, 6, 20),
    )

    assert [row["value"] for row in fit_rows] == [1]
    assert [row["value"] for row in validation_rows] == [2, 3]


def test_compute_brier_score_is_zero_for_perfect_predictions():
    score = compute_brier_score(
        rows=[
            {"predicted_probability": 1.0, "actual_outcome": 1.0},
            {"predicted_probability": 0.0, "actual_outcome": 0.0},
        ]
    )

    assert score == 0.0


def test_compute_log_loss_penalizes_overconfident_misses_more():
    conservative = compute_log_loss(
        rows=[{"predicted_probability": 0.60, "actual_outcome": 0.0}]
    )
    aggressive = compute_log_loss(
        rows=[{"predicted_probability": 0.95, "actual_outcome": 0.0}]
    )

    assert aggressive > conservative


def test_compute_reliability_gap_stays_within_probability_bounds():
    gap = compute_reliability_gap(
        rows=[
            {"predicted_probability": 0.60, "actual_outcome": 1.0},
            {"predicted_probability": 0.62, "actual_outcome": 0.0},
            {"predicted_probability": 0.61, "actual_outcome": 1.0},
        ],
        bucket_size=0.1,
    )

    assert 0.0 <= gap <= 1.0


def test_compute_reliability_gap_respects_bucket_boundaries_for_float_edges():
    gap = compute_reliability_gap(
        rows=[
            {"predicted_probability": 0.30, "actual_outcome": 1.0},
            {"predicted_probability": 0.39, "actual_outcome": 0.0},
            {"predicted_probability": 0.60, "actual_outcome": 1.0},
            {"predicted_probability": 0.69, "actual_outcome": 0.0},
        ],
        bucket_size=0.1,
    )

    assert gap == pytest.approx(0.15)


def test_rebuild_market_calibration_profiles_persists_all_market_families(session):
    home = NationalTeam(
        fifa_code="GER",
        name="Germany",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="CRC",
        name="Costa Rica",
        confederation="CONCACAF",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="mc-rebuild-1",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 20, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        home_score=3,
        away_score=1,
        half_time_score="2-0",
        status="finished",
    )
    session.add(match_row)
    session.flush()

    run = PredictionRun(
        match_id=match_row.id,
        captured_at=datetime(2026, 6, 20, 12, 0, 0),
        model_version="v1-rules",
    )
    session.add(run)
    session.flush()

    session.add(
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
            market_handicap_line=-1.25,
            market_total_line=2.75,
            market_home_probability=0.64,
            market_draw_probability=0.22,
            market_away_probability=0.14,
            market_over_price=1.91,
            market_under_price=1.95,
            lambda_home=2.2,
            lambda_away=0.9,
            projected_tempo_score=0.0,
            learning_adjustment=0.0,
            feature_payload_json={},
        )
    )
    session.add(
        MatchPrediction(
            prediction_run_id=run.id,
            home_win_probability=0.68,
            draw_probability=0.20,
            away_win_probability=0.12,
            calibrated_home_win_probability=0.66,
            calibrated_draw_probability=0.21,
            calibrated_away_win_probability=0.13,
            expected_home_goals=2.2,
            expected_away_goals=0.9,
            over_2_5_probability=0.59,
            under_2_5_probability=0.41,
            handicap_cover_probability=0.52,
            handicap_push_probability=0.18,
            handicap_fail_probability=0.30,
            totals_over_probability=0.56,
            totals_push_probability=0.17,
            totals_under_probability=0.27,
            fair_handicap_line=-1.0,
            fair_total_line=2.75,
            market_handicap_line=-1.25,
            recommended_handicap_side="home",
            recommended_totals_side="over",
            totals_tendency="over 2.5",
            likely_scorelines="2-0,3-1,2-1",
            confidence_level="medium",
            summary_conclusion="test fixture",
            calibration_summary_json={},
        )
    )
    session.commit()

    built = rebuild_market_calibration_profiles(
        session,
        captured_at=datetime(2026, 6, 21, 12, 0, 0),
    )
    session.commit()

    profiles = session.scalars(select(MarketCalibrationProfile)).all()

    assert built["1x2"] >= 1
    assert built["handicap"] >= 1
    assert built["totals"] >= 1
    assert {profile.market_family for profile in profiles} >= {"1x2", "handicap", "totals"}


def test_rebuild_market_calibration_profiles_builds_1x2_without_feature_snapshot(session):
    home = NationalTeam(
        fifa_code="NED",
        name="Netherlands",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="SEN",
        name="Senegal",
        confederation="CAF",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="mc-rebuild-1x2-only",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 19, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        home_score=1,
        away_score=0,
        half_time_score="1-0",
        status="finished",
    )
    session.add(match_row)
    session.flush()

    run = PredictionRun(
        match_id=match_row.id,
        captured_at=datetime(2026, 6, 19, 12, 0, 0),
        model_version="v1-rules",
    )
    session.add(run)
    session.flush()

    session.add(
        MatchPrediction(
            prediction_run_id=run.id,
            home_win_probability=0.55,
            draw_probability=0.27,
            away_win_probability=0.18,
            calibrated_home_win_probability=0.55,
            calibrated_draw_probability=0.27,
            calibrated_away_win_probability=0.18,
            expected_home_goals=1.4,
            expected_away_goals=0.8,
            over_2_5_probability=0.41,
            under_2_5_probability=0.59,
            handicap_cover_probability=None,
            handicap_push_probability=None,
            handicap_fail_probability=None,
            totals_over_probability=None,
            totals_push_probability=None,
            totals_under_probability=None,
            fair_handicap_line=-0.5,
            fair_total_line=2.25,
            market_handicap_line=None,
            recommended_handicap_side="home",
            recommended_totals_side=None,
            totals_tendency="under 2.5",
            likely_scorelines="1-0,1-1,2-0",
            confidence_level="medium",
            summary_conclusion="1x2 only fixture",
            calibration_summary_json={},
        )
    )
    session.commit()

    built = rebuild_market_calibration_profiles(
        session,
        captured_at=datetime(2026, 6, 21, 12, 0, 0),
    )
    session.commit()

    one_x_two_profiles = session.scalars(
        select(MarketCalibrationProfile).where(MarketCalibrationProfile.market_family == "1x2")
    ).all()

    assert built["1x2"] >= 1
    assert one_x_two_profiles


def test_rebuild_market_calibration_profiles_rejects_duplicate_predictions_for_same_run(session):
    home = NationalTeam(
        fifa_code="USA",
        name="United States",
        confederation="CONCACAF",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="IRN",
        name="Iran",
        confederation="AFC",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="mc-rebuild-duplicate-run",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 18, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        home_score=2,
        away_score=1,
        half_time_score="1-1",
        status="finished",
    )
    session.add(match_row)
    session.flush()

    run = PredictionRun(
        match_id=match_row.id,
        captured_at=datetime(2026, 6, 18, 12, 0, 0),
        model_version="v1-rules",
    )
    session.add(run)
    session.flush()

    session.add(
        MatchFeatureSnapshot(
            prediction_run_id=run.id,
            match_id=match_row.id,
            captured_at=run.captured_at,
            model_version="v1-rules",
            home_overall_score=80.0,
            away_overall_score=76.0,
            home_attack_score=78.0,
            away_attack_score=73.0,
            home_defense_score=77.0,
            away_defense_score=74.0,
            home_recent_form_score=79.0,
            away_recent_form_score=75.0,
            power_delta=4.0,
            attack_delta=5.0,
            defense_delta=3.0,
            form_delta=4.0,
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
            market_home_probability=0.51,
            market_draw_probability=0.28,
            market_away_probability=0.21,
            market_over_price=1.94,
            market_under_price=1.9,
            lambda_home=1.4,
            lambda_away=1.0,
            projected_tempo_score=0.0,
            learning_adjustment=0.0,
            feature_payload_json={},
        )
    )
    session.add_all(
        [
            MatchPrediction(
                prediction_run_id=run.id,
                home_win_probability=0.48,
                draw_probability=0.29,
                away_win_probability=0.23,
                calibrated_home_win_probability=0.48,
                calibrated_draw_probability=0.29,
                calibrated_away_win_probability=0.23,
                expected_home_goals=1.4,
                expected_away_goals=1.0,
                over_2_5_probability=0.46,
                under_2_5_probability=0.54,
                handicap_cover_probability=0.45,
                handicap_push_probability=0.23,
                handicap_fail_probability=0.32,
                totals_over_probability=0.44,
                totals_push_probability=0.17,
                totals_under_probability=0.39,
                fair_handicap_line=-0.25,
                fair_total_line=2.5,
                market_handicap_line=-0.5,
                recommended_handicap_side="away",
                recommended_totals_side="under",
                totals_tendency="under 2.5",
                likely_scorelines="1-1,2-1,1-0",
                confidence_level="medium",
                summary_conclusion="duplicate prediction a",
                calibration_summary_json={},
            ),
            MatchPrediction(
                prediction_run_id=run.id,
                home_win_probability=0.52,
                draw_probability=0.27,
                away_win_probability=0.21,
                calibrated_home_win_probability=0.52,
                calibrated_draw_probability=0.27,
                calibrated_away_win_probability=0.21,
                expected_home_goals=1.6,
                expected_away_goals=0.9,
                over_2_5_probability=0.49,
                under_2_5_probability=0.51,
                handicap_cover_probability=0.48,
                handicap_push_probability=0.21,
                handicap_fail_probability=0.31,
                totals_over_probability=0.47,
                totals_push_probability=0.16,
                totals_under_probability=0.37,
                fair_handicap_line=-0.5,
                fair_total_line=2.5,
                market_handicap_line=-0.5,
                recommended_handicap_side="home",
                recommended_totals_side="over",
                totals_tendency="over 2.5",
                likely_scorelines="2-1,1-0,1-1",
                confidence_level="medium",
                summary_conclusion="duplicate prediction b",
                calibration_summary_json={},
            ),
        ]
    )
    session.commit()

    with pytest.raises(ValueError, match=f"prediction_run_id={run.id}"):
        rebuild_market_calibration_profiles(
            session,
            captured_at=datetime(2026, 6, 21, 12, 0, 0),
        )


def test_rebuild_market_calibration_profiles_replaces_existing_v1_profiles(session):
    home = NationalTeam(
        fifa_code="FRA",
        name="France",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="POL",
        name="Poland",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="mc-rebuild-replace-v1",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 20, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        home_score=2,
        away_score=0,
        half_time_score="1-0",
        status="finished",
    )
    session.add(match_row)
    session.flush()

    run = PredictionRun(
        match_id=match_row.id,
        captured_at=datetime(2026, 6, 20, 12, 0, 0),
        model_version="v1-rules",
    )
    session.add(run)
    session.flush()

    session.add(
        MatchFeatureSnapshot(
            prediction_run_id=run.id,
            match_id=match_row.id,
            captured_at=run.captured_at,
            model_version="v1-rules",
            home_overall_score=85.0,
            away_overall_score=76.0,
            home_attack_score=84.0,
            away_attack_score=72.0,
            home_defense_score=81.0,
            away_defense_score=73.0,
            home_recent_form_score=83.0,
            away_recent_form_score=74.0,
            power_delta=9.0,
            attack_delta=12.0,
            defense_delta=8.0,
            form_delta=9.0,
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
            market_handicap_line=-0.75,
            market_total_line=2.5,
            market_home_probability=0.58,
            market_draw_probability=0.25,
            market_away_probability=0.17,
            market_over_price=1.93,
            market_under_price=1.91,
            lambda_home=1.7,
            lambda_away=0.8,
            projected_tempo_score=0.0,
            learning_adjustment=0.0,
            feature_payload_json={},
        )
    )
    session.add(
        MatchPrediction(
            prediction_run_id=run.id,
            home_win_probability=0.60,
            draw_probability=0.24,
            away_win_probability=0.16,
            calibrated_home_win_probability=0.60,
            calibrated_draw_probability=0.24,
            calibrated_away_win_probability=0.16,
            expected_home_goals=1.7,
            expected_away_goals=0.8,
            over_2_5_probability=0.47,
            under_2_5_probability=0.53,
            handicap_cover_probability=0.51,
            handicap_push_probability=0.19,
            handicap_fail_probability=0.30,
            totals_over_probability=0.45,
            totals_push_probability=0.17,
            totals_under_probability=0.38,
            fair_handicap_line=-0.5,
            fair_total_line=2.5,
            market_handicap_line=-0.75,
            recommended_handicap_side="away",
            recommended_totals_side="under",
            totals_tendency="under 2.5",
            likely_scorelines="1-0,2-0,2-1",
            confidence_level="medium",
            summary_conclusion="replace fixture",
            calibration_summary_json={},
        )
    )
    session.add(
        MarketCalibrationProfile(
            market_family="1x2",
            bucket_key="stale_bucket",
            profile_version="v1",
            sample_count=99,
            fallback_bucket_key=None,
            profile_json={"stale": True},
            updated_at=datetime(2026, 6, 19, 12, 0, 0),
        )
    )
    session.commit()

    first_built = rebuild_market_calibration_profiles(
        session,
        captured_at=datetime(2026, 6, 21, 12, 0, 0),
    )
    session.commit()
    second_built = rebuild_market_calibration_profiles(
        session,
        captured_at=datetime(2026, 6, 21, 12, 30, 0),
    )
    session.commit()

    profiles = session.scalars(
        select(MarketCalibrationProfile).where(MarketCalibrationProfile.profile_version == "v1")
    ).all()

    assert first_built == second_built
    assert all(profile.bucket_key != "stale_bucket" for profile in profiles)
    assert len(profiles) == sum(second_built.values())


def test_rebuild_market_calibration_profiles_uses_snapshot_from_selected_prediction_run(session):
    home = NationalTeam(
        fifa_code="ENG",
        name="England",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    away = NationalTeam(
        fifa_code="WAL",
        name="Wales",
        confederation="UEFA",
        tactical_labels=[],
        common_formations=[],
        is_supported=True,
    )
    session.add_all([home, away])
    session.flush()

    match_row = Match(
        external_id="mc-rebuild-run-alignment",
        competition="FIFA World Cup",
        stage="Group Stage",
        kickoff_at=datetime(2026, 6, 20, 18, 0, 0),
        home_team_id=home.id,
        away_team_id=away.id,
        is_neutral_site=True,
        home_score=3,
        away_score=0,
        half_time_score="1-0",
        status="finished",
    )
    session.add(match_row)
    session.flush()

    older_run = PredictionRun(
        match_id=match_row.id,
        captured_at=datetime(2026, 6, 20, 10, 0, 0),
        model_version="v1-rules",
    )
    newer_run = PredictionRun(
        match_id=match_row.id,
        captured_at=datetime(2026, 6, 20, 12, 0, 0),
        model_version="v1-rules",
    )
    session.add_all([older_run, newer_run])
    session.flush()

    session.add(
        MatchFeatureSnapshot(
            prediction_run_id=older_run.id,
            match_id=match_row.id,
            captured_at=older_run.captured_at,
            model_version="v1-rules",
            home_overall_score=84.0,
            away_overall_score=74.0,
            home_attack_score=82.0,
            away_attack_score=71.0,
            home_defense_score=80.0,
            away_defense_score=72.0,
            home_recent_form_score=81.0,
            away_recent_form_score=73.0,
            power_delta=10.0,
            attack_delta=11.0,
            defense_delta=8.0,
            form_delta=8.0,
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
            market_handicap_line=-1.25,
            market_total_line=2.75,
            market_home_probability=0.62,
            market_draw_probability=0.23,
            market_away_probability=0.15,
            market_over_price=1.9,
            market_under_price=1.94,
            lambda_home=1.8,
            lambda_away=0.9,
            projected_tempo_score=0.0,
            learning_adjustment=0.0,
            feature_payload_json={},
        )
    )
    session.add_all(
        [
            MatchPrediction(
                prediction_run_id=older_run.id,
                home_win_probability=0.61,
                draw_probability=0.24,
                away_win_probability=0.15,
                calibrated_home_win_probability=0.61,
                calibrated_draw_probability=0.24,
                calibrated_away_win_probability=0.15,
                expected_home_goals=1.8,
                expected_away_goals=0.9,
                over_2_5_probability=0.49,
                under_2_5_probability=0.51,
                handicap_cover_probability=0.52,
                handicap_push_probability=0.18,
                handicap_fail_probability=0.30,
                totals_over_probability=0.47,
                totals_push_probability=0.17,
                totals_under_probability=0.36,
                fair_handicap_line=-0.75,
                fair_total_line=2.5,
                market_handicap_line=-1.25,
                recommended_handicap_side="away",
                recommended_totals_side="under",
                totals_tendency="under 2.5",
                likely_scorelines="2-0,2-1,1-0",
                confidence_level="medium",
                summary_conclusion="older run",
                calibration_summary_json={},
            ),
            MatchPrediction(
                prediction_run_id=newer_run.id,
                home_win_probability=0.66,
                draw_probability=0.21,
                away_win_probability=0.13,
                calibrated_home_win_probability=0.66,
                calibrated_draw_probability=0.21,
                calibrated_away_win_probability=0.13,
                expected_home_goals=2.1,
                expected_away_goals=0.7,
                over_2_5_probability=0.54,
                under_2_5_probability=0.46,
                handicap_cover_probability=0.57,
                handicap_push_probability=0.15,
                handicap_fail_probability=0.28,
                totals_over_probability=0.52,
                totals_push_probability=0.16,
                totals_under_probability=0.32,
                fair_handicap_line=-1.0,
                fair_total_line=2.75,
                market_handicap_line=-0.5,
                recommended_handicap_side="home",
                recommended_totals_side="over",
                totals_tendency="over 2.5",
                likely_scorelines="3-0,2-0,2-1",
                confidence_level="medium",
                summary_conclusion="newer run",
                calibration_summary_json={},
            ),
        ]
    )
    session.commit()

    built = rebuild_market_calibration_profiles(
        session,
        captured_at=datetime(2026, 6, 21, 12, 0, 0),
    )
    session.commit()

    handicap_profiles = session.scalars(
        select(MarketCalibrationProfile).where(MarketCalibrationProfile.market_family == "handicap")
    ).all()
    totals_profiles = session.scalars(
        select(MarketCalibrationProfile).where(MarketCalibrationProfile.market_family == "totals")
    ).all()

    assert built["handicap"] == 0
    assert built["totals"] == 1
    assert handicap_profiles == []
    assert len(totals_profiles) == 1
    assert totals_profiles[0].bucket_key == "totals_2.5_3.0"
