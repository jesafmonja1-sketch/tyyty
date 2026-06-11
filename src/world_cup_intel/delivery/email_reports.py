from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from sqlalchemy import desc, select

from world_cup_intel.config import Settings
from world_cup_intel.schema import Match, MatchPrediction, NationalTeam, PredictionFactor, PredictionRun, SentReport


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
    reason_lines = [
        f"- {factor.factor_name}: {factor.factor_value:.2f} ({factor.explanation})"
        for factor in factors
    ]
    if not reason_lines:
        reason_lines = ["- no structured factor explanations available"]

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
        f"{'\n'.join(reason_lines)}\n"
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
