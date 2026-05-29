#!/usr/bin/env python3
"""
MIRRA Continuity Demo — Home Robot

One command shows the continuity substrate:
1. Agent identity creation (QSEAL signed)
2. Signed memory write (BCP/ICP store)
3. Memory recall from persisted storage
4. Verification (Entry 500)
5. Governed response (Execution Governor)
6. Human-readable provenance output

No paid API calls. No local LLM weights. No MIRRA_PRIME required.

Usage:
    python3 examples/continuity_demo/home_robot.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mirra import AgentMemory, Identity, respond, verify


DEMO_DATA_DIR = Path(
    os.environ.get(
        "MIRRA_CONTINUITY_DEMO_DATA",
        PROJECT_ROOT / "examples" / "continuity_demo" / "data",
    )
)


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


def main() -> None:
    print_section("MIRRA Continuity Demo — Home Robot")

    print_section("1. Agent Identity")
    agent = Identity.load(
        "home_robot_17",
        kind="household_assistant",
        scope="household",
        consent_model="family",
    )

    print(f"Agent ID: {agent.agent_id}")
    print(f"Type: {agent.kind}")
    print(f"Scope: {agent.scope}")
    print(f"Consent Model: {agent.consent_model}")
    print(f"QSEAL Signature: {agent.qseal_signature[:32]}...")
    print("✅ Identity created and signed")

    print_section("2. Signed Memory Write")
    memory_store = AgentMemory.open(agent, data_dir=DEMO_DATA_DIR)
    subject = "Jack"
    event = "Jack had a math test today"

    memory_store.remember(
        event,
        subject=subject,
        scope="household",
        consent="family",
    )

    # Simulate a fresh process/session before recall.
    fresh_store = AgentMemory.open(agent, data_dir=DEMO_DATA_DIR)
    recalled = fresh_store.recall(subject=subject)
    if not recalled:
        raise RuntimeError(f"No persisted memories found for {subject}")
    memory = recalled[-1]

    print(f"Subject: {subject}")
    print(f"Event: {event}")
    print(f"Memory Hash: {memory.meta_hash[:32]}...")
    print(f"Memory QSEAL: {memory.qseal_signature[:32]}...")
    print(f"PAD State: P={memory.raw['pad_after']['pleasure']:.2f}, A={memory.raw['pad_after']['arousal']:.2f}, D={memory.raw['pad_after']['dominance']:.2f}")
    print(f"RNT Metrics: R={memory.raw['rnt']['resonance']:.2f}, N={memory.raw['rnt']['novelty']:.2f}, T={memory.raw['rnt']['transferability']:.2f}")
    print("✅ Memory written and signed")

    print_section("3. Memory Recall")
    print(f"Recalled: {memory.text}")
    print(f"Memory Hash: {memory.meta_hash[:32]}...")
    print(f"PAD Snapshot: P={memory.raw['pad_after']['pleasure']:.2f}")
    print(f"✅ Memory recalled for {subject}")

    print_section("4. Verification (Entry 500)")
    verification = verify(memory, engine="stub")

    print(f"Engine Used: {verification.engine_used}")
    print(f"Confidence: {verification.confidence:.2f}")
    print(f"Trust Level: {verification.trust_level}")
    print(f"Stub Mode: {verification.stub_mode}")
    print("✅ Memory verified")

    print_section("5. Governance")
    governance = respond(agent, subject=subject, memory=memory, verification=verification)

    print(f"Allowed: {governance.allowed}")
    print(f"Reason: {governance.reason}")
    print(f"Governor Outcome: {governance.outcome}")
    print(f"Scope: {memory.scope}")
    print(f"Consent: {memory.consent}")
    print(f"Verification Confidence: {verification.confidence:.2f}")
    print(f"Evidence Hash: {governance.evidence_hash[:32]}...")
    print("✅ Response governed")

    print_section("6. Response")
    print(f"To: {subject}")
    print(f"Response: {governance.response}")
    print("✅ Response generated")

    print_section("7. Provenance")
    print(f"Proof ID: {memory.proof_id}")
    print(f"Agent: {agent.agent_id}")
    print(f"Subject: {subject}")
    print(f"Memory: {memory.text}")
    print(f"Signature: {memory.meta_hash[:32]}...")
    print(f"Memory QSEAL: {memory.qseal_signature[:32]}...")
    print(f"Verified: {governance.allowed}")
    print(f"Governed: {governance.allowed}")
    print(f"Governor Evidence: {governance.evidence_hash[:32]}...")
    print("✅ Provenance complete")

    print_section("Demo Complete")
    print("✅ Agent identity created and signed")
    print("✅ Memory written with QSEAL signature")
    print("✅ Memory recalled from signed store")
    print("✅ Memory verified through Entry 500")
    print("✅ Response governed by policy layer")
    print("✅ Provenance chain complete")
    print(f"\nFinal Response: \"{governance.response}\"")
    print(f"Proof: {memory.proof_id}")
    print("\n" + "=" * 60)
    print("This is how an agent becomes continuous.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n❌ Demo failed: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
