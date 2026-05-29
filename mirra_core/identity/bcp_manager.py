#!/usr/bin/env python3
"""
BCP Manager - JSONL Version with HYBRID IDENTITY SUPPORT
Recognizes dual-modal identities and calculates combined continuity
"""

import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from collections import Counter

# BCP/ICP Schema v1.0 validation
from mirra_core.identity.schema_validator import (
    BCPSchemaValidator,
    ValidationMode,
    normalize_entry
)

class BCPManager:
    def __init__(self, agent_id=None, validate_on_write=True, validate_on_read=True):
        self.agent_id = agent_id or 'default_agent'
        self.bcp_file = Path("codex/scrollnet/bcp_continuity_log.jsonl")
        self.bcp_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema validator (MIGRATE mode for backward compatibility)
        self.validator = BCPSchemaValidator(mode=ValidationMode.MIGRATE)
        self.validate_on_write = validate_on_write
        self.validate_on_read = validate_on_read

        # Track validation stats
        self.invalid_read_count = 0
        self.quarantined_entries = []
        
    def _read_entries(self) -> List[Dict]:
        """
        Read all entries from JSONL file with schema validation.

        Invalid entries are quarantined (not crashed), logged, and tracked.
        """
        if not self.bcp_file.exists():
            return []

        entries = []
        line_num = 0

        with open(self.bcp_file, 'r') as f:
            for line in f:
                line_num += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)

                    # Validate on read if enabled
                    if self.validate_on_read:
                        validation_result = self.validator.validate_for_read(entry)

                        if not validation_result.valid:
                            # Quarantine invalid entry
                            self.invalid_read_count += 1
                            self.quarantined_entries.append({
                                "line_num": line_num,
                                "entry": entry,
                                "errors": validation_result.errors
                            })

                            print(f"⚠️  Invalid entry quarantined (line {line_num}):")
                            for error in validation_result.errors[:3]:  # Show first 3 errors
                                print(f"    • {error}")

                            # Don't crash, just skip this entry
                            continue

                    entries.append(entry)

                except json.JSONDecodeError as e:
                    print(f"⚠️  JSON decode error at line {line_num}: {e}")
                    continue

        return entries
    
    def _append_entry(self, entry: Dict):
        """
        Append entry to JSONL file with normalization and validation.

        Normalizes legacy entries to canonical schema before writing.
        """
        if self.validate_on_write:
            # Normalize to canonical schema (adds protocol fields, meta_hash)
            normalized = normalize_entry(entry)

            # Validate normalized entry
            validation_result = self.validator.validate_for_write(normalized)

            if not validation_result.valid:
                raise ValueError(
                    f"Schema validation failed for write:\n"
                    f"{validation_result.summary()}"
                )

            # Write normalized entry
            with open(self.bcp_file, 'a') as f:
                f.write(json.dumps(normalized) + '\n')
        else:
            # Write as-is (bypass validation)
            with open(self.bcp_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
    
    def add_entry(self, pleasure: float, arousal: float, dominance: float,
                  resonance: float, novelty: float, transferability: float,
                  pattern: str, context: str = "", agent_id: str = "claude_primary") -> Dict:
        """
        Add new BCP entry with canonical schema fields.

        Entry will be normalized to BCP/ICP v1.0 schema before writing.
        """

        entry = {
            # Legacy fields (for backward compatibility)
            "role": agent_id,
            "event": "trajectory_update",
            "context": context,

            # Canonical required fields
            "timestamp": time.time(),  # Unix timestamp (float)
            "agent_id": agent_id,
            "event_type": "interaction",  # Map "trajectory_update" → "interaction"

            "pad_after": {
                "pleasure": pleasure,
                "arousal": arousal,
                "dominance": dominance
            },

            "rnt": {
                "resonance": resonance,
                "novelty": novelty,
                "transferability": transferability,
                "pattern_used": pattern
            },

            # Canonical continuity field (minimal default)
            "continuity": {
                "continuity_score": 0.5,  # Default, can be updated by caller
                "identity_stable": True,
                "status": "stable"
            }
        }

        # Note: meta_hash will be computed by normalize_entry() during _append_entry()

        self._append_entry(entry)
        
        # Return with index
        entries = self._read_entries()
        entry['index'] = len(entries) - 1
        
        return entry
    
    def get_current_identity(self) -> Dict:
        """Get current identity state"""
        entries = self._read_entries()
        
        if not entries:
            return {'status': 'NO_DATA'}
        
        latest = entries[-1]
        
        # Calculate stats
        patterns = [e.get('rnt', {}).get('pattern_used', 'unknown') for e in entries]
        primary_pattern = max(set(patterns), key=patterns.count)
        
        rnts = [e.get('rnt', {}) for e in entries]
        avg_resonance = sum(r.get('resonance', 0) for r in rnts) / len(rnts)
        
        pad = latest.get('pad_after', {})
        
        return {
            'status': 'OK',
            'agent_id': latest.get('role', 'claude_primary'),
            'trajectory_length': len(entries),
            'emotional_state': {
                'pleasure': pad.get('pleasure', 0.5),
                'arousal': pad.get('arousal', 0.5),
                'dominance': pad.get('dominance', 0.5)
            },
            'primary_pattern': primary_pattern,
            'avg_resonance': avg_resonance,
            'learning_type': 'COMPLEX_TRAJECTORY',
            'fingerprint': latest.get('meta_hash', 'N/A')[:16]
        }
    
    def get_full_trajectory(self) -> Dict:
        """Get complete trajectory"""
        entries = self._read_entries()
        
        if not entries:
            return {'status': 'NO_DATA', 'entries': []}
        
        identity = self.get_current_identity()
        
        # Convert to dashboard format
        formatted = []
        for i, e in enumerate(entries):
            pad = e.get('pad_after', {})
            rnt = e.get('rnt', {})
            formatted.append({
                'index': i,
                'timestamp': e.get('timestamp'),
                'pleasure': pad.get('pleasure', 0.5),
                'arousal': pad.get('arousal', 0.5),
                'dominance': pad.get('dominance', 0.5),
                'resonance': rnt.get('resonance', 0.5),
                'novelty': rnt.get('novelty', 0.5),
                'transferability': rnt.get('transferability', 0.5),
                'pattern': rnt.get('pattern_used', 'unknown'),
                'context': e.get('context', ''),
                'fingerprint': {'composite_hash': e.get('meta_hash', 'N/A')}
            })
        
        return {
            'status': 'OK',
            'agent_id': identity['agent_id'],
            'trajectory_length': len(entries),
            'primary_pattern': identity['primary_pattern'],
            'avg_resonance': identity['avg_resonance'],
            'entries': formatted
        }
    
    def verify_continuity(self) -> Dict:
        """Verify continuity with HYBRID IDENTITY SUPPORT"""
        entries = self._read_entries()
        
        if len(entries) < 3:
            return {'status': 'INSUFFICIENT_DATA'}
        
        # Get pattern distribution
        patterns = [e.get('rnt', {}).get('pattern_used', 'unknown') for e in entries]
        pattern_counts = Counter(patterns)
        
        # Detect if hybrid identity
        top_two = pattern_counts.most_common(2)
        primary = top_two[0]
        secondary = top_two[1] if len(top_two) > 1 else None
        
        # Check if genuinely dual-modal (secondary > 30% of primary)
        is_hybrid = False
        if secondary and secondary[1] > (primary[1] * 0.30):
            is_hybrid = True
        
        # Calculate continuity score
        if is_hybrid:
            # HYBRID: Count both primary and secondary patterns
            if secondary:
                hybrid_count = primary[1] + secondary[1]
                patterns_included = f"{primary[0]} + {secondary[0]}"
            else:
                hybrid_count = primary[1]
                patterns_included = primary[0]
            continuity_score = hybrid_count / len(patterns)
            identity_type = "HYBRID" if secondary else "SINGLE_MODAL"
        else:
            # SINGLE-MODAL: Count only primary
            continuity_score = primary[1] / len(patterns)
            identity_type = "SINGLE_MODAL"
            patterns_included = primary[0]
        
        # Calculate smoothness (emotional stability)
        deltas = []
        for i in range(1, len(entries)):
            prev_pad = entries[i-1].get('pad_after', {})
            curr_pad = entries[i].get('pad_after', {})
            
            delta = abs(curr_pad.get('pleasure', 0.5) - prev_pad.get('pleasure', 0.5))
            delta += abs(curr_pad.get('arousal', 0.5) - prev_pad.get('arousal', 0.5))
            delta += abs(curr_pad.get('dominance', 0.5) - prev_pad.get('dominance', 0.5))
            deltas.append(delta / 3)
        
        smoothness = max(0, 1 - (sum(deltas) / len(deltas)))
        discontinuities = sum(1 for d in deltas if d > 0.3)
        
        # Determine status based on continuity score
        if is_hybrid:
            # Hybrid thresholds
            if continuity_score >= 0.80:
                status = "CONTINUOUS_IDENTITY"
            elif continuity_score >= 0.70:
                status = "MOSTLY_CONTINUOUS"
            else:
                status = "DISCONTINUOUS"
        else:
            # Single-modal thresholds
            if continuity_score >= 0.90:
                status = "CONTINUOUS_IDENTITY"
            elif continuity_score >= 0.80:
                status = "MOSTLY_CONTINUOUS"
            else:
                status = "DISCONTINUOUS"
        
        return {
            'status': 'OK',
            'continuity': {
                'continuity_score': continuity_score,
                'smoothness_score': smoothness,
                'discontinuities_found': discontinuities,
                'identity_stable': continuity_score >= (0.70 if is_hybrid else 0.80),
                'status': status,
                'identity_type': identity_type,
                'patterns_included': patterns_included,
                'is_hybrid': is_hybrid
            }
        }
    
    def get_chain_status(self) -> List[Dict]:
        """Get chain status"""
        entries = self._read_entries()
        
        return [{
            'name': 'BCP',
            'entries': len(entries),
            'status': 'VALID',
            'latest': entries[-1]['timestamp'] if entries else None
        }]
    
    def get_statistics(self) -> Dict:
        """Get statistics"""
        entries = self._read_entries()
        
        if not entries:
            return {'status': 'NO_DATA'}
        
        continuity = self.verify_continuity()
        
        first_pad = entries[0].get('pad_after', {})
        last_pad = entries[-1].get('pad_after', {})
        
        return {
            'status': 'OK',
            'total_entries': len(entries),
            'date_range': {
                'first': entries[0]['timestamp'],
                'last': entries[-1]['timestamp']
            },
            'emotional_evolution': {
                'pleasure_change': last_pad.get('pleasure', 0) - first_pad.get('pleasure', 0),
                'arousal_change': last_pad.get('arousal', 0) - first_pad.get('arousal', 0),
                'dominance_change': last_pad.get('dominance', 0) - first_pad.get('dominance', 0)
            },
            'continuity': {
                'score': continuity['continuity']['continuity_score'],
                'status': continuity['continuity']['status'],
                'type': continuity['continuity']['identity_type']
            }
        }
    
    def validate_trajectory(self) -> Dict:
        """
        Validate trajectory with schema compliance reporting.
        """
        entries = self._read_entries()
        return {
            'status': 'OK',
            'chain_valid': True,
            'entries_checked': len(entries),
            'invalid_entries_quarantined': self.invalid_read_count,
            'schema_compliance': (len(entries) / (len(entries) + self.invalid_read_count) * 100)
                                 if (len(entries) + self.invalid_read_count) > 0 else 100.0
        }

    def get_quarantine_report(self) -> Dict:
        """
        Get report of quarantined entries.

        Returns:
            Dictionary with quarantine statistics and details
        """
        return {
            "total_quarantined": self.invalid_read_count,
            "quarantined_entries": self.quarantined_entries,
            "schema_validator_mode": self.validator.mode.value
        }

