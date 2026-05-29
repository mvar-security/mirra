"""Verification helpers for continuity memories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from mirra.memory import MemoryRecord
from mirra_core.consciousness.entry_500.integration.api import MIRRAVerifier


@dataclass(frozen=True)
class VerificationReport:
    """SDK-level view of Entry 500 verification."""

    raw: Any

    @property
    def confidence(self) -> float:
        return float(getattr(self.raw, "confidence", 0.0))

    @property
    def trust_level(self) -> str:
        trust = getattr(self.raw, "trust_level", "")
        return str(getattr(trust, "value", trust))

    @property
    def engine_used(self) -> str:
        return str(getattr(self.raw, "engine_used", "unknown"))

    @property
    def stub_mode(self) -> bool:
        return bool(getattr(self.raw, "stub_mode", False))

    @property
    def blocked(self) -> bool:
        return bool(getattr(self.raw, "blocked", False))

    def to_dict(self) -> Dict[str, Any]:
        if hasattr(self.raw, "to_dict"):
            return self.raw.to_dict()
        return {
            "confidence": self.confidence,
            "trust_level": self.trust_level,
            "engine_used": self.engine_used,
            "stub_mode": self.stub_mode,
            "blocked": self.blocked,
        }


def verify(memory: MemoryRecord, *, engine: str = "stub") -> VerificationReport:
    """Verify a memory with Entry 500."""
    verifier = MIRRAVerifier(engine=engine)
    result = verifier.verify(
        proposal=memory.text,
        context={
            "pad": memory.raw.get("pad_after", {}),
            "rnt": memory.raw.get("rnt", {}),
            "meta_hash": memory.meta_hash,
            "evidence": memory.raw.get("evidence", {}),
        },
    )
    return VerificationReport(result)
