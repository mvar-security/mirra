# MIRRA — Continuity Substrate for AI Agents

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-12%2F12%20passing-green)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

Every AI agent today starts from zero. No memory of what happened yesterday. No identity that persists across sessions. No way to prove what it knew, when it knew it, or why it acted.

MIRRA fixes that. It gives agents persistent identity, trusted memory, and governed action — with a cryptographic proof chain from memory through verification to response.

```python
from mirra import AgentMemory, Identity, respond, verify

agent = Identity.load("home_robot_17")
memory = AgentMemory.open(agent)
memory.remember("Jack had a math test today", subject="Jack")
record = memory.recall(subject="Jack")[-1]
governance = respond(agent, subject="Jack", memory=record, verification=verify(record))
```

Six lines. The agent remembers, verifies, and responds — with a signed audit trail.

[Why this matters](docs/MANIFESTO.md) | [SDK Quickstart](docs/MIRRA_SDK_QUICKSTART.md)

---

## Quick Start

```bash
git clone https://github.com/mvar-security/mirra.git
cd mirra
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
export QSEAL_SECRET=$(openssl rand -hex 32)
python examples/continuity_demo/home_robot.py
```

## Run Tests

```bash
python run_sdk_tests.py          # Standalone, no dependencies
python -m pytest tests/ -q       # If pytest is installed
```

---

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

Identity persists. Memory persists. Consent travels with memory. Recall is verified before use. Response is governed by policy. Provenance is auditable end-to-end.

---

## API Surface

| API | What it does |
| --- | --- |
| `Identity.load()` | Create or load a cryptographically signed agent identity |
| `AgentMemory.open()` | Open a persistent memory store for one identity |
| `AgentMemory.remember()` | Write a signed, scoped memory event |
| `AgentMemory.recall()` | Recall memories from the persisted store |
| `verify()` | Verify a recalled memory through the Entry 500 epistemic pipeline |
| `respond()` | Generate a governed response through the Execution Governor |

## Architecture

| Layer | SDK API | What happens |
| --- | --- | --- |
| Identity | `Identity.load()` | QSEAL HMAC-SHA256 signed identity payload |
| Memory | `AgentMemory.remember()` / `recall()` | BCP/ICP persistent JSONL store with content hashing |
| Verification | `verify()` | Entry 500 epistemic verification with confidence scoring |
| Governance | `respond()` | Execution Governor enforces scope, consent, and trust policy |
| Provenance | `MemoryRecord.proof_id` | End-to-end hash chain from memory through governance |

---

## Design Principles

MIRRA does not claim biological consciousness. It provides the substrate mechanics agents need before they can grow with humans across time.

**Fail closed.** If verification fails, the governor blocks. No silent fallthrough.

**Consent travels with data.** Every memory carries its scope and consent model. Policy enforcement happens at response time, not after.

**Prove, don't promise.** Every action produces a cryptographic evidence chain. The demo prints the proof — run it and see.

**Zero external services.** The SDK runs locally with no paid API calls, no cloud dependencies, and no model weights. `QSEAL_SECRET` is the only setup.

---

## Runtime Dependencies

`jsonschema` (schema validation for memory records). Everything else is Python stdlib.

## License

Apache 2.0. See [LICENSE](LICENSE) for details.

---

Built by [Shawn Cohen](https://github.com/mvar-security) at Universal Media.
