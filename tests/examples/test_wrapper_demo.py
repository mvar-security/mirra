import os
import subprocess
import sys


def test_wrapper_demo_runs_existing_agent_with_continuity(tmp_path):
    env = dict(os.environ)
    env["MIRRA_WRAPPER_DEMO_DATA"] = str(tmp_path / "wrapper_data")
    result = subprocess.run(
        [sys.executable, "examples/wrapper_demo/wrap_existing_agent.py"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Existing agent wrapped with MIRRA continuity" in result.stdout
    assert "Outcome: executed" in result.stdout
    assert "math test" in result.stdout
    assert "Evidence Hash:" in result.stdout
