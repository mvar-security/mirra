"""Relationship-level affective continuity primitives."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from mirra_core.security.qseal_engine import generate_signature


@dataclass(frozen=True)
class PADState:
    """Pleasure-arousal-dominance state used as relationship tone metadata."""

    pleasure: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | None) -> "PADState":
        payload = payload or {}
        return cls(
            pleasure=float(payload.get("pleasure", 0.0)),
            arousal=float(payload.get("arousal", 0.0)),
            dominance=float(payload.get("dominance", 0.0)),
        )


@dataclass
class RelationshipEmotionalState:
    """Rolling relationship tone for one person."""

    person_id: str
    pad_baseline: PADState = field(default_factory=PADState)
    pad_current: PADState = field(default_factory=PADState)
    interaction_count: int = 0
    last_interaction: str = ""
    emotional_trend: str = "stable"
    notable_events: List[str] = field(default_factory=list)
    qseal_signature: str = ""

    def update(
        self,
        new_pad: PADState,
        *,
        event_significance: float = 0.5,
        notable_event: Optional[str] = None,
    ) -> "RelationshipEmotionalState":
        alpha = max(0.0, min(0.3, event_significance))
        previous_pleasure = self.pad_baseline.pleasure
        self.pad_baseline = PADState(
            pleasure=self.pad_baseline.pleasure * (1 - alpha) + new_pad.pleasure * alpha,
            arousal=self.pad_baseline.arousal * (1 - alpha) + new_pad.arousal * alpha,
            dominance=self.pad_baseline.dominance * (1 - alpha) + new_pad.dominance * alpha,
        )
        self.pad_current = new_pad
        self.interaction_count += 1
        self.last_interaction = datetime.now(timezone.utc).isoformat()
        if notable_event and notable_event not in self.notable_events:
            self.notable_events.append(notable_event)
        self.emotional_trend = _trend(previous_pleasure, self.pad_baseline.pleasure)
        self.qseal_signature = generate_signature(self.to_dict(include_signature=False))
        return self

    def to_dict(self, *, include_signature: bool = True) -> Dict[str, Any]:
        payload = {
            "person_id": self.person_id,
            "pad_baseline": self.pad_baseline.to_dict(),
            "pad_current": self.pad_current.to_dict(),
            "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction,
            "emotional_trend": self.emotional_trend,
            "notable_events": list(self.notable_events),
        }
        if include_signature:
            payload["qseal_signature"] = self.qseal_signature
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RelationshipEmotionalState":
        return cls(
            person_id=str(payload["person_id"]),
            pad_baseline=PADState.from_dict(payload.get("pad_baseline")),
            pad_current=PADState.from_dict(payload.get("pad_current")),
            interaction_count=int(payload.get("interaction_count", 0)),
            last_interaction=str(payload.get("last_interaction", "")),
            emotional_trend=str(payload.get("emotional_trend", "stable")),
            notable_events=list(payload.get("notable_events", [])),
            qseal_signature=str(payload.get("qseal_signature", "")),
        )


class EmotionalStateStore:
    """Persistent store for relationship-level PAD aggregates."""

    def __init__(self, agent_id: str, data_dir: str | Path):
        self.agent_id = agent_id
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / f"{agent_id}_emotional_state.jsonl"

    def get(self, person_id: str) -> RelationshipEmotionalState:
        return self._load().get(person_id) or RelationshipEmotionalState(person_id=person_id)

    def update(
        self,
        person_id: str,
        pad: PADState,
        *,
        event_significance: float = 0.5,
        notable_event: Optional[str] = None,
    ) -> RelationshipEmotionalState:
        states = self._load()
        state = states.get(person_id) or RelationshipEmotionalState(person_id=person_id)
        state.update(
            pad,
            event_significance=event_significance,
            notable_event=notable_event,
        )
        states[person_id] = state
        self._save(states)
        return state

    def _load(self) -> Dict[str, RelationshipEmotionalState]:
        if not self.path.exists():
            return {}
        states: Dict[str, RelationshipEmotionalState] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    state = RelationshipEmotionalState.from_dict(json.loads(line))
                    states[state.person_id] = state
        return states

    def _save(self, states: Dict[str, RelationshipEmotionalState]) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for state in states.values():
                handle.write(json.dumps(state.to_dict(), sort_keys=True) + "\n")


def _trend(previous: float, current: float) -> str:
    delta = current - previous
    if delta > 0.05:
        return "warming"
    if delta < -0.05:
        return "cooling"
    return "stable"
