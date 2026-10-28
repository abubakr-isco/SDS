"""Shipment tracking integration point.

No tracking backend is connected yet, so the bot says so honestly. To integrate
a TMS or carrier API, implement TrackingProvider and select it in build_tracking_provider().

Contract for implementations:
  * Look the shipment up in the authorized source of truth — never guess.
  * Check that `telegram_user_id` is allowed to see the shipment. If not, return
    NOT_FOUND (do not reveal that the reference exists).
  * Return only customer-safe fields: the latest CONFIRMED status and when it was updated.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class TrackingOutcome(enum.StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class TrackingResult:
    outcome: TrackingOutcome
    reference: str
    status: str | None = None
    last_updated: datetime | None = None


class TrackingProvider(Protocol):
    @property
    def is_configured(self) -> bool: ...

    async def lookup(self, reference: str, telegram_user_id: int) -> TrackingResult: ...


class NotConfiguredTrackingProvider:
    is_configured = False

    async def lookup(self, reference: str, telegram_user_id: int) -> TrackingResult:
        return TrackingResult(outcome=TrackingOutcome.UNAVAILABLE, reference=reference)


def build_tracking_provider(name: str) -> TrackingProvider:
    if name == "none":
        return NotConfiguredTrackingProvider()
    raise ValueError(f"Unknown tracking provider: {name}")
