from __future__ import annotations

from enum import StrEnum


class LedgerEntryType(StrEnum):
    EARNED = "earned"
    REDEEMED = "redeemed"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


class LedgerSourceType(StrEnum):
    WASTE_REPORT = "waste_report"
    COLLECTION_TASK = "collection_task"
    RECOVERY_RECORD = "recovery_record"
    COMMUNITY_INCIDENT = "community_incident"
    MANUAL = "manual"
    REWARD_REDEMPTION = "reward_redemption"


class RedemptionStatus(StrEnum):
    """``pending``: points are spent and the reward is waiting to be handed over."""

    PENDING = "pending"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L: read aloud and typed by hand
CODE_LENGTH = 10
MAX_ITEM_COST = 1_000_000
