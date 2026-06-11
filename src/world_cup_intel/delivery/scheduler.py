from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_, select

from world_cup_intel.schema import Match


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


def build_scheduler() -> BackgroundScheduler:
    return BackgroundScheduler(timezone="UTC")
