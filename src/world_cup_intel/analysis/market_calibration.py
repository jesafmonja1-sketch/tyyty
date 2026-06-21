from __future__ import annotations

from datetime import datetime
import math


def build_probability_band_key(probability: float) -> str:
    if probability < 0.15:
        return "p_0.00_0.15"
    if probability < 0.30:
        return "p_0.15_0.30"
    if probability < 0.45:
        return "p_0.30_0.45"
    if probability < 0.60:
        return "p_0.45_0.60"
    if probability < 0.75:
        return "p_0.60_0.75"
    return "p_0.75_1.00"


def build_handicap_bucket_key(line: float) -> str:
    if line <= -2.75:
        return "hcp_-2.75_deeper"
    if -2.50 <= line <= -1.75:
        return "hcp_-1.75_-2.50"
    if -1.50 <= line <= -1.00:
        return "hcp_-1.00_-1.50"
    if -0.75 <= line <= -0.25:
        return "hcp_-0.25_-0.75"
    return f"hcp_{line:.2f}"


def build_totals_bucket_key(line: float) -> str:
    if line >= 3.25:
        return "totals_3.0_3.5_plus"
    if line == 3.0:
        return "totals_3.0"
    if line == 2.75:
        return "totals_2.5_3.0"
    if line == 2.5:
        return "totals_2.5"
    if line in (2.0, 2.25):
        return "totals_2.0_2.5"
    return f"totals_{line:.1f}"


def _split_quarter_line(line: float) -> tuple[float, float] | None:
    quarter_remainder = int(round(abs(line) * 100)) % 50
    if quarter_remainder == 25:
        if line > 0:
            return (line - 0.25, line + 0.25)
        return (line + 0.25, line - 0.25)
    return None


def _settle_single_handicap(*, goal_difference: int, line: float) -> dict[str, float]:
    adjusted_margin = goal_difference + line
    if adjusted_margin > 0:
        return {"cover": 1.0, "push": 0.0, "fail": 0.0}
    if adjusted_margin == 0:
        return {"cover": 0.0, "push": 1.0, "fail": 0.0}
    return {"cover": 0.0, "push": 0.0, "fail": 1.0}


def settle_handicap_line(*, home_goals: int, away_goals: int, line: float) -> dict[str, float]:
    goal_difference = home_goals - away_goals
    split_line = _split_quarter_line(line)
    if split_line is None:
        return _settle_single_handicap(goal_difference=goal_difference, line=line)

    first = _settle_single_handicap(goal_difference=goal_difference, line=split_line[0])
    second = _settle_single_handicap(goal_difference=goal_difference, line=split_line[1])
    return {
        "cover": (first["cover"] + second["cover"]) / 2,
        "push": (first["push"] + second["push"]) / 2,
        "fail": (first["fail"] + second["fail"]) / 2,
    }


def _settle_single_total(*, total_goals: int, line: float) -> dict[str, float]:
    if total_goals > line:
        return {"over": 1.0, "push": 0.0, "under": 0.0}
    if total_goals == line:
        return {"over": 0.0, "push": 1.0, "under": 0.0}
    return {"over": 0.0, "push": 0.0, "under": 1.0}


def settle_total_line(*, total_goals: int, line: float) -> dict[str, float]:
    split_line = _split_quarter_line(line)
    if split_line is None:
        return _settle_single_total(total_goals=total_goals, line=line)

    first = _settle_single_total(total_goals=total_goals, line=split_line[0])
    second = _settle_single_total(total_goals=total_goals, line=split_line[1])
    return {
        "over": (first["over"] + second["over"]) / 2,
        "push": (first["push"] + second["push"]) / 2,
        "under": (first["under"] + second["under"]) / 2,
    }


def choose_profile_with_fallback(
    profiles: dict,
    *,
    market_family: str | None = None,
    exact_bucket_key: str | None = None,
    minimum_sample_count: int,
    fallback_bucket_keys: list[str] | None = None,
    bucket_key: str | None = None,
):
    exact_key = exact_bucket_key or bucket_key
    if exact_key is None:
        raise ValueError("exact_bucket_key or bucket_key is required")

    def _lookup(bucket: str):
        if market_family is not None:
            profile = profiles.get((market_family, bucket))
            if profile is not None:
                return profile
        return profiles.get(bucket)

    fallback_level = 0
    visited: set[str] = set()
    pending_keys = [exact_key, *(fallback_bucket_keys or [])]

    while pending_keys:
        current_key = pending_keys.pop(0)
        if current_key in visited:
            continue
        visited.add(current_key)

        profile = _lookup(current_key)
        if profile is None:
            fallback_level += 1
            continue

        if profile["sample_count"] >= minimum_sample_count:
            return {**profile, "fallback_level": fallback_level}

        fallback_level += 1
        next_key = profile.get("fallback_bucket_key")
        if next_key is not None:
            pending_keys.insert(0, next_key)

    return None


def _laplace_binary(successes: float, total: int, *, alpha: float = 1.0) -> float:
    return (successes + alpha) / (total + 2 * alpha)


def _laplace_trinary(first: float, second: float, third: float, *, alpha: float = 1.0) -> dict[str, float]:
    total = first + second + third
    denominator = total + 3 * alpha
    return {
        "first": (first + alpha) / denominator,
        "second": (second + alpha) / denominator,
        "third": (third + alpha) / denominator,
    }


def build_one_x_two_profile(
    *,
    rows: list[dict],
    bucket_key: str,
    profile_version: str,
    captured_at: datetime | str,
):
    sample_count = len(rows)
    hit_count = sum(float(row["outcome_hit"]) for row in rows)
    return {
        "market_family": "1x2",
        "bucket_key": bucket_key,
        "profile_version": profile_version,
        "sample_count": sample_count,
        "captured_at": captured_at,
        "calibrated_hit_rate": _laplace_binary(hit_count, sample_count),
    }


def build_handicap_profile(
    *,
    rows: list[dict],
    bucket_key: str,
    profile_version: str,
    captured_at: datetime | str,
):
    sample_count = len(rows)
    smoothed = _laplace_trinary(
        sum(float(row["cover"]) for row in rows),
        sum(float(row["push"]) for row in rows),
        sum(float(row["fail"]) for row in rows),
    )
    return {
        "market_family": "handicap",
        "bucket_key": bucket_key,
        "profile_version": profile_version,
        "sample_count": sample_count,
        "captured_at": captured_at,
        "cover_probability": smoothed["first"],
        "push_probability": smoothed["second"],
        "fail_probability": smoothed["third"],
    }


def build_totals_profile(
    *,
    rows: list[dict],
    bucket_key: str,
    profile_version: str,
    captured_at: datetime | str,
):
    sample_count = len(rows)
    smoothed = _laplace_trinary(
        sum(float(row["over"]) for row in rows),
        sum(float(row["push"]) for row in rows),
        sum(float(row["under"]) for row in rows),
    )
    return {
        "market_family": "totals",
        "bucket_key": bucket_key,
        "profile_version": profile_version,
        "sample_count": sample_count,
        "captured_at": captured_at,
        "over_probability": smoothed["first"],
        "push_probability": smoothed["second"],
        "under_probability": smoothed["third"],
    }


def _normalize_probabilities(probabilities: dict[str, float]) -> dict[str, float]:
    total = sum(probabilities.values())
    if total <= 0:
        raise ValueError("probabilities must sum to a positive value")
    return {key: value / total for key, value in probabilities.items()}


def _one_x_two_fallback_bucket_keys(bucket_key: str) -> list[str]:
    ordered_keys = [
        "p_0.00_0.15",
        "p_0.15_0.30",
        "p_0.30_0.45",
        "p_0.45_0.60",
        "p_0.60_0.75",
        "p_0.75_1.00",
    ]
    if bucket_key not in ordered_keys:
        return []
    index = ordered_keys.index(bucket_key)
    fallback_keys: list[str] = []
    if index > 0:
        fallback_keys.append(ordered_keys[index - 1])
    if index < len(ordered_keys) - 1:
        fallback_keys.append(ordered_keys[index + 1])
    return fallback_keys


def _handicap_fallback_bucket_keys(bucket_key: str) -> list[str]:
    if bucket_key == "hcp_-2.75_deeper":
        return ["hcp_-1.75_-2.50"]
    if bucket_key == "hcp_-1.75_-2.50":
        return ["hcp_-1.00_-1.50", "hcp_-2.75_deeper"]
    if bucket_key == "hcp_-1.00_-1.50":
        return ["hcp_-0.25_-0.75", "hcp_-1.75_-2.50"]
    if bucket_key == "hcp_-0.25_-0.75":
        return ["hcp_-1.00_-1.50"]
    return ["hcp_-0.25_-0.75", "hcp_-1.00_-1.50"]


def _totals_fallback_bucket_keys(bucket_key: str) -> list[str]:
    if bucket_key == "totals_3.0_3.5_plus":
        return ["totals_3.0", "totals_2.5_3.0"]
    if bucket_key == "totals_3.0":
        return ["totals_2.5_3.0", "totals_3.0_3.5_plus"]
    if bucket_key == "totals_2.5_3.0":
        return ["totals_2.5", "totals_3.0", "totals_2.0_2.5"]
    if bucket_key == "totals_2.5":
        return ["totals_2.0_2.5", "totals_2.5_3.0"]
    if bucket_key == "totals_2.0_2.5":
        return ["totals_2.5", "totals_2.5_3.0"]
    return ["totals_2.0_2.5", "totals_2.5", "totals_2.5_3.0"]


def calibrate_one_x_two_market(
    *,
    home_probability: float,
    draw_probability: float,
    away_probability: float,
    profiles: dict | None = None,
    minimum_sample_count: int = 30,
) -> dict[str, object]:
    calibrated = _normalize_probabilities(
        {
            "home": home_probability,
            "draw": draw_probability,
            "away": away_probability,
        }
    )
    profile = None
    bucket_key = build_probability_band_key(max(calibrated.values()))
    if profiles is not None:
        profile = choose_profile_with_fallback(
            profiles,
            market_family="1x2",
            exact_bucket_key=bucket_key,
            fallback_bucket_keys=_one_x_two_fallback_bucket_keys(bucket_key),
            minimum_sample_count=minimum_sample_count,
        )

    source = "fallback"
    if profile is not None:
        source = "profile"
        strongest_outcome_key = max(calibrated, key=calibrated.get)
        strongest_outcome_probability = calibrated[strongest_outcome_key]
        target_hit_rate = float(profile.get("calibrated_hit_rate", strongest_outcome_probability))
        calibrated_strongest_probability = min(
            max((strongest_outcome_probability + target_hit_rate) / 2.0, 0.01),
            0.95,
        )
        remaining_probability = 1.0 - calibrated_strongest_probability
        raw_remaining_probability = 1.0 - strongest_outcome_probability
        recalibrated: dict[str, float] = {}
        for outcome_key, probability in calibrated.items():
            if outcome_key == strongest_outcome_key:
                recalibrated[outcome_key] = calibrated_strongest_probability
                continue
            if raw_remaining_probability <= 0:
                recalibrated[outcome_key] = remaining_probability / 2.0
            else:
                recalibrated[outcome_key] = remaining_probability * (probability / raw_remaining_probability)
        calibrated = _normalize_probabilities(recalibrated)

    return {
        "calibrated_home_win_probability": round(calibrated["home"], 6),
        "calibrated_draw_probability": round(calibrated["draw"], 6),
        "calibrated_away_win_probability": round(calibrated["away"], 6),
        "summary": {
            "market_family": "1x2",
            "bucket_key": bucket_key,
            "selected_bucket_key": bucket_key if profile is None else profile.get("bucket_key", bucket_key),
            "source": source,
            "fallback_level": None if profile is None else profile.get("fallback_level"),
            "sample_count": None if profile is None else profile.get("sample_count"),
            "profile_version": None if profile is None else profile.get("profile_version"),
        },
    }


def calibrate_handicap_market(
    *,
    score_matrix: dict[tuple[int, int], float],
    market_line: float,
    profiles: dict | None = None,
    minimum_sample_count: int = 30,
) -> dict[str, object]:
    cover = 0.0
    push = 0.0
    fail = 0.0
    for (home_goals, away_goals), probability in score_matrix.items():
        settled = settle_handicap_line(home_goals=home_goals, away_goals=away_goals, line=market_line)
        cover += probability * settled["cover"]
        push += probability * settled["push"]
        fail += probability * settled["fail"]

    calibrated = _normalize_probabilities(
        {
            "cover": cover,
            "push": push,
            "fail": fail,
        }
    )
    profile = None
    bucket_key = build_handicap_bucket_key(market_line)
    if profiles is not None:
        profile = choose_profile_with_fallback(
            profiles,
            market_family="handicap",
            exact_bucket_key=bucket_key,
            fallback_bucket_keys=_handicap_fallback_bucket_keys(bucket_key),
            minimum_sample_count=minimum_sample_count,
        )

    source = "fallback"
    if profile is not None:
        source = "profile"
        calibrated = _normalize_probabilities(
            {
                "cover": float(profile.get("cover_probability", calibrated["cover"])),
                "push": float(profile.get("push_probability", calibrated["push"])),
                "fail": float(profile.get("fail_probability", calibrated["fail"])),
            }
        )

    return {
        "handicap_cover_probability": round(calibrated["cover"], 6),
        "handicap_push_probability": round(calibrated["push"], 6),
        "handicap_fail_probability": round(calibrated["fail"], 6),
        "summary": {
            "market_family": "handicap",
            "bucket_key": bucket_key,
            "selected_bucket_key": bucket_key if profile is None else profile.get("bucket_key", bucket_key),
            "market_line": market_line,
            "source": source,
            "fallback_level": None if profile is None else profile.get("fallback_level"),
            "sample_count": None if profile is None else profile.get("sample_count"),
            "profile_version": None if profile is None else profile.get("profile_version"),
        },
    }


def calibrate_totals_market(
    *,
    score_matrix: dict[tuple[int, int], float],
    market_line: float,
    line_source: str = "market_total_line",
    profiles: dict | None = None,
    minimum_sample_count: int = 30,
) -> dict[str, object]:
    over = 0.0
    push = 0.0
    under = 0.0
    for (home_goals, away_goals), probability in score_matrix.items():
        settled = settle_total_line(total_goals=home_goals + away_goals, line=market_line)
        over += probability * settled["over"]
        push += probability * settled["push"]
        under += probability * settled["under"]

    calibrated = _normalize_probabilities(
        {
            "over": over,
            "push": push,
            "under": under,
        }
    )
    profile = None
    bucket_key = build_totals_bucket_key(market_line)
    if profiles is not None:
        profile = choose_profile_with_fallback(
            profiles,
            market_family="totals",
            exact_bucket_key=bucket_key,
            fallback_bucket_keys=_totals_fallback_bucket_keys(bucket_key),
            minimum_sample_count=minimum_sample_count,
        )

    source = "fallback"
    if profile is not None:
        source = "profile"
        calibrated = _normalize_probabilities(
            {
                "over": float(profile.get("over_probability", calibrated["over"])),
                "push": float(profile.get("push_probability", calibrated["push"])),
                "under": float(profile.get("under_probability", calibrated["under"])),
            }
        )

    return {
        "totals_over_probability": round(calibrated["over"], 6),
        "totals_push_probability": round(calibrated["push"], 6),
        "totals_under_probability": round(calibrated["under"], 6),
        "recommended_totals_side": "over" if calibrated["over"] >= calibrated["under"] else "under",
        "summary": {
            "market_family": "totals",
            "bucket_key": bucket_key,
            "selected_bucket_key": bucket_key if profile is None else profile.get("bucket_key", bucket_key),
            "market_line": market_line,
            "line_source": line_source,
            "source": source,
            "fallback_level": None if profile is None else profile.get("fallback_level"),
            "sample_count": None if profile is None else profile.get("sample_count"),
            "profile_version": None if profile is None else profile.get("profile_version"),
        },
    }


def split_rows_by_time(rows: list[dict], split_at: datetime) -> tuple[list[dict], list[dict]]:
    fit_rows = [row for row in rows if row["captured_at"] < split_at]
    validation_rows = [row for row in rows if row["captured_at"] >= split_at]
    return fit_rows, validation_rows


def compute_brier_score(*, rows: list[dict[str, float]]) -> float:
    if not rows:
        return 0.0
    return round(
        sum((row["predicted_probability"] - row["actual_outcome"]) ** 2 for row in rows) / len(rows),
        6,
    )


def compute_log_loss(*, rows: list[dict[str, float]]) -> float:
    if not rows:
        return 0.0
    epsilon = 1e-9
    total = 0.0
    for row in rows:
        probability = min(max(row["predicted_probability"], epsilon), 1.0 - epsilon)
        outcome = row["actual_outcome"]
        total += -(outcome * math.log(probability) + (1.0 - outcome) * math.log(1.0 - probability))
    return round(total / len(rows), 6)


def compute_reliability_gap(*, rows: list[dict[str, float]], bucket_size: float = 0.1) -> float:
    if not rows:
        return 0.0
    if bucket_size <= 0:
        raise ValueError("bucket_size must be positive")

    grouped: dict[tuple[float, float], list[dict[str, float]]] = {}
    for row in rows:
        bucket_index = int((row["predicted_probability"] + 1e-12) / bucket_size)
        lower = bucket_index * bucket_size
        lower = min(max(lower, 0.0), 1.0)
        upper = min(lower + bucket_size, 1.0)
        grouped.setdefault((lower, upper), []).append(row)

    gap = 0.0
    for bucket_rows in grouped.values():
        average_probability = sum(row["predicted_probability"] for row in bucket_rows) / len(bucket_rows)
        average_outcome = sum(row["actual_outcome"] for row in bucket_rows) / len(bucket_rows)
        gap += abs(average_probability - average_outcome) * (len(bucket_rows) / len(rows))
    return round(gap, 6)
