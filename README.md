# MIRRA — Continuity Substrate for AI Agents

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

MIRRA gives stateless AI agents persistent identity, trusted memory, and governed action.

```python
from mirra import AgentMemory, Identity, respond, verify

agent = Identity.load("home_robot_17")
memory = AgentMemory.open(agent)
memory.remember("Jack had a math test today", subject="Jack")
record = memory.recall(subject="Jack")[-1]
governance = respond(agent, subject="Jack", memory=record, verification=verify(record))
```

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
python examples/continuity_demo/home_robot.py
```

MIRRA does not claim biological consciousness. It provides the substrate mechanics agents need before they can grow with humans across time: identity, memory, consent, verification, governed action, and provenance.

Runtime dependency: `jsonschema`.

[SDK Quickstart](docs/MIRRA_SDK_QUICKSTART.md)

---

## Install

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
pip install -e .
```

## Run the Demo

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
python examples/continuity_demo/home_robot.py
```

## Run Tests

```bash
python run_sdk_tests.py
# Optional, if pytest is installed:
python -m pytest tests/ -q
```

---

## API Surface

| API | Purpose |
| --- | --- |
| `Identity.load()` | Create/load a QSEAL-signed agent identity |
| `AgentMemory.open()` | Open a persistent BCP/ICP memory store |
| `AgentMemory.remember()` | Write signed scoped memory |
| `AgentMemory.recall()` | Recall memory from persisted storage |
| `verify()` | Verify recalled memory through Entry 500 |
| `respond()` | Run response generation through `ExecutionGovernor` |

## What the Demo Proves

```text
Agent ID: home_robot_17
Memory Hash: b52be041e47334110151be62f78fdcee...
Memory QSEAL: XzZN4RXE0OCErPbu0bflXKIobA8KrZAH...
Governor Outcome: executed
Evidence Hash: 1aab79753dd4555f51011e490fbbe6cc...
Response: Hey Jack, how was school? How did the math test go?
Proof ID: qseal://bcp_entry_38_b52be041e4733411
```

Identity persists. Memory persists. Consent travels with memory. Recall is verified. Response is governed. Provenance is auditable.

---

## Architecture

| Layer | SDK API | Backing System |
| --- | --- | --- |
| Identity | `Identity.load()` | QSEAL HMAC-SHA256 signing |
| Memory | `AgentMemory.remember()` / `recall()` | BCP/ICP persistent store |
| Verification | `verify()` | Entry 500 epistemic pipeline |
| Governance | `respond()` | Execution Governor |
| Provenance | `MemoryRecord.proof_id` | BCP hash + Governor evidence |

---

## License

Apache 2.0. See [LICENSE](LICENSE) for details.

---

**Primary Architect:** Shawn Cohen — shawn@universalmediaus.com
