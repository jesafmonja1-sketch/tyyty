from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import math
import random

from sqlalchemy import desc, select

from world_cup_intel.schema import (
    Match,
    MatchContextSnapshot,
    MatchFeatureSnapshot,
    MatchWeatherSnapshot,
    MatchPrediction,
    MatchTeamStat,
    NationalTeam,
    OddsMarket,
    OddsQuote,
    PredictionFactor,
    PredictionRun,
    TeamEnvironmentProfile,
    TeamLearningSnapshot,
    TeamPowerSnapshot,
    Venue,
)


@dataclass
class PredictionDiagnostic:
    match_id: int
    home_team: str
    away_team: str
    summary_conclusion: str
    recommended_handicap_side: str
    market_handicap_line: float | None
    fair_handicap_line: float
    expected_home_goals: float
    expected_away_goals: float
    over_2_5_probability: float
    under_2_5_probability: float
    fair_total_line: float
    market_probability_summary: str
    value_edge_summary: str
    totals_tendency: str
    likely_scorelines: str
    factor_lines: list[str]
    issue_hints: list[str]
    toto_recommendation_lines: list[str]


@dataclass
class TotoRecommendation:
    primary_pick: str
    handicap_pick: str
    totals_pick: str
    score_pick: str
    risk_level: str
    reason: str
    suitability_label: str
    suitability_reason: str
    handicap_suitability_label: str
    handicap_suitability_reason: str
    totals_suitability_label: str
    totals_suitability_reason: str


@dataclass
class MotivationAdjustment:
    delta: float
    draw_anchor_delta: float
    goal_pressure: float
    explanation: str


SIMULATION_TRIALS = 50000
MIN_EXPECTED_GOALS = 0.25
MAX_EXPECTED_GOALS = 3.25
FAIR_TOTAL_LINE_CANDIDATES = tuple(round(1.5 + 0.25 * index, 2) for index in range(13))
FAIR_HANDICAP_LINE_CANDIDATES = tuple(round(-2.5 + 0.25 * index, 2) for index in range(21))


def _latest_team_power(session, team_id: int) -> TeamPowerSnapshot:
    snapshot = session.scalars(
        select(TeamPowerSnapshot)
        .where(TeamPowerSnapshot.national_team_id == team_id)
        .order_by(desc(TeamPowerSnapshot.captured_at))
    ).first()
    if snapshot is None:
        raise ValueError(f"Missing team power snapshot for team_id={team_id}")
    return snapshot


def _latest_market_handicap(session, match_id: int) -> float | None:
    quote = session.scalars(
        select(OddsQuote)
        .join(OddsMarket, OddsMarket.id == OddsQuote.odds_market_id)
        .where(OddsMarket.match_id == match_id, OddsMarket.market_type == "handicap")
        .order_by(desc(OddsQuote.captured_at))
    ).first()
    return None if quote is None else quote.line_value


def _latest_market_1x2(session, match_id: int) -> OddsQuote | None:
    return session.scalars(
        select(OddsQuote)
        .join(OddsMarket, OddsMarket.id == OddsQuote.odds_market_id)
        .where(OddsMarket.match_id == match_id, OddsMarket.market_type == "1x2")
        .order_by(desc(OddsQuote.captured_at))
    ).first()


def _market_implied_probabilities(quote: OddsQuote | None) -> tuple[float, float, float] | None:
    if (
        quote is None
        or quote.home_price is None
        or quote.draw_price is None
        or quote.away_price is None
        or quote.home_price <= 0
        or quote.draw_price <= 0
        or quote.away_price <= 0
    ):
        return None

    raw_home = 1.0 / quote.home_price
    raw_draw = 1.0 / quote.draw_price
    raw_away = 1.0 / quote.away_price
    raw_total = raw_home + raw_draw + raw_away
    return (
        round(raw_home / raw_total, 6),
        round(raw_draw / raw_total, 6),
        round(raw_away / raw_total, 6),
    )


def _latest_learning_snapshot(session, team_id: int) -> TeamLearningSnapshot | None:
    return session.scalars(
        select(TeamLearningSnapshot)
        .where(TeamLearningSnapshot.national_team_id == team_id)
        .order_by(desc(TeamLearningSnapshot.captured_at))
    ).first()


def _latest_environment_profile(session, team_id: int) -> TeamEnvironmentProfile | None:
    return session.scalars(
        select(TeamEnvironmentProfile)
        .where(TeamEnvironmentProfile.national_team_id == team_id)
        .order_by(desc(TeamEnvironmentProfile.captured_at))
    ).first()


def _latest_weather_snapshot(session, match_id: int) -> MatchWeatherSnapshot | None:
    return session.scalars(
        select(MatchWeatherSnapshot)
        .where(MatchWeatherSnapshot.match_id == match_id)
        .order_by(desc(MatchWeatherSnapshot.captured_at))
    ).first()


def _latest_match_context(session, match_id: int) -> MatchContextSnapshot | None:
    return session.scalars(
        select(MatchContextSnapshot)
        .where(MatchContextSnapshot.match_id == match_id)
        .order_by(desc(MatchContextSnapshot.captured_at))
    ).first()


def _discipline_risk(session, team_id: int, before_time: datetime) -> float:
    rows = session.scalars(
        select(MatchTeamStat)
        .join(Match, Match.id == MatchTeamStat.match_id)
        .where(
            MatchTeamStat.national_team_id == team_id,
            Match.status == "finished",
            Match.kickoff_at < before_time,
        )
        .order_by(desc(Match.kickoff_at))
        .limit(3)
    ).all()
    if not rows:
        return 0.0

    risk = 0.0
    for row in rows:
        yellow_cards = float(row.yellow_cards or 0)
        red_cards = float(row.red_cards or 0)
        risk += yellow_cards * 0.25 + red_cards * 2.0
        if yellow_cards >= 5:
            risk += 0.75
    return round(risk / len(rows), 2)


def _learning_value(snapshot: TeamLearningSnapshot | None) -> float:
    if snapshot is None:
        return 0.0
    return (
        (snapshot.readiness_score - 70.0) * 0.18
        + (snapshot.momentum_score - 50.0) * 0.14
        + (snapshot.tactical_continuity_score - 65.0) * 0.08
        - snapshot.availability_alert_count * 2.5
    )


def _normalized_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _need_state_score(value: object | None) -> float:
    text = _normalized_text(value)
    if not text:
        return 0.0
    if _contains_any(text, ("must win", "need win", "must attack", "need three points")):
        return 1.8
    if _contains_any(text, ("win helps qualification", "need edge", "need result", "should win")):
        return 1.0
    if _contains_any(text, ("draw acceptable", "avoid defeat", "protect point", "point good enough")):
        return -1.2
    return 0.0


def _goal_difference_pressure(value: object | None) -> float:
    text = _normalized_text(value)
    if not text:
        return 0.0
    if _contains_any(text, ("multiple goals", "by 2", "big win", "goal difference")):
        return 1.0
    return 0.5


def _knockout_path_score(value: object | None) -> float:
    text = _normalized_text(value)
    if not text:
        return 0.0
    if _contains_any(text, ("second acceptable", "harder next opponent", "avoid winning group")):
        return -0.6
    if _contains_any(text, ("win group", "attack early", "top spot")):
        return 0.4
    return 0.0


def _risk_score(value: object | None) -> float:
    if isinstance(value, (int, float)):
        return min(max(float(value), 0.0), 2.0)
    text = _normalized_text(value)
    if not text:
        return 0.0
    if "high" in text or "several starters" in text:
        return 1.0
    if "medium" in text or "some risk" in text:
        return 0.5
    return 0.25


def _rotation_tolerance_score(value: object | None) -> float:
    if isinstance(value, (int, float)):
        return min(max(float(value), 0.0), 2.0)
    text = _normalized_text(value)
    if not text:
        return 0.0
    if _contains_any(text, ("high", "can rotate", "can rest starters")):
        return 1.0
    if _contains_any(text, ("some rotation", "moderate")):
        return 0.5
    return 0.0


def _motivation_adjustment(match_row: Match, context: MatchContextSnapshot | None) -> MotivationAdjustment:
    if match_row.stage != "Group Stage" or context is None:
        return MotivationAdjustment(0.0, 0.0, 0.0, "no structured motivation adjustment")

    motivation = context.motivation or {}
    if not motivation:
        return MotivationAdjustment(0.0, 0.0, 0.0, "no structured motivation adjustment")

    matchday = int(motivation.get("group_matchday") or 1)
    matchday_scale = {1: 0.35, 2: 0.75, 3: 1.0}.get(matchday, 1.0)

    reasons: list[str] = [f"group matchday {matchday}"]
    delta = 0.0
    draw_anchor_delta = 0.0
    goal_pressure = 0.0

    home_need_score = _need_state_score(motivation.get("home_need"))
    away_need_score = _need_state_score(motivation.get("away_need"))
    if home_need_score or away_need_score:
        need_delta = (home_need_score - away_need_score) * matchday_scale
        delta += need_delta
        reasons.append(
            f"need-state home {home_need_score:+.1f} vs away {away_need_score:+.1f}"
        )

    draw_value_text = _normalized_text(motivation.get("draw_value"))
    if draw_value_text:
        if "high" in draw_value_text and "both" in draw_value_text:
            draw_anchor_delta += 0.04 * matchday_scale
            reasons.append("high draw value for both teams")
        elif "high" in draw_value_text:
            draw_anchor_delta += 0.025 * matchday_scale
            reasons.append("high draw value")
        elif "medium" in draw_value_text:
            draw_anchor_delta += 0.012 * matchday_scale
            reasons.append("medium draw value")

    home_goal_pressure = _goal_difference_pressure(motivation.get("home_goal_difference_pressure"))
    away_goal_pressure = _goal_difference_pressure(motivation.get("away_goal_difference_pressure"))
    if home_goal_pressure or away_goal_pressure:
        pressure_delta = (home_goal_pressure - away_goal_pressure) * 0.7 * matchday_scale
        delta += pressure_delta
        goal_pressure += (home_goal_pressure + away_goal_pressure) * matchday_scale
        reasons.append(
            f"goal-difference pressure home {home_goal_pressure:.1f} vs away {away_goal_pressure:.1f}"
        )

    home_path_score = _knockout_path_score(motivation.get("home_knockout_path_preference"))
    away_path_score = _knockout_path_score(motivation.get("away_knockout_path_preference"))
    if home_path_score or away_path_score:
        path_delta = (home_path_score - away_path_score) * 0.6 * matchday_scale
        delta += path_delta
        reasons.append(f"path incentive home {home_path_score:+.1f} vs away {away_path_score:+.1f}")

    home_suspension_risk = _risk_score(motivation.get("home_suspension_risk"))
    away_suspension_risk = _risk_score(motivation.get("away_suspension_risk"))
    if home_suspension_risk or away_suspension_risk:
        discipline_caution_delta = (away_suspension_risk - home_suspension_risk) * 0.45 * matchday_scale
        delta += discipline_caution_delta
        reasons.append(
            f"suspension caution home {home_suspension_risk:.1f} vs away {away_suspension_risk:.1f}"
        )

    home_rotation_tolerance = _rotation_tolerance_score(motivation.get("home_rotation_tolerance"))
    away_rotation_tolerance = _rotation_tolerance_score(motivation.get("away_rotation_tolerance"))
    if home_rotation_tolerance or away_rotation_tolerance:
        rotation_delta = (away_rotation_tolerance - home_rotation_tolerance) * 0.35 * matchday_scale
        delta += rotation_delta
        reasons.append(
            f"rotation tolerance home {home_rotation_tolerance:.1f} vs away {away_rotation_tolerance:.1f}"
        )

    delta = max(-3.5, min(3.5, round(delta, 2)))
    draw_anchor_delta = max(-0.02, min(0.04, round(draw_anchor_delta, 3)))
    goal_pressure = round(goal_pressure, 2)
    explanation = ", ".join(reasons) if reasons else "no structured motivation adjustment"
    return MotivationAdjustment(delta, draw_anchor_delta, goal_pressure, explanation)


def build_toto_recommendation(
    *,
    home_team: str,
    away_team: str,
    home_win_probability: float,
    draw_probability: float,
    away_win_probability: float,
    fair_handicap_line: float,
    market_handicap_line: float | None,
    recommended_handicap_side: str,
    totals_tendency: str,
    likely_scorelines: str,
    over_2_5_probability: float,
    under_2_5_probability: float,
    fair_total_line: float,
) -> TotoRecommendation:
    outcome_probabilities = {
        "主胜": home_win_probability,
        "平": draw_probability,
        "客胜": away_win_probability,
    }
    primary_pick = max(outcome_probabilities, key=outcome_probabilities.get)
    primary_edge = outcome_probabilities[primary_pick] - sorted(outcome_probabilities.values())[-2]
    handicap_gap = 0.0 if market_handicap_line is None else abs(market_handicap_line - fair_handicap_line)

    if primary_edge < 0.08 and handicap_gap < 0.25:
        totals_edge = abs(over_2_5_probability - under_2_5_probability)
        return TotoRecommendation(
            primary_pick="不建议下",
            handicap_pick="不建议下",
            totals_pick="不建议下",
            score_pick=likely_scorelines.split(",")[0],
            risk_level="高",
            reason=(
                f"{home_team} vs {away_team} 这场模型胜率差距不够大，且盘口与模型基本一致，"
                "当前没有明显价值空间，优势不足。"
            ),
            suitability_label="不建议下",
            suitability_reason="模型优势不足，盘口也没有给出明显价值空间，当前更适合放过。",
            handicap_suitability_label="不建议碰",
            handicap_suitability_reason="让球盘口和模型太接近，当前没有明显让球价值。",
            totals_suitability_label="不建议碰" if totals_edge < 0.1 else "谨慎碰",
            totals_suitability_reason=(
                "总进球方向不够清楚，大小球优势不足。"
                if totals_edge < 0.1
                else "总进球方向有轻微倾向，但边际还不够大，适合保守处理。"
            ),
        )

    handicap_pick = "让胜" if recommended_handicap_side == "home" else "让负"
    totals_pick = "总进球偏大" if totals_tendency.startswith("over") else "总进球偏小"
    score_pick = likely_scorelines.split(",")[0]
    risk_level = "低" if primary_edge >= 0.16 or handicap_gap >= 0.5 else "中"
    totals_edge = abs(over_2_5_probability - under_2_5_probability)
    market_is_deeper_than_model = (
        market_handicap_line is not None
        and recommended_handicap_side == "away"
        and handicap_gap >= 0.25
    )
    if primary_edge >= 0.16 and not market_is_deeper_than_model:
        suitability_label = "适合下"
        suitability_reason = "模型优势明确，盘口没有把风险抬得过深，方向和空间都比较清楚。"
    else:
        suitability_label = "谨慎下"
        if market_is_deeper_than_model:
            suitability_reason = "模型方向还在，但盘口已经比模型更深，深盘和卡盘风险更高，适合保守处理。"
        else:
            suitability_reason = "方向还在，但深盘、卡盘或比赛摇摆风险仍在，适合保守处理。"

    if market_handicap_line is None:
        handicap_suitability_label = "谨慎碰"
        handicap_suitability_reason = "当前缺少完整让球盘口，只能结合模型方向轻度参考。"
    elif handicap_gap >= 0.5 or market_is_deeper_than_model:
        handicap_suitability_label = "适合碰"
        handicap_suitability_reason = "盘口和模型偏差明显，让球一侧有相对清楚的价值空间。"
    elif handicap_gap >= 0.25:
        handicap_suitability_label = "谨慎碰"
        handicap_suitability_reason = "让球方向有一定空间，但深盘和卡盘风险仍在。"
    else:
        handicap_suitability_label = "不建议碰"
        handicap_suitability_reason = "让球盘口和模型接近，当前没有足够让球优势。"

    if totals_edge >= 0.18 or abs(fair_total_line - 2.5) >= 0.5:
        totals_suitability_label = "适合碰"
        totals_suitability_reason = "总进球方向清楚，模型对大小球倾向给出了足够边际。"
    elif totals_edge >= 0.1 or abs(fair_total_line - 2.5) >= 0.25:
        totals_suitability_label = "谨慎碰"
        totals_suitability_reason = "大小球有倾向，但总进球波动仍不小，适合控制风险。"
    else:
        totals_suitability_label = "不建议碰"
        totals_suitability_reason = "总进球方向不够清楚，大小球优势不足。"

    if market_handicap_line is None:
        reason = (
            f"当前缺少明确让球市场线，模型更偏向 {primary_pick}，"
            f"比分倾向先看 {score_pick}，总进球更偏 {totals_pick}。"
        )
    elif handicap_gap >= 0.25:
        deeper_side = home_team if market_handicap_line < fair_handicap_line else away_team
        reason = (
            f"盘口比模型更深，市场当前更压 {deeper_side} 一侧，"
            f"模型建议改走 {handicap_pick}，同时常规赛果更偏 {primary_pick}。"
        )
    else:
        reason = (
            f"模型常规赛果更偏 {primary_pick}，让球方向同步偏 {handicap_pick}，"
            f"大小球倾向为 {totals_pick}，比分先看 {score_pick}。"
        )

    return TotoRecommendation(
        primary_pick=primary_pick,
        handicap_pick=handicap_pick,
        totals_pick=totals_pick,
        score_pick=score_pick,
        risk_level=risk_level,
        reason=reason,
        suitability_label=suitability_label,
        suitability_reason=suitability_reason,
        handicap_suitability_label=handicap_suitability_label,
        handicap_suitability_reason=handicap_suitability_reason,
        totals_suitability_label=totals_suitability_label,
        totals_suitability_reason=totals_suitability_reason,
    )


def _environment_delta(
    match_row: Match,
    venue: Venue | None,
    weather: MatchWeatherSnapshot | None,
    home_profile: TeamEnvironmentProfile | None,
    away_profile: TeamEnvironmentProfile | None,
) -> tuple[float, str]:
    if venue is None and weather is None:
        return 0.0, "no venue or weather adjustments available"

    home_score = 0.0
    away_score = 0.0
    reasons: list[str] = []

    if venue is not None and venue.altitude_meters and venue.altitude_meters >= 1500:
        home_alt = 65.0 if home_profile is None else home_profile.altitude_adaptation_score
        away_alt = 65.0 if away_profile is None else away_profile.altitude_adaptation_score
        altitude_delta = (home_alt - away_alt) / 12.0
        home_score += altitude_delta
        away_score -= altitude_delta
        reasons.append("high altitude")
    if weather is not None and weather.apparent_temperature_c and weather.apparent_temperature_c >= 30.0:
        home_heat = 65.0 if home_profile is None else home_profile.heat_adaptation_score
        away_heat = 65.0 if away_profile is None else away_profile.heat_adaptation_score
        heat_delta = (home_heat - away_heat) / 18.0
        home_score += heat_delta
        away_score -= heat_delta
        reasons.append("hot conditions")
    if weather is not None and weather.humidity_pct and weather.humidity_pct >= 60.0:
        home_humidity = 65.0 if home_profile is None else home_profile.humidity_adaptation_score
        away_humidity = 65.0 if away_profile is None else away_profile.humidity_adaptation_score
        humidity_delta = (home_humidity - away_humidity) / 20.0
        home_score += humidity_delta
        away_score -= humidity_delta
        reasons.append("humid air")
    if weather is not None and weather.wind_speed_kph and weather.wind_speed_kph >= 20.0:
        reasons.append("wind may lower finishing quality")

    if not match_row.is_neutral_site:
        home_recovery = 65.0 if home_profile is None else home_profile.travel_recovery_score
        away_recovery = 65.0 if away_profile is None else away_profile.travel_recovery_score
        travel_delta = (home_recovery - away_recovery) / 25.0
        home_score += travel_delta
        away_score -= travel_delta
        reasons.append("home travel familiarity")

    delta = round(home_score - away_score, 2)
    return delta, ", ".join(reasons) if reasons else "environment profiles roughly balanced"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _factor_value(factor_map: dict[str, PredictionFactor], factor_name: str) -> float | None:
    factor = factor_map.get(factor_name)
    return None if factor is None else factor.factor_value


def _probability_summary(
    factor_map: dict[str, PredictionFactor],
    *,
    home_label: str = "主胜",
    draw_label: str = "平",
    away_label: str = "客胜",
) -> str:
    home = _factor_value(factor_map, "market_home_probability")
    draw = _factor_value(factor_map, "market_draw_probability")
    away = _factor_value(factor_map, "market_away_probability")
    if home is None or draw is None or away is None:
        return "市场概率: 暂无 1X2 赔率去水数据"
    return f"市场概率: {home_label} {home:.2%} / {draw_label} {draw:.2%} / {away_label} {away:.2%}"


def _value_edge_summary(factor_map: dict[str, PredictionFactor]) -> str:
    home = _factor_value(factor_map, "value_edge_home")
    draw = _factor_value(factor_map, "value_edge_draw")
    away = _factor_value(factor_map, "value_edge_away")
    if home is None or draw is None or away is None:
        return "价值差: 暂无模型和市场概率差异"
    return f"价值差: 主胜 {home:+.2%} / 平 {draw:+.2%} / 客胜 {away:+.2%}"


def _poisson_sample(rng: random.Random, lambda_value: float) -> int:
    threshold = math.exp(-lambda_value)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return count - 1


def _poisson_probability(goals: int, lambda_value: float) -> float:
    if lambda_value < 0:
        raise ValueError("Poisson lambda must be non-negative.")
    return math.exp(-lambda_value) * (lambda_value**goals) / math.factorial(goals)


def _dixon_coles_tau(
    home_goals: int,
    away_goals: int,
    *,
    lambda_home: float,
    lambda_away: float,
    dixon_coles_rho: float,
) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - (lambda_home * lambda_away * dixon_coles_rho)
    if home_goals == 0 and away_goals == 1:
        return 1.0 + (lambda_home * dixon_coles_rho)
    if home_goals == 1 and away_goals == 0:
        return 1.0 + (lambda_away * dixon_coles_rho)
    if home_goals == 1 and away_goals == 1:
        return 1.0 - dixon_coles_rho
    return 1.0


def _build_score_probability_matrix(
    lambda_home: float,
    lambda_away: float,
    *,
    max_goals: int = 8,
    dixon_coles_rho: float = -0.08,
) -> dict[tuple[int, int], float]:
    if max_goals < 0:
        raise ValueError("max_goals must be non-negative.")

    # This is a truncated score matrix over 0..max_goals for each side, then renormalized.
    matrix: dict[tuple[int, int], float] = {}
    total_probability = 0.0

    for home_goals in range(max_goals + 1):
        home_probability = _poisson_probability(home_goals, lambda_home)
        for away_goals in range(max_goals + 1):
            away_probability = _poisson_probability(away_goals, lambda_away)
            probability = home_probability * away_probability
            probability *= _dixon_coles_tau(
                home_goals,
                away_goals,
                lambda_home=lambda_home,
                lambda_away=lambda_away,
                dixon_coles_rho=dixon_coles_rho,
            )
            if probability < 0:
                raise ValueError("Dixon-Coles adjustment produced a negative probability.")
            scoreline = (home_goals, away_goals)
            matrix[scoreline] = probability
            total_probability += probability

    if total_probability <= 0:
        raise ValueError("Corrected score matrix must have positive total probability.")

    return {
        scoreline: probability / total_probability
        for scoreline, probability in matrix.items()
    }


def _goal_adjustment_from_weather(weather: MatchWeatherSnapshot | None) -> float:
    if weather is None:
        return 0.0

    adjustment = 0.0
    if weather.wind_speed_kph and weather.wind_speed_kph >= 20.0:
        adjustment -= 0.16
    if weather.apparent_temperature_c and weather.apparent_temperature_c >= 30.0:
        adjustment -= 0.05
    if weather.precipitation_mm and weather.precipitation_mm >= 4.0:
        adjustment -= 0.08
    return adjustment


def _expected_goals(
    *,
    home: TeamPowerSnapshot,
    away: TeamPowerSnapshot,
    adjusted_gap: float,
    learning_delta: float,
    environment_delta: float,
    discipline_delta: float,
    motivation_adjustment: MotivationAdjustment,
    weather: MatchWeatherSnapshot | None,
) -> tuple[float, float]:
    base_home = 1.15 + (home.attack_score - away.defense_score) / 30.0
    base_away = 1.15 + (away.attack_score - home.defense_score) / 30.0

    home_expected = base_home
    away_expected = base_away

    home_expected += adjusted_gap / 65.0
    away_expected -= adjusted_gap / 65.0

    home_expected += learning_delta / 40.0
    away_expected -= learning_delta / 40.0

    home_expected += environment_delta / 60.0
    away_expected -= environment_delta / 60.0

    home_expected += discipline_delta / 55.0
    away_expected -= discipline_delta / 55.0

    pressure_boost = motivation_adjustment.goal_pressure * 0.25
    home_expected += pressure_boost
    away_expected += pressure_boost

    if motivation_adjustment.draw_anchor_delta > 0:
        home_expected -= motivation_adjustment.draw_anchor_delta * 1.4
        away_expected -= motivation_adjustment.draw_anchor_delta * 1.4

    weather_drag = _goal_adjustment_from_weather(weather)
    home_expected += weather_drag
    away_expected += weather_drag

    return (
        round(_clamp(home_expected, MIN_EXPECTED_GOALS, MAX_EXPECTED_GOALS), 3),
        round(_clamp(away_expected, MIN_EXPECTED_GOALS, MAX_EXPECTED_GOALS), 3),
    )


def _fair_total_line_from_distribution(total_counts: Counter[int], total_trials: int) -> float:
    best_line = FAIR_TOTAL_LINE_CANDIDATES[0]
    best_gap = float("inf")
    for line in FAIR_TOTAL_LINE_CANDIDATES:
        over_expectation = 0.0
        for goals, count in total_counts.items():
            if goals > line:
                over_expectation += count
            elif goals == line:
                over_expectation += 0.5 * count
            elif line % 1 == 0.25 and goals == math.floor(line):
                over_expectation += 0.5 * count
            elif line % 1 == 0.75 and goals == math.ceil(line):
                over_expectation += 0.0
        gap = abs((over_expectation / total_trials) - 0.5)
        if gap < best_gap - 1e-12:
            best_gap = gap
            best_line = line
    return round(best_line, 2)


def _distribution_from_score_matrix(
    lambda_home: float,
    lambda_away: float,
    *,
    max_goals: int = 8,
    dixon_coles_rho: float = -0.08,
) -> dict[str, object]:
    matrix = _build_score_probability_matrix(
        lambda_home,
        lambda_away,
        max_goals=max_goals,
        dixon_coles_rho=dixon_coles_rho,
    )

    home_wins = 0.0
    draws = 0.0
    away_wins = 0.0
    over_2_5 = 0.0
    total_counter: Counter[int] = Counter()
    goal_diff_counter: Counter[int] = Counter()

    for (home_goals, away_goals), probability in matrix.items():
        total_goals = home_goals + away_goals
        goal_diff = home_goals - away_goals
        total_counter[total_goals] += probability
        goal_diff_counter[goal_diff] += probability

        if home_goals > away_goals:
            home_wins += probability
        elif home_goals < away_goals:
            away_wins += probability
        else:
            draws += probability

        if total_goals >= 3:
            over_2_5 += probability

    likely_scores = [
        f"{home_goals}-{away_goals}"
        for (home_goals, away_goals), _ in sorted(
            matrix.items(),
            key=lambda item: (-item[1], item[0]),
        )[:4]
    ]

    return {
        "home_win_probability": round(home_wins, 6),
        "draw_probability": round(draws, 6),
        "away_win_probability": round(1.0 - round(home_wins, 6) - round(draws, 6), 6),
        "over_2_5_probability": over_2_5,
        "under_2_5_probability": 1.0 - over_2_5,
        "likely_scorelines": ",".join(likely_scores),
        "goal_diff_counter": goal_diff_counter,
        "fair_total_line": _fair_total_line_from_distribution(total_counter, 1),
        "fair_handicap_line": _fair_handicap_line_from_distribution(goal_diff_counter, 1),
    }


def _simulate_match_distribution(
    lambda_home: float,
    lambda_away: float,
    *,
    trials: int = SIMULATION_TRIALS,
) -> dict[str, object]:
    rng = random.Random(int(lambda_home * 1000) * 100_003 + int(lambda_away * 1000) * 10_007 + trials)

    home_wins = 0
    draws = 0
    away_wins = 0
    over_2_5 = 0
    score_counter: Counter[str] = Counter()
    total_counter: Counter[int] = Counter()
    goal_diff_counter: Counter[int] = Counter()

    for _ in range(trials):
        home_goals = _poisson_sample(rng, lambda_home)
        away_goals = _poisson_sample(rng, lambda_away)
        score_counter[f"{home_goals}-{away_goals}"] += 1
        total_goals = home_goals + away_goals
        total_counter[total_goals] += 1
        goal_diff_counter[home_goals - away_goals] += 1

        if home_goals > away_goals:
            home_wins += 1
        elif home_goals < away_goals:
            away_wins += 1
        else:
            draws += 1

        if total_goals >= 3:
            over_2_5 += 1

    home_win_probability = round(home_wins / trials, 6)
    draw_probability = round(draws / trials, 6)
    away_win_probability = round(away_wins / trials, 6)
    over_2_5_probability = round(over_2_5 / trials, 6)
    under_2_5_probability = round(1.0 - over_2_5_probability, 6)
    scoreline_ranking = sorted(score_counter.items(), key=lambda item: (-item[1], item[0]))
    likely_scores: list[str] = []
    if home_wins > away_wins:
        home_score = next(
            (score for score, _ in scoreline_ranking if int(score.split("-", 1)[0]) > int(score.split("-", 1)[1])),
            None,
        )
        if home_score is not None:
            likely_scores.append(home_score)
    elif away_wins > home_wins:
        away_score = next(
            (score for score, _ in scoreline_ranking if int(score.split("-", 1)[0]) < int(score.split("-", 1)[1])),
            None,
        )
        if away_score is not None:
            likely_scores.append(away_score)

    for score, _ in scoreline_ranking:
        if score not in likely_scores:
            likely_scores.append(score)
        if len(likely_scores) == 3:
            break
    likely_scorelines = ",".join(likely_scores)
    fair_total_line = _fair_total_line_from_distribution(total_counter, trials)

    return {
        "home_win_probability": home_win_probability,
        "draw_probability": draw_probability,
        "away_win_probability": away_win_probability,
        "over_2_5_probability": over_2_5_probability,
        "under_2_5_probability": under_2_5_probability,
        "likely_scorelines": likely_scorelines,
        "fair_total_line": fair_total_line,
        "goal_diff_counter": goal_diff_counter,
    }


def _fair_handicap_line_from_distribution(goal_diff_counter: Counter[int], total_trials: int) -> float:
    best_line = FAIR_HANDICAP_LINE_CANDIDATES[0]
    best_gap = float("inf")
    for line in FAIR_HANDICAP_LINE_CANDIDATES:
        cover_expectation = 0.0
        target = -line
        for goal_diff, count in goal_diff_counter.items():
            adjusted = goal_diff - target
            if adjusted > 0:
                cover_expectation += count
            elif adjusted == 0:
                cover_expectation += 0.5 * count
            elif line % 1 == -0.25 % 1 and adjusted == -0.25:
                cover_expectation += 0.5 * count
        gap = abs((cover_expectation / total_trials) - 0.5)
        if gap < best_gap - 1e-12:
            best_gap = gap
            best_line = line
    return round(best_line, 2)


def _build_match_feature_snapshot(
    *,
    run_id: int,
    match_row: Match,
    captured_at: datetime,
    model_version: str,
    home: TeamPowerSnapshot,
    away: TeamPowerSnapshot,
    home_learning: TeamLearningSnapshot | None,
    away_learning: TeamLearningSnapshot | None,
    learning_delta: float,
    environment_delta: float,
    discipline_delta: float,
    motivation_adjustment: MotivationAdjustment,
    market_handicap: float | None,
    market_probabilities: tuple[float, float, float] | None,
    expected_home_goals: float,
    expected_away_goals: float,
) -> MatchFeatureSnapshot:
    home_tactical_continuity = 0.0 if home_learning is None else home_learning.tactical_continuity_score
    away_tactical_continuity = 0.0 if away_learning is None else away_learning.tactical_continuity_score
    home_market_probability: float | None = None
    market_draw_probability: float | None = None
    away_market_probability: float | None = None
    if market_probabilities is not None:
        home_market_probability, market_draw_probability, away_market_probability = market_probabilities

    return MatchFeatureSnapshot(
        prediction_run_id=run_id,
        match_id=match_row.id,
        captured_at=captured_at,
        model_version=model_version,
        home_overall_score=home.overall_score,
        away_overall_score=away.overall_score,
        home_attack_score=home.attack_score,
        away_attack_score=away.attack_score,
        home_defense_score=home.defense_score,
        away_defense_score=away.defense_score,
        home_recent_form_score=home.recent_form_score,
        away_recent_form_score=away.recent_form_score,
        power_delta=round(home.overall_score - away.overall_score, 3),
        attack_delta=round(home.attack_score - away.attack_score, 3),
        defense_delta=round(home.defense_score - away.defense_score, 3),
        form_delta=round(home.recent_form_score - away.recent_form_score, 3),
        home_learning_readiness_score=0.0 if home_learning is None else home_learning.readiness_score,
        away_learning_readiness_score=0.0 if away_learning is None else away_learning.readiness_score,
        home_learning_momentum_score=0.0 if home_learning is None else home_learning.momentum_score,
        away_learning_momentum_score=0.0 if away_learning is None else away_learning.momentum_score,
        home_tactical_continuity_score=home_tactical_continuity,
        away_tactical_continuity_score=away_tactical_continuity,
        learning_delta=learning_delta,
        tactical_continuity_delta=round(home_tactical_continuity - away_tactical_continuity, 3),
        home_availability_alert_count=0 if home_learning is None else home_learning.availability_alert_count,
        away_availability_alert_count=0 if away_learning is None else away_learning.availability_alert_count,
        home_minutes_risk_score=0.0,
        away_minutes_risk_score=0.0,
        discipline_delta=discipline_delta,
        environment_delta=environment_delta,
        weather_delta=0.0,
        referee_delta=0.0,
        motivation_delta=motivation_adjustment.delta,
        fatigue_delta=0.0,
        scenario_pressure_delta=0.0,
        goal_difference_pressure_delta=motivation_adjustment.goal_pressure,
        market_handicap_line=market_handicap,
        market_total_line=None,
        market_home_probability=home_market_probability,
        market_draw_probability=market_draw_probability,
        market_away_probability=away_market_probability,
        market_over_price=None,
        market_under_price=None,
        lambda_home=expected_home_goals,
        lambda_away=expected_away_goals,
        projected_tempo_score=round(expected_home_goals + expected_away_goals, 3),
        learning_adjustment=learning_delta,
        feature_payload_json={
            "motivation_explanation": motivation_adjustment.explanation,
            "draw_anchor_delta": motivation_adjustment.draw_anchor_delta,
            "goal_pressure": motivation_adjustment.goal_pressure,
        },
    )


def generate_match_prediction(session, match_id: int, captured_at: datetime) -> MatchPrediction:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    home = _latest_team_power(session, match_row.home_team_id)
    away = _latest_team_power(session, match_row.away_team_id)
    rating_gap = home.overall_score - away.overall_score
    home_learning = _latest_learning_snapshot(session, match_row.home_team_id)
    away_learning = _latest_learning_snapshot(session, match_row.away_team_id)
    learning_delta = round(_learning_value(home_learning) - _learning_value(away_learning), 2)
    match_context = _latest_match_context(session, match_id)
    venue = session.get(Venue, match_row.venue_id) if match_row.venue_id is not None else None
    weather = _latest_weather_snapshot(session, match_id)
    home_environment = _latest_environment_profile(session, match_row.home_team_id)
    away_environment = _latest_environment_profile(session, match_row.away_team_id)
    environment_delta, environment_reason = _environment_delta(
        match_row,
        venue,
        weather,
        home_environment,
        away_environment,
    )
    home_discipline_risk = _discipline_risk(session, match_row.home_team_id, match_row.kickoff_at)
    away_discipline_risk = _discipline_risk(session, match_row.away_team_id, match_row.kickoff_at)
    discipline_delta = round(away_discipline_risk - home_discipline_risk, 2)
    motivation_adjustment = _motivation_adjustment(match_row, match_context)
    adjusted_gap = rating_gap + motivation_adjustment.delta
    market_handicap = _latest_market_handicap(session, match_id)
    market_probabilities = _market_implied_probabilities(_latest_market_1x2(session, match_id))

    expected_home_goals, expected_away_goals = _expected_goals(
        home=home,
        away=away,
        adjusted_gap=adjusted_gap,
        learning_delta=learning_delta,
        environment_delta=environment_delta,
        discipline_delta=discipline_delta,
        motivation_adjustment=motivation_adjustment,
        weather=weather,
    )
    distribution = _distribution_from_score_matrix(expected_home_goals, expected_away_goals)
    home_win = float(distribution["home_win_probability"])
    draw_probability = float(distribution["draw_probability"])
    away_win = float(distribution["away_win_probability"])
    likely_scorelines = str(distribution["likely_scorelines"])
    over_2_5_probability = float(distribution["over_2_5_probability"])
    under_2_5_probability = float(distribution["under_2_5_probability"])
    fair_total_line = float(distribution["fair_total_line"])
    fair_handicap = float(distribution["fair_handicap_line"])
    recommended_side = "home" if market_handicap is None or fair_handicap < market_handicap else "away"
    totals_tendency = "over 2.5" if over_2_5_probability >= under_2_5_probability else "under 2.5"
    confidence = "high" if abs(rating_gap) >= 6.0 else "medium"

    model_version = "v1-rules"
    run = PredictionRun(match_id=match_id, captured_at=captured_at, model_version=model_version)
    session.add(run)
    session.flush()
    session.add(
        _build_match_feature_snapshot(
            run_id=run.id,
            match_row=match_row,
            captured_at=captured_at,
            model_version=model_version,
            home=home,
            away=away,
            home_learning=home_learning,
            away_learning=away_learning,
            learning_delta=learning_delta,
            environment_delta=environment_delta,
            discipline_delta=discipline_delta,
            motivation_adjustment=motivation_adjustment,
            market_handicap=market_handicap,
            market_probabilities=market_probabilities,
            expected_home_goals=expected_home_goals,
            expected_away_goals=expected_away_goals,
        )
    )

    prediction = MatchPrediction(
        prediction_run_id=run.id,
        home_win_probability=round(home_win, 6),
        draw_probability=round(draw_probability, 6),
        away_win_probability=round(away_win, 6),
        expected_home_goals=expected_home_goals,
        expected_away_goals=expected_away_goals,
        over_2_5_probability=over_2_5_probability,
        under_2_5_probability=under_2_5_probability,
        fair_handicap_line=fair_handicap,
        fair_total_line=fair_total_line,
        market_handicap_line=market_handicap,
        recommended_handicap_side=recommended_side,
        totals_tendency=totals_tendency,
        likely_scorelines=likely_scorelines,
        confidence_level=confidence,
        summary_conclusion=(
            f"rating gap {rating_gap:.2f}, learning {learning_delta:+.2f}, "
            f"environment {environment_delta:+.2f}, discipline {discipline_delta:+.2f}, "
            f"motivation {motivation_adjustment.delta:+.2f}, "
            f"xg {expected_home_goals:.2f}-{expected_away_goals:.2f}, "
            f"recommend {recommended_side} side"
        ),
    )
    session.add(prediction)
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="rating_gap",
            factor_value=rating_gap,
            explanation="overall team power difference",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="market_handicap",
            factor_value=market_handicap or 0.0,
            explanation="latest available handicap line",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="learning_delta",
            factor_value=learning_delta,
            explanation="post-match learning adjustment from the latest team review snapshots",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="environment_delta",
            factor_value=environment_delta,
            explanation=f"environment impact from venue, weather, and adaptation: {environment_reason}",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="discipline_delta",
            factor_value=discipline_delta,
            explanation=(
                "card discipline adjustment from recent finished matches; "
                f"home risk {home_discipline_risk:.2f}, away risk {away_discipline_risk:.2f}"
            ),
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="motivation_delta",
            factor_value=motivation_adjustment.delta,
            explanation=(
                "group-stage motivation adjustment from structured context; "
                f"{motivation_adjustment.explanation}; draw anchor {motivation_adjustment.draw_anchor_delta:+.3f}"
            ),
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="lambda_home",
            factor_value=expected_home_goals,
            explanation="context-adjusted expected goals for the home side",
        )
    )
    session.add(
        PredictionFactor(
            prediction_run_id=run.id,
            factor_name="lambda_away",
            factor_value=expected_away_goals,
            explanation="context-adjusted expected goals for the away side",
        )
    )
    if market_probabilities is not None:
        market_home, market_draw, market_away = market_probabilities
        session.add_all(
            [
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="market_home_probability",
                    factor_value=market_home,
                    explanation="de-vigged 1X2 market probability for home win",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="market_draw_probability",
                    factor_value=market_draw,
                    explanation="de-vigged 1X2 market probability for draw",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="market_away_probability",
                    factor_value=market_away,
                    explanation="de-vigged 1X2 market probability for away win",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="value_edge_home",
                    factor_value=round(home_win - market_home, 6),
                    explanation="model home-win probability minus market home-win probability",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="value_edge_draw",
                    factor_value=round(draw_probability - market_draw, 6),
                    explanation="model draw probability minus market draw probability",
                ),
                PredictionFactor(
                    prediction_run_id=run.id,
                    factor_name="value_edge_away",
                    factor_value=round(away_win - market_away, 6),
                    explanation="model away-win probability minus market away-win probability",
                ),
            ]
        )
    return prediction


def diagnose_prediction(session, match_id: int) -> PredictionDiagnostic:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    home = session.get(NationalTeam, match_row.home_team_id)
    away = session.get(NationalTeam, match_row.away_team_id)
    if home is None or away is None:
        raise ValueError(f"Teams missing for match_id={match_id}")
    try:
        home_power = _latest_team_power(session, match_row.home_team_id)
    except ValueError:
        home_power = None
    try:
        away_power = _latest_team_power(session, match_row.away_team_id)
    except ValueError:
        away_power = None

    row = session.execute(
        select(MatchPrediction, PredictionRun)
        .join(PredictionRun, PredictionRun.id == MatchPrediction.prediction_run_id)
        .where(PredictionRun.match_id == match_id)
        .order_by(desc(PredictionRun.captured_at))
    ).first()
    if row is None:
        raise ValueError(f"Prediction not found for match_id={match_id}")

    prediction, run = row
    match_age_hours = (match_row.kickoff_at - run.captured_at).total_seconds() / 3600.0
    factors = session.scalars(
        select(PredictionFactor)
        .where(PredictionFactor.prediction_run_id == run.id)
        .order_by(PredictionFactor.factor_name)
    ).all()

    factor_map = {factor.factor_name: factor for factor in factors}
    factor_lines = [
        f"{factor.factor_name}: {factor.factor_value:+.2f} | {factor.explanation}"
        for factor in factors
    ]

    issue_hints: list[str] = []
    rating_gap = factor_map.get("rating_gap")
    learning_delta = factor_map.get("learning_delta")
    market_handicap = factor_map.get("market_handicap")
    discipline_delta = factor_map.get("discipline_delta")
    motivation_delta = factor_map.get("motivation_delta")
    if rating_gap is not None and abs(rating_gap.factor_value) < 2.0:
        issue_hints.append("实力快照差距较小，若结果看着怪，先复查基础实力评分是否过于接近。")
    if learning_delta is not None and abs(learning_delta.factor_value) >= 2.0:
        issue_hints.append("复盘学习修正较大，若方向异常，优先检查上一场复盘和学习快照是否偏重。")
        issue_hints.append("复盘扰动: 上一场伤停或战术变化对下一场判断的影响偏强。")
    if discipline_delta is not None and abs(discipline_delta.factor_value) >= 2.0:
        issue_hints.append("纪律风险: 近期黄牌或红牌风险已经明显影响下一场判断。")
    if motivation_delta is not None and abs(motivation_delta.factor_value) >= 0.75:
        issue_hints.append("小组出线动机: 当前预测已计入必须抢分、平局价值或出线压力。")
        if "draw value" in motivation_delta.explanation:
            issue_hints.append("平局价值: 这场小组赛平局收益较高，模型对平局概率做了上调。")
        if "path incentive" in motivation_delta.explanation:
            issue_hints.append("路径因素: 潜在淘汰赛对手强弱已轻度影响本场进取程度。")
    if market_handicap is not None and abs((prediction.market_handicap_line or 0.0) - prediction.fair_handicap_line) >= 0.5:
        issue_hints.append("盘口和模型差距较大，若判断有争议，优先检查盘口数据与让球规则。")
        issue_hints.append("盘口分歧: 市场让球与模型公平盘出现明显错位。")
    if match_age_hours >= 12.0:
        issue_hints.append("数据薄弱: 当前预测距离开球较久，需优先补最新伤病、首发和盘口。")
    if home_power is None or away_power is None:
        issue_hints.append("数据薄弱: 当前缺少完整球队实力快照，建议先补基础实力与状态数据。")
    elif (run.captured_at - home_power.captured_at).total_seconds() >= 72 * 3600 or (
        run.captured_at - away_power.captured_at
    ).total_seconds() >= 72 * 3600:
        issue_hints.append("数据薄弱: 当前球队实力快照较旧，建议补最新状态和可用性数据。")
    if len(factors) <= 2:
        issue_hints.append("数据薄弱: 当前结构化因子偏少，建议补充更真实的球队情报与盘口快照。")
    if not issue_hints:
        issue_hints.append("当前没有显著异常信号，若结果不符合预期，优先复查规则输出与最新输入数据。")

    toto = build_toto_recommendation(
        home_team=home.name,
        away_team=away.name,
        home_win_probability=prediction.home_win_probability,
        draw_probability=prediction.draw_probability,
        away_win_probability=prediction.away_win_probability,
        fair_handicap_line=prediction.fair_handicap_line,
        market_handicap_line=prediction.market_handicap_line,
        recommended_handicap_side=prediction.recommended_handicap_side,
        totals_tendency=prediction.totals_tendency,
        likely_scorelines=prediction.likely_scorelines,
        over_2_5_probability=prediction.over_2_5_probability or 0.0,
        under_2_5_probability=prediction.under_2_5_probability or 0.0,
        fair_total_line=prediction.fair_total_line or 2.5,
    )

    return PredictionDiagnostic(
        match_id=match_id,
        home_team=home.name,
        away_team=away.name,
        summary_conclusion=prediction.summary_conclusion,
        recommended_handicap_side=prediction.recommended_handicap_side,
        market_handicap_line=prediction.market_handicap_line,
        fair_handicap_line=prediction.fair_handicap_line,
        expected_home_goals=prediction.expected_home_goals or 0.0,
        expected_away_goals=prediction.expected_away_goals or 0.0,
        over_2_5_probability=prediction.over_2_5_probability or 0.0,
        under_2_5_probability=prediction.under_2_5_probability or 0.0,
        fair_total_line=prediction.fair_total_line or 2.5,
        market_probability_summary=_probability_summary(factor_map),
        value_edge_summary=_value_edge_summary(factor_map),
        totals_tendency=prediction.totals_tendency,
        likely_scorelines=prediction.likely_scorelines,
        factor_lines=factor_lines,
        issue_hints=issue_hints,
        toto_recommendation_lines=[
            f"适合下球判断: {toto.suitability_label}",
            f"适合度理由: {toto.suitability_reason}",
            f"让球适合度判断: {toto.handicap_suitability_label}",
            f"让球适合度理由: {toto.handicap_suitability_reason}",
            f"大小球适合度判断: {toto.totals_suitability_label}",
            f"大小球适合度理由: {toto.totals_suitability_reason}",
            f"体彩建议: {toto.primary_pick}",
            f"让球胜平负建议: {toto.handicap_pick}",
            f"总进球建议: {toto.totals_pick}",
            f"比分建议: {toto.score_pick}",
            f"风险等级: {toto.risk_level}",
            f"建议理由: {toto.reason}",
        ],
    )
