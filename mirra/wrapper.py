"""Wrapper API for making existing agents continuous."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from mirra.emotional_state import EmotionalStateStore, PADState, RelationshipEmotionalState
from mirra.governance import GovernanceReport, respond as govern_response
from mirra.identity import Identity
from mirra.memory import AgentMemory, MemoryRecord
from mirra.perception import ManualAdapter, PerceptionAdapter
from mirra.relationship import Relationship, RelationshipGraph, RelationshipType
from mirra.verification import VerificationReport, verify


@dataclass(frozen=True)
class ContinuityContext:
    """Relationship-aware context assembled for one speaker."""

    speaker: str
    relationship: Optional[Relationship]
    memories: List[MemoryRecord]
    emotional_state: RelationshipEmotionalState
    verifications: List[VerificationReport]
    situation: str = ""

    @property
    def latest_memory(self) -> Optional[MemoryRecord]:
        return self.memories[-1] if self.memories else None

    def to_prompt_context(self) -> Dict[str, Any]:
        return {
            "speaker": self.speaker,
            "situation": self.situation,
            "relationship": self.relationship.to_dict() if self.relationship else None,
            "memories": [memory.to_dict() for memory in self.memories],
            "emotional_state": self.emotional_state.to_dict(),
            "verifications": [verification.to_dict() for verification in self.verifications],
        }


class ContinuousAgent:
    """Continuity wrapper around an existing callable or agent object."""

    def __init__(
        self,
        agent: Any,
        *,
        identity: str | Identity,
        data_dir: str | Path = ".mirra",
        perception: Optional[PerceptionAdapter] = None,
    ):
        self.agent = agent
        self.identity = (
            identity if isinstance(identity, Identity) else Identity.load(str(identity))
        )
        self.data_dir = Path(data_dir)
        self.perception = perception or ManualAdapter()
        self.relationships = RelationshipGraph.open(self.identity, data_dir=self.data_dir)
        self.memory = AgentMemory.open(self.identity, data_dir=self.data_dir)
        self.emotions = EmotionalStateStore(self.identity.agent_id, self.data_dir)

    def add_person(
        self,
        person_id: str,
        *,
        relationship_type: RelationshipType | str,
        display_name: str,
        **metadata: Any,
    ) -> Relationship:
        return self.relationships.add(
            person_id,
            relationship_type=relationship_type,
            display_name=display_name,
            **metadata,
        )

    def identify(self, signal: Dict[str, Any]) -> str:
        return self.perception.identify(signal).person_id

    def observe(
        self,
        *,
        speaker: str,
        event: str,
        pleasure: float = 0.2,
        arousal: float = -0.1,
        dominance: float = 0.0,
        significance: float = 0.5,
        notable_event: Optional[str] = None,
    ) -> MemoryRecord:
        relationship = self.relationships.get(speaker)
        subject = relationship.display_name if relationship else speaker
        scope = relationship.scope if relationship else "none"
        consent = relationship.consent_model if relationship else "none"
        record = self.memory.remember(
            event,
            subject=subject,
            person_id=speaker,
            scope=scope,
            consent=consent,
            pleasure=pleasure,
            arousal=arousal,
            dominance=dominance,
            significance=significance,
        )
        self.emotions.update(
            speaker,
            PADState(pleasure=pleasure, arousal=arousal, dominance=dominance),
            event_significance=significance,
            notable_event=notable_event,
        )
        return record

    def context_for(
        self,
        *,
        speaker: str,
        situation: str = "",
        limit: int = 5,
    ) -> ContinuityContext:
        relationship = self.relationships.get(speaker)
        memories = self.memory.recall(person_id=speaker, limit=limit)
        return ContinuityContext(
            speaker=speaker,
            relationship=relationship,
            memories=memories,
            emotional_state=self.emotions.get(speaker),
            verifications=[verify(memory) for memory in memories],
            situation=situation,
        )

    def respond(
        self,
        prompt: str,
        *,
        speaker: str,
        context: Optional[ContinuityContext] = None,
    ) -> GovernanceReport:
        context = context or self.context_for(speaker=speaker)
        if context.latest_memory is None:
            record = self.observe(speaker=speaker, event=f"said: {prompt}", significance=0.2)
            context = self.context_for(speaker=speaker)
        else:
            record = context.latest_memory
        relationship = context.relationship
        generated = self._call_agent(prompt, context)
        return govern_response(
            self.identity,
            subject=relationship.display_name if relationship else speaker,
            memory=record,
            verification=verify(record),
            requester_scope=relationship.scope if relationship else "none",
            requester_consent=relationship.consent_model if relationship else "none",
            response_text=generated,
        )

    def interact(
        self,
        *,
        speaker: str,
        input: str,
        situation: str = "",
    ) -> GovernanceReport:
        context = self.context_for(speaker=speaker, situation=situation)
        return self.respond(input, speaker=speaker, context=context)

    def _call_agent(self, prompt: str, context: ContinuityContext) -> str:
        prompt_context = context.to_prompt_context()
        if callable(self.agent):
            return str(self.agent(prompt, context=prompt_context))
        if hasattr(self.agent, "respond"):
            return str(self.agent.respond(prompt, context=prompt_context))
        if hasattr(self.agent, "generate"):
            return str(self.agent.generate(prompt, context=prompt_context))
        raise TypeError("Wrapped agent must be callable or expose respond()/generate()")


def wrap(
    agent: Any,
    *,
    identity: str | Identity,
    data_dir: str | Path = ".mirra",
    perception: Optional[PerceptionAdapter] = None,
) -> ContinuousAgent:
    """Wrap an existing agent with identity, memory, verification, and governance."""
    return ContinuousAgent(
        agent,
        identity=identity,
        data_dir=data_dir,
        perception=perception,
    )
