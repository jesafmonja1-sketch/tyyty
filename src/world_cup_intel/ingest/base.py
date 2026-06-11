from __future__ import annotations

from datetime import datetime
import json

from world_cup_intel.schema import RawPayload, RawSourceRun


def record_source_run(
    session,
    *,
    source_name: str,
    endpoint: str,
    captured_at: datetime,
    payload: dict,
) -> RawSourceRun:
    run = RawSourceRun(
        source_name=source_name,
        endpoint=endpoint,
        captured_at=captured_at,
        status="success",
    )
    session.add(run)
    session.flush()
    session.add(RawPayload(source_run_id=run.id, payload_json=json.dumps(payload, ensure_ascii=False)))
    return run
