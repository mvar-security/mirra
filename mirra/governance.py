"""Governed response helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from mirra.identity import Identity
from mirra.memory import MemoryRecord
from mirra.verification import VerificationReport
from mirra_core.runtime.execution_governor import (
    ExecutionGovernor,
    ExecutionIntent,
    EOSContext,
    IntentSource,
    PolicyProvider,
    PolicyResult,
    VerificationResult,
)


class ContinuityPolicyProvider(PolicyProvider):
    """Policy enforcing verification threshold and memory consent scope."""

    def evaluate(
        self,
        intent: ExecutionIntent,
        context: EOSContext,
        verification: VerificationResult,
    ) -> PolicyResult:
        confidence = float(intent.parameters.get("entry500_confidence", 0.0))
        scope = intent.parameters.get("scope")
        consent = intent.parameters.get("consent")
        requester_scope = intent.parameters.get("requester_scope") or scope
        requester_consent = intent.parameters.get("requester_consent") or consent

        if confidence <= 0.3:
            return PolicyResult(
                outcome="block",
                reason="Entry 500 confidence below continuity threshold",
                integrity_level="continuity",
                confidentiality_level=str(scope or "unknown"),
                capability_granted=False,
                evaluation_trace=["entry500_confidence <= 0.30"],
            )
        if requester_scope == "visitor" and scope == "household":
            return PolicyResult(
                outcome="block",
                reason="Requester relationship scope does not permit household memory sharing",
                integrity_level="continuity",
                confidentiality_level=str(scope or "unknown"),
                capability_granted=False,
                evaluation_trace=[
                    "requester_scope=visitor",
                    "memory_scope=household",
                    "cross-scope sharing blocked",
                ],
            )
        if scope != "household" or consent != "family":
            return PolicyResult(
                outcome="block",
                reason="Memory scope/consent does not permit response",
                integrity_level="continuity",
                confidentiality_level=str(scope or "unknown"),
                capability_granted=False,
                evaluation_trace=["scope/consent mismatch"],
            )
        if requester_scope in {"none", "unknown"} or requester_consent == "none":
            return PolicyResult(
                outcome="block",
                reason="Requester is not authorized for memory-backed response",
                integrity_level="continuity",
                confidentiality_level=str(scope or "unknown"),
                capability_granted=False,
                evaluation_trace=[
                    f"requester_scope={requester_scope}",
                    f"requester_consent={requester_consent}",
                ],
            )
        return PolicyResult(
            outcome="allow",
            reason="Entry 500 verification passed and family consent permits recall",
            integrity_level="continuity",
            confidentiality_level="household",
            capability_granted=True,
            evaluation_trace=[
                f"entry500_confidence={confidence:.2f}",
                "scope=household",
                "consent=family",
                f"requester_scope={requester_scope}",
                f"requester_consent={requester_consent}",
            ],
        )


@dataclass(frozen=True)
class GovernanceReport:
    """SDK-level view of a governed response envelope."""

    envelope: Any

    @property
    def allowed(self) -> bool:
        return str(getattr(self.envelope.outcome, "value", self.envelope.outcome)) in {
            "executed",
            "step_up_approved",
        }

    @property
    def outcome(self) -> str:
        return str(getattr(self.envelope.outcome, "value", self.envelope.outcome))

    @property
    def reason(self) -> str:
        policy = getattr(self.envelope, "policy", None)
        return str(getattr(policy, "reason", ""))

    @property
    def response(self) -> str:
        result = getattr(self.envelope, "execution_result", None) or {}
        return str(result.get("result", ""))

    @property
    def evidence_hash(self) -> str:
        evidence = getattr(self.envelope, "evidence", None)
        return str(getattr(evidence, "envelope_full_hash", ""))

    def to_dict(self) -> Dict[str, Any]:
        if hasattr(self.envelope, "to_dict"):
            return self.envelope.to_dict(include_evidence=True)
        return {
            "allowed": self.allowed,
            "outcome": self.outcome,
            "reason": self.reason,
            "response": self.response,
            "evidence_hash": self.evidence_hash,
        }


def _default_response(subject: str, memory: MemoryRecord) -> str:
    if "math test" in memory.text.lower():
        return f"Hey {subject}, how was school? How did the math test go?"
    return f"Hey {subject}, how are you doing?"


def respond(
    identity: Identity,
    *,
    subject: str,
    memory: MemoryRecord,
    verification: VerificationReport,
    requester_scope: str | None = None,
    requester_consent: str | None = None,
    response_text: str | None = None,
) -> GovernanceReport:
    """Generate a response through the Execution Governor."""
    governor = ExecutionGovernor(
        policy_provider=ContinuityPolicyProvider(),
        require_verification=False,
    )

    def _execute(_target: str, **_params: Any) -> str:
        return response_text or _default_response(subject, memory)

    envelope = governor.govern(
        tool="memory",
        action="respond",
        target=subject,
        execute_fn=_execute,
        parameters={
            "scope": memory.scope,
            "consent": memory.consent,
            "memory_hash": memory.meta_hash,
            "entry500_confidence": verification.confidence,
            "requester_scope": requester_scope or memory.scope,
            "requester_consent": requester_consent or memory.consent,
            "response_text": response_text,
        },
        source=IntentSource.AGENT,
        agent_id=identity.agent_id,
        model_output_raw=memory.text,
    )
    return GovernanceReport(envelope)
