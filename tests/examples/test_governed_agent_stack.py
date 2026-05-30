import os
import subprocess
import sys


def test_governed_agent_stack_demo_proves_composition(tmp_path):
    env = dict(os.environ)
    env["MIRRA_GOVERNED_STACK_DEMO_DATA"] = str(tmp_path / "stack_data")
    result = subprocess.run(
        [sys.executable, "examples/governed_agent_stack/stack.py"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "MIRRA Governed Agent Stack" in result.stdout
    assert "Perimeter Decision: allowed" in result.stdout
    assert "MIRRA Outcome: executed" in result.stdout
    assert "MIRRA Outcome: blocked" in result.stdout
    assert "Requester relationship scope does not permit household memory sharing" in result.stdout
    assert "Perimeter Decision: blocked" in result.stdout
    assert "destructive memory-store action requires human approval" in result.stdout
    assert "perimeter governs actions; MIRRA governs memory" in result.stdout
