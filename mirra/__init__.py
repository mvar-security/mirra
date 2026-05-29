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
from mirra.verification import VerificationReport, verify
from mirra.governance import GovernanceReport, respond

__all__ = [
    "__version__",
    "Identity",
    "AgentMemory",
    "MemoryRecord",
    "VerificationReport",
    "GovernanceReport",
    "verify",
    "respond",
]
