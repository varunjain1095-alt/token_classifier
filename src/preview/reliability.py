"""Model-reliability diagnostics for preview runs.

Produces per-record and run-level diagnostics WITHOUT modifying the model's
raw classifications: schema validation, exact-source evidence verification,
category-evidence mismatch, taxonomy-gap and label-drift flags. Also provides
run fingerprints and stability comparison for optional repeat runs.
"""
import hashlib
import json
import re
from typing import Dict, Any, List, Optional

from src.shared.logger import get_logger

logger = get_logger(__name__)

VALID_STATES = {'matched', 'unmatched', 'ambiguous'}
VALID_CONFIDENCE = {'high', 'medium', 'low'}


def build_run_fingerprint(sample_records: List[Dict[str, Any]],
                          config: Dict[str, Any],
                          taxonomy: Optional[Dict[str, Any]],
                          model: str) -> str:
    """Deterministic fingerprint of what was run: sample ids + config knobs +
    taxonomy id/version + model. Identical reruns produce identical fingerprints."""
    material = {
        'record_ids': [r.get('id') for r in sample_records],
        'objective': config.get('objective'),
        'label_mode': config.get('label_mode'),
        'output_fields': sorted(config.get('output_fields') or []),
        'classification_type': config.get('classification_type'),
        'category_mode': config.get('category_mode'),
        'taxonomy_id': (taxonomy or {}).get('id'),
        'taxonomy_version': (taxonomy or {}).get('version'),
        'model': model,
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True).encode('utf-8')
    ).hexdigest()[:16]


def assess_record(classification: Any, review_text: str,
                  output_fields: List[str],
                  taxonomy_labels: List[str],
                  unmatched_label: str = 'other') -> Dict[str, Any]:
    """Validate one raw classification. Returns flags; never alters the result."""
    flags: List[str] = []
    missing: List[str] = []

    if not isinstance(classification, dict):
        return {
            'schema_valid': False,
            'missing_fields': ['primary_category'],
            'evidence_verbatim': None,
            'label_in_taxonomy': None,
            'flags': ['unparseable_result'],
        }

    # Schema: primary_category always required plus requested output fields
    required = ['primary_category'] + [f for f in output_fields
                                       if f != 'primary_category']
    for f in required:
        if f not in classification:
            missing.append(f)
    if missing:
        flags.append('schema_missing_fields')

    if 'secondary_categories' in classification and \
            not isinstance(classification['secondary_categories'], list):
        flags.append('schema_type_error')

    state = str(classification.get('classification_state') or '').lower()
    if 'classification_state' in classification and state not in VALID_STATES:
        flags.append('invalid_classification_state')

    conf = str(classification.get('confidence') or '').lower()
    if 'confidence' in classification and conf not in VALID_CONFIDENCE:
        flags.append('invalid_confidence')

    label = classification.get('primary_category')

    # Exact-source evidence verification
    evidence = classification.get('supporting_evidence')
    evidence_verbatim = None
    if evidence is not None:
        evidence_verbatim = bool(str(evidence).strip()) and \
            str(evidence).strip() in review_text
        if not str(evidence).strip():
            flags.append('missing_evidence')
        elif not evidence_verbatim:
            flags.append('evidence_not_verbatim')

    # Taxonomy conformance (discovery mode only)
    label_in_taxonomy = None
    unmatched = (unmatched_label or 'other').lower()
    if taxonomy_labels:
        label_in_taxonomy = label in taxonomy_labels
        if not label_in_taxonomy and str(label).lower() not in (unmatched, 'none'):
            flags.append('label_drift')  # label outside the shared taxonomy
        if str(label).lower() in (unmatched, 'none') or state == 'unmatched':
            flags.append('taxonomy_gap')  # no theme fit this record

    # Category-evidence mismatch: claims matched but evidence cannot support it
    if state == 'matched' and (not str(evidence or '').strip()
                               or evidence_verbatim is False):
        flags.append('category_evidence_mismatch')
    if state == 'matched' and conf == 'low':
        flags.append('low_confidence_match')

    return {
        'schema_valid': not missing and 'schema_type_error' not in flags,
        'missing_fields': missing,
        'evidence_verbatim': evidence_verbatim,
        'label_in_taxonomy': label_in_taxonomy,
        'flags': flags,
    }


def assess_run(results: List[Dict[str, Any]],
               sample_records: List[Dict[str, Any]],
               config: Dict[str, Any],
               taxonomy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Run-level diagnostics: per-record assessments + flag counts."""
    output_fields = config.get('output_fields') or []
    taxonomy_labels = (taxonomy or {}).get('labels') or []
    unmatched_label = (taxonomy or {}).get('unmatched_label') or 'other'
    texts = {r.get('id'): str(r.get('review_text', '')) for r in sample_records}

    per_record: Dict[str, Any] = {}
    counts: Dict[str, int] = {}
    for r in results:
        rid = r.get('record_id')
        if not rid or not r.get('success'):
            continue
        cls = (r.get('result') or {}).get('classification')
        diag = assess_record(cls, texts.get(rid, ''), output_fields,
                             taxonomy_labels, unmatched_label)
        per_record[rid] = diag
        for f in diag['flags']:
            counts[f] = counts.get(f, 0) + 1

    return {'records': per_record, 'flag_counts': counts}


def compare_runs(results_a: List[Dict[str, Any]],
                 results_b: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Stability check: compare raw primary_category between two identical runs."""
    labels_a = {}
    labels_b = {}
    for r in results_a:
        if r.get('success'):
            labels_a[r.get('record_id')] = \
                ((r.get('result') or {}).get('classification') or {}) \
                .get('primary_category')
    for r in results_b:
        if r.get('success'):
            labels_b[r.get('record_id')] = \
                ((r.get('result') or {}).get('classification') or {}) \
                .get('primary_category')

    records = {}
    changed = 0
    for rid, la in labels_a.items():
        lb = labels_b.get(rid)
        stable = la == lb
        if not stable:
            changed += 1
        records[rid] = {'run_a': la, 'run_b': lb, 'stable': stable}

    total = len(records)
    return {
        'records': records,
        'changed': changed,
        'total': total,
        'stability_rate': round((total - changed) / total * 100, 1) if total else None,
    }
