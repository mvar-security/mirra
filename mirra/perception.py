"""Pluggable identity resolution interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class IdentityMatch:
    """Resolved person identity returned by a perception adapter."""

    person_id: str
    confidence: float
    method: str
    raw_signal: Optional[Dict[str, Any]] = None

    @property
    def trusted(self) -> bool:
        return self.confidence >= 0.7 and self.person_id != "stranger"


class PerceptionAdapter(ABC):
    """Maps a deployment-specific signal to a known person identity."""

    @abstractmethod
    def identify(self, signal: Dict[str, Any]) -> IdentityMatch:
        """Resolve a signal into a person identifier."""


class ManualAdapter(PerceptionAdapter):
    """Explicit person-id adapter for demos, tests, and server-side routing."""

    def identify(self, signal: Dict[str, Any]) -> IdentityMatch:
        person_id = str(signal.get("person_id") or signal.get("speaker") or "stranger")
        confidence = 1.0 if person_id != "stranger" else 0.0
        return IdentityMatch(
            person_id=person_id,
            confidence=confidence,
            method="manual",
            raw_signal=_audit_signal(signal),
        )


class UsernameAdapter(PerceptionAdapter):
    """Resolve chat usernames to person identifiers."""

    def __init__(self, username_map: Mapping[str, str]):
        self.username_map = dict(username_map)

    def identify(self, signal: Dict[str, Any]) -> IdentityMatch:
        username = str(signal.get("value") or signal.get("username") or "")
        person_id = self.username_map.get(username, "stranger")
        return IdentityMatch(
            person_id=person_id,
            confidence=1.0 if person_id != "stranger" else 0.0,
            method="username",
            raw_signal=_audit_signal(signal),
        )


class CallerIDAdapter(PerceptionAdapter):
    """Resolve caller IDs to person identifiers."""

    def __init__(self, phone_map: Mapping[str, str]):
        self.phone_map = dict(phone_map)

    def identify(self, signal: Dict[str, Any]) -> IdentityMatch:
        phone = str(signal.get("phone") or signal.get("caller_id") or "")
        person_id = self.phone_map.get(phone, "stranger")
        return IdentityMatch(
            person_id=person_id,
            confidence=1.0 if person_id != "stranger" else 0.0,
            method="caller_id",
            raw_signal=_audit_signal(signal),
        )


def _audit_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Keep audit metadata without retaining raw biometric payloads."""
    blocked = {"audio", "audio_embedding", "image", "image_embedding", "frame"}
    return {
        key: value for key, value in signal.items()
        if key not in blocked
    }
