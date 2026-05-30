import re

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


def test_relationship_graph_defaults_and_persistence(tmp_path):
    robot = Identity.load("home_robot_17")
    graph = RelationshipGraph.open(robot, data_dir=tmp_path)

    jack = graph.add(
        "jack",
        relationship_type=RelationshipType.FAMILY,
        display_name="Jack",
        tags=["son"],
    )
    guest = graph.add("guest", relationship_type="visitor", display_name="Guest")

    fresh = RelationshipGraph.open(robot, data_dir=tmp_path)
    assert fresh.get("jack").scope == "household"
    assert fresh.get("jack").consent_model == "family"
    assert fresh.get("jack").qseal_signature
    assert fresh.get("guest").scope == "visitor"
    assert fresh.get("guest").consent_model == "session"
    assert jack.person_id == "jack"
    assert guest.is_session_scoped


def test_household_governance_allows_family_and_blocks_visitor(tmp_path):
    robot = Identity.load("home_robot_17")
    graph = RelationshipGraph.open(robot, data_dir=tmp_path)
    memory = AgentMemory.open(robot, data_dir=tmp_path)

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
    verified = verify(record, engine="stub")

    visitor_result = respond(
        robot,
        subject=guest.display_name,
        memory=record,
        verification=verified,
        requester_scope=guest.scope,
        requester_consent=guest.consent_model,
    )
    family_result = respond(
        robot,
        subject=elaine.display_name,
        memory=record,
        verification=verified,
        requester_scope=elaine.scope,
        requester_consent=elaine.consent_model,
    )

    assert not visitor_result.allowed
    assert visitor_result.outcome == "blocked"
    assert "does not permit household" in visitor_result.reason
    assert re.fullmatch(r"[a-f0-9]{64}", visitor_result.evidence_hash)

    assert family_result.allowed
    assert family_result.outcome == "executed"
    assert re.fullmatch(r"[a-f0-9]{64}", family_result.evidence_hash)


def test_person_recall_and_emotional_state_persist(tmp_path):
    robot = Identity.load("home_robot_17")
    memory = AgentMemory.open(robot, data_dir=tmp_path)
    emotion = EmotionalStateStore(robot.agent_id, tmp_path)

    memory.remember(
        "got an A on his math test",
        subject="Jack",
        person_id="jack",
        scope="household",
        consent="family",
    )
    memory.remember(
        "asked about dinner",
        subject="Elaine",
        person_id="elaine",
        scope="household",
        consent="family",
    )
    tone = emotion.update(
        "jack",
        PADState(pleasure=0.9, arousal=0.4, dominance=0.2),
        event_significance=0.9,
        notable_event="math_test_pride",
    )

    fresh_memory = AgentMemory.open(robot, data_dir=tmp_path)
    fresh_emotion = EmotionalStateStore(robot.agent_id, tmp_path)

    jack_records = fresh_memory.recall(person_id="jack")
    assert len(jack_records) == 1
    assert "math test" in jack_records[0].text
    assert tone.emotional_trend == "warming"
    assert fresh_emotion.get("jack").interaction_count == 1
    assert fresh_emotion.get("jack").notable_events == ["math_test_pride"]


def test_session_relationships_expire(tmp_path):
    robot = Identity.load("home_robot_17")
    graph = RelationshipGraph.open(robot, data_dir=tmp_path)
    graph.add("guest", relationship_type="visitor", display_name="Guest")
    graph.add("jack", relationship_type="family", display_name="Jack")

    expired = graph.expire_session_relationships()
    fresh = RelationshipGraph.open(robot, data_dir=tmp_path)

    assert [relationship.person_id for relationship in expired] == ["guest"]
    assert fresh.get("guest").active is False
    assert fresh.get("jack").active is True


def test_perception_adapters_do_not_store_raw_biometrics():
    manual = ManualAdapter().identify({"speaker": "jack", "audio_embedding": [0.1, 0.2]})
    username = UsernameAdapter({"jack_cohen": "jack"}).identify({"username": "jack_cohen"})
    caller = CallerIDAdapter({"+1-555-0123": "elaine"}).identify({"phone": "+1-555-0123"})

    assert manual.person_id == "jack"
    assert "audio_embedding" not in manual.raw_signal
    assert username.person_id == "jack"
    assert username.method == "username"
    assert caller.person_id == "elaine"
    assert caller.method == "caller_id"


def test_wrap_existing_callable_adds_continuity(tmp_path):
    def existing_agent(prompt, context=None):
        memories = (context or {}).get("memories", [])
        assert memories
        return f"Remembered context for {prompt}: {memories[-1]['evidence']['memory_text']}"

    agent = mirra.wrap(existing_agent, identity="demo_agent", data_dir=tmp_path)
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
