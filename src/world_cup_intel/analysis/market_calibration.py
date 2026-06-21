from __future__ import annotations


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
