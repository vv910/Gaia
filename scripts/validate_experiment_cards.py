"""Validate Gaia perovskite experiment-card YAML outputs.

The gate is intentionally standalone: it validates generated ``experiments.yaml``
files without reaching into package state, SQLite, or LKM. It checks that cards
carry the grounding/evidence/decision fields required by the
``gaia-gap-to-experiment-perovskite`` skill.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REQUIRED_FIELDS = (
    "hypothesis_H",
    "alternative_Alt",
    "discriminating_observation",
    "database_queries_run",
    "database_precedents",
    "lkm_evidence_summary",
    "outcome_matrix",
    "controls",
    "primary_readouts",
    "expected_result_if_H",
    "expected_result_if_Alt",
    "success_criterion_for_closing_gap",
    "safety_boundary_note",
)

REAL_PACKAGE_FIELDS = (
    "source_package",
    "target_claims",
    "affected_conclusions",
    "current_belief",
    "original_evidence_gap_text",
    "device_context",
)

DEVICE_CONTEXT_FIELDS = (
    "solar_cell_structure",
    "perovskite_composition",
    "intervention_location",
    "modulator_material_or_family",
)

OUTCOME_MATRIX_FIELDS = {
    "supports_H": ("observation_pattern", "interpretation", "remaining_caveat"),
    "supports_Alt": ("observation_pattern", "interpretation", "remaining_caveat"),
    "mixed_or_unresolved": ("observation_pattern", "interpretation", "next_step"),
}

PARSE_COVERAGE_METRICS = ("pce", "ff", "voc", "jsc", "hysteresis")
TOP_ROW_FIELDS = ("similarity_score", "why_comparable", "why_limited", "parsed_deltas")
TIER_COUNT_KEYS = ("tier1", "tier2", "tier3", "rejected")

GENERIC_DEVICE_CONTEXTS = {
    "perovskite solar cell",
    "perovskite solar cells",
    "psc",
    "generic perovskite solar cell",
}

GENERIC_PHRASES = (
    "do more characterization",
    "further study is needed",
    "optimize conditions",
    "perform additional tests",
    "study stability further",
)

UNKNOWN_VALUES = {"", "unknown", "unk", "na", "n/a", "none", "null", "-"}
README_FALLBACK_MARKERS = (
    "readme evidence gap",
    "readme evidence gaps",
    "readme fallback",
    "fallback to readme",
)
ANALYSIS_ABSENT_MARKERS = (
    "analysis.md absent",
    "analysis.md missing",
    "analysis missing",
)
VAGUE_SUCCESS_MARKERS = (
    "close the gap",
    "improve performance",
    "clear result",
    "validate hypothesis",
    "confirm the mechanism",
    "better understanding",
    "determine whether",
)
LKM_EVIDENCE_MARKERS = (
    "lkm",
    "reasoning",
    "claim",
    "chain",
    "paper graph",
    "paper_graph",
    "mechanism",
    "premise",
)
LKM_FAILURE_MARKERS = (
    "unavailable",
    "not available",
    "failed",
    "failure",
    "timeout",
    "timed out",
    "error",
    "access key",
    "no lkm",
)
READOUT_MAPPING_KEYS = (
    "maps_to_uncertainty",
    "uncertainty",
    "alternative_explanation",
    "supports_H_pattern",
    "supports_Alt_pattern",
    "h_alt_mapping",
    "decision_mapping",
)


@dataclass
class ValidationResult:
    """Validation findings for one or more experiment cards."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extend(self, other: ValidationResult) -> None:
        """Append findings from ``other``."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def is_missing(value: Any) -> bool:
    """Return true when a YAML value should be treated as absent."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def path_join(base: str, key: str | int) -> str:
    """Build a stable dotted/list path for diagnostics."""
    if isinstance(key, int):
        return f"{base}[{key}]"
    if not base:
        return key
    return f"{base}.{key}"


def load_yaml(path: Path) -> Any:
    """Load YAML from ``path`` with safe parsing."""
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemExit(f"failed to read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SystemExit(f"failed to parse YAML in {path}: {exc}") from exc


def extract_cards(payload: Any) -> tuple[list[Any], bool]:
    """Return ``(cards, has_context_missing_preflight)`` from common output shapes."""
    if isinstance(payload, list):
        return payload, False
    if not isinstance(payload, dict):
        raise ValueError("top-level YAML must be a list or mapping")

    has_preflight = "context_missing_preflight" in payload
    for key in ("experiments", "experiment_cards", "cards"):
        value = payload.get(key)
        if isinstance(value, list):
            return value, has_preflight
    if has_preflight:
        return [], True
    raise ValueError("no experiment card list found; expected top-level list or `experiments:`")


def validate_payload(
    payload: Any, *, smoke_test: bool = False, allow_readme_fallback: bool = False
) -> ValidationResult:
    """Validate a parsed YAML payload."""
    result = ValidationResult()
    try:
        cards, has_preflight = extract_cards(payload)
    except ValueError as exc:
        result.errors.append(str(exc))
        return result

    if not cards:
        if has_preflight:
            return result
        result.errors.append("no experiment cards found")
        return result

    for index, card in enumerate(cards):
        card_path = f"cards[{index}]"
        result.extend(
            validate_card(
                card,
                card_path=card_path,
                smoke_test=smoke_test,
                allow_readme_fallback=allow_readme_fallback,
            )
        )
    return result


def validate_card(
    card: Any,
    *,
    card_path: str,
    smoke_test: bool = False,
    allow_readme_fallback: bool = False,
) -> ValidationResult:
    """Validate one experiment card."""
    result = ValidationResult()
    if not isinstance(card, dict):
        result.errors.append(f"{card_path}: card must be a mapping")
        return result

    required = list(REQUIRED_FIELDS)
    if not smoke_test:
        for field_name in REAL_PACKAGE_FIELDS:
            if field_name not in required:
                required.append(field_name)

    for field_name in required:
        if is_missing(card.get(field_name)):
            result.errors.append(f"{card_path}.{field_name}: required field is missing")

    if not smoke_test:
        validate_device_context(
            card.get("device_context"), result, path_join(card_path, "device_context")
        )

    if "interpretation_decision_tree" not in card and "outcome_matrix" not in card:
        result.errors.append(
            f"{card_path}: requires `interpretation_decision_tree` or `outcome_matrix`"
        )

    validate_database_precedents(
        card.get("database_precedents"),
        result,
        path_join(card_path, "database_precedents"),
    )
    warn_database_confidence_limitations(card, result, card_path)
    validate_outcome_matrix(
        card.get("outcome_matrix"), result, path_join(card_path, "outcome_matrix")
    )
    warn_readout_mappings(
        card.get("primary_readouts"), result, path_join(card_path, "primary_readouts")
    )
    warn_generic_device_context(
        card.get("device_context"), result, path_join(card_path, "device_context")
    )
    validate_readme_fallback(
        card,
        result,
        card_path,
        smoke_test=smoke_test,
        allow_readme_fallback=allow_readme_fallback,
    )
    warn_lkm_evidence_summary(card.get("lkm_evidence_summary"), result, card_path)
    warn_vague_success_criterion(card.get("success_criterion_for_closing_gap"), result, card_path)
    warn_unknown_composition_confidence(card, result, card_path)
    warn_generic_phrases(card, result, card_path)

    return result


def validate_device_context(value: Any, result: ValidationResult, path: str) -> None:
    """Require concrete device/intervention context in real-package mode."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping in real-package mode")
        return

    for field_name in DEVICE_CONTEXT_FIELDS:
        if is_missing(value.get(field_name)):
            result.errors.append(f"{path}.{field_name}: required device-context field is missing")


def validate_database_precedents(value: Any, result: ValidationResult, path: str) -> None:
    """Validate tier counts, parse coverage, and top precedent row shape."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping with tier counts and top rows")
        return

    validate_tier_counts(value, result, path)
    validate_parse_coverage(value.get("parse_coverage"), result, path_join(path, "parse_coverage"))
    validate_top_precedent_rows(lookup_top_rows(value), result, path)


def validate_tier_counts(value: dict[str, Any], result: ValidationResult, path: str) -> None:
    """Validate required tier-count fields."""
    for tier in TIER_COUNT_KEYS:
        if lookup_tier_count(value, tier) is None:
            result.errors.append(f"{path}: missing `{tier}` tier count")


def validate_parse_coverage(value: Any, result: ValidationResult, path: str) -> None:
    """Validate required metric parse-coverage fields."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: required mapping is missing")
        return

    for metric in PARSE_COVERAGE_METRICS:
        if is_missing(value.get(metric)):
            result.errors.append(f"{path}.{metric}: metric coverage is missing")


def validate_top_precedent_rows(rows: Any, result: ValidationResult, path: str) -> None:
    """Validate the top precedent row list."""
    if rows is None:
        result.errors.append(f"{path}: missing top precedent rows")
        return
    if not isinstance(rows, list):
        result.errors.append(f"{path}: top precedent rows must be a list")
        return

    for index, row in enumerate(rows):
        row_path = path_join(f"{path}.top_precedent_rows", index)
        if not isinstance(row, dict):
            result.errors.append(f"{row_path}: precedent row must be a mapping")
            continue
        for field_name in TOP_ROW_FIELDS:
            if is_missing(row.get(field_name)):
                result.errors.append(
                    f"{row_path}.{field_name}: required precedent field is missing"
                )


def warn_database_confidence_limitations(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Warn when low parse coverage lacks a database-confidence limitation."""
    precedents = card.get("database_precedents")
    if not isinstance(precedents, dict):
        return

    parse_coverage = precedents.get("parse_coverage")
    if not isinstance(parse_coverage, dict):
        return

    if not parse_coverage_is_low(parse_coverage):
        return

    if is_missing(card.get("database_confidence")):
        result.warnings.append(
            f"{path}.database_confidence: low parse coverage should be recorded "
            "as a database-confidence limitation"
        )


def parse_coverage_is_low(parse_coverage: dict[str, Any]) -> bool:
    """Return true when a parse-coverage mapping contains a low ratio."""
    for value in parse_coverage.values():
        ratio = parse_coverage_ratio(value)
        if ratio is not None and ratio < 0.5:
            return True
    return False


def parse_coverage_ratio(value: Any) -> float | None:
    """Parse common coverage values into a 0-1 ratio."""
    if isinstance(value, int | float):
        numeric = float(value)
        return numeric if 0 <= numeric <= 1 else None

    text = stringify(value).strip()
    if "/" not in text:
        return None

    numerator_text, denominator_text = text.split("/", 1)
    try:
        numerator = float(numerator_text)
        denominator = float(denominator_text)
    except ValueError:
        return None

    if denominator <= 0:
        return None
    return numerator / denominator


def lookup_tier_count(database_precedents: dict[str, Any], tier: str) -> Any:
    """Find a tier count across accepted tier-count shapes."""
    direct_names = (f"{tier}_count", f"{tier[0:4]}_{tier[4:]}_count")
    for name in direct_names:
        if name in database_precedents:
            return database_precedents[name]

    tier_counts = database_precedents.get("tier_counts")
    if isinstance(tier_counts, dict):
        for name in (tier, f"{tier}_count"):
            if name in tier_counts:
                return tier_counts[name]
    return None


def lookup_top_rows(database_precedents: dict[str, Any]) -> Any:
    """Find top precedent rows across accepted key names."""
    for key in ("top_precedent_rows", "top_precedents", "top_rows", "rows"):
        if key in database_precedents:
            return database_precedents[key]
    return None


def validate_outcome_matrix(value: Any, result: ValidationResult, path: str) -> None:
    """Validate mandatory H/Alt/unresolved outcome matrix."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: required mapping is missing")
        return

    for branch, fields in OUTCOME_MATRIX_FIELDS.items():
        branch_value = value.get(branch)
        branch_path = path_join(path, branch)
        if not isinstance(branch_value, dict):
            result.errors.append(f"{branch_path}: required mapping is missing")
            continue
        for field_name in fields:
            if is_missing(branch_value.get(field_name)):
                result.errors.append(f"{branch_path}.{field_name}: required field is missing")


def warn_readout_mappings(value: Any, result: ValidationResult, path: str) -> None:
    """Warn when primary readouts do not identify their H/Alt uncertainty mapping."""
    if is_missing(value):
        return
    if not isinstance(value, list):
        result.warnings.append(f"{path}: should be a list with readout-to-uncertainty mappings")
        return

    for index, readout in enumerate(value):
        readout_path = path_join(path, index)
        if not isinstance(readout, dict):
            result.warnings.append(f"{readout_path}: readout lacks an H/Alt mapping")
            continue
        if all(is_missing(readout.get(key)) for key in READOUT_MAPPING_KEYS):
            result.warnings.append(f"{readout_path}: readout lacks an H/Alt mapping")


def warn_generic_device_context(value: Any, result: ValidationResult, path: str) -> None:
    """Warn if the device context is only generic PSC text."""
    if isinstance(value, str) and value.strip().lower() in GENERIC_DEVICE_CONTEXTS:
        result.warnings.append(f"{path}: contains only generic perovskite solar-cell context")
        return
    if isinstance(value, dict):
        nonempty_values = [
            stringify(item).strip().lower() for item in value.values() if not is_missing(item)
        ]
        if nonempty_values and all(item in GENERIC_DEVICE_CONTEXTS for item in nonempty_values):
            result.warnings.append(f"{path}: contains only generic perovskite solar-cell context")


def validate_readme_fallback(
    card: dict[str, Any],
    result: ValidationResult,
    path: str,
    *,
    smoke_test: bool,
    allow_readme_fallback: bool,
) -> None:
    """Reject README Evidence Gap fallback in strict real-package mode."""
    if smoke_test:
        return

    fallback_text = " ".join(text.lower() for _, text in iter_strings(card, path))
    used_readme_fallback = any(marker in fallback_text for marker in README_FALLBACK_MARKERS)
    used_readme_fallback = used_readme_fallback or (
        "readme" in fallback_text
        and "evidence gap" in fallback_text
        and any(marker in fallback_text for marker in ANALYSIS_ABSENT_MARKERS)
    )
    if not used_readme_fallback:
        return

    message = (
        f"{path}: README Evidence Gap fallback is not allowed in strict mode when "
        "ANALYSIS.md is absent"
    )
    if allow_readme_fallback:
        result.warnings.append(f"{message}; confidence must be downgraded")
    else:
        result.errors.append(message)


def warn_lkm_evidence_summary(value: Any, result: ValidationResult, path: str) -> None:
    """Warn when LKM summary lacks evidence content or an explicit failure reason."""
    if is_missing(value):
        return

    text = " ".join(text.lower() for _, text in iter_strings(value, path))
    if not text.strip():
        return

    has_evidence = any(marker in text for marker in LKM_EVIDENCE_MARKERS)
    has_failure = any(marker in text for marker in LKM_FAILURE_MARKERS)
    if not has_evidence and not has_failure:
        result.warnings.append(
            f"{path}.lkm_evidence_summary: does not describe LKM evidence or an "
            "explicit LKM failure reason"
        )


def warn_vague_success_criterion(value: Any, result: ValidationResult, path: str) -> None:
    """Warn when the gap-closing success criterion is too vague to validate."""
    if is_missing(value):
        return

    text = stringify(value).strip()
    lowered = text.lower()
    if len(text) < 24 or any(marker in lowered for marker in VAGUE_SUCCESS_MARKERS):
        result.warnings.append(
            f"{path}.success_criterion_for_closing_gap: success criterion is vague"
        )


def warn_unknown_composition_confidence(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Warn when many unknown-composition precedents are paired with high confidence."""
    rows = collect_precedent_rows(card.get("database_precedents"))
    if not rows:
        return

    unknown = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        composition = first_present(
            row,
            (
                "perovskite_composition",
                "composition",
                "absorber",
                "absorber_composition",
            ),
        )
        if stringify(composition).strip().lower() in UNKNOWN_VALUES:
            unknown += 1

    if unknown < 2 or unknown < len(rows) / 2:
        return

    confidence = stringify(card.get("confidence")).strip().lower()
    if confidence in {"high", "moderate", "medium", "0.8", "0.9", "1.0"}:
        result.warnings.append(
            f"{path}.database_precedents: many rows have unknown composition "
            "without a low-confidence downgrade"
        )


def collect_precedent_rows(value: Any) -> list[Any]:
    """Return top precedent rows when present."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        rows = lookup_top_rows(value)
        if isinstance(rows, list):
            return rows
    return []


def warn_generic_phrases(value: Any, result: ValidationResult, path: str) -> None:
    """Warn when generic non-decision phrases appear anywhere in a card."""
    for item_path, text in iter_strings(value, path):
        lowered = text.lower()
        for phrase in GENERIC_PHRASES:
            if phrase in lowered:
                result.warnings.append(f"{item_path}: generic phrase `{phrase}`")


def iter_strings(value: Any, path: str) -> list[tuple[str, str]]:
    """Collect all strings under ``value`` with diagnostic paths."""
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, dict):
        strings: list[tuple[str, str]] = []
        for key, item in value.items():
            strings.extend(iter_strings(item, path_join(path, stringify(key))))
        return strings
    if isinstance(value, list):
        strings = []
        for index, item in enumerate(value):
            strings.extend(iter_strings(item, path_join(path, index)))
        return strings
    return []


def first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-missing mapping value for ``keys``."""
    for key in keys:
        value = mapping.get(key)
        if not is_missing(value):
            return value
    return None


def stringify(value: Any) -> str:
    """Convert diagnostics values to stable strings."""
    if value is None:
        return ""
    return str(value)


def print_result(result: ValidationResult) -> None:
    """Print validation findings."""
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if result.errors:
        print(
            f"experiment-card validation failed: {len(result.errors)} error(s), "
            f"{len(result.warnings)} warning(s)",
            file=sys.stderr,
        )
    else:
        print(f"experiment-card validation OK: {len(result.warnings)} warning(s)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to experiments.yaml")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Relax real-package grounding checks for explicit synthetic smoke fixtures.",
    )
    parser.add_argument(
        "--allow-readme-fallback",
        action="store_true",
        help=(
            "Allow permissive/trial README Evidence Gap fallback when ANALYSIS.md "
            "is absent; strict real-package mode should not use this."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Validate an experiment-card YAML file."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    payload = load_yaml(args.path)
    result = validate_payload(
        payload,
        smoke_test=args.smoke_test,
        allow_readme_fallback=args.allow_readme_fallback,
    )
    print_result(result)
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
