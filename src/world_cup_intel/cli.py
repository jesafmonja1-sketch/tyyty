from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path

import typer
from typer.core import TyperArgument

from world_cup_intel.config import Settings
from world_cup_intel.db import SessionLocal, build_engine, create_schema
from world_cup_intel.delivery.email_reports import render_match_report
from world_cup_intel.delivery.scheduler import send_due_reports
from world_cup_intel.seed.upcoming_world_cup import seed_upcoming_world_cup_matches


def _patch_typer_click_compat() -> None:
    if TyperArgument.make_metavar.__code__.co_argcount == 1:
        def _compat_make_metavar(self, ctx=None):
            if self.metavar is not None:
                return self.metavar

            var = (self.name or "").upper()
            if not self.required:
                var = f"[{var}]"
            try:
                type_var = self.type.get_metavar(param=self, ctx=ctx)
            except TypeError:
                type_var = self.type.get_metavar(self)
            if type_var:
                var += f":{type_var}"
            if self.nargs != 1:
                var += "..."
            return var

        TyperArgument.make_metavar = _compat_make_metavar


_patch_typer_click_compat()
app = typer.Typer()


@app.callback()
def main() -> None:
    """World Cup intelligence commands."""


def _load_local_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _session():
    _load_local_env()
    settings = Settings.from_env()
    engine = build_engine(settings.database_url)
    create_schema(engine)
    SessionLocal.configure(bind=engine)
    return SessionLocal()


@app.command("preview-report")
def preview_report(match_id: int) -> None:
    with _session() as session:
        report = render_match_report(session, match_id)
        typer.echo(report.subject)
        typer.echo(report.body)


@app.command("send-due-reports")
def send_due_reports_command(window_minutes: int = 125) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    _load_local_env()
    settings = Settings.from_env()
    with _session() as session:
        sent_ids = send_due_reports(
            session,
            settings,
            now,
            timedelta(minutes=window_minutes),
        )
        session.commit()
        typer.echo(f"Sent {len(sent_ids)} report(s).")


@app.command("seed-upcoming-world-cup")
def seed_upcoming_world_cup_command() -> None:
    captured_at = datetime.now(UTC).replace(tzinfo=None)
    with _session() as session:
        seeded = seed_upcoming_world_cup_matches(session, captured_at)
        session.commit()
        typer.echo(f"Seeded {len(seeded)} upcoming World Cup match(es).")
