"""Signed persistent memory primitives."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from mirra.identity import Identity
from mirra_core.identity.bcp_manager import BCPManager
from mirra_core.security.qseal_engine import generate_signature


@contextmanager
def _working_directory(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    original_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original_dir)


@dataclass(frozen=True)
class MemoryRecord:
    """A normalized BCP/ICP memory record."""

    raw: Dict[str, Any]
    index: int = 0

    @property
    def subject(self) -> str:
        return str(self.raw.get("evidence", {}).get("subject", ""))

    @property
    def event(self) -> str:
        return str(self.raw.get("evidence", {}).get("event", ""))

    @property
    def text(self) -> str:
        return str(self.raw.get("evidence", {}).get("memory_text", ""))

    @property
    def scope(self) -> str:
        return str(self.raw.get("evidence", {}).get("scope", ""))

    @property
    def consent(self) -> str:
        return str(self.raw.get("evidence", {}).get("consent", ""))

    @property
    def meta_hash(self) -> str:
        return str(self.raw.get("meta_hash", ""))

    @property
    def qseal_signature(self) -> str:
        return str(self.raw.get("qseal_signature", ""))

    @property
    def proof_id(self) -> str:
        return f"qseal://bcp_entry_{self.index}_{self.meta_hash[:16]}"

    def to_dict(self) -> Dict[str, Any]:
        payload = dict(self.raw)
        payload["index"] = self.index
        payload["proof_id"] = self.proof_id
        return payload


class AgentMemory:
    """Persistent signed memory store for one identity."""

    def __init__(self, identity: Identity, data_dir: str | Path):
        self.identity = identity
        self.data_dir = Path(data_dir)

    @classmethod
    def open(
        cls,
        identity: Identity,
        *,
        data_dir: str | Path = "examples/continuity_demo/data",
    ) -> "AgentMemory":
        return cls(identity, data_dir)

    def remember(
        self,
        event: str,
        *,
        subject: str,
        scope: Optional[str] = None,
        consent: Optional[str] = None,
        pleasure: float = 0.2,
        arousal: float = -0.1,
        dominance: float = 0.0,
        resonance: float = 0.7,
        novelty: float = 0.3,
        transferability: float = 0.4,
        pattern: str = "household_observation",
        significance: float = 0.7,
    ) -> MemoryRecord:
        """Write a signed memory and return the normalized stored record."""
        scope = scope or self.identity.scope
        consent = consent or self.identity.consent_model
        entry = {
            "timestamp": time.time(),
            "agent_id": self.identity.agent_id,
            "event_type": "interaction",
            "pad_after": {
                "pleasure": pleasure,
                "arousal": arousal,
                "dominance": dominance,
            },
            "rnt": {
                "resonance": resonance,
                "novelty": novelty,
                "transferability": transferability,
                "pattern_used": pattern,
            },
            "continuity": {
                "continuity_score": 0.5,
                "identity_stable": True,
                "status": "stable",
            },
            "significance": significance,
            "evidence": {
                "subject": subject,
                "event": event,
                "memory_text": f"{subject}: {event}",
                "scope": scope,
                "consent": consent,
            },
        }
        entry["qseal_signature"] = generate_signature(entry)

        with _working_directory(self.data_dir):
            manager = BCPManager(agent_id=self.identity.agent_id)
            manager._append_entry(entry)
            records = self._records_from_entries(manager._read_entries())
        return records[-1]

    def recall(self, *, subject: str, limit: int = 10) -> List[MemoryRecord]:
        """Recall recent memories for a subject from the persisted store."""
        with _working_directory(self.data_dir):
            manager = BCPManager(agent_id=self.identity.agent_id)
            records = self._records_from_entries(manager._read_entries())

        recent = records[-limit:] if limit > 0 else records
        return [
            record for record in recent
            if record.subject == subject or subject in record.text
        ]

    @staticmethod
    def _records_from_entries(entries: Iterable[Dict[str, Any]]) -> List[MemoryRecord]:
        return [
            MemoryRecord(raw=dict(entry), index=index)
            for index, entry in enumerate(entries)
        ]
