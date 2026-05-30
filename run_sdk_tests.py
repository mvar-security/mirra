#!/usr/bin/env python3
"""Standalone SDK test runner — no pytest required."""

import os
import re
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

os.environ.setdefault("QSEAL_SECRET", os.popen("openssl rand -hex 32").read().strip())
sys.path.insert(0, str(Path(__file__).parent))

import mirra
from mirra import (
    AgentMemory,
    CallerIDAdapter,
    EmotionalStateStore,
    Identity,
    ManualAdapter,
    PADState,
    RelationshipGraph,
    RelationshipType,
    UsernameAdapter,
    respond,
    verify,
)

passed = 0
failed = 0
errors = []

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except AssertionError as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ✗ {name}: {e}")
    except Exception as e:
        failed += 1
        errors.append((name, traceback.format_exc()))
        print(f"  ✗ {name}: {e}")

print("=" * 70)
print("  MIRRA SDK — Test Suite")
print("=" * 70)
print()

# ── SDK Continuity Loop ─────────────────────────────────────────────

print("SDK Continuity Loop:")

def t_full_loop():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load(
            "home_robot_17",
            kind="household_assistant",
            scope="household",
            consent_model="family",
        )
        memory = AgentMemory.open(agent, data_dir=Path(tmp) / "memory")
        written = memory.remember(
            "Jack had a math test today",
            subject="Jack",
            scope="household",
            consent="family",
        )
        # Reopen from disk
        fresh = AgentMemory.open(agent, data_dir=Path(tmp) / "memory")
        recalled = fresh.recall(subject="Jack")
        assert recalled, "No memories recalled"
        record = recalled[-1]
        assert record.text == "Jack: Jack had a math test today"
        assert record.meta_hash == written.meta_hash
        assert re.fullmatch(r"[a-f0-9]{64}", record.meta_hash)
        assert record.qseal_signature
        assert re.fullmatch(r"qseal://bcp_entry_\d+_[a-f0-9]{16}", record.proof_id)

        verification = verify(record, engine="stub")
        assert verification.confidence > 0.3
        assert verification.engine_used == "stub"

        governance = respond(agent, subject="Jack", memory=record, verification=verification)
        assert governance.allowed
        assert governance.outcome == "executed"
        assert "math test" in governance.response
        assert re.fullmatch(r"[a-f0-9]{64}", governance.evidence_hash)
test("Full continuity loop: write → persist → recall → verify → govern", t_full_loop)

def t_wrong_consent_blocked():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("home_robot_17")
        memory = AgentMemory.open(agent, data_dir=Path(tmp) / "memory")
        record = memory.remember(
            "Jack had a math test today",
            subject="Jack",
            scope="private",
            consent="none",
        )
        verification = verify(record, engine="stub")
        governance = respond(agent, subject="Jack", memory=record, verification=verification)
        assert not governance.allowed
        assert governance.outcome == "blocked"
        assert "does not permit" in governance.reason
test("Wrong consent/scope → governance blocks", t_wrong_consent_blocked)

# ── Identity ────────────────────────────────────────────────────────

print()
print("Identity:")

def t_identity_signed():
    agent = Identity.load("test_agent", kind="assistant", scope="household", consent_model="family")
    assert agent.agent_id == "test_agent"
    assert agent.kind == "assistant"
    assert agent.qseal_signature
    assert len(agent.qseal_signature) > 16
test("Identity.load() creates signed identity", t_identity_signed)

def t_identity_dict():
    agent = Identity.load("test_agent")
    d = agent.to_dict()
    assert d["agent_id"] == "test_agent"
test("Identity.to_dict() serializes", t_identity_dict)

# ── Memory ──────────────────────────────────────────────────────────

print()
print("Memory:")

def t_memory_persist():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("mem_test")
        mem = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        mem.remember("Test event", subject="Alice")
        fresh = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        results = fresh.recall(subject="Alice")
        assert results
        assert "Alice" in results[-1].text
test("Memory persists across instances", t_memory_persist)

def t_memory_hash():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("hash_test")
        mem = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        record = mem.remember("Hash test", subject="Bob")
        assert re.fullmatch(r"[a-f0-9]{64}", record.meta_hash)
        assert record.qseal_signature
test("Memory records have hash and signature", t_memory_hash)

# ── Relationship Continuity ─────────────────────────────────────────

print()
print("Relationship Continuity:")

def t_relationship_graph_persists():
    with tempfile.TemporaryDirectory() as tmp:
        robot = Identity.load("home_robot_17")
        graph = RelationshipGraph.open(robot, data_dir=Path(tmp))
        graph.add("jack", relationship_type=RelationshipType.FAMILY, display_name="Jack", tags=["son"])
        graph.add("guest", relationship_type="visitor", display_name="Guest")
        fresh = RelationshipGraph.open(robot, data_dir=Path(tmp))
        assert fresh.get("jack").scope == "household"
        assert fresh.get("jack").consent_model == "family"
        assert fresh.get("guest").scope == "visitor"
        assert fresh.get("guest").consent_model == "session"
        assert fresh.get("jack").qseal_signature
test("Relationship graph persists signed family/visitor policy defaults", t_relationship_graph_persists)

def t_visitor_block_family_allowed():
    with tempfile.TemporaryDirectory() as tmp:
        robot = Identity.load("home_robot_17")
        graph = RelationshipGraph.open(robot, data_dir=Path(tmp))
        memory = AgentMemory.open(robot, data_dir=Path(tmp))
        jack = graph.add("jack", relationship_type="family", display_name="Jack")
        elaine = graph.add("elaine", relationship_type="family", display_name="Elaine")
        guest = graph.add("guest", relationship_type="visitor", display_name="Guest")
        record = memory.remember(
            "got an A on his math test",
            subject=jack.display_name,
            person_id=jack.person_id,
            scope=jack.scope,
            consent=jack.consent_model,
        )
        v = verify(record, engine="stub")
        blocked = respond(
            robot,
            subject=guest.display_name,
            memory=record,
            verification=v,
            requester_scope=guest.scope,
            requester_consent=guest.consent_model,
        )
        allowed = respond(
            robot,
            subject=elaine.display_name,
            memory=record,
            verification=v,
            requester_scope=elaine.scope,
            requester_consent=elaine.consent_model,
        )
        assert not blocked.allowed
        assert blocked.outcome == "blocked"
        assert "does not permit household" in blocked.reason
        assert allowed.allowed
        assert allowed.outcome == "executed"
test("Visitor blocked from household memory while family is allowed", t_visitor_block_family_allowed)

def t_person_recall_and_emotion():
    with tempfile.TemporaryDirectory() as tmp:
        robot = Identity.load("home_robot_17")
        memory = AgentMemory.open(robot, data_dir=Path(tmp))
        emotion = EmotionalStateStore(robot.agent_id, Path(tmp))
        memory.remember("got an A on his math test", subject="Jack", person_id="jack")
        memory.remember("asked about dinner", subject="Elaine", person_id="elaine")
        tone = emotion.update(
            "jack",
            PADState(pleasure=0.9, arousal=0.4, dominance=0.2),
            event_significance=0.9,
            notable_event="math_test_pride",
        )
        fresh_memory = AgentMemory.open(robot, data_dir=Path(tmp))
        fresh_emotion = EmotionalStateStore(robot.agent_id, Path(tmp))
        jack_records = fresh_memory.recall(person_id="jack")
        assert len(jack_records) == 1
        assert "math test" in jack_records[0].text
        assert tone.emotional_trend == "warming"
        assert fresh_emotion.get("jack").interaction_count == 1
test("Per-person recall and relationship tone persist", t_person_recall_and_emotion)

def t_perception_adapters():
    manual = ManualAdapter().identify({"speaker": "jack", "audio_embedding": [0.1, 0.2]})
    username = UsernameAdapter({"jack_cohen": "jack"}).identify({"username": "jack_cohen"})
    caller = CallerIDAdapter({"+1-555-0123": "elaine"}).identify({"phone": "+1-555-0123"})
    assert manual.person_id == "jack"
    assert "audio_embedding" not in manual.raw_signal
    assert username.person_id == "jack"
    assert caller.person_id == "elaine"
test("Perception adapters resolve identity without storing raw biometrics", t_perception_adapters)

def t_wrap_existing_callable():
    with tempfile.TemporaryDirectory() as tmp:
        def existing_agent(prompt, context=None):
            memories = (context or {}).get("memories", [])
            assert memories
            return f"Remembered context for {prompt}: {memories[-1]['evidence']['memory_text']}"

        agent = mirra.wrap(existing_agent, identity="demo_agent", data_dir=Path(tmp))
        agent.add_person("jack", relationship_type="family", display_name="Jack")
        observed = agent.observe(speaker="jack", event="had a math test")
        context = agent.context_for(speaker="jack", situation="after school")
        result = agent.interact(speaker="jack", input="I'm home!", situation="after school")
        assert observed.meta_hash
        assert context.relationship.display_name == "Jack"
        assert context.latest_memory.text == "Jack: had a math test"
        assert result.allowed
        assert result.outcome == "executed"
        assert "had a math test" in result.response
        assert re.fullmatch(r"[a-f0-9]{64}", result.evidence_hash)
test("mirra.wrap() makes an existing callable continuous", t_wrap_existing_callable)

# ── Verification ────────────────────────────────────────────────────

print()
print("Verification:")

def t_verify_stub():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("ver_test")
        mem = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        record = mem.remember("Verify test", subject="Carol")
        v = verify(record, engine="stub")
        assert v.engine_used == "stub"
        assert v.confidence > 0
        assert v.stub_mode is True
test("verify() returns stub verification", t_verify_stub)

def t_verify_report_dict():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("dict_test")
        mem = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        record = mem.remember("Dict test", subject="Dave")
        v = verify(record, engine="stub")
        d = v.to_dict()
        assert "confidence" in d
        assert "engine_used" in d
test("VerificationReport.to_dict() serializes", t_verify_report_dict)

# ── Governance ──────────────────────────────────────────────────────

print()
print("Governance:")

def t_governance_allow():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("gov_test", scope="household", consent_model="family")
        mem = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        record = mem.remember("Gov test", subject="Eve", scope="household", consent="family")
        v = verify(record, engine="stub")
        g = respond(agent, subject="Eve", memory=record, verification=v)
        assert g.allowed
        assert g.outcome == "executed"
        assert g.evidence_hash
test("respond() allows valid scope/consent", t_governance_allow)

def t_governance_dict():
    with tempfile.TemporaryDirectory() as tmp:
        agent = Identity.load("dict_gov_test", scope="household", consent_model="family")
        mem = AgentMemory.open(agent, data_dir=Path(tmp) / "data")
        record = mem.remember("Dict gov test", subject="Frank", scope="household", consent="family")
        v = verify(record, engine="stub")
        g = respond(agent, subject="Frank", memory=record, verification=v)
        d = g.to_dict()
        assert "intent" in d or "allowed" in d
test("GovernanceReport.to_dict() serializes", t_governance_dict)

# ── Demo Script ─────────────────────────────────────────────────────

print()
print("Demo Script:")

def t_demo_runs():
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["MIRRA_CONTINUITY_DEMO_DATA"] = str(Path(tmp) / "demo_data")
        env["PYTHONPATH"] = str(Path(__file__).parent)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "examples" / "continuity_demo" / "home_robot.py")],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, f"Demo failed:\n{result.stderr}"
test("home_robot.py runs successfully", t_demo_runs)

def t_demo_output():
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["MIRRA_CONTINUITY_DEMO_DATA"] = str(Path(tmp) / "demo_data")
        env["PYTHONPATH"] = str(Path(__file__).parent)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "examples" / "continuity_demo" / "home_robot.py")],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert "Proof ID: qseal://bcp_entry_" in result.stdout
        assert "Governor Outcome: executed" in result.stdout
        assert "Evidence Hash:" in result.stdout
        assert "Hey Jack" in result.stdout
        assert "math test" in result.stdout
        assert "This is how an agent becomes continuous." in result.stdout
test("Demo output contains proof, governance, and tagline", t_demo_output)

def t_household_demo_output():
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["MIRRA_HOUSEHOLD_DEMO_DATA"] = str(Path(tmp) / "household_data")
        env["PYTHONPATH"] = str(Path(__file__).parent)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "examples" / "household_demo" / "household.py")],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, f"Household demo failed:\n{result.stderr}"
        assert "Jack proof: qseal://bcp_entry_" in result.stdout
        assert "Governor Outcome: blocked" in result.stdout
        assert "Requester relationship scope does not permit household memory sharing" in result.stdout
        assert "Response: Jack got an A on his math test today." in result.stdout
        assert "Expired session relationships: guest" in result.stdout
        assert "Still riding high from that A yesterday" in result.stdout
test("household.py proves family/visitor relationship boundaries", t_household_demo_output)

def t_wrapper_demo_output():
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["MIRRA_WRAPPER_DEMO_DATA"] = str(Path(tmp) / "wrapper_data")
        env["PYTHONPATH"] = str(Path(__file__).parent)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).parent / "examples" / "wrapper_demo" / "wrap_existing_agent.py")],
            capture_output=True, text=True, timeout=30, env=env,
        )
        assert result.returncode == 0, f"Wrapper demo failed:\n{result.stderr}"
        assert "Existing agent wrapped with MIRRA continuity" in result.stdout
        assert "Outcome: executed" in result.stdout
        assert "math test" in result.stdout
        assert "Evidence Hash:" in result.stdout
test("wrap_existing_agent.py proves one-line continuity wrapper", t_wrapper_demo_output)

# ── Results ─────────────────────────────────────────────────────────

print()
print("=" * 70)
total = passed + failed
print(f"  RESULTS: {passed}/{total} passed", end="")
if failed:
    print(f" ({failed} FAILED)")
else:
    print(" — ALL PASSING ✓")
print("=" * 70)

if errors:
    print("\nFailures:")
    for name, err in errors:
        print(f"  • {name}: {err[:300]}")

sys.exit(0 if failed == 0 else 1)
