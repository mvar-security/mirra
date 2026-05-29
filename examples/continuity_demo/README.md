# MIRRA Continuity Demo — Home Robot

One command shows the substrate pattern:

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
.venv/bin/python examples/continuity_demo/home_robot.py
# or
python3 examples/continuity_demo/home_robot.py
```

No paid API calls. No 27GB model. No MIRRA_PRIME dependency.

## What It Proves

The demo uses the public `mirra` SDK surface:

```python
from mirra import AgentMemory, Identity, respond, verify

agent = Identity.load("home_robot_17", kind="household_assistant")
memory = AgentMemory.open(agent)

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
```

This proves:

- Agent identity is QSEAL signed.
- Memory is written to a persistent BCP/ICP JSONL store.
- Recall happens through a fresh memory store instance, not a local variable.
- The stored memory has a BCP `meta_hash` and QSEAL memory signature.
- Entry 500 verifies the recalled memory.
- The response runs through an `ExecutionGovernor` envelope.
- The output includes a proof ID and Governor evidence hash.

## Expected Shape

```text
Agent ID: home_robot_17
Memory Hash: b52be041e47334110151be62f78fdcee...
Memory QSEAL: XzZN4RXE0OCErPbu0bflXKIobA8KrZAH...
Recalled: Jack: Jack had a math test today
Engine Used: stub
Confidence: 0.60
Governor Outcome: executed
Evidence Hash: 1aab79753dd4555f51011e490fbbe6cc...
Response: Hey Jack, how was school? How did the math test go?
Proof ID: qseal://bcp_entry_38_b52be041e4733411
```

Final line:

```text
This is how an agent becomes continuous.
```

## Architecture

| Layer | SDK/API | Backing System |
| --- | --- | --- |
| Identity | `Identity.load()` | `mirra_core.security.qseal_engine` |
| Memory | `AgentMemory.remember()` / `recall()` | `mirra_core.identity.bcp_manager` |
| Verification | `verify()` | Entry 500 `MIRRAVerifier` |
| Governance | `respond()` | `ExecutionGovernor` |
| Provenance | `MemoryRecord.proof_id`, `GovernanceReport.evidence_hash` | BCP hash + Governor evidence |

## Data Storage

By default, the demo writes local-only data here:

```text
examples/continuity_demo/data/codex/scrollnet/bcp_continuity_log.jsonl
```

The directory is ignored by git. Override it for tests or experiments:

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
MIRRA_CONTINUITY_DEMO_DATA=/tmp/mirra-demo .venv/bin/python examples/continuity_demo/home_robot.py
```

## Tests

```bash
.venv/bin/python run_sdk_tests.py
# Optional, if pytest is installed:
.venv/bin/python -m pytest tests/sdk/test_mirra_continuity_sdk.py tests/examples/test_continuity_demo.py -q
```

The tests assert the technical claims:

- persisted recall,
- non-empty proof hash,
- QSEAL memory signature,
- Entry 500 verification,
- Governor execution,
- Governor evidence hash.

## Why This Matters

Without continuity, agents can talk and act, but they do not carry trusted identity or memory across time.

With MIRRA continuity:

- identity persists,
- memory persists,
- consent and scope travel with memory,
- recall is verified before use,
- response is governed,
- provenance is auditable.

This is the first runnable proof of the substrate pattern.
