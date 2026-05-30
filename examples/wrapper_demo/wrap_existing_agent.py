#!/usr/bin/env python3
"""Wrap an existing agent with MIRRA continuity."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mirra  # noqa: E402


DATA_DIR = Path(
    os.environ.get(
        "MIRRA_WRAPPER_DEMO_DATA",
        Path(__file__).with_name("data"),
    )
)


def my_agent(prompt: str, context=None) -> str:
    memories = (context or {}).get("memories", [])
    if memories and "math test" in memories[-1]["evidence"]["memory_text"]:
        return "Hey Jack, I remember that math test. Still feeling good about that A?"
    return f"You said: {prompt}"


def main() -> int:
    if os.environ.get("MIRRA_WRAPPER_DEMO_KEEP_DATA") != "1":
        shutil.rmtree(DATA_DIR, ignore_errors=True)

    agent = mirra.wrap(my_agent, identity="demo_agent", data_dir=DATA_DIR)
    agent.add_person("jack", relationship_type="family", display_name="Jack")
    agent.observe(
        speaker="jack",
        event="got an A on his math test",
        pleasure=0.9,
        arousal=0.4,
        dominance=0.2,
        significance=0.9,
        notable_event="math_test_pride",
    )
    result = agent.interact(speaker="jack", input="I'm home!", situation="after school")

    print("Existing agent wrapped with MIRRA continuity")
    print(f"Outcome: {result.outcome}")
    print(f"Response: {result.response}")
    print(f"Evidence Hash: {result.evidence_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
