"""Optional Deribit ingestion worker; demo mode remains available without
credentials."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import httpx


@dataclass(frozen=True)
class OptionQuote:
    instrument: str
    underlying: str
    timestamp: datetime
    expiry: datetime
    strike: float
    option_type: str
    bid: float | None
    ask: float | None
    mark: float | None
    underlying_price: float
    interest_rate: float
    dividend_yield: float = 0.0


class OptionProvider(Protocol):
    async def get_chain(self, underlying: str) -> Sequence[OptionQuote]: ...


class DeribitProvider:
    def __init__(self, base_url: str = "https://www.deribit.com/api/v2"):
        self.base_url = base_url.rstrip("/")

    async def get_chain(self, underlying: str) -> list[OptionQuote]:
        async with httpx.AsyncClient(timeout=15) as client:
            instruments = await client.get(
                f"{self.base_url}/public/get_instruments",
                params={
                    "currency": underlying.upper(),
                    "kind": "option",
                    "expired": "false",
                },
            )
            instruments.raise_for_status()
            rows = instruments.json()["result"]
            ticker_rows = []
            for instrument in rows:
                response = await client.get(
                    f"{self.base_url}/public/ticker",
                    params={"instrument_name": instrument["instrument_name"]},
                )
                if response.is_success:
                    ticker_rows.append((instrument, response.json()["result"]))
        now = datetime.now(UTC)
        quotes = []
        for instrument, ticker in ticker_rows:
            expiry = datetime.fromtimestamp(
                instrument["expiration_timestamp"] / 1000, UTC
            )
            quotes.append(
                OptionQuote(
                    instrument=instrument["instrument_name"],
                    underlying=underlying.upper(),
                    timestamp=now,
                    expiry=expiry,
                    strike=float(instrument["strike"]),
                    option_type="call"
                    if instrument["option_type"] == "call"
                    else "put",
                    bid=ticker.get("best_bid_price"),
                    ask=ticker.get("best_ask_price"),
                    mark=ticker.get("mark_price"),
                    underlying_price=float(
                        ticker.get("underlying_price") or ticker.get("index_price")
                    ),
                    interest_rate=0.0,
                )
            )
        return quotes


async def snapshot(underlying: str = "BTC") -> int:
    if os.getenv("DEMO_MODE", "true").lower() == "true":
        return 0
    provider = DeribitProvider()
    quotes = await provider.get_chain(underlying)
    # Persistence is injected at deployment time; this worker only owns acquisition.
    return len(quotes)


if __name__ == "__main__":
    print(asyncio.run(snapshot(os.getenv("UNDERLYING", "BTC"))))
