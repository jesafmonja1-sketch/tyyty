from __future__ import annotations

from datetime import UTC, datetime, timedelta

import typer
from typer.core import TyperArgument

from world_cup_intel.config import Settings
from world_cup_intel.db import SessionLocal, build_engine, create_schema
from world_cup_intel.delivery.email_reports import render_match_report
from world_cup_intel.delivery.scheduler import send_due_reports


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


def _session():
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
