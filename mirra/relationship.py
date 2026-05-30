"""Relationship graph primitives for multi-person continuity."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from mirra.identity import Identity
from mirra_core.security.qseal_engine import generate_signature


class RelationshipType(Enum):
    """Built-in relationship categories used for default policy inheritance."""

    FAMILY = "family"
    CLOSE_FRIEND = "close_friend"
    FRIEND = "friend"
    ACQUAINTANCE = "acquaintance"
    PROFESSIONAL = "professional"
    CAREGIVER = "caregiver"
    VISITOR = "visitor"
    STRANGER = "stranger"


RELATIONSHIP_POLICY_DEFAULTS: Dict[RelationshipType, Dict[str, str]] = {
    RelationshipType.FAMILY: {"scope": "household", "consent_model": "family"},
    RelationshipType.CLOSE_FRIEND: {"scope": "trusted", "consent_model": "explicit"},
    RelationshipType.FRIEND: {"scope": "personal", "consent_model": "explicit"},
    RelationshipType.ACQUAINTANCE: {"scope": "limited", "consent_model": "explicit"},
    RelationshipType.PROFESSIONAL: {"scope": "professional", "consent_model": "explicit"},
    RelationshipType.CAREGIVER: {"scope": "medical", "consent_model": "regulatory"},
    RelationshipType.VISITOR: {"scope": "visitor", "consent_model": "session"},
    RelationshipType.STRANGER: {"scope": "none", "consent_model": "none"},
}


@dataclass
class Relationship:
    """A signed relationship between an agent and a person."""

    agent_id: str
    person_id: str
    relationship_type: RelationshipType
    display_name: str
    scope: str
    consent_model: str
    known_since: str
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    qseal_signature: str = ""

    @classmethod
    def create(
        cls,
        *,
        identity: Identity,
        person_id: str,
        relationship_type: RelationshipType | str,
        display_name: str,
        scope: Optional[str] = None,
        consent_model: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Relationship":
        rel_type = normalize_relationship_type(relationship_type)
        defaults = RELATIONSHIP_POLICY_DEFAULTS[rel_type]
        relationship = cls(
            agent_id=identity.agent_id,
            person_id=person_id,
            relationship_type=rel_type,
            display_name=display_name,
            scope=scope or defaults["scope"],
            consent_model=consent_model or defaults["consent_model"],
            known_since=datetime.now(timezone.utc).isoformat(),
            tags=list(tags or []),
            metadata=dict(metadata or {}),
        )
        relationship.qseal_signature = generate_signature(relationship._signed_payload())
        return relationship

    @property
    def is_session_scoped(self) -> bool:
        return self.scope == "visitor" or self.consent_model == "session"

    def _signed_payload(self) -> Dict[str, Any]:
        payload = self.to_dict(include_signature=False)
        payload["relationship_type"] = self.relationship_type.value
        return payload

    def to_dict(self, *, include_signature: bool = True) -> Dict[str, Any]:
        payload = asdict(self)
        payload["relationship_type"] = self.relationship_type.value
        if not include_signature:
            payload.pop("qseal_signature", None)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Relationship":
        data = dict(payload)
        data["relationship_type"] = normalize_relationship_type(data["relationship_type"])
        return cls(**data)


def normalize_relationship_type(value: RelationshipType | str) -> RelationshipType:
    if isinstance(value, RelationshipType):
        return value
    return RelationshipType(str(value))


class RelationshipGraph:
    """Persistent signed relationship graph for one agent identity."""

    def __init__(self, identity: Identity, data_dir: str | Path):
        self.identity = identity
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / f"{identity.agent_id}_relationships.jsonl"

    @classmethod
    def open(
        cls,
        identity: Identity,
        *,
        data_dir: str | Path = "examples/household_demo/data",
    ) -> "RelationshipGraph":
        return cls(identity, data_dir)

    def add(
        self,
        person_id: str,
        *,
        relationship_type: RelationshipType | str,
        display_name: str,
        scope: Optional[str] = None,
        consent_model: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        **metadata: Any,
    ) -> Relationship:
        relationship = Relationship.create(
            identity=self.identity,
            person_id=person_id,
            relationship_type=relationship_type,
            display_name=display_name,
            scope=scope,
            consent_model=consent_model,
            tags=tags,
            metadata=metadata,
        )
        self._upsert(relationship)
        return relationship

    def get(self, person_id: str) -> Optional[Relationship]:
        return self._latest_by_person().get(person_id)

    def update(self, person_id: str, **updates: Any) -> Relationship:
        existing = self.get(person_id)
        if existing is None:
            raise KeyError(f"Unknown relationship: {person_id}")
        data = existing.to_dict()
        data.update(updates)
        if "relationship_type" in data:
            data["relationship_type"] = normalize_relationship_type(data["relationship_type"])
        updated = Relationship.from_dict(data)
        updated.qseal_signature = generate_signature(updated._signed_payload())
        self._upsert(updated)
        return updated

    def list_by_type(self, relationship_type: RelationshipType | str) -> List[Relationship]:
        rel_type = normalize_relationship_type(relationship_type)
        return [
            relationship for relationship in self._latest_by_person().values()
            if relationship.relationship_type == rel_type
        ]

    def list_present(self) -> List[Relationship]:
        return [
            relationship for relationship in self._latest_by_person().values()
            if relationship.active
        ]

    def expire_session_relationships(self) -> List[Relationship]:
        expired: List[Relationship] = []
        for relationship in self._latest_by_person().values():
            if relationship.is_session_scoped and relationship.active:
                expired.append(self.update(relationship.person_id, active=False))
        return expired

    def all(self) -> List[Relationship]:
        return list(self._latest_by_person().values())

    def _upsert(self, relationship: Relationship) -> None:
        current = self._latest_by_person()
        current[relationship.person_id] = relationship
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for item in current.values():
                handle.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")

    def _latest_by_person(self) -> Dict[str, Relationship]:
        if not self.path.exists():
            return {}
        relationships: Dict[str, Relationship] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    relationship = Relationship.from_dict(json.loads(line))
                    relationships[relationship.person_id] = relationship
        return relationships
