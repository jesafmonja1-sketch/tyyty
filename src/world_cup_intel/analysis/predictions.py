from __future__ import annotations

from datetime import datetime
import math

from sqlalchemy import desc, select

from world_cup_intel.schema import (
    Match,
    MatchPrediction,
    OddsMarket,
    OddsQuote,
    PredictionFactor,
    PredictionRun,
    TeamPowerSnapshot,
)


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


def generate_match_prediction(session, match_id: int, captured_at: datetime) -> MatchPrediction:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    home = _latest_team_power(session, match_row.home_team_id)
    away = _latest_team_power(session, match_row.away_team_id)
    rating_gap = home.overall_score - away.overall_score
    draw_anchor = 0.26 if match_row.stage == "Group Stage" else 0.23

    home_win = 1.0 / (1.0 + math.exp(-rating_gap / 6.5))
    away_win = 1.0 - home_win
    home_win = home_win * (1.0 - draw_anchor)
    away_win = away_win * (1.0 - draw_anchor)

    total = home_win + away_win + draw_anchor
    home_win /= total
    away_win /= total
    draw_probability = draw_anchor / total

    fair_handicap = round(-(rating_gap / 20.0), 2)
    market_handicap = _latest_market_handicap(session, match_id)
    recommended_side = "home" if market_handicap is None or fair_handicap < market_handicap else "away"

    expected_home_goals = max(0.4, round((home.attack_score + away.defense_score) / 100.0, 2))
    expected_away_goals = max(0.4, round((away.attack_score + home.defense_score) / 100.0, 2))
    likely_scorelines = "1-0,1-1,2-1" if expected_home_goals >= expected_away_goals else "0-1,1-1,1-2"
    totals_tendency = "under 2.5" if expected_home_goals + expected_away_goals < 2.7 else "over 2.5"
    confidence = "high" if abs(rating_gap) >= 6.0 else "medium"

    run = PredictionRun(match_id=match_id, captured_at=captured_at, model_version="v1-rules")
    session.add(run)
    session.flush()

    prediction = MatchPrediction(
        prediction_run_id=run.id,
        home_win_probability=round(home_win, 6),
        draw_probability=round(draw_probability, 6),
        away_win_probability=round(away_win, 6),
        fair_handicap_line=fair_handicap,
        market_handicap_line=market_handicap,
        recommended_handicap_side=recommended_side,
        totals_tendency=totals_tendency,
        likely_scorelines=likely_scorelines,
        confidence_level=confidence,
        summary_conclusion=f"rating gap {rating_gap:.2f}, recommend {recommended_side} side",
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
    return prediction
