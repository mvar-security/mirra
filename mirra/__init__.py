"""MIRRA continuity substrate SDK.

Persistent identity, trusted memory, verification, and governed action for
stateless AI agents.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mirra")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from mirra.identity import Identity
from mirra.memory import AgentMemory, MemoryRecord
from mirra.relationship import Relationship, RelationshipGraph, RelationshipType
from mirra.perception import (
    CallerIDAdapter,
    IdentityMatch,
    ManualAdapter,
    PerceptionAdapter,
    UsernameAdapter,
)
from mirra.emotional_state import (
    EmotionalStateStore,
    PADState,
    RelationshipEmotionalState,
)
from mirra.verification import VerificationReport, verify
from mirra.governance import GovernanceReport, respond
from mirra.wrapper import ContinuityContext, ContinuousAgent, wrap

__all__ = [
    "__version__",
    "Identity",
    "AgentMemory",
    "MemoryRecord",
    "Relationship",
    "RelationshipGraph",
    "RelationshipType",
    "IdentityMatch",
    "PerceptionAdapter",
    "ManualAdapter",
    "UsernameAdapter",
    "CallerIDAdapter",
    "PADState",
    "RelationshipEmotionalState",
    "EmotionalStateStore",
    "VerificationReport",
    "GovernanceReport",
    "ContinuityContext",
    "ContinuousAgent",
    "verify",
    "respond",
    "wrap",
]
