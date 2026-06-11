from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from world_cup_intel.ingest.base import record_source_run
from world_cup_intel.schema import Match, OddsMarket, OddsQuote


def ingest_odds_bundle(session, payload: dict, captured_at: datetime) -> None:
    record_source_run(
        session,
        source_name="odds-data",
        endpoint="/odds",
        captured_at=captured_at,
        payload=payload,
    )

    match_row = session.scalar(select(Match).where(Match.external_id == payload["match_external_id"]))
    assert match_row is not None, "match must exist before odds ingestion"

    for quote in payload["quotes"]:
        market = OddsMarket(
            match_id=match_row.id,
            source_name="odds-data",
            bookmaker_name=payload["bookmaker"],
            market_type=quote["market_type"],
        )
        session.add(market)
        session.flush()
        session.add(
            OddsQuote(
                odds_market_id=market.id,
                captured_at=datetime.fromisoformat(quote["captured_at"].replace("Z", "+00:00")),
                line_value=quote.get("line_value"),
                home_price=quote.get("home_price"),
                draw_price=quote.get("draw_price"),
                away_price=quote.get("away_price"),
                over_price=quote.get("over_price"),
                under_price=quote.get("under_price"),
            )
        )
