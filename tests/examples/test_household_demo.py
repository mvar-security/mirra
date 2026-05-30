import os
import subprocess
import sys


def test_household_demo_runs_and_proves_boundaries(tmp_path):
    env = dict(os.environ)
    env["MIRRA_HOUSEHOLD_DEMO_DATA"] = str(tmp_path / "household_data")
    result = subprocess.run(
        [sys.executable, "examples/household_demo/household.py"],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Jack proof: qseal://bcp_entry_" in result.stdout
    assert "Governor Outcome: blocked" in result.stdout
    assert "Requester relationship scope does not permit household memory sharing" in result.stdout
    assert "Response: Jack got an A on his math test today." in result.stdout
    assert "Expired session relationships: guest" in result.stdout
    assert "Still riding high from that A yesterday" in result.stdout
    assert "relationship-aware continuity" in result.stdout
