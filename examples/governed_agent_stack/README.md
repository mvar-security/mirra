# Governed Agent Stack Demo

This demo shows MIRRA composing with an external governance perimeter.

The external perimeter controls what the agent may do. MIRRA controls what the
agent may remember, share, and prove.

Run:

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
python examples/governed_agent_stack/stack.py
```

The demo proves three boundaries:

- External policy allows ordinary conversation.
- MIRRA allows Elaine to receive Jack's household memory.
- MIRRA blocks a guest from receiving Jack's household memory.
- External policy blocks a destructive memory-store action before it reaches the agent.
