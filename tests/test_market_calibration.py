from world_cup_intel.analysis.market_calibration import build_handicap_bucket_key
from world_cup_intel.analysis.market_calibration import build_probability_band_key
from world_cup_intel.analysis.market_calibration import build_totals_bucket_key
from world_cup_intel.analysis.market_calibration import choose_profile_with_fallback
from world_cup_intel.analysis.market_calibration import settle_handicap_line
from world_cup_intel.analysis.market_calibration import settle_total_line


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
