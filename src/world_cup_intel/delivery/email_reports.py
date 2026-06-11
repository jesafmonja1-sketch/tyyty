from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from sqlalchemy import desc, select

from world_cup_intel.config import Settings
from world_cup_intel.schema import Match, MatchPrediction, MatchReview, NationalTeam, PredictionFactor, PredictionRun, SentReport


@dataclass
class RenderedReport:
    subject: str
    body: str


def _latest_prediction(session, match_id: int) -> tuple[MatchPrediction, PredictionRun]:
    row = session.execute(
        select(MatchPrediction, PredictionRun)
        .join(PredictionRun, PredictionRun.id == MatchPrediction.prediction_run_id)
        .where(PredictionRun.match_id == match_id)
        .order_by(desc(PredictionRun.captured_at))
    ).first()
    if row is None:
        raise ValueError(f"Prediction not found for match_id={match_id}")
    return row


def _prediction_reasons(session, prediction_run_id: int) -> list[PredictionFactor]:
    return session.scalars(
        select(PredictionFactor).where(PredictionFactor.prediction_run_id == prediction_run_id)
    ).all()


def _latest_match_review(session, match_id: int, team_id: int) -> MatchReview | None:
    return session.scalars(
        select(MatchReview)
        .where(MatchReview.match_id == match_id, MatchReview.national_team_id == team_id)
        .order_by(desc(MatchReview.created_at))
    ).first()


def _reason_map(factors: list[PredictionFactor]) -> dict[str, PredictionFactor]:
    return {factor.factor_name: factor for factor in factors}


def render_match_report(session, match_id: int) -> RenderedReport:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    home = session.get(NationalTeam, match_row.home_team_id)
    away = session.get(NationalTeam, match_row.away_team_id)
    if home is None or away is None:
        raise ValueError(f"Teams missing for match_id={match_id}")

    prediction, run = _latest_prediction(session, match_id)
    factors = _prediction_reasons(session, run.id)
    factor_map = _reason_map(factors)
    home_review = _latest_match_review(session, match_id, home.id)
    away_review = _latest_match_review(session, match_id, away.id)

    rating_gap = factor_map.get("rating_gap")
    market_handicap = factor_map.get("market_handicap")
    strength_line = (
        f"实力差来源: 模型测得双方综合实力差为 {rating_gap.factor_value:.2f}，"
        f"当前更偏向 {home.name if prediction.home_win_probability >= prediction.away_win_probability else away.name}。"
        if rating_gap
        else "实力差来源: 当前没有可用的结构化实力差数据。"
    )
    market_line = (
        f"盘口差异: 市场最新让球为 {prediction.market_handicap_line}，模型公平让球为 {prediction.fair_handicap_line}，"
        f"当前建议方向为 {prediction.recommended_handicap_side}。"
        if market_handicap
        else "盘口差异: 当前没有可用的让球市场数据。"
    )
    tactical_line = (
        f"战术变化: {home.name} {home_review.tactical_change_summary} {home_review.strength_change_summary}"
        if home_review is not None
        else f"战术变化: {home.name} 暂无上一场后的战术变化摘要。"
    )
    injury_line = (
        f"伤停影响: {home_review.summary_text} {home_review.next_match_impact_summary}"
        if home_review is not None
        else f"伤停影响: {home.name} 暂无上一场后的伤停跟踪记录。"
    )
    away_line = (
        f"对手补充: {away.name} {away_review.summary_text} {away_review.next_match_impact_summary}"
        if away_review is not None
        else f"对手补充: {away.name} 暂无上一场后的补充复盘。"
    )
    summary_line = f"一句话结论: {prediction.summary_conclusion}"

    subject = f"[World Cup] {home.name} vs {away.name} pre-match report"
    body = (
        f"Match: {home.name} vs {away.name}\n"
        f"Kickoff: {match_row.kickoff_at.isoformat()}\n"
        f"Stage: {match_row.stage}\n"
        f"Win/Draw/Loss: {prediction.home_win_probability:.2%} / "
        f"{prediction.draw_probability:.2%} / {prediction.away_win_probability:.2%}\n"
        f"Handicap: fair {prediction.fair_handicap_line}, "
        f"market {prediction.market_handicap_line}, "
        f"recommendation {prediction.recommended_handicap_side}\n"
        f"Totals: {prediction.totals_tendency}\n"
        f"Scorelines: {prediction.likely_scorelines}\n"
        f"Confidence: {prediction.confidence_level}\n"
        f"Summary: {prediction.summary_conclusion}\n\n"
        "分析理由:\n"
        f"- {strength_line}\n"
        f"- {market_line}\n"
        f"- {tactical_line}\n"
        f"- {injury_line}\n"
        f"- {away_line}\n"
        f"- {summary_line}\n"
    )
    return RenderedReport(subject=subject, body=body)


def send_match_report(session, settings: Settings, match_id: int, sent_at) -> SentReport:
    match_row = session.get(Match, match_id)
    if match_row is None:
        raise ValueError(f"Match not found: match_id={match_id}")

    report = render_match_report(session, match_id)
    message = EmailMessage()
    message["From"] = settings.email.username
    message["To"] = settings.email.recipient
    message["Subject"] = report.subject
    message.set_content(report.body)

    with smtplib.SMTP_SSL(settings.email.smtp_host, settings.email.smtp_port) as client:
        client.login(settings.email.username, settings.email.password)
        client.send_message(message)

    sent_report = SentReport(
        match_id=match_id,
        sent_at=sent_at,
        recipient=settings.email.recipient,
        subject=report.subject,
        body_text=report.body,
    )
    session.add(sent_report)
    return sent_report
