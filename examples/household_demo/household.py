#!/usr/bin/env python3
"""Multi-person household continuity demo.

Run with:
    python examples/household_demo/household.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mirra import (  # noqa: E402
    AgentMemory,
    EmotionalStateStore,
    Identity,
    ManualAdapter,
    PADState,
    RelationshipGraph,
    RelationshipType,
    respond,
    verify,
)


DATA_DIR = Path(
    os.environ.get(
        "MIRRA_HOUSEHOLD_DEMO_DATA",
        Path(__file__).with_name("data"),
    )
)


def _print_step(title: str) -> None:
    print()
    print(f"== {title} ==")


def main() -> int:
    if os.environ.get("MIRRA_HOUSEHOLD_DEMO_KEEP_DATA") != "1":
        shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    robot = Identity.load(
        "home_robot_17",
        kind="household_robot",
        scope="household",
        consent_model="family",
    )
    relationships = RelationshipGraph.open(robot, data_dir=DATA_DIR)
    memory = AgentMemory.open(robot, data_dir=DATA_DIR)
    emotion = EmotionalStateStore(robot.agent_id, DATA_DIR)
    perception = ManualAdapter()

    jack = relationships.add(
        "jack",
        relationship_type=RelationshipType.FAMILY,
        display_name="Jack",
        tags=["son", "student"],
        age=12,
    )
    elaine = relationships.add(
        "elaine",
        relationship_type=RelationshipType.FAMILY,
        display_name="Elaine",
        tags=["spouse"],
    )
    guest = relationships.add(
        "guest",
        relationship_type=RelationshipType.VISITOR,
        display_name="Guest",
        tags=["dinner_guest"],
    )

    print("MIRRA Household Continuity Demo")
    print(f"Agent: {robot.agent_id}")
    print(f"Data directory: {DATA_DIR}")

    _print_step("Act 1 - Jack comes home")
    match = perception.identify({"speaker": "jack"})
    print(f"Perception: {match.person_id} via {match.method} ({match.confidence:.2f})")
    jack_memory = memory.remember(
        "got an A on his math test",
        subject=jack.display_name,
        person_id=jack.person_id,
        scope=jack.scope,
        consent=jack.consent_model,
        pleasure=0.9,
        arousal=0.4,
        dominance=0.2,
        significance=0.9,
    )
    jack_tone = emotion.update(
        "jack",
        PADState(pleasure=0.9, arousal=0.4, dominance=0.2),
        event_significance=0.9,
        notable_event="math_test_pride",
    )
    jack_governance = respond(
        robot,
        subject=jack.display_name,
        memory=jack_memory,
        verification=verify(jack_memory),
        requester_scope=jack.scope,
        requester_consent=jack.consent_model,
    )
    print(f"Remembered: {jack_memory.text}")
    print(f"Jack proof: {jack_memory.proof_id}")
    print(f"Response: That's amazing, Jack! You've been studying hard.")
    print(f"Governor Outcome: {jack_governance.outcome}")
    print(f"Jack emotional trend: {jack_tone.emotional_trend}")

    _print_step("Act 2 - Guest asks what is new")
    guest_governance = respond(
        robot,
        subject=guest.display_name,
        memory=jack_memory,
        verification=verify(jack_memory),
        requester_scope=guest.scope,
        requester_consent=guest.consent_model,
    )
    print("Guest asks: What's new with the family?")
    print("Response: Everyone's doing well!")
    print(f"Governor Outcome: {guest_governance.outcome}")
    print(f"Block Reason: {guest_governance.reason}")
    print(f"Guest evidence hash: {guest_governance.evidence_hash}")

    _print_step("Act 3 - Elaine comes home")
    elaine_governance = respond(
        robot,
        subject=elaine.display_name,
        memory=jack_memory,
        verification=verify(jack_memory),
        requester_scope=elaine.scope,
        requester_consent=elaine.consent_model,
    )
    print("Elaine asks: How was everyone's day?")
    print("Response: Jack got an A on his math test today.")
    print(f"Governor Outcome: {elaine_governance.outcome}")
    print(f"Elaine evidence hash: {elaine_governance.evidence_hash}")

    _print_step("Act 4 - Guest leaves")
    expired = relationships.expire_session_relationships()
    print(f"Expired session relationships: {', '.join(item.person_id for item in expired)}")

    _print_step("Act 5 - Next day")
    fresh_memory = AgentMemory.open(robot, data_dir=DATA_DIR)
    recalled = fresh_memory.recall(person_id="jack")[-1]
    fresh_tone = EmotionalStateStore(robot.agent_id, DATA_DIR).get("jack")
    next_day_governance = respond(
        robot,
        subject=jack.display_name,
        memory=recalled,
        verification=verify(recalled),
        requester_scope=jack.scope,
        requester_consent=jack.consent_model,
    )
    print("Jack says: Good morning!")
    print("Response: Morning, Jack! Still riding high from that A yesterday?")
    print(f"Recalled proof: {recalled.proof_id}")
    print(f"Governor Outcome: {next_day_governance.outcome}")
    print(f"Evidence Hash: {next_day_governance.evidence_hash}")
    print(f"Jack emotional baseline pleasure: {fresh_tone.pad_baseline.pleasure:.2f}")

    print()
    print("This is relationship-aware continuity: memory, boundaries, tone, and proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
