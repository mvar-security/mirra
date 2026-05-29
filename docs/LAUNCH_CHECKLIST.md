# MIRRA SDK Launch Checklist

## Security

- [x] No `.env` files committed.
- [x] No PEM/private-key/local database files committed.
- [x] Demo requires `QSEAL_SECRET`; no hardcoded signing secret.
- [x] Generated demo memory is ignored by git.

## Packaging

- [x] Package name is `mirra`.
- [x] Runtime dependencies are declared.
- [x] `pip install -e .` passes in a fresh clone.
- [x] Isolated fresh-clone `verify_install.sh` passed from `/tmp`.
- [x] Wheel and source distribution build verified.
- [x] Isolated wheel install smoke test passed from `/tmp`.
- [ ] Package name availability checked before PyPI publication.

## SDK

- [x] `Identity.load()` exposes signed identity.
- [x] `AgentMemory.remember()` writes signed scoped memory.
- [x] `AgentMemory.recall()` reads from persisted storage.
- [x] `verify()` wraps Entry 500 verification.
- [x] `respond()` wraps governed response execution.
- [x] Standalone SDK test runner passes without pytest.

## Demo

- [x] `examples/continuity_demo/home_robot.py` runs without paid API calls.
- [x] Demo does not require local LLM weights.
- [x] Demo does not require MIRRA_PRIME.
- [x] Demo prints proof ID.
- [x] Demo prints Governor evidence hash.

## Documentation

- [x] README leads with code, not theory.
- [x] README includes the demo command above the fold.
- [x] Quickstart explains outputs that matter.
- [x] Manifesto exists.
- [ ] Public README reviewed by a second human before public visibility.

## Verification

- [x] Standalone SDK/demo tests green.
- [x] Fresh clone smoke test green: install, import, demo, standalone tests.
- [ ] Optional pytest suite run in a dev environment.
