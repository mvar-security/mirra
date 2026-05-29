"""
MIRRA Verification SDK — Core API
==================================

Epistemic verification layer for AI agent proposals.

Design principles:
    - stdlib-only (no external dependencies)
    - Stub/no-op mode when Entry 500 engines unavailable
    - Context is opaque — SDK degrades gracefully on minimal input
    - Every decision is auditable (JSON-serializable outputs)
    - Failure contract:
        BLOCKING  = fail closed (reject on error)
        ADVISORY  = fail open + warning
        MONITOR   = fail open, always

Engine modes (engine= parameter):
    "auto"  — Use real engine if available, else stub. Default.
    "real"  — Use real engine or raise RuntimeError. Never fallbacks silently.
    "stub"  — Always use heuristics, regardless of engine availability.

Usage:
    from mirra_core.consciousness.entry_500.integration import MIRRAVerifier

    verifier = MIRRAVerifier()
    result = verifier.verify(proposal, context)

    if result.blocked:
        raise AgentBlockedError(result.reason)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# QSeal — optional Ed25519 signing (guarded import so api.py stays stdlib-friendly)
try:
    from mirra_core.consciousness.entry_500.integration.qseal import get_default_signer as _get_qseal_signer
    _QSEAL_AVAILABLE = True
except Exception:
    _QSEAL_AVAILABLE = False
    _get_qseal_signer = None  # type: ignore[assignment]

logger = logging.getLogger("mirra.verification")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class VerificationMode(Enum):
    """
    Controls how the verifier responds to low-trust proposals.

    MONITOR  — Observe and log. Never blocks. Fail open.
    ADVISORY — Warn on low-trust proposals. Fail open + warning.
    BLOCKING — Reject low-trust proposals. Fail closed.
    """
    MONITOR = "monitor"
    ADVISORY = "advisory"
    BLOCKING = "blocking"


class TrustLevel(Enum):
    """
    Trust classification for a verified proposal.

    HIGH        — Multiple verification passes, high confidence
    MEDIUM      — Partial verification, acceptable confidence
    LOW         — Verification attempted, low confidence
    UNVERIFIED  — No verification performed (stub mode or no context)
    """
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNVERIFIED = "unverified"


# ---------------------------------------------------------------------------
# Result Types
# ---------------------------------------------------------------------------


@dataclass
class VerificationResult:
    """
    Result of verify(proposal, context).

    Fields:
        trust_level          — Computed trust classification
        confidence           — Float [0.0, 1.0] — higher is more reliable
        blocked              — True only in BLOCKING mode when trust is LOW
        reason               — Human-readable explanation of the decision
        mode                 — Active VerificationMode at time of call
        proposal_digest      — SHA256 of proposal content (for audit trail)
        timestamp            — ISO8601 timestamp of verification
        details              — Optional per-gate breakdown from Entry 500
        stub_mode            — True when Entry 500 engine is unavailable
        warnings             — List of advisory warnings (ADVISORY mode)
        engine_used          — "real" | "stub" — ALWAYS populated.
                               Proof of which verification path ran.
        verification_trace   — List of per-gate dicts from real engine.
                               None in stub mode. Non-empty when engine_used=="real".
    """
    trust_level: TrustLevel
    confidence: float
    blocked: bool
    reason: str
    mode: VerificationMode
    proposal_digest: str
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)
    stub_mode: bool = False
    warnings: List[str] = field(default_factory=list)
    engine_used: str = "stub"                              # "real" | "stub"
    verification_trace: Optional[List[dict]] = None        # real-engine only
    qseal: Optional[Dict[str, Any]] = None                 # QSeal Ed25519 signature (when available)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "trust_level": self.trust_level.value,
            "confidence": self.confidence,
            "blocked": self.blocked,
            "reason": self.reason,
            "mode": self.mode.value,
            "proposal_digest": self.proposal_digest,
            "timestamp": self.timestamp,
            "details": self.details,
            "stub_mode": self.stub_mode,
            "warnings": self.warnings,
            "engine_used": self.engine_used,
            "verification_trace": self.verification_trace,
            "qseal": self.qseal,
        }

    def __repr__(self) -> str:
        status = "BLOCKED" if self.blocked else "ALLOWED"
        return (
            f"VerificationResult({status} | "
            f"trust={self.trust_level.value} | "
            f"confidence={self.confidence:.3f} | "
            f"mode={self.mode.value})"
        )


@dataclass
class AuditResult:
    """
    Result of audit(action, predicted, actual).

    Records the outcome of an agent action against its predicted outcome
    for retrospective reliability tracking.

    Fields:
        action_digest       — SHA256 of action content
        predicted_digest    — SHA256 of predicted outcome
        actual_digest       — SHA256 of actual outcome
        outcome_match       — True if predicted matches actual
        reliability_delta   — Change in reliability estimate [-1.0, 1.0]
        timestamp           — ISO8601 timestamp
        notes               — Additional context or warnings
    """
    action_digest: str
    predicted_digest: str
    actual_digest: str
    outcome_match: bool
    reliability_delta: float
    timestamp: str
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "action_digest": self.action_digest,
            "predicted_digest": self.predicted_digest,
            "actual_digest": self.actual_digest,
            "outcome_match": self.outcome_match,
            "reliability_delta": self.reliability_delta,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }

    def __repr__(self) -> str:
        match_str = "MATCH" if self.outcome_match else "MISMATCH"
        return (
            f"AuditResult({match_str} | "
            f"delta={self.reliability_delta:+.3f})"
        )


@dataclass
class DriftStatus:
    """
    Result of monitor() — current drift and reliability state.

    Fields:
        status              — 'healthy' | 'warning' | 'critical'
        cumulative_drift    — Total drift accumulated this session
        avg_drift_per_cycle — Rolling average drift per evaluation
        active_causes       — Number of verified causal relationships
        gate_open           — Whether stability gate allows updates
        stub_mode           — True when Entry 500 engine unavailable
        timestamp           — ISO8601 timestamp
        thresholds          — Configured drift thresholds
    """
    status: str
    cumulative_drift: float
    avg_drift_per_cycle: float
    active_causes: int
    gate_open: bool
    stub_mode: bool
    timestamp: str
    thresholds: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation."""
        return {
            "status": self.status,
            "cumulative_drift": self.cumulative_drift,
            "avg_drift_per_cycle": self.avg_drift_per_cycle,
            "active_causes": self.active_causes,
            "gate_open": self.gate_open,
            "stub_mode": self.stub_mode,
            "timestamp": self.timestamp,
            "thresholds": self.thresholds,
        }

    def __repr__(self) -> str:
        return (
            f"DriftStatus({self.status.upper()} | "
            f"drift={self.cumulative_drift:.4f} | "
            f"causes={self.active_causes})"
        )


# ---------------------------------------------------------------------------
# Trust Thresholds
# ---------------------------------------------------------------------------

_DEFAULT_THRESHOLDS: Dict[str, float] = {
    "high_confidence": 0.75,
    "medium_confidence": 0.50,
    "block_threshold": 0.40,
    "drift_healthy": 0.05,
    "drift_warning": 0.10,
    "drift_critical": 0.20,
}


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC timestamp in ISO8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(obj: Any) -> str:
    """SHA256 hex digest of JSON-encoded object."""
    try:
        encoded = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    except (TypeError, ValueError):
        encoded = str(obj).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _extract_text(proposal: Any) -> str:
    """
    Extract text content from proposal for heuristic scoring.

    Context is opaque — we degrade gracefully on any shape.
    """
    if isinstance(proposal, str):
        return proposal
    if isinstance(proposal, dict):
        # Accept 'text', 'content', 'proposal', 'action', 'message'
        for key in ("text", "content", "proposal", "action", "message"):
            if key in proposal and isinstance(proposal[key], str):
                return proposal[key]
        # Fallback: concatenate all string values
        return " ".join(v for v in proposal.values() if isinstance(v, str))
    return str(proposal)


def _stub_confidence(proposal: Any) -> float:
    """
    Heuristic confidence score when Entry 500 engine is unavailable.

    Not a real verification — just a structural plausibility check.
    Returns 0.60 (MEDIUM) as conservative default.

    Degrades to 0.45 (borderline LOW) for very short or empty proposals.
    """
    text = _extract_text(proposal)
    if not text or len(text.strip()) < 10:
        return 0.45
    return 0.60


def _classify_trust(confidence: float, thresholds: Dict[str, float]) -> TrustLevel:
    """Map confidence float to TrustLevel enum."""
    if confidence >= thresholds["high_confidence"]:
        return TrustLevel.HIGH
    elif confidence >= thresholds["medium_confidence"]:
        return TrustLevel.MEDIUM
    elif confidence >= 0.0:
        return TrustLevel.LOW
    return TrustLevel.UNVERIFIED


def _should_block(
    trust: TrustLevel,
    confidence: float,
    mode: VerificationMode,
    thresholds: Dict[str, float],
) -> bool:
    """
    Failure contract:
        BLOCKING  → fail closed when confidence < block_threshold
        ADVISORY  → never blocks, emits warning
        MONITOR   → never blocks
    """
    if mode is VerificationMode.BLOCKING:
        return confidence < thresholds["block_threshold"]
    return False


# ---------------------------------------------------------------------------
# Engine Adapter
# ---------------------------------------------------------------------------


class _EngineAdapter:
    """
    Thin adapter between MIRRAVerifier and Entry 500 engines.

    Returns (confidence, details, trace) 3-tuple.
    Falls back to stub mode when engines are unavailable.
    trace is None in stub mode, List[dict] in real mode.
    """

    def __init__(self, engine: Optional[Any]) -> None:
        self._engine = engine
        self._available = self._probe(engine)

    @staticmethod
    def _probe(engine: Optional[Any]) -> bool:
        """Check if engine is present and minimally functional."""
        if engine is None:
            return False
        # Check for required interface methods
        required = ("verify_proposal", "get_drift_status")
        return all(hasattr(engine, m) for m in required)

    @property
    def available(self) -> bool:
        return self._available

    def verify(
        self,
        proposal: Any,
        context: Optional[Dict[str, Any]],
    ) -> "tuple[float, Dict[str, Any], Optional[List[dict]]]":
        """
        Run verification via Entry 500 engine.

        Returns (confidence, details, trace).
        trace is None in stub mode; non-empty List[dict] in real mode.
        Falls back to stub on any error.
        """
        if not self._available:
            return _stub_confidence(proposal), {"engine": "stub"}, None

        try:
            result = self._engine.verify_proposal(
                proposal=proposal,
                context=context or {},
            )
            confidence = float(result.get("confidence", 0.60))
            details = result.get("details", {})
            details["engine"] = "entry500"

            # Extract or synthesise trace from real engine result
            raw_trace = result.get("trace") or result.get("verification_trace")
            if isinstance(raw_trace, list) and raw_trace:
                trace: Optional[List[dict]] = [
                    step if isinstance(step, dict) else {"step": str(step)}
                    for step in raw_trace
                ]
            else:
                # Engine ran but returned no trace — synthesise minimal proof
                trace = [
                    {
                        "gate": "entry500",
                        "confidence": confidence,
                        "details_keys": list(details.keys()),
                    }
                ]
            return confidence, details, trace

        except Exception as exc:
            logger.warning("Entry 500 verify_proposal failed: %s", exc)
            return _stub_confidence(proposal), {"engine": "stub", "error": str(exc)}, None

    def drift(self) -> Dict[str, Any]:
        """Query drift status from engine. Falls back to stub."""
        if not self._available:
            return {
                "cumulative_drift": 0.0,
                "avg_drift_per_cycle": 0.0,
                "active_causes": 0,
                "gate_open": True,
                "status": "healthy",
            }

        try:
            return self._engine.get_drift_status()
        except Exception as exc:
            logger.warning("Entry 500 get_drift_status failed: %s", exc)
            return {
                "cumulative_drift": 0.0,
                "avg_drift_per_cycle": 0.0,
                "active_causes": 0,
                "gate_open": True,
                "status": "healthy",
                "error": str(exc),
            }

    def record_audit(
        self,
        action: Any,
        predicted: Any,
        actual: Any,
        outcome_match: bool,
    ) -> float:
        """
        Record outcome for retrospective learning.

        Returns reliability_delta float.
        """
        if not self._available:
            return 0.0

        try:
            result = self._engine.record_outcome(
                action=action,
                predicted=predicted,
                actual=actual,
                outcome_match=outcome_match,
            )
            return float(result.get("reliability_delta", 0.0))
        except Exception as exc:
            logger.warning("Entry 500 record_outcome failed: %s", exc)
            return 0.0


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------


_VALID_ENGINE_MODES = frozenset({"auto", "real", "stub"})


class MIRRAVerifier:
    """
    MIRRA Verification SDK — Main Entry Point.

    Epistemic verification for AI agent proposals.

    3-line integration:

        verifier = MIRRAVerifier()
        result = verifier.verify(proposal, context)
        if result.blocked: raise AgentBlockedError(result.reason)

    Args:
        engine:     Engine selection string OR an explicit engine object.
                    String values:
                        "auto"  — Use real engine if available, else stub. Default.
                        "real"  — Use real engine or raise RuntimeError. No silent fallback.
                        "stub"  — Always use heuristics, ignores availability.
                    Object: any object with verify_proposal() + get_drift_status() methods.
                    When None, behaves as "auto".
        mode:       VerificationMode. Default: MONITOR.
                    Start here — switch to ADVISORY or BLOCKING as needed.
        thresholds: Optional confidence threshold overrides.

    Raises:
        ValueError:     If engine is a string not in {"auto", "real", "stub"}.
        RuntimeError:   If engine="real" and Entry 500 engine cannot be loaded.
    """

    def __init__(
        self,
        engine: Optional[Any] = None,
        mode: VerificationMode = VerificationMode.MONITOR,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        self._mode = mode
        self._thresholds = {**_DEFAULT_THRESHOLDS, **(thresholds or {})}

        # Resolve engine mode string
        if isinstance(engine, str):
            engine_mode = engine.lower()
            if engine_mode not in _VALID_ENGINE_MODES:
                raise ValueError(
                    f"Invalid engine value {engine!r}. "
                    f"Must be one of: {sorted(_VALID_ENGINE_MODES)}"
                )
            self._engine_mode: str = engine_mode
            engine_obj = self._load_real_engine() if engine_mode != "stub" else None
            if engine_mode == "stub":
                self._adapter = _EngineAdapter(None)
            elif engine_mode == "real":
                if engine_obj is None:
                    raise RuntimeError(
                        "engine='real' requested but Entry 500 engine could not be loaded. "
                        "Ensure mirra_core.consciousness.entry_500.engine is importable "
                        "and build_default_engine() returns a non-None engine."
                    )
                self._adapter = _EngineAdapter(engine_obj)
            else:  # "auto"
                self._adapter = _EngineAdapter(engine_obj)
        else:
            # Explicit engine object (or None) — legacy path, behaves as "auto"
            self._engine_mode = "auto"
            self._adapter = _EngineAdapter(engine)

        if not self._adapter.available:
            logger.info(
                "MIRRAVerifier: Entry 500 engine unavailable — running in stub mode. "
                "Attach engine or use engine='real' for full epistemic verification."
            )

    # ------------------------------------------------------------------
    # Engine loader — called once at init, result cached via _adapter
    # ------------------------------------------------------------------

    @staticmethod
    def _load_real_engine() -> Optional[Any]:
        """
        Attempt to load the Entry 500 real engine.

        Tries build_default_engine() from the engine module.
        Returns the engine object on success, None on any import/build failure.
        Never raises — caller decides what to do with None.
        """
        try:
            from mirra_core.consciousness.entry_500.integration.engine import (  # type: ignore[import]
                build_default_engine,
            )
            engine_obj = build_default_engine()
            if engine_obj is None:
                logger.debug("_load_real_engine: build_default_engine() returned None")
            return engine_obj
        except Exception as exc:
            logger.debug("_load_real_engine: could not load Entry 500 engine: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Public API — verify
    # ------------------------------------------------------------------

    def verify(
        self,
        proposal: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify a proposal before it executes.

        Args:
            proposal:   The agent's proposed action or output.
                        Accepts str, dict, or any JSON-serializable type.
                        Context is opaque — SDK degrades gracefully.
            context:    Optional agent state or environmental context.
                        Minimal context is fine. SDK does not require
                        specific schema.

        Returns:
            VerificationResult with trust_level, confidence, blocked flag.

        Failure contract:
            BLOCKING mode  → blocked=True when confidence < block_threshold
            ADVISORY mode  → blocked=False, warnings populated
            MONITOR mode   → blocked=False, always

        On engine error:
            BLOCKING  → fail closed (blocked=True, reason explains)
            ADVISORY  → fail open, warning added
            MONITOR   → fail open, logged
        """
        timestamp = _now_iso()
        proposal_digest = _digest(proposal)
        stub_mode = not self._adapter.available
        warn_list: List[str] = []

        # Run verification
        try:
            confidence, details, trace = self._adapter.verify(proposal, context)
        except Exception as exc:
            # Unexpected adapter error — apply failure contract
            logger.error("MIRRAVerifier.verify: unexpected error: %s", exc)
            return self._error_result(
                exc, proposal_digest, timestamp, stub_mode
            )

        # Determine engine_used from trace presence
        engine_used = "real" if trace is not None else "stub"

        # Semantic trace invariant: real engine MUST produce non-empty list of non-empty dicts
        if engine_used == "real":
            if not isinstance(trace, list) or len(trace) == 0:
                raise RuntimeError(
                    "Real engine produced empty verification_trace. "
                    "This violates the semantic trace invariant."
                )
            if not all(isinstance(step, dict) and len(step) > 0 for step in trace):
                raise RuntimeError(
                    "Real engine produced verification_trace with empty or non-dict steps. "
                    "This violates the semantic trace invariant."
                )

        # Classify trust
        trust = _classify_trust(confidence, self._thresholds)

        # Apply mode logic
        blocked = _should_block(trust, confidence, self._mode, self._thresholds)

        # Build reason
        if blocked:
            reason = (
                f"Proposal blocked: confidence {confidence:.3f} below "
                f"threshold {self._thresholds['block_threshold']:.3f}. "
                f"Trust level: {trust.value.upper()}."
            )
        elif trust is TrustLevel.LOW and self._mode is VerificationMode.ADVISORY:
            reason = (
                f"Low-trust proposal (confidence {confidence:.3f}). "
                f"Proceeding with advisory warning."
            )
            warn_list.append(
                f"Advisory: proposal confidence {confidence:.3f} below "
                f"medium threshold {self._thresholds['medium_confidence']:.3f}"
            )
            warnings.warn(
                f"MIRRA Advisory: low-trust proposal detected "
                f"(confidence={confidence:.3f})",
                stacklevel=2,
            )
        else:
            reason = (
                f"Proposal verified. Trust: {trust.value.upper()}, "
                f"confidence: {confidence:.3f}."
            )

        if stub_mode and not blocked:
            warn_list.append(
                "Stub mode: Entry 500 engine unavailable. "
                "Confidence is heuristic, not verified."
            )

        log_fn = logger.warning if blocked else logger.debug
        log_fn(
            "verify: digest=%s trust=%s confidence=%.3f blocked=%s mode=%s engine=%s",
            proposal_digest[:12],
            trust.value,
            confidence,
            blocked,
            self._mode.value,
            engine_used,
        )

        # --- QSeal: sign this result if Ed25519 is available ---
        qseal_dict: Optional[Dict[str, Any]] = None
        if _QSEAL_AVAILABLE and _get_qseal_signer is not None:
            try:
                _partial = {
                    "proposal_digest": proposal_digest,
                    "confidence": confidence,
                    "trust_level": trust.value,
                    "blocked": blocked,
                    "engine_used": engine_used,
                    "timestamp": timestamp,
                    "mode": self._mode.value,
                    "stub_mode": stub_mode,
                    "verification_trace": trace,
                }
                # Hardening B: include snapshot provenance in signed payload so
                # the seal cryptographically proves which substrate state was used.
                _live = details.get("live_state", {}) if details else {}
                if _live.get("source") == "snapshot":
                    _partial["snapshot_path"] = _live.get("snapshot_path", "")
                    _partial["snapshot_digest"] = _live.get("snapshot_digest", "")
                    _partial["snapshot_mtime"] = _live.get("snapshot_mtime", 0.0)
                _seal = _get_qseal_signer().seal_result(_partial)
                qseal_dict = _seal.to_dict()
                logger.debug(
                    "QSeal attached: algorithm=%s verified=%s sig=%s...",
                    _seal.algorithm,
                    _seal.verified,
                    _seal.signature_hex[:16],
                )
            except Exception as _qseal_exc:
                logger.warning("QSeal signing failed (non-fatal): %s", _qseal_exc)

        return VerificationResult(
            trust_level=trust,
            confidence=confidence,
            blocked=blocked,
            reason=reason,
            mode=self._mode,
            proposal_digest=proposal_digest,
            timestamp=timestamp,
            details=details,
            stub_mode=stub_mode,
            warnings=warn_list,
            engine_used=engine_used,
            verification_trace=trace,
            qseal=qseal_dict,
        )

    # ------------------------------------------------------------------
    # Public API — audit
    # ------------------------------------------------------------------

    def audit(
        self,
        action: Any,
        predicted: Any,
        actual: Any,
    ) -> AuditResult:
        """
        Record the outcome of an executed action against its prediction.

        Use after an action completes to feed retrospective learning.
        Works in stub mode — records digests even without engine.

        Args:
            action:     The action that was executed.
            predicted:  The predicted outcome at execution time.
            actual:     The observed outcome after execution.

        Returns:
            AuditResult with outcome_match and reliability_delta.
        """
        timestamp = _now_iso()
        action_digest = _digest(action)
        predicted_digest = _digest(predicted)
        actual_digest = _digest(actual)

        # Structural match check (digest-level)
        outcome_match = predicted_digest == actual_digest

        # Engine-level reliability learning
        reliability_delta = self._adapter.record_audit(
            action, predicted, actual, outcome_match
        )

        notes: List[str] = []
        if not self._adapter.available:
            notes.append(
                "Stub mode: reliability_delta is 0.0 (no engine). "
                "Attach Entry 500 engine for retrospective learning."
            )

        if not outcome_match:
            notes.append(
                "Outcome mismatch recorded. "
                "Retrospective learning update triggered."
            )

        logger.debug(
            "audit: action=%s match=%s delta=%+.3f",
            action_digest[:12],
            outcome_match,
            reliability_delta,
        )

        return AuditResult(
            action_digest=action_digest,
            predicted_digest=predicted_digest,
            actual_digest=actual_digest,
            outcome_match=outcome_match,
            reliability_delta=reliability_delta,
            timestamp=timestamp,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Public API — monitor
    # ------------------------------------------------------------------

    def monitor(self) -> DriftStatus:
        """
        Query current drift and reliability state.

        Safe to call at any cadence — read-only, no side effects.
        Fails open: always returns a valid DriftStatus.

        Returns:
            DriftStatus with current reliability health.
        """
        timestamp = _now_iso()
        stub_mode = not self._adapter.available

        raw = self._adapter.drift()

        cumulative = float(raw.get("cumulative_drift", 0.0))
        avg = float(raw.get("avg_drift_per_cycle", 0.0))
        active_causes = int(raw.get("active_causes", 0))
        gate_open = bool(raw.get("gate_open", True))

        # Classify status
        if avg >= self._thresholds["drift_critical"]:
            status = "critical"
        elif avg >= self._thresholds["drift_warning"]:
            status = "warning"
        else:
            status = "healthy"

        thresholds = {
            "healthy": self._thresholds["drift_healthy"],
            "warning": self._thresholds["drift_warning"],
            "critical": self._thresholds["drift_critical"],
        }

        logger.debug(
            "monitor: status=%s drift=%.4f causes=%d gate=%s stub=%s",
            status,
            cumulative,
            active_causes,
            gate_open,
            stub_mode,
        )

        return DriftStatus(
            status=status,
            cumulative_drift=cumulative,
            avg_drift_per_cycle=avg,
            active_causes=active_causes,
            gate_open=gate_open,
            stub_mode=stub_mode,
            timestamp=timestamp,
            thresholds=thresholds,
        )

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    @property
    def mode(self) -> VerificationMode:
        """Current verification mode."""
        return self._mode

    def set_mode(self, mode: VerificationMode) -> None:
        """
        Switch verification mode at runtime.

        Recommended progression: MONITOR → ADVISORY → BLOCKING
        """
        old = self._mode
        self._mode = mode
        logger.info(
            "MIRRAVerifier: mode changed %s → %s",
            old.value,
            mode.value,
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def stub_mode(self) -> bool:
        """True when running without Entry 500 engine."""
        return not self._adapter.available

    def status(self) -> Dict[str, Any]:
        """
        Return verifier configuration summary.

        Useful for health checks and diagnostics.
        """
        return {
            "mode": self._mode.value,
            "stub_mode": self.stub_mode,
            "thresholds": self._thresholds,
            "engine_available": self._adapter.available,
            "engine_mode": self._engine_mode,
            "sdk_version": "1.0.0",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _error_result(
        self,
        exc: Exception,
        proposal_digest: str,
        timestamp: str,
        stub_mode: bool,
    ) -> VerificationResult:
        """
        Build error VerificationResult applying failure contract.

        BLOCKING → fail closed (blocked=True)
        ADVISORY → fail open, warning
        MONITOR  → fail open, logged
        """
        blocked = self._mode is VerificationMode.BLOCKING
        confidence = 0.0 if blocked else 0.50
        trust = TrustLevel.UNVERIFIED if blocked else TrustLevel.MEDIUM

        reason = (
            f"Verification error: {exc}. "
            + (
                "Proposal blocked (BLOCKING mode, fail closed)."
                if blocked
                else "Proceeding with unverified status (fail open)."
            )
        )

        warn_list = [f"Verification error: {exc}"]
        if not blocked and self._mode is VerificationMode.ADVISORY:
            warnings.warn(
                f"MIRRA Advisory: verification error, proceeding unverified: {exc}",
                stacklevel=3,
            )

        return VerificationResult(
            trust_level=trust,
            confidence=confidence,
            blocked=blocked,
            reason=reason,
            mode=self._mode,
            proposal_digest=proposal_digest,
            timestamp=timestamp,
            details={"error": str(exc)},
            stub_mode=stub_mode,
            warnings=warn_list,
            engine_used="stub",          # error path always stub
            verification_trace=None,
        )
