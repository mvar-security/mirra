# MIRRA SDK Quickstart

MIRRA gives stateless AI agents continuity: persistent identity, signed memory,
verification, governed response, and auditable provenance.

This SDK does not claim biological consciousness. It provides the substrate
mechanics agents need before they can grow with humans across time: identity,
memory, consent, verification, governed action, and provenance.

## Minimal Continuity Loop

```python
from mirra import AgentMemory, Identity, respond, verify

agent = Identity.load("home_robot_17")
memory = AgentMemory.open(agent)
memory.remember("Jack had a math test today", subject="Jack")
record = memory.recall(subject="Jack")[-1]
governance = respond(agent, subject="Jack", memory=record, verification=verify(record))
```

## Install/Run Locally

From this repo:

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
.venv/bin/python examples/continuity_demo/home_robot.py
```

Run the SDK proof tests:

```bash
.venv/bin/python run_sdk_tests.py
# Optional, if pytest is installed:
.venv/bin/python -m pytest tests/sdk/test_mirra_continuity_sdk.py tests/examples/test_continuity_demo.py -q
```

## Full Example

```python
from mirra import AgentMemory, Identity, respond, verify

agent = Identity.load(
    "home_robot_17",
    kind="household_assistant",
    scope="household",
    consent_model="family",
)

memory = AgentMemory.open(agent, data_dir="/tmp/mirra-home-memory")

memory.remember(
    "Jack had a math test today",
    subject="Jack",
    scope="household",
    consent="family",
)

record = memory.recall(subject="Jack")[-1]
verification = verify(record, engine="stub")
governance = respond(agent, subject="Jack", memory=record, verification=verification)

print(governance.response)
print(record.proof_id)
print(governance.evidence_hash)
```

## API Surface

| API | Purpose |
| --- | --- |
| `Identity.load()` | Create/load a QSEAL-signed agent identity |
| `AgentMemory.open()` | Open a persistent BCP/ICP memory store |
| `AgentMemory.remember()` | Write signed scoped memory |
| `AgentMemory.recall()` | Recall memory from persisted storage |
| `verify()` | Verify recalled memory through Entry 500 |
| `respond()` | Run response generation through `ExecutionGovernor` |

## Outputs That Matter

- `Identity.qseal_signature`: signed agent identity.
- `MemoryRecord.meta_hash`: BCP/ICP content hash.
- `MemoryRecord.qseal_signature`: QSEAL signature on the memory event.
- `MemoryRecord.proof_id`: human-readable provenance reference.
- `GovernanceReport.outcome`: Governor result, such as `executed` or `blocked`.
- `GovernanceReport.evidence_hash`: hash of the governed execution envelope.
