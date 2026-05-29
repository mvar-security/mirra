# Household Continuity Demo

This demo shows MIRRA handling three people with different relationship scopes:

- Jack: family, household scope, family consent
- Elaine: family, household scope, family consent
- Guest: visitor scope, session consent

Run:

```bash
export QSEAL_SECRET=$(openssl rand -hex 32)
python examples/household_demo/household.py
```

The proof is the boundary:

- Jack's memory is signed and stored.
- The guest cannot receive Jack's household memory.
- Elaine can receive Jack's household memory.
- Guest session state is expired.
- Jack's memory and relationship tone persist into the next day.
