#!/usr/bin/env python3
"""
BCP/ICP Schema Validator v1.0
==============================

Strict validation enforcing the canonical BCP_ICP schema at all read/write boundaries.

DESIGN PRINCIPLES:
1. **Fail Fast** - Invalid entries rejected immediately at write boundary
2. **Zero Tolerance** - No silent coercion; schema violations are fatal in prod mode
3. **Backward Compatible** - Legacy entries can be normalized to canonical format
4. **Cryptographic Integrity** - meta_hash validation ensures tamper-evidence
5. **Performance** - Schema compiled once, validated many times

USAGE:
    from mirra_core.identity.schema_validator import BCPSchemaValidator, ValidationMode

    validator = BCPSchemaValidator(mode=ValidationMode.STRICT)

    # Validate existing entry
    result = validator.validate(entry)
    if not result.valid:
        print(result.errors)

    # Normalize legacy entry to canonical format
    canonical = validator.normalize(legacy_entry)

    # Compute canonical hash
    hash_value = validator.compute_meta_hash(entry)
"""

from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import jsonschema
from jsonschema import Draft7Validator


# ============================================================================
# VALIDATION MODES
# ============================================================================

class ValidationMode(Enum):
    """Validation strictness levels."""
    PERMISSIVE = "permissive"  # Warn only, allow non-conforming entries
    STRICT = "strict"           # Reject non-conforming entries (production mode)
    MIGRATE = "migrate"         # Auto-normalize legacy entries on read


# ============================================================================
# VALIDATION RESULT
# ============================================================================

@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    normalized: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        """Allow if result: ... checks."""
        return self.valid

    def summary(self) -> str:
        """Human-readable summary."""
        if self.valid:
            status = "✅ VALID"
        else:
            status = "❌ INVALID"

        lines = [status]

        if self.errors:
            lines.append(f"  Errors ({len(self.errors)}):")
            for error in self.errors[:5]:  # Show first 5
                lines.append(f"    • {error}")
            if len(self.errors) > 5:
                lines.append(f"    ... and {len(self.errors) - 5} more")

        if self.warnings:
            lines.append(f"  Warnings ({len(self.warnings)}):")
            for warning in self.warnings[:3]:  # Show first 3
                lines.append(f"    • {warning}")
            if len(self.warnings) > 3:
                lines.append(f"    ... and {len(self.warnings) - 3} more")

        return "\n".join(lines)


# ============================================================================
# SCHEMA VALIDATOR
# ============================================================================

class BCPSchemaValidator:
    """
    Validates BCP/ICP entries against canonical schema v1.0.

    Thread-safe, compiled schema, optimized for high-frequency validation.
    """

    # Canonical field ordering for hash computation
    CANONICAL_FIELDS = [
        "protocol_family",
        "protocol_version",
        "schema_version",
        "timestamp",
        "agent_id",
        "event_type",
        "pad_after",
        "rnt",
        "continuity",
        "pad_before",
        "psi",
        "phi",
        "cycle",
        "session_id",
        "user_id",
        "archetype",
        "significance",
        "evidence",
        "qseal_signature"
    ]

    # Required fields (subset of CANONICAL_FIELDS)
    REQUIRED_FIELDS = [
        "protocol_family",
        "protocol_version",
        "schema_version",
        "timestamp",
        "agent_id",
        "event_type",
        "pad_after",
        "rnt",
        "continuity",
        "meta_hash"
    ]

    def __init__(self, mode: ValidationMode = ValidationMode.STRICT):
        """
        Initialize validator.

        Args:
            mode: Validation strictness level
        """
        self.mode = mode

        # Load and compile schema
        schema_path = Path(__file__).parent / "schemas" / "bcp_icp_v1.json"
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema not found: {schema_path}")

        with open(schema_path) as f:
            self.schema = json.load(f)

        # Compile validator (for performance)
        self.validator = Draft7Validator(self.schema)

        # Precompile JSON schema checker
        jsonschema.Draft7Validator.check_schema(self.schema)

    # ========================================================================
    # VALIDATION
    # ========================================================================

    def validate(self, entry: Dict[str, Any]) -> ValidationResult:
        """
        Validate entry against canonical schema.

        Args:
            entry: BCP/ICP entry to validate

        Returns:
            ValidationResult with errors/warnings
        """
        errors = []
        warnings = []

        # Schema validation
        schema_errors = list(self.validator.iter_errors(entry))
        if schema_errors:
            for error in schema_errors:
                path = ".".join(str(p) for p in error.path) if error.path else "root"
                errors.append(f"{path}: {error.message}")

        # Required fields check (redundant with schema, but explicit)
        for field in self.REQUIRED_FIELDS:
            if field not in entry:
                errors.append(f"Missing required field: {field}")

        # Protocol family/version check
        if entry.get("protocol_family") != "BCP_ICP":
            errors.append(f"Invalid protocol_family: {entry.get('protocol_family')} (must be 'BCP_ICP')")

        if entry.get("protocol_version") != "1.0":
            errors.append(f"Invalid protocol_version: {entry.get('protocol_version')} (must be '1.0')")

        if entry.get("schema_version") != "mirra.bcp_icp.v1":
            errors.append(f"Invalid schema_version: {entry.get('schema_version')} (must be 'mirra.bcp_icp.v1')")

        # Meta-hash validation
        if "meta_hash" in entry:
            computed_hash = self.compute_meta_hash(entry)
            stored_hash = entry["meta_hash"]

            if computed_hash != stored_hash:
                errors.append(
                    f"meta_hash mismatch: stored={stored_hash[:16]}..., "
                    f"computed={computed_hash[:16]}... (possible tampering)"
                )

        # Unknown fields warning (strict mode only)
        if self.mode == ValidationMode.STRICT:
            allowed_fields = set(self.CANONICAL_FIELDS + ["meta_hash"])
            unknown_fields = set(entry.keys()) - allowed_fields
            if unknown_fields:
                warnings.append(f"Unknown fields will be ignored: {sorted(unknown_fields)}")

        # Build result
        valid = len(errors) == 0

        return ValidationResult(
            valid=valid,
            errors=errors,
            warnings=warnings
        )

    def validate_or_raise(self, entry: Dict[str, Any]) -> None:
        """
        Validate entry and raise exception if invalid.

        Args:
            entry: BCP/ICP entry to validate

        Raises:
            ValueError: If validation fails
        """
        result = self.validate(entry)
        if not result.valid:
            raise ValueError(f"Schema validation failed:\n{result.summary()}")

    # ========================================================================
    # NORMALIZATION
    # ========================================================================

    def normalize(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize legacy entry to canonical schema.

        Adds missing protocol fields, computes meta_hash, removes unknown fields.

        Args:
            entry: Legacy or partial entry

        Returns:
            Normalized entry conforming to canonical schema
        """
        normalized = {}

        # Add protocol fields if missing
        normalized["protocol_family"] = entry.get("protocol_family", "BCP_ICP")
        normalized["protocol_version"] = entry.get("protocol_version", "1.0")
        normalized["schema_version"] = entry.get("schema_version", "mirra.bcp_icp.v1")

        # Copy canonical fields in order
        for field in self.CANONICAL_FIELDS:
            if field in entry:
                normalized[field] = entry[field]

        # Compute meta_hash
        normalized["meta_hash"] = self.compute_meta_hash(normalized)

        return normalized

    def normalize_batch(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize multiple entries.

        Args:
            entries: List of legacy entries

        Returns:
            List of normalized entries
        """
        return [self.normalize(entry) for entry in entries]

    # ========================================================================
    # HASH COMPUTATION
    # ========================================================================

    def compute_meta_hash(self, entry: Dict[str, Any]) -> str:
        """
        Compute SHA-256 meta_hash for entry.

        Hash is computed over canonical JSON (sorted keys, no whitespace)
        of all fields EXCEPT meta_hash itself.

        Args:
            entry: BCP/ICP entry (with or without meta_hash)

        Returns:
            64-character lowercase hex SHA-256 hash
        """
        # Create copy without meta_hash
        entry_for_hash = {k: v for k, v in entry.items() if k != "meta_hash"}

        # Canonical JSON: sorted keys, no whitespace, ensure_ascii
        canonical_json = json.dumps(
            entry_for_hash,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=True
        )

        # SHA-256 hash
        hash_obj = hashlib.sha256(canonical_json.encode('utf-8'))
        return hash_obj.hexdigest()

    def verify_meta_hash(self, entry: Dict[str, Any]) -> bool:
        """
        Verify that stored meta_hash matches computed hash.

        Args:
            entry: BCP/ICP entry with meta_hash field

        Returns:
            True if hash matches, False if mismatch or missing
        """
        if "meta_hash" not in entry:
            return False

        computed = self.compute_meta_hash(entry)
        stored = entry["meta_hash"]

        return computed == stored

    # ========================================================================
    # READ/WRITE BOUNDARY ENFORCEMENT
    # ========================================================================

    def validate_for_write(self, entry: Dict[str, Any]) -> ValidationResult:
        """
        Validate entry before writing to storage.

        In STRICT mode, this will reject non-conforming entries.
        In PERMISSIVE mode, warnings only.
        In MIGRATE mode, auto-normalize.

        Args:
            entry: Entry to validate

        Returns:
            ValidationResult (with normalized entry in MIGRATE mode)
        """
        if self.mode == ValidationMode.MIGRATE:
            # Auto-normalize
            normalized = self.normalize(entry)
            result = self.validate(normalized)
            result.normalized = normalized
            return result

        else:
            # Standard validation
            return self.validate(entry)

    def validate_for_read(self, entry: Dict[str, Any]) -> ValidationResult:
        """
        Validate entry after reading from storage.

        Verifies meta_hash to detect tampering.

        Args:
            entry: Entry read from storage

        Returns:
            ValidationResult
        """
        result = self.validate(entry)

        # Additional check: verify meta_hash hasn't been tampered with
        if result.valid and "meta_hash" in entry:
            if not self.verify_meta_hash(entry):
                result.valid = False
                result.errors.append("meta_hash verification failed (possible tampering)")

        return result

    # ========================================================================
    # UTILITY
    # ========================================================================

    def get_schema_version(self) -> str:
        """Get schema version string."""
        return self.schema.get("title", "Unknown")

    def get_required_fields(self) -> List[str]:
        """Get list of required field names."""
        return self.REQUIRED_FIELDS.copy()

    def get_canonical_fields(self) -> List[str]:
        """Get list of all canonical field names (required + optional)."""
        return self.CANONICAL_FIELDS.copy()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def validate_entry(entry: Dict[str, Any], mode: ValidationMode = ValidationMode.STRICT) -> ValidationResult:
    """
    Convenience function: validate a single entry.

    Args:
        entry: BCP/ICP entry to validate
        mode: Validation mode

    Returns:
        ValidationResult
    """
    validator = BCPSchemaValidator(mode=mode)
    return validator.validate(entry)


def normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function: normalize a single entry.

    Args:
        entry: Legacy entry

    Returns:
        Normalized canonical entry
    """
    validator = BCPSchemaValidator()
    return validator.normalize(entry)


def compute_hash(entry: Dict[str, Any]) -> str:
    """
    Convenience function: compute meta_hash for entry.

    Args:
        entry: BCP/ICP entry

    Returns:
        64-character hex SHA-256 hash
    """
    validator = BCPSchemaValidator()
    return validator.compute_meta_hash(entry)


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("BCP/ICP Schema Validator v1.0 - Self Test")
    print("="*70 + "\n")

    # Test 1: Valid entry
    print("Test 1: Valid canonical entry")
    valid_entry = {
        "protocol_family": "BCP_ICP",
        "protocol_version": "1.0",
        "schema_version": "mirra.bcp_icp.v1",
        "timestamp": 1776409054.51,
        "agent_id": "test_agent",
        "event_type": "interaction",
        "pad_after": {
            "pleasure": 0.65,
            "arousal": 0.42,
            "dominance": 0.78
        },
        "rnt": {
            "resonance": 0.82,
            "novelty": 0.45,
            "transferability": 0.73,
            "pattern_used": "analytical_synthesis"
        },
        "continuity": {
            "continuity_score": 0.91,
            "identity_stable": True,
            "status": "stable"
        },
        "meta_hash": ""  # Will be computed
    }

    validator = BCPSchemaValidator()
    valid_entry["meta_hash"] = validator.compute_meta_hash(valid_entry)

    result = validator.validate(valid_entry)
    print(result.summary())
    print()

    # Test 2: Invalid entry (missing required field)
    print("Test 2: Invalid entry (missing required field)")
    invalid_entry = {
        "protocol_family": "BCP_ICP",
        "protocol_version": "1.0",
        "schema_version": "mirra.bcp_icp.v1",
        "timestamp": 1776409054.51,
        "agent_id": "test_agent",
        # Missing event_type
        "pad_after": {"pleasure": 0.5, "arousal": 0.5, "dominance": 0.5},
        "rnt": {"resonance": 0.5, "novelty": 0.5, "transferability": 0.5, "pattern_used": "test"},
        "continuity": {"continuity_score": 0.5, "identity_stable": True, "status": "stable"},
        "meta_hash": "0" * 64
    }

    result = validator.validate(invalid_entry)
    print(result.summary())
    print()

    # Test 3: Normalization
    print("Test 3: Normalize legacy entry")
    legacy_entry = {
        "timestamp": 1776409054.51,
        "agent_id": "legacy_agent",
        "event_type": "interaction",
        "pad_after": {"pleasure": 0.5, "arousal": 0.5, "dominance": 0.5},
        "rnt": {"resonance": 0.5, "novelty": 0.5, "transferability": 0.5, "pattern_used": "legacy_pattern"},
        "continuity": {"continuity_score": 0.8, "identity_stable": True, "status": "stable"},
        "extra_field": "should be removed"
    }

    normalized = validator.normalize(legacy_entry)
    print(f"✅ Normalized entry:")
    print(f"   protocol_family: {normalized['protocol_family']}")
    print(f"   protocol_version: {normalized['protocol_version']}")
    print(f"   schema_version: {normalized['schema_version']}")
    print(f"   meta_hash: {normalized['meta_hash'][:16]}...")
    print(f"   extra_field removed: {'extra_field' not in normalized}")
    print()

    result = validator.validate(normalized)
    print(result.summary())
    print()

    # Test 4: Hash tampering detection
    print("Test 4: Detect hash tampering")
    tampered = valid_entry.copy()
    tampered["timestamp"] = 999999.99  # Tamper with timestamp
    # but keep original hash

    result = validator.validate(tampered)
    print(result.summary())
    print()

    print("="*70)
    print("Self test complete")
    print("="*70 + "\n")
