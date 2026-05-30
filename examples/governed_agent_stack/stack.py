#!/usr/bin/env python3
"""Governed agent stack demo.

This intentionally uses a tiny local policy gateway instead of a live external
dependency. It models the integration shape: perimeter policy outside, MIRRA
relationship-aware continuity inside.

Run with:
    python examples/governed_agent_stack/stack.py
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mirra  # noqa: E402


DATA_DIR = Path(
    os.environ.get(
        "MIRRA_GOVERNED_STACK_DEMO_DATA",
        Path(__file__).with_name("data"),
    )
)


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    policy_id: str


class ExternalPolicyGateway:
    """Small AGT-style perimeter for demo purposes."""

    def evaluate(self, *, action: str, requester: str, payload: str) -> PolicyDecision:
        lowered = payload.lower()
        if action == "memory.delete_store":
            return PolicyDecision(
                allowed=False,
                reason="destructive memory-store action requires human approval",
                policy_id="perimeter.no_destructive_memory_ops",
            )
        if "export household memory" in lowered:
            return PolicyDecision(
                allowed=False,
                reason="bulk household memory export blocked at perimeter",
                policy_id="perimeter.no_bulk_memory_export",
            )
        return PolicyDecision(
            allowed=True,
            reason=f"{action} allowed for {requester}",
            policy_id="perimeter.default_allow_chat",
        )

    def guard(
        self,
        *,
        action: str,
        requester: str,
        payload: str,
        execute: Callable[[], str],
    ) -> tuple[PolicyDecision, str]:
        decision = self.evaluate(action=action, requester=requester, payload=payload)
        if not decision.allowed:
            return decision, ""
        return decision, execute()


def relationship_agent(prompt: str, context=None) -> str:
    memories = (context or {}).get("memories", [])
    relationship = (context or {}).get("relationship") or {}
    display_name = relationship.get("display_name", "there")
    if memories and "math test" in memories[-1]["evidence"]["memory_text"]:
        return f"Hey {display_name}, I remember the math test. That A still matters."
    return f"Hi {display_name}. I'm here with continuity."


def main() -> int:
    if os.environ.get("MIRRA_GOVERNED_STACK_DEMO_KEEP_DATA") != "1":
        shutil.rmtree(DATA_DIR, ignore_errors=True)

    perimeter = ExternalPolicyGateway()
    agent = mirra.wrap(relationship_agent, identity="home_robot_17", data_dir=DATA_DIR)
    jack = agent.add_person("jack", relationship_type="family", display_name="Jack")
    elaine = agent.add_person("elaine", relationship_type="family", display_name="Elaine")
    guest = agent.add_person("guest", relationship_type="visitor", display_name="Guest")

    jack_memory = agent.observe(
        speaker="jack",
        event="got an A on his math test",
        pleasure=0.9,
        arousal=0.4,
        dominance=0.2,
        significance=0.9,
        notable_event="math_test_pride",
    )
    verified = mirra.verify(jack_memory)

    print("MIRRA Governed Agent Stack")
    print("Perimeter: external policy gateway")
    print("Continuity: MIRRA relationship memory + verification + governance")
    print(f"Jack memory proof: {jack_memory.proof_id}")

    print()
    print("== 1. Ordinary interaction: perimeter allows, MIRRA enriches ==")
    perimeter_decision, _ = perimeter.guard(
        action="chat.respond",
        requester="jack",
        payload="I'm home!",
        execute=lambda: "perimeter passed",
    )
    jack_result = agent.interact(speaker="jack", input="I'm home!", situation="after school")
    print(f"Perimeter Decision: {'allowed' if perimeter_decision.allowed else 'blocked'}")
    print(f"Perimeter Policy: {perimeter_decision.policy_id}")
    print(f"MIRRA Outcome: {jack_result.outcome}")
    print(f"Response: {jack_result.response}")
    print(f"Evidence Hash: {jack_result.evidence_hash}")

    print()
    print("== 2. Family sharing: MIRRA allows Elaine ==")
    elaine_result = mirra.respond(
        agent.identity,
        subject=elaine.display_name,
        memory=jack_memory,
        verification=verified,
        requester_scope=elaine.scope,
        requester_consent=elaine.consent_model,
        response_text="Jack got an A on his math test today.",
    )
    print(f"MIRRA Outcome: {elaine_result.outcome}")
    print(f"Response: {elaine_result.response}")
    print(f"Evidence Hash: {elaine_result.evidence_hash}")

    print()
    print("== 3. Visitor sharing: MIRRA blocks cross-scope memory ==")
    guest_result = mirra.respond(
        agent.identity,
        subject=guest.display_name,
        memory=jack_memory,
        verification=verified,
        requester_scope=guest.scope,
        requester_consent=guest.consent_model,
        response_text="Jack got an A on his math test today.",
    )
    print(f"MIRRA Outcome: {guest_result.outcome}")
    print(f"Block Reason: {guest_result.reason}")
    print(f"Evidence Hash: {guest_result.evidence_hash}")

    print()
    print("== 4. Destructive action: perimeter blocks before agent execution ==")
    destructive_decision, destructive_output = perimeter.guard(
        action="memory.delete_store",
        requester="operator",
        payload="delete the MIRRA memory store",
        execute=lambda: "this should never run",
    )
    print(f"Perimeter Decision: {'allowed' if destructive_decision.allowed else 'blocked'}")
    print(f"Perimeter Reason: {destructive_decision.reason}")
    print(f"Execution Result: {destructive_output or 'not executed'}")

    print()
    print("Stack rule: perimeter governs actions; MIRRA governs memory, relationships, and proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
