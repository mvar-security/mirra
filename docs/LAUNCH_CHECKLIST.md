# MIRRA Launch Checklist

## Security

- [x] Secrets audit passed.
- [x] Live API keys rotated.
- [x] `.env` protected by `.gitignore`.
- [x] Private-key-like material blocked from normal commits.
- [ ] Security-sensitive archives reviewed and moved to encrypted/private storage.
- [ ] No `.env` files committed.

## Repository Hygiene

- [x] Pre-cleanup backup created.
- [x] Vanilla 27GB model removed with redownload command documented.
- [x] Byte-identical duplicate files removed.
- [x] Divergent duplicates classified.
- [x] Critical divergent `mirra_core` files reviewed and archived.
- [x] Broken duplicate venvs archived.
- [ ] Remaining security divergent files reviewed.
- [ ] Remaining test/docs/script divergent files reviewed or archived.
- [x] No generated continuity demo data committed.

## SDK

- [x] `mirra` SDK package created.
- [x] `Identity.load()` exposes signed identity.
- [x] `AgentMemory.remember()` writes signed scoped memory.
- [x] `AgentMemory.recall()` reads from persisted storage.
- [x] `verify()` wraps Entry 500 verification.
- [x] `respond()` wraps governed response execution.
- [x] SDK contract tests added.
- [x] `pip install -e .` covered by `verify_install.sh`.
- [x] Isolated fresh-clone `verify_install.sh` passed from `/tmp`.
- [ ] Wheel build verified.

## Demo

- [x] `examples/continuity_demo/home_robot.py` runs without paid API calls.
- [x] Demo does not require local LLM weights.
- [x] Demo does not require MIRRA_PRIME.
- [x] Demo prints proof ID.
- [x] Demo prints Governor evidence hash.
- [x] Demo tests validate proof, verification, governance, response, and persisted recall.

## Documentation

- [x] Top-level README leads with the SDK loop, not theory.
- [x] README includes the continuity demo command above the fold.
- [x] Quickstart leads with trust positioning and code.
- [x] SDK quickstart documents outputs that matter.
- [x] Launch checklist exists.
- [ ] Public README reviewed for internal-only material before publication.
- [ ] Manifesto / launch narrative drafted.

## Verification

- [x] Standalone SDK/demo tests green.
- [x] Fresh clone smoke test green: install, import, demo, standalone tests.
- [x] `datetime.utcnow()` warning resolved in Entry 500 timestamp helper.
- [ ] Full bridge/governor test suite run after SDK changes.
- [ ] MVAR focused contracts rerun.
- [ ] ClawSeal CLI install smoke rerun.
- [ ] Mission Control test cache issue resolved or documented.
