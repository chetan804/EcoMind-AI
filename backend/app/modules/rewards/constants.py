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
