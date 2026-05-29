"""
Tests for continuity demo

Verifies that the demo runs successfully and produces expected output.
"""

import subprocess
import sys
import os
import re
from pathlib import Path


def run_demo(tmp_path):
    demo_script = Path(__file__).parent.parent.parent / "examples" / "continuity_demo" / "home_robot.py"
    env = dict(os.environ)
    env["MIRRA_CONTINUITY_DEMO_DATA"] = str(tmp_path / "continuity_data")

    return subprocess.run(
        [sys.executable, str(demo_script)],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_continuity_demo_runs(tmp_path):
    """Test that continuity demo runs without errors"""
    result = run_demo(tmp_path)

    assert result.returncode == 0, f"Demo failed with error:\n{result.stderr}"


def test_continuity_demo_output_contains_proof(tmp_path):
    """Test that demo output contains proof ID"""
    result = run_demo(tmp_path)

    assert "Proof ID: qseal://bcp_entry_" in result.stdout
    assert "Proof: qseal://bcp_entry_" in result.stdout
    assert re.search(r"Proof ID: qseal://bcp_entry_\d+_[a-f0-9]{16}", result.stdout)


def test_continuity_demo_output_contains_verification(tmp_path):
    """Test that demo output contains verification result"""
    result = run_demo(tmp_path)

    assert "Verification (Entry 500)" in result.stdout
    assert "Engine Used:" in result.stdout
    assert "Confidence:" in result.stdout
    assert "Trust Level:" in result.stdout


def test_continuity_demo_output_contains_governance(tmp_path):
    """Test that demo output contains governance result"""
    result = run_demo(tmp_path)

    assert "Governance" in result.stdout
    assert "Allowed:" in result.stdout
    assert "Governor Outcome: executed" in result.stdout
    assert "Evidence Hash:" in result.stdout
    assert "Scope:" in result.stdout
    assert "Consent:" in result.stdout


def test_continuity_demo_output_contains_response(tmp_path):
    """Test that demo output contains final response"""
    result = run_demo(tmp_path)

    assert "Final Response:" in result.stdout
    assert "Hey Jack" in result.stdout
    assert "math test" in result.stdout


def test_continuity_demo_output_contains_all_checkmarks(tmp_path):
    """Test that all stages complete successfully"""
    result = run_demo(tmp_path)

    # Count checkmarks for each stage
    assert "✅ Identity created and signed" in result.stdout
    assert "✅ Memory written and signed" in result.stdout
    assert "✅ Memory recalled for Jack" in result.stdout
    assert "✅ Memory verified" in result.stdout
    assert "✅ Response governed" in result.stdout
    assert "✅ Response generated" in result.stdout
    assert "✅ Provenance complete" in result.stdout


def test_continuity_demo_output_contains_tagline(tmp_path):
    """Test that demo ends with the tagline"""
    result = run_demo(tmp_path)

    assert "This is how an agent becomes continuous." in result.stdout


def test_continuity_demo_recalls_from_persisted_store(tmp_path):
    """The demo should recall normalized memory from disk, not a local variable."""
    result = run_demo(tmp_path)

    assert result.returncode == 0
    assert "Recalled: Jack: Jack had a math test today" in result.stdout
    assert re.search(r"Memory Hash: [a-f0-9]{32}\.\.\.", result.stdout)
    assert re.search(r"Memory QSEAL: [A-Za-z0-9+/=]{16,}\.\.\.", result.stdout)
