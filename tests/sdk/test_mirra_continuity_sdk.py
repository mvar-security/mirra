import re

from mirra import AgentMemory, Identity, respond, verify


def test_sdk_continuity_loop_persists_verifies_and_governs(tmp_path):
    agent = Identity.load(
        "home_robot_17",
        kind="household_assistant",
        scope="household",
        consent_model="family",
    )
    memory = AgentMemory.open(agent, data_dir=tmp_path / "memory")

    written = memory.remember(
        "Jack had a math test today",
        subject="Jack",
        scope="household",
        consent="family",
    )

    # Reopen to prove recall is coming from persisted storage, not instance state.
    fresh_memory = AgentMemory.open(agent, data_dir=tmp_path / "memory")
    recalled = fresh_memory.recall(subject="Jack")

    assert recalled
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


def test_sdk_governance_blocks_wrong_consent(tmp_path):
    agent = Identity.load("home_robot_17")
    memory = AgentMemory.open(agent, data_dir=tmp_path / "memory")
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
