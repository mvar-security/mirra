"""
mirra_core/security/qseal_utils.py
QSEAL Utility Functions
Handles hash computation, field injection, and signature metadata prep.
"""

import os

# CRITICAL: QSEAL_SECRET must be set before any QSEAL operations
# No fallback. No dev default. Fail-closed security model.
QSEAL_SECRET = os.getenv("QSEAL_SECRET")
if not QSEAL_SECRET:
    raise RuntimeError(
        "QSEAL_SECRET not set. "
        "Run: export QSEAL_SECRET=$(openssl rand -hex 32) "
        "and add it to your shell profile. "
        "See CLAUDE_CODE_MCP_SETUP.md for full setup instructions."
    )

import json
import hashlib
from datetime import datetime, timezone


def compute_meta_hash(data: dict) -> str:
    """
    Compute a deterministic hash over a dictionary.
    Uses sorted keys and UTF-8 encoding for consistency.
    Includes QSEAL_SECRET in the hash input for extra entropy.
    """
    canonical_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
    combined = canonical_json + QSEAL_SECRET
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


def inject_derived_fields(entry: dict, agent_id: str = None) -> dict:
    """
    Enrich an entry with standard QSEAL metadata fields:
    - timestamp (UTC ISO8601)
    - meta_hash (short SHA256)
    - agent_id (if provided)
    """
    enriched = entry.copy()
    enriched["timestamp"] = datetime.now(timezone.utc).isoformat()
    enriched["meta_hash"] = compute_meta_hash(entry)
    if agent_id:
        enriched["agent_id"] = agent_id
    return enriched


def prepare_for_signature(entry: dict) -> str:
    """
    Prepare canonical string for signing.
    Sorts keys, removes non-essential fields like qseal_signature.
    """
    filtered = {k: v for k, v in entry.items() if k != "qseal_signature"}
    canonical_json = json.dumps(filtered, sort_keys=True, ensure_ascii=False)
    return canonical_json


def verify_meta_hash(entry: dict) -> bool:
    """
    Verify that the meta_hash matches recomputed value.
    Returns True if valid, False if mismatch.
    """
    if "meta_hash" not in entry:
        return False
    expected = compute_meta_hash({k: v for k, v in entry.items() if k != "meta_hash"})
    return entry["meta_hash"] == expected


def timestamp_iso() -> str:
    """Utility for standardized UTC timestamps."""
    return datetime.now(timezone.utc).isoformat()


def qseal_info() -> dict:
    """Return QSEAL utility metadata."""
    return {
        "module": "qseal_utils",
        "version": "1.0.0",
        "functions": [
            "compute_meta_hash",
            "inject_derived_fields",
            "prepare_for_signature",
            "verify_meta_hash",
            "timestamp_iso"
        ]
    }


# Helper to access QSEAL_SECRET elsewhere
def get_qseal_secret() -> str:
    return QSEAL_SECRET