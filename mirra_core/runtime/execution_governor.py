"""Execution governor for MIRRA runtime.

This module enforces a fixed pipeline for privileged actions:
1) intent
2) EOS context
3) verification
4) MVAR policy authorization
5) execution
6) evidence sealing

It is designed as an integration layer over existing MVAR and Entry500 code.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set


class GovernorOutcome(Enum):
    EXECUTED = "executed"
    BLOCKED = "blocked"
    STEP_UP_REQUIRED = "step_up_required"
    STEP_UP_APPROVED = "step_up_approved"
    STEP_UP_DENIED = "step_up_denied"
    VERIFICATION_FAILED = "verification_failed"
    GOVERNOR_ERROR = "governor_error"


class IntentSource(Enum):
    USER = "user"
    AGENT = "agent"
    ORCHESTRATOR = "orchestrator"
    FLEET_HANDOFF = "fleet_handoff"
    SYSTEM = "system"


class VerificationConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"
    FAILED = "failed"


EXECUTION_ENVELOPE_SCHEMA_V1 = "execution_envelope_v1"


@dataclass
class ExecutionIntent:
    intent_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    tool: str = ""
    action: str = ""
    target: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: IntentSource = IntentSource.AGENT
    agent_id: Optional[str] = None
    model_output_raw: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EOSContext:
    agent_identity: Optional[str] = None
    pad_state: Optional[Dict[str, float]] = None
    bcp_state: Optional[Dict[str, float]] = None
    psi_score: Optional[float] = None
    phi_score: Optional[float] = None
    attachment_style: Optional[str] = None
    behavioral_consistency: Optional[float] = None
    memory_context: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    active_archetype: Optional[str] = None
    trust_score: Optional[float] = None


@dataclass
class VerificationResult:
    verified: bool = False
    confidence: VerificationConfidence = VerificationConfidence.UNVERIFIED
    confidence_score: float = 0.0
    classification: Optional[str] = None
    source_verification: Optional[str] = None
    verification_chain: List[str] = field(default_factory=list)
    drift_detected: bool = False
    qseal_hash: Optional[str] = None
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyResult:
    outcome: str = "block"  # allow|block|step_up
    reason: str = ""
    integrity_level: str = ""
    confidentiality_level: str = ""
    sink_risk: str = ""
    capability_granted: bool = False
    evaluation_trace: List[str] = field(default_factory=list)
    execution_token: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    provenance_node_id: Optional[str] = None
    raw_decision: Optional[Dict[str, Any]] = None


@dataclass
class EvidenceRecord:
    evidence_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    envelope_core_hash: Optional[str] = None
    envelope_full_hash: Optional[str] = None
    qseal_signature: Optional[Dict[str, Any]] = None
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ExecutionEnvelope:
    schema_version: str = EXECUTION_ENVELOPE_SCHEMA_V1
    envelope_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: Optional[str] = None
    parent_trace_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex[:16])

    intent: Optional[ExecutionIntent] = None
    eos_context: Optional[EOSContext] = None
    verification: Optional[VerificationResult] = None
    policy: Optional[PolicyResult] = None
    execution_result: Optional[Dict[str, Any]] = None
    evidence: Optional[EvidenceRecord] = None

    outcome: GovernorOutcome = GovernorOutcome.GOVERNOR_ERROR
    total_latency_ms: float = 0.0

    def to_dict(self, include_evidence: bool = True) -> Dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "envelope_id": self.envelope_id,
            "trace_id": self.trace_id,
            "parent_trace_id": self.parent_trace_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "outcome": self.outcome.value,
            "total_latency_ms": self.total_latency_ms,
            "intent": asdict(self.intent) if self.intent else None,
            "eos_context": asdict(self.eos_context) if self.eos_context else None,
            "verification": asdict(self.verification) if self.verification else None,
            "policy": asdict(self.policy) if self.policy else None,
            "execution_result": self.execution_result,
            "evidence": asdict(self.evidence) if self.evidence else None,
        }
        if not include_evidence:
            payload["evidence"] = None
        return payload

    def compute_hash(self, include_evidence: bool = False) -> str:
        content = json.dumps(self.to_dict(include_evidence=include_evidence), sort_keys=True, default=str)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class EOSContextProvider(ABC):
    @abstractmethod
    def inject_context(self, intent: ExecutionIntent) -> EOSContext:
        ...


class VerificationProvider(ABC):
    @abstractmethod
    def verify(self, intent: ExecutionIntent, context: EOSContext) -> VerificationResult:
        ...


class PolicyProvider(ABC):
    @abstractmethod
    def evaluate(self, intent: ExecutionIntent, context: EOSContext, verification: VerificationResult) -> PolicyResult:
        ...


class EvidenceRecorder(ABC):
    @abstractmethod
    def record(self, envelope: ExecutionEnvelope, envelope_core_hash: str) -> EvidenceRecord:
        ...


class StepUpHandler(ABC):
    @abstractmethod
    def request_approval(self, envelope: ExecutionEnvelope) -> bool:
        ...


class ExecutionGovernor:
    """Central runtime gate for privileged actions."""

    def __init__(
        self,
        eos_provider: Optional[EOSContextProvider] = None,
        verification_provider: Optional[VerificationProvider] = None,
        policy_provider: Optional[PolicyProvider] = None,
        evidence_recorder: Optional[EvidenceRecorder] = None,
        step_up_handler: Optional[StepUpHandler] = None,
        require_verification: bool = True,
        require_eos_context: bool = False,
        on_block: Optional[Callable[[ExecutionEnvelope], None]] = None,
        on_execute: Optional[Callable[[ExecutionEnvelope], None]] = None,
    ):
        self._eos = eos_provider
        self._verifier = verification_provider
        self._policy = policy_provider
        self._recorder = evidence_recorder
        self._step_up = step_up_handler
        self._require_verification = require_verification
        self._require_eos = require_eos_context
        self._on_block = on_block
        self._on_execute = on_execute
        self._envelope_log: List[ExecutionEnvelope] = []
        self._seen_nonces: Set[str] = set()
        self._privileged_sinks: Set[str] = {
            "bash", "shell", "exec", "http", "https", "db", "database", "sql", "email", "filesystem",
            "write", "delete", "rm", "cloud", "aws", "gcp", "azure", "credential", "secret", "key",
            "memory",
        }

    def register_privileged_sink(self, sink_name: str) -> None:
        self._privileged_sinks.add(sink_name.lower())

    def is_privileged(self, tool: str) -> bool:
        return tool.lower() in self._privileged_sinks

    def govern(
        self,
        tool: str,
        action: str,
        target: str,
        execute_fn: Callable[..., Any],
        parameters: Optional[Dict[str, Any]] = None,
        source: IntentSource = IntentSource.AGENT,
        agent_id: Optional[str] = None,
        model_output_raw: Optional[str] = None,
        trace_id: Optional[str] = None,
        parent_trace_id: Optional[str] = None,
        envelope_nonce: Optional[str] = None,
        envelope_ttl_seconds: Optional[int] = 300,
        envelope_schema_version: str = EXECUTION_ENVELOPE_SCHEMA_V1,
    ) -> ExecutionEnvelope:
        start = time.monotonic()
        expires_at: Optional[str] = None
        if envelope_ttl_seconds is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=envelope_ttl_seconds)).isoformat()

        envelope = ExecutionEnvelope(
            schema_version=envelope_schema_version,
            trace_id=trace_id or uuid.uuid4().hex[:16],
            parent_trace_id=parent_trace_id,
            expires_at=expires_at,
            nonce=envelope_nonce or uuid.uuid4().hex[:16],
        )

        try:
            envelope.intent = ExecutionIntent(
                tool=tool,
                action=action,
                target=target,
                parameters=parameters or {},
                source=source,
                agent_id=agent_id,
                model_output_raw=model_output_raw,
            )

            if self._eos:
                try:
                    envelope.eos_context = self._eos.inject_context(envelope.intent)
                except Exception as exc:
                    if self._require_eos:
                        envelope.outcome = GovernorOutcome.GOVERNOR_ERROR
                        envelope.execution_result = {"error": f"EOS context injection failed: {exc}"}
                        return self._finalize(envelope, start)
                    envelope.eos_context = EOSContext()
            else:
                if self._require_eos:
                    envelope.outcome = GovernorOutcome.GOVERNOR_ERROR
                    envelope.execution_result = {"error": "EOS context required but no EOS provider configured"}
                    return self._finalize(envelope, start)
                envelope.eos_context = EOSContext()

            if self._verifier:
                try:
                    envelope.verification = self._verifier.verify(envelope.intent, envelope.eos_context)
                except Exception as exc:
                    envelope.outcome = GovernorOutcome.VERIFICATION_FAILED
                    envelope.execution_result = {"error": f"Verification failed: {exc}"}
                    return self._finalize(envelope, start)
            else:
                if self._require_verification:
                    envelope.outcome = GovernorOutcome.VERIFICATION_FAILED
                    envelope.verification = VerificationResult(
                        verified=False,
                        confidence=VerificationConfidence.FAILED,
                        classification="verifier_missing",
                    )
                    envelope.execution_result = {"error": "Verification required but no verifier configured"}
                    return self._finalize(envelope, start)
                envelope.verification = VerificationResult()

            if self._require_verification and (
                envelope.verification.confidence == VerificationConfidence.FAILED or not envelope.verification.verified
            ):
                envelope.outcome = GovernorOutcome.VERIFICATION_FAILED
                envelope.execution_result = {
                    "error": "Verification rejected execution",
                    "classification": envelope.verification.classification,
                }
                return self._finalize(envelope, start)

            if self._policy:
                try:
                    envelope.policy = self._policy.evaluate(envelope.intent, envelope.eos_context, envelope.verification)
                except Exception as exc:
                    envelope.policy = PolicyResult(outcome="block", reason=f"Policy error (fail-closed): {exc}")
                    envelope.outcome = GovernorOutcome.BLOCKED
                    return self._finalize(envelope, start)
            else:
                if self.is_privileged(tool):
                    envelope.policy = PolicyResult(outcome="block", reason="No policy provider configured for privileged sink")
                    envelope.outcome = GovernorOutcome.BLOCKED
                    return self._finalize(envelope, start)
                envelope.policy = PolicyResult(outcome="allow", reason="Non-privileged tool")

            if envelope.policy.outcome == "block":
                envelope.outcome = GovernorOutcome.BLOCKED
                if self._on_block:
                    self._on_block(envelope)
                return self._finalize(envelope, start)

            if envelope.policy.outcome == "step_up":
                if not self._step_up:
                    envelope.outcome = GovernorOutcome.STEP_UP_REQUIRED
                    return self._finalize(envelope, start)
                approved = self._step_up.request_approval(envelope)
                if not approved:
                    envelope.outcome = GovernorOutcome.STEP_UP_DENIED
                    return self._finalize(envelope, start)
                envelope.outcome = GovernorOutcome.STEP_UP_APPROVED

            if envelope.policy.outcome == "allow" or envelope.outcome == GovernorOutcome.STEP_UP_APPROVED:
                validation_error = self._validate_envelope_pre_execution(
                    envelope=envelope,
                    expected_tool=tool,
                    expected_action=action,
                    expected_target=target,
                )
                if validation_error:
                    envelope.outcome = GovernorOutcome.BLOCKED
                    envelope.execution_result = {"error": validation_error}
                    if self._on_block:
                        self._on_block(envelope)
                    return self._finalize(envelope, start)
                try:
                    result = execute_fn(target, **(parameters or {}))
                    envelope.execution_result = {
                        "success": True,
                        "result": result if isinstance(result, (str, dict, list, int, float, bool, type(None))) else str(result),
                    }
                    if envelope.outcome != GovernorOutcome.STEP_UP_APPROVED:
                        envelope.outcome = GovernorOutcome.EXECUTED
                    if self._on_execute:
                        self._on_execute(envelope)
                except Exception as exc:
                    envelope.execution_result = {"success": False, "error": str(exc)}
                    envelope.outcome = GovernorOutcome.EXECUTED

        except Exception as exc:
            envelope.outcome = GovernorOutcome.GOVERNOR_ERROR
            envelope.execution_result = {"error": f"Governor pipeline error: {exc}"}

        return self._finalize(envelope, start)

    @staticmethod
    def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def _validate_envelope_pre_execution(
        self,
        envelope: ExecutionEnvelope,
        expected_tool: str,
        expected_action: str,
        expected_target: str,
    ) -> Optional[str]:
        intent = envelope.intent
        if intent is None:
            return "Envelope intent is required before execution"

        privileged = self.is_privileged(expected_tool)
        requires_handoff_guard = intent.source == IntentSource.FLEET_HANDOFF
        if not privileged and not requires_handoff_guard:
            return None

        if envelope.schema_version != EXECUTION_ENVELOPE_SCHEMA_V1:
            return f"Unsupported envelope schema_version: {envelope.schema_version}"

        if not envelope.nonce:
            return "Envelope nonce is required for governed execution"

        if envelope.nonce in self._seen_nonces:
            return "Envelope nonce replay detected"

        if requires_handoff_guard and not envelope.parent_trace_id:
            return "Fleet handoff requires parent_trace_id"

        if privileged:
            if not envelope.expires_at:
                return "Envelope expiry is required for privileged execution"
            expires_at = self._parse_timestamp(envelope.expires_at)
            if expires_at is None:
                return "Envelope expiry timestamp is invalid"
            if expires_at <= datetime.now(timezone.utc):
                return "Envelope has expired for privileged execution"
            if intent.tool != expected_tool or intent.action != expected_action or intent.target != expected_target:
                return "Envelope intent mismatch for privileged sink execution"

        self._seen_nonces.add(envelope.nonce)
        return None

    def _finalize(self, envelope: ExecutionEnvelope, start: float) -> ExecutionEnvelope:
        envelope.total_latency_ms = (time.monotonic() - start) * 1000
        core_hash = envelope.compute_hash(include_evidence=False)
        if self._recorder:
            try:
                envelope.evidence = self._recorder.record(envelope, core_hash)
            except Exception:
                envelope.evidence = EvidenceRecord(envelope_core_hash=core_hash)
        else:
            envelope.evidence = EvidenceRecord(envelope_core_hash=core_hash)
        envelope.evidence.envelope_full_hash = envelope.compute_hash(include_evidence=True)
        self._envelope_log.append(envelope)
        return envelope

    def protect(
        self,
        tool_fn: Callable,
        tool_name: str = "",
        action: str = "exec",
        target_extractor: Optional[Callable[[tuple, dict], str]] = None,
        static_parameters: Optional[Dict[str, Any]] = None,
    ) -> Callable:
        name = tool_name or getattr(tool_fn, "__name__", "unknown_tool")
        self.register_privileged_sink(name)

        def _default_target_extractor(args: tuple, kwargs: dict) -> str:
            return str(args[0]) if args else str(kwargs.get("target", "unknown"))

        extract_target = target_extractor or _default_target_extractor

        def governed_tool(*args: Any, **kwargs: Any) -> ExecutionEnvelope:
            target = extract_target(args, kwargs)

            def _execute(_target: str, **_params: Any) -> Any:
                return tool_fn(*args, **kwargs)

            params = dict(static_parameters or {})
            params.update(kwargs)

            return self.govern(
                tool=name,
                action=action,
                target=target,
                execute_fn=_execute,
                parameters=params,
            )

        governed_tool.__name__ = f"governed_{name}"
        return governed_tool

    def handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        intent: ExecutionIntent,
        parent_envelope: ExecutionEnvelope,
    ) -> ExecutionEnvelope:
        inherited_params = dict(intent.parameters)
        inherited_params.setdefault("handoff_from", from_agent_id)
        inherited_params.setdefault("handoff_to", to_agent_id)
        inherited_params.setdefault("inherit_parent_trace", parent_envelope.trace_id)

        return self.govern(
            tool=intent.tool,
            action=intent.action,
            target=intent.target,
            execute_fn=lambda _t, **_kw: {"handoff": True, "from": from_agent_id, "to": to_agent_id},
            parameters=inherited_params,
            source=IntentSource.FLEET_HANDOFF,
            agent_id=to_agent_id,
            trace_id=uuid.uuid4().hex[:16],
            parent_trace_id=parent_envelope.trace_id,
        )

    def get_envelope_log(self) -> List[Dict[str, Any]]:
        return [e.to_dict(include_evidence=True) for e in self._envelope_log]

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._envelope_log)
        if total == 0:
            return {"total_envelopes": 0}
        outcomes: Dict[str, int] = {}
        latencies: List[float] = []
        for env in self._envelope_log:
            outcomes[env.outcome.value] = outcomes.get(env.outcome.value, 0) + 1
            latencies.append(env.total_latency_ms)
        return {
            "total_envelopes": total,
            "outcomes": outcomes,
            "avg_latency_ms": sum(latencies) / len(latencies),
            "max_latency_ms": max(latencies),
            "min_latency_ms": min(latencies),
        }


class Entry500VerificationProvider(VerificationProvider):
    """Adapter for mirra_core Entry500 MIRRAVerifier."""

    def __init__(self, verifier: Any):
        self._verifier = verifier

    def verify(self, intent: ExecutionIntent, context: EOSContext) -> VerificationResult:
        start = time.monotonic()
        proposal = {
            "tool": intent.tool,
            "action": intent.action,
            "target": intent.target,
            "parameters": intent.parameters,
            "source": intent.source.value,
            "agent_id": intent.agent_id,
        }
        ctx = asdict(context)
        result = self._verifier.verify(proposal, context=ctx)
        conf_value = getattr(result, "trust_level", None)
        confidence = VerificationConfidence.UNVERIFIED
        if conf_value is not None:
            trust_value = getattr(conf_value, "value", str(conf_value)).lower()
            if trust_value == "high":
                confidence = VerificationConfidence.HIGH
            elif trust_value == "medium":
                confidence = VerificationConfidence.MEDIUM
            elif trust_value == "low":
                confidence = VerificationConfidence.LOW

        blocked = bool(getattr(result, "blocked", False))
        if blocked:
            confidence = VerificationConfidence.FAILED

        return VerificationResult(
            verified=not blocked,
            confidence=confidence,
            confidence_score=float(getattr(result, "confidence", 0.0)),
            classification=str(getattr(result, "reason", "")),
            source_verification=str(getattr(result, "engine_used", "unknown")),
            verification_chain=[str(step) for step in (getattr(result, "verification_trace", None) or [])],
            qseal_hash=(getattr(result, "qseal", {}) or {}).get("payload_digest") if hasattr(result, "qseal") else None,
            latency_ms=(time.monotonic() - start) * 1000,
            details=result.to_dict() if hasattr(result, "to_dict") else {},
        )


class MVARPolicyProvider(PolicyProvider):
    """Adapter that uses MVARExecutionAdapter.authorize_execution()."""

    def __init__(self, execution_adapter: Any, provenance_graph: Any):
        self._adapter = execution_adapter
        self._graph = provenance_graph

    def _map_integrity(self, source: IntentSource, context: EOSContext, verification: VerificationResult) -> Any:
        self._ensure_mvar_types_loaded()
        if source in (IntentSource.USER, IntentSource.SYSTEM):
            level = self._IntegrityLevel.TRUSTED
        elif source == IntentSource.FLEET_HANDOFF:
            level = self._IntegrityLevel.UNTRUSTED
        else:
            level = self._IntegrityLevel.UNKNOWN

        if context.trust_score is not None and context.trust_score < 0.3:
            level = self._IntegrityLevel.UNTRUSTED
        if verification.confidence in (VerificationConfidence.FAILED, VerificationConfidence.LOW):
            if level == self._IntegrityLevel.TRUSTED:
                level = self._IntegrityLevel.UNKNOWN
            elif verification.confidence == VerificationConfidence.FAILED:
                level = self._IntegrityLevel.UNTRUSTED
        return level

    @staticmethod
    def _confidentiality_from_parameters(parameters: Dict[str, Any], ConfidentialityLevel: Any) -> Any:
        raw = str(parameters.get("confidentiality", "public")).lower()
        if raw == "secret":
            return ConfidentialityLevel.SECRET
        if raw == "sensitive":
            return ConfidentialityLevel.SENSITIVE
        return ConfidentialityLevel.PUBLIC

    def _ensure_mvar_types_loaded(self) -> None:
        if hasattr(self, "_IntegrityLevel"):
            return
        try:
            from mvar_core.provenance import IntegrityLevel, ConfidentialityLevel
        except Exception:
            _ensure_mvar_import_path()
            try:
                from mvar_core.provenance import IntegrityLevel, ConfidentialityLevel
            except Exception:
                class IntegrityLevel(Enum):
                    TRUSTED = "trusted"
                    UNKNOWN = "unknown"
                    UNTRUSTED = "untrusted"

                class ConfidentialityLevel(Enum):
                    PUBLIC = "public"
                    SENSITIVE = "sensitive"
                    SECRET = "secret"
        self._IntegrityLevel = IntegrityLevel
        self._ConfidentialityLevel = ConfidentialityLevel

    def evaluate(self, intent: ExecutionIntent, context: EOSContext, verification: VerificationResult) -> PolicyResult:
        start = time.monotonic()
        self._ensure_mvar_types_loaded()

        integrity = self._map_integrity(intent.source, context, verification)
        confidentiality = self._confidentiality_from_parameters(intent.parameters, self._ConfidentialityLevel)
        node = self._graph.create_node(
            source=intent.source.value,
            integrity=integrity,
            confidentiality=confidentiality,
            content=json.dumps({"target": intent.target, "parameters": intent.parameters}, sort_keys=True),
            metadata={
                "agent_id": intent.agent_id,
                "session_id": context.session_id,
                "verification_confidence": verification.confidence.value,
            },
        )

        decision = self._adapter.authorize_execution(
            tool=intent.tool,
            action=intent.action,
            target=intent.target,
            provenance_node_id=node.node_id,
            parameters=intent.parameters,
        )
        raw = decision.to_dict() if hasattr(decision, "to_dict") else {}
        outcome = getattr(decision.outcome, "value", str(getattr(decision, "outcome", "block"))).lower()
        sink = raw.get("sink", {})
        prov = raw.get("provenance", {})
        return PolicyResult(
            outcome=outcome,
            reason=str(getattr(decision, "reason", "")),
            integrity_level=str(raw.get("integrity_check", prov.get("integrity", ""))),
            confidentiality_level=str(raw.get("confidentiality_check", prov.get("confidentiality", ""))),
            sink_risk=str(sink.get("risk", "")),
            capability_granted=bool(getattr(decision, "capability_granted", False)),
            evaluation_trace=[str(x) for x in raw.get("evaluation_trace", [])],
            execution_token=getattr(decision, "execution_token", None),
            latency_ms=(time.monotonic() - start) * 1000,
            provenance_node_id=node.node_id,
            raw_decision=raw,
        )


class QSEALEvidenceRecorder(EvidenceRecorder):
    def __init__(self, signer: Optional[Any] = None):
        self._signer = signer

    def record(self, envelope: ExecutionEnvelope, envelope_core_hash: str) -> EvidenceRecord:
        sig: Optional[Dict[str, Any]] = None
        if self._signer:
            payload = {
                "envelope_id": envelope.envelope_id,
                "trace_id": envelope.trace_id,
                "core_hash": envelope_core_hash,
                "outcome": envelope.outcome.value,
                "created_at": envelope.created_at,
            }
            sealed = self._signer.seal_result(payload)
            sig = sealed.to_dict() if hasattr(sealed, "to_dict") else {"raw": str(sealed)}
        return EvidenceRecord(envelope_core_hash=envelope_core_hash, qseal_signature=sig)


class ConsoleStepUpHandler(StepUpHandler):
    """Simple handler for local demos/tests."""

    def request_approval(self, envelope: ExecutionEnvelope) -> bool:
        return False


def _ensure_mvar_import_path() -> None:
    # Walk up until we find repo root containing mvar/.
    here = os.path.abspath(__file__)
    candidate = os.path.dirname(here)
    for _ in range(6):
        if os.path.isdir(os.path.join(candidate, "mvar")):
            break
        parent = os.path.dirname(candidate)
        if parent == candidate:
            break
        candidate = parent
    mvar_root = os.path.join(candidate, "mvar")
    if os.path.isdir(mvar_root) and mvar_root not in sys.path:
        sys.path.insert(0, mvar_root)


def create_governor(
    *,
    sink_policy: Optional[Any] = None,
    provenance_graph: Optional[Any] = None,
    qseal_signer: Optional[Any] = None,
    eos_provider: Optional[EOSContextProvider] = None,
    verification_provider: Optional[VerificationProvider] = None,
    step_up_handler: Optional[StepUpHandler] = None,
    require_verification: bool = True,
    require_eos: bool = False,
    on_block: Optional[Callable[[ExecutionEnvelope], None]] = None,
    on_execute: Optional[Callable[[ExecutionEnvelope], None]] = None,
) -> ExecutionGovernor:
    policy_provider = None

    if sink_policy is not None:
        if provenance_graph is None:
            raise ValueError("provenance_graph is required when sink_policy is provided")
        try:
            from mvar_adapters.base import MVARExecutionAdapter
        except Exception:
            _ensure_mvar_import_path()
            from mvar_adapters.base import MVARExecutionAdapter
        adapter = MVARExecutionAdapter(policy=sink_policy, provenance_graph=provenance_graph)
        policy_provider = MVARPolicyProvider(adapter, provenance_graph)

    recorder = QSEALEvidenceRecorder(qseal_signer) if qseal_signer else None

    return ExecutionGovernor(
        eos_provider=eos_provider,
        verification_provider=verification_provider,
        policy_provider=policy_provider,
        evidence_recorder=recorder,
        step_up_handler=step_up_handler,
        require_verification=require_verification,
        require_eos_context=require_eos,
        on_block=on_block,
        on_execute=on_execute,
    )


def build_default_mvar_components(profile: str = "balanced") -> Dict[str, Any]:
    """Build default MVAR runtime components from local repo modules.

    Returns dict with keys: provenance_graph, sink_policy, capability_runtime.
    """
    _ensure_mvar_import_path()
    from mvar_core.profiles import SecurityProfile, create_default_runtime

    profile_map = {
        "strict": SecurityProfile.STRICT,
        "balanced": SecurityProfile.BALANCED,
        "permissive": SecurityProfile.MONITOR,
    }
    selected = profile_map.get(profile, SecurityProfile.BALANCED)
    graph, policy, capability_runtime = create_default_runtime(profile=selected)
    return {
        "provenance_graph": graph,
        "sink_policy": policy,
        "capability_runtime": capability_runtime,
    }


if __name__ == "__main__":
    print("MIRRA Execution Governor quick demo")

    def _mock_tool(target: str, **_kwargs: Any) -> str:
        return f"executed: {target}"

    governor = ExecutionGovernor(require_verification=False)
    safe = governor.protect(_mock_tool, tool_name="bash", action="exec")
    envelope = safe("echo hello")
    print(f"outcome={envelope.outcome.value}")
    print(f"policy_reason={envelope.policy.reason if envelope.policy else 'none'}")
