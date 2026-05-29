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

from mirra import AgentMemory, Identity, respond, verify

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
