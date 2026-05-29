"""Cryptographic agent identity helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from mirra_core.security.qseal_engine import sign_entry


@dataclass(frozen=True)
class Identity:
    """A signed identity for an agent or device."""

    agent_id: str
    kind: str = "agent"
    scope: str = "household"
    consent_model: str = "family"
    signed: Dict[str, Any] | None = None

    @classmethod
    def load(
        cls,
        agent_id: str,
        *,
        kind: str = "agent",
        scope: str = "household",
        consent_model: str = "family",
    ) -> "Identity":
        """Create/load a signed identity payload.

        The current SDK keeps identity material local and deterministic at the
        API boundary; future versions can swap this for a key store without
        changing caller code.
        """
        payload = {
            "agent_id": agent_id,
            "type": kind,
            "scope": scope,
            "consent_model": consent_model,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return cls(
            agent_id=agent_id,
            kind=kind,
            scope=scope,
            consent_model=consent_model,
            signed=sign_entry(payload, agent_id=agent_id),
        )

    @property
    def qseal_signature(self) -> str:
        if not self.signed:
            return ""
        return str(self.signed.get("qseal_signature", ""))

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.signed or {})
