#!/bin/bash
# ============================================================================
# MIRRA SDK — Fresh-Clone Verification
# Run this from the repo root after cloning:
#   chmod +x verify_install.sh && ./verify_install.sh
# ============================================================================

set -e

echo "============================================================================"
echo "  MIRRA SDK — Fresh-Clone Verification"
echo "============================================================================"
echo ""

# ── Step 1: Create virtual environment ──────────────────────────────
echo "── Step 1: Virtual Environment ─────────────────────────────────"
if [ -d ".venv" ]; then
    echo "  .venv already exists, reusing"
else
    python3 -m venv .venv
    echo "  Created .venv"
fi
source .venv/bin/activate
echo "  Activated: $(python3 --version)"
echo ""

# ── Step 2: Install in editable mode ────────────────────────────────
echo "── Step 2: pip install -e . ────────────────────────────────────"
pip install -e . --quiet
echo "  OK — mirra installed"
echo ""

# ── Step 3: Verify import ──────────────────────────────────────────
echo "── Step 3: Import Check ────────────────────────────────────────"
export QSEAL_SECRET="${QSEAL_SECRET:-$(openssl rand -hex 32)}"
python3 -c "
from mirra import AgentMemory, Identity, respond, verify, __version__
print(f'  mirra {__version__} imported successfully')
print(f'  Exports: Identity, AgentMemory, verify, respond')
"
echo ""

# ── Step 4: Run the continuity demo ────────────────────────────────
echo "── Step 4: Continuity Demo ─────────────────────────────────────"
MIRRA_CONTINUITY_DEMO_DATA=$(mktemp -d) python3 examples/continuity_demo/home_robot.py
echo ""

# ── Step 5: Run standalone tests ───────────────────────────────────
echo "── Step 5: Standalone SDK Tests ─────────────────────────────────"
python3 run_sdk_tests.py
echo ""

# ── Step 6: Run pytest if available ────────────────────────────────
echo "── Step 6: pytest (optional) ───────────────────────────────────"
if python3 -m pytest --version >/dev/null 2>&1; then
    python3 -m pytest tests/ -q --tb=short
else
    echo "  pytest not installed; standalone tests already passed"
fi
echo ""

# ── Result ──────────────────────────────────────────────────────────
echo "============================================================================"
echo "  ALL CHECKS PASSED"
echo "============================================================================"
echo ""
echo "  pip install -e .     ✅"
echo "  import mirra         ✅"
echo "  continuity demo      ✅"
echo "  standalone tests     ✅"
echo "  pytest               optional"
echo ""
echo "  Ready for: git init && git add -A && git commit -m 'Initial SDK extraction'"
echo "============================================================================"
