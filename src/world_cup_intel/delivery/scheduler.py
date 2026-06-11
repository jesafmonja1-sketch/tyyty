from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_, select

from world_cup_intel.config import Settings
from world_cup_intel.delivery.email_reports import send_match_report
from world_cup_intel.schema import Match
from world_cup_intel.schema import SentReport


def select_matches_needing_report(session, now: datetime, window: timedelta):
    window_end = now + window
    return session.scalars(
        select(Match).where(
            and_(
                Match.status == "scheduled",
                Match.kickoff_at >= now,
                Match.kickoff_at <= window_end,
            )
        )
    ).all()


def send_due_reports(
    session,
    settings: Settings,
    now: datetime,
    window: timedelta,
) -> list[int]:
    due_matches = select_matches_needing_report(session, now, window)
    sent_match_ids = {
        match_id
        for match_id in session.scalars(
            select(SentReport.match_id).where(SentReport.match_id.in_([match.id for match in due_matches]))
        ).all()
    }

    delivered_ids = []
    for match in due_matches:
        if match.id in sent_match_ids:
            continue
        send_match_report(session, settings, match.id, now)
        delivered_ids.append(match.id)

    return delivered_ids


def build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")
