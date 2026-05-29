"""
MIRRA Verification SDK
======================

Epistemic verification for AI agent proposals.

3-line integration:

    from mirra_core.consciousness.entry_500.integration import MIRRAVerifier
    verifier = MIRRAVerifier()
    result = verifier.verify(proposal, context)

Modes:
    MONITOR  - Observe and log. Never blocks. Fail open.
    ADVISORY - Warn on low-trust proposals. Fail open + warning.
    BLOCKING - Reject low-trust proposals. Fail closed.

Public API:
    MIRRAVerifier       - Main verifier class
    VerificationResult  - Result of verify()
    AuditResult         - Result of audit()
    DriftStatus         - Result of monitor()
    VerificationMode    - Enum: MONITOR / ADVISORY / BLOCKING
    TrustLevel          - Enum: HIGH / MEDIUM / LOW / UNVERIFIED
"""

from .api import (
    MIRRAVerifier,
    VerificationResult,
    AuditResult,
    DriftStatus,
    VerificationMode,
    TrustLevel,
)

__all__ = [
    "MIRRAVerifier",
    "VerificationResult",
    "AuditResult",
    "DriftStatus",
    "VerificationMode",
    "TrustLevel",
]

__version__ = "1.0.0"
