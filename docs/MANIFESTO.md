# MIRRA Manifesto

AI agents are becoming capable, but most of them still live moment to moment.

They can answer, call tools, browse files, and execute tasks. Then the session
ends, the context window collapses, and the agent starts again as if nothing
was learned.

MIRRA exists to close that gap.

## Continuity, Not Consciousness Claims

MIRRA does not claim biological consciousness.

It provides the substrate mechanics agents need before they can grow with
humans across time:

- persistent identity,
- signed memory,
- consent and scope attached to recall,
- verification before use,
- governed action,
- auditable provenance.

That is the practical foundation for continuity.

## The Missing Layer

Agent frameworks give models hands.

Memory stores give models notes.

Policy engines give models boundaries.

MIRRA ties those pieces into a continuity loop:

```text
identity -> memory -> recall -> verification -> governed response -> provenance
```

The result is simple to inspect:

```python
from mirra import AgentMemory, Identity, respond, verify

agent = Identity.load("home_robot_17")
memory = AgentMemory.open(agent)
memory.remember("Jack had a math test today", subject="Jack")
record = memory.recall(subject="Jack")[-1]
governance = respond(agent, subject="Jack", memory=record, verification=verify(record))
```

The agent remembers. The memory is signed. The response is governed. The proof
is inspectable.

## Why It Matters

The next generation of agents will not be judged only by how smart they are in
one turn. They will be judged by whether they can become reliable over time:

- learning a household without leaking it,
- remembering a collaborator without fabricating intimacy,
- carrying task history without losing provenance,
- acting with boundaries when memory touches real people.

MIRRA is a small first proof of that substrate.

Stateless agents need continuity.

MIRRA is the continuity layer.
