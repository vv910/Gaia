"""Validate Gaia perovskite experiment-card YAML outputs.

The gate is intentionally standalone: it validates generated ``experiments.yaml``
files without reaching into package state, SQLite, or LKM. It checks that cards
carry the grounding/evidence/decision fields required by the
``gaia-gap-to-experiment-perovskite`` skill.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REQUIRED_FIELDS = (
    "gap_id",
    "package_mode",
    "gap_type",
    "gap_classifier_output",
    "mechanism_axes",
    "primary_mechanism_axis",
    "secondary_mechanism_axes",
    "card_archetype",
    "classification_mode",
    "archetype_selection",
    "design_motif_evidence",
    "design_memory_role",
    "priority",
    "priority_rationale",
    "scientific_uncertainty",
    "hypothesis_H",
    "alternative_Alt",
    "discriminating_observation",
    "database_queries_run",
    "database_precedents",
    "sqlite_role",
    "sqlite_precedent_quality",
    "sqlite_quality_warning",
    "lkm_queries_run",
    "lkm_role",
    "lkm_design_reasoning",
    "lkm_evidence_summary",
    "top_reasoning_chains",
    "mechanism_source_breakdown",
    "same_package_lkm_chains",
    "cross_package_lkm_chains",
    "ambiguous_lkm_chains",
    "sqlite_lkm_conflicts",
    "mechanism_attribution_limitations",
    "gap_resolution_strategy",
    "outcome_matrix",
    "variables_to_vary",
    "controls",
    "primary_readouts",
    "secondary_readouts",
    "observable_to_mechanism_mapping",
    "expected_result_if_H",
    "expected_result_if_Alt",
    "success_criterion_for_closing_gap",
    "non_closure_criteria",
    "minimum_replicate_logic",
    "statistics_or_comparison_logic",
    "failure_modes",
    "interpretation_decision_tree",
    "belief_update_target",
    "belief_update_contract",
    "feasibility_notes",
    "confidence",
    "open_questions",
    "safety_boundary_note",
)

REAL_PACKAGE_FIELDS = (
    "source_package",
    "target_claims",
    "affected_conclusions",
    "gap_claim_belief",
    "original_evidence_gap_text",
    "source_device_context",
    "lab_translation_context",
    "p_i_n_adaptation_design",
    "portability_risks_for_p_i_n",
)

DEVICE_CONTEXT_FIELDS = (
    "solar_cell_structure",
    "cell_stack_sequence",
    "perovskite_composition",
    "intervention_location",
    "modulator_material_or_family",
)

LAB_TRANSLATION_CONTEXT_FIELDS = (
    "lab_preferred_device_architecture",
    "translation_status",
    "translation_note",
    "translation_targets",
)

MECHANISM_SOURCE_FIELDS = (
    "package_local_gaia_evidence",
    "lkm_mechanism_reasoning",
    "sqlite_precedent_delta_background",
)

OUTCOME_MATRIX_FIELDS = {
    "supports_H": ("observation_pattern", "interpretation", "remaining_caveat"),
    "supports_Alt": ("observation_pattern", "interpretation", "remaining_caveat"),
    "mixed_or_unresolved": ("observation_pattern", "interpretation", "next_step"),
}

PARSE_COVERAGE_METRICS = ("pce", "ff", "voc", "jsc", "hysteresis")
TOP_ROW_FIELDS = (
    "similarity_score",
    "precedent_group",
    "why_comparable",
    "why_limited",
    "parsed_deltas",
)
TIER_COUNT_KEYS = (
    "tier1_strong_precedent",
    "tier2_related_precedent",
    "tier3_broad_context",
    "rejected_or_unusable",
)
SIMILARITY_SCORE_FIELDS = (
    "architecture",
    "absorber",
    "intervention_location",
    "modulator_family",
    "paired_metric_completeness",
    "mechanism_relevance",
    "total",
)
V2_RECOMMENDED_FIELDS = (
    "planning_level",
    "execution_phase",
    "depends_on",
    "enables",
    "execution_rationale",
    "package_evidence_brief",
    "mechanism_decomposition_question",
    "factor_decomposition",
    "minimal_discriminating_matrix",
    "route_designs",
    "morphology_normalization_strategy",
    "same_sample_measurement_bundle",
    "passivation_transport_tradeoff_logic",
    "boundary_condition_tests",
    "gaia_evidence_node_mapping",
    "matrix_closure_rules",
    "matrix_non_closure_rules",
    "lab_reference_stack",
    "database_confidence",
)

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
    "lkm_unavailable",
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
LKM_PROVENANCE_FIELDS = (
    "source_package",
    "paper_id",
    "claim_id",
    "conclusion_id",
    "chain_id",
    "local_id",
    "doi",
    "title",
    "score",
    "rerank_score",
)
FORBIDDEN_PLACEHOLDER_STRINGS = (
    "The target transport/contact or performance-limiting branch explains the claim.",
    "A competing branch or uncontrolled covariate explains the aggregate metric.",
    "direct H-vs-Alt discriminating readout class",
    "mechanism-relevant condition",
    "matched control class",
    "A primary readout pattern separates H from Alt under matched controls.",
    "H becomes the favored mechanism.",
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
SQLITE_ROLE_MARKERS = (
    "precedent discovery",
    "stack",
    "intervention",
    "paired delta",
    "not mechanism proof",
)
SQLITE_FORBIDDEN_MECHANISM_PATTERNS = (
    "sqlite proves",
    "database proves",
    "sqlite confirms the mechanism",
    "database confirms the mechanism",
    "sqlite closes the mechanism gap",
    "database closes the mechanism gap",
    "deltas prove",
    "delta proves",
)
CAUSAL_ATTRIBUTION_MARKERS = (
    "sole cause attribution",
    "passivation not isolated",
    "morphology/contact alternative",
    "hydrophobicity alternative",
    "multifunctional",
    "causal attribution",
    "causal isolation",
)
ANALOG_COVARIATE_MARKERS = (
    "morphology",
    "crystallinity",
    "hydrophobicity",
    "contact energetics",
    "recombination",
    "trap",
)
PIN_MARKERS = ("p-i-n", "pin", "inverted", "reverse")
NIP_MARKERS = ("n-i-p", "nip")
OPERATIONAL_RECIPE_MARKERS = (
    "spin coat",
    "spin-coat",
    "drop-cast",
    "antisolvent",
    "hotplate",
    "glovebox",
    "anneal at",
    "anneal for",
    "dmf",
    "dmso",
    "chlorobenzene",
    "toluene",
    "isopropanol",
    "ipa",
    "rpm",
)
OPERATIONAL_RECIPE_PATTERNS = (
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:mg\s*/\s*ml|mg\s+ml-1|mm|mM|mol\s*/\s*l|"
        r"mol\s*%|mol%|wt\s*%|wt%|vol\s*%|vol%)(?=\b|[^A-Za-z0-9_])",
        re.I,
    ),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*%\b(?=\s*(?:excess|best|optimum|optimal|window|boundary|dose))",
        re.I,
    ),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ul|uL|ml|mL)\b"),
    re.compile(r"\b(?:anneal|heating|heat)\b.{0,40}\b\d{2,3}\s*(?:degc|c|°c)\b", re.I),
    re.compile(
        r"(?i)(?:(?<=_)|^)(?:one|two|three|four|five|six|seven|eight|nine|ten)_percent(?=_|$)"
    ),
    re.compile(r"(?i)(?:(?<=_)|^)\d+(?:_\d+)?(?:m|mm|mol|pct|percent)(?=_|$)"),
    re.compile(r"(?i)(?:(?<=_)|^)recipe\d+(?:_\d+)*(?=_|$)"),
)
SYNTHESIS_EVIDENCE_TABLE_FIELDS = (
    "candidate_synthesis_claim",
    "source_labels",
    "evidence_class",
    "direction",
    "confidence_tier",
    "over_counting_risk",
)
SEMANTIC_MATRIX_ROW_FIELDS = (
    "row_label",
    "evidence_basis",
    "source_labels",
    "variable_role",
    "held_constant_design_assumptions",
    "discriminating_readouts",
    "h_alt_interpretation",
    "closure_rule",
    "non_closure_rule",
)
BROAD_FACTOR_GROUPS = {
    "intervention_family_axis",
    "absorber_or_phase_axis",
    "mechanism_axis",
    "morphology_normalization_axis",
    "architecture_translation_axis",
}
REQUIRED_BUNDLE_CLASSES = (
    "phase_composition",
    "residual_phase_quantification",
    "recombination_trap",
    "device_metrics",
    "stability_readout_history",
)
PBX2_REQUIRED_UPDATE_LABELS = (
    "chloride_distribution_isolated",
    "pb_rich_residue_effect_isolated",
    "morphology_normalization_survives",
    "wrong_location_residual_phase_penalty",
    "high_boundary_negative_case_confirmed",
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


def validate_retrieval_evidence_payload(payload: Any) -> ValidationResult:
    """Validate optional ``retrieval_evidence.yaml`` diagnostics."""
    result = ValidationResult()
    gap_entries = extract_retrieval_gap_entries(payload)
    if not gap_entries:
        result.errors.append("retrieval_evidence.yaml: no per-gap retrieval entries found")
        return result

    for index, gap in enumerate(gap_entries):
        path = f"retrieval_evidence[{index}]"
        if not isinstance(gap, dict):
            result.errors.append(f"{path}: gap retrieval entry must be a mapping")
            continue
        for field_name in (
            "gap_id",
            "successful_endpoints",
            "failed_endpoints",
            "same_package_lkm_chains",
            "cross_package_lkm_chains",
            "ambiguous_lkm_chains",
        ):
            if field_name not in gap or (
                field_name == "gap_id" and is_missing(gap.get(field_name))
            ):
                result.errors.append(f"{path}.{field_name}: required field is missing")
        if parse_coverage_is_low_mapping(gap) and is_missing(gap.get("parse_coverage_warning")):
            result.warnings.append(
                f"{path}.parse_coverage_warning: low SQLite coverage should be explicit"
            )
        if not is_missing(gap.get("architecture_translation_warning")):
            continue
        architecture_text = " ".join(text.lower() for _, text in iter_strings(gap, path))
        if contains_any(architecture_text, NIP_MARKERS) and contains_any(
            architecture_text, PIN_MARKERS
        ):
            result.warnings.append(
                f"{path}.architecture_translation_warning: source/lab architecture "
                "translation should be explicit"
            )
    return result


def extract_retrieval_gap_entries(payload: Any) -> list[Any]:
    """Return common per-gap retrieval evidence shapes."""
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("gaps", "retrieval_evidence", "gap_retrieval", "per_gap"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return list(value.values())
    return []


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

    validate_required_fields(card, required, result, card_path)
    validate_v2_planning_fields(card, result, card_path, smoke_test=smoke_test)
    warn_legacy_current_belief(card, result, card_path)

    if not smoke_test:
        source_context = card.get("source_device_context")
        if is_missing(source_context):
            source_context = card.get("device_context")
        validate_device_context(
            source_context,
            result,
            path_join(card_path, "source_device_context"),
            package_mode=stringify(card.get("package_mode")),
        )
        validate_lab_translation_context(
            card.get("lab_translation_context"),
            source_context,
            result,
            path_join(card_path, "lab_translation_context"),
        )
        validate_device_orientation_policy(card, source_context, result, card_path)

    if "interpretation_decision_tree" not in card and "outcome_matrix" not in card:
        result.errors.append(
            f"{card_path}: requires `interpretation_decision_tree` or `outcome_matrix`"
        )

    validate_database_precedents(
        card.get("database_precedents"),
        result,
        path_join(card_path, "database_precedents"),
    )
    validate_database_confidence(card.get("database_confidence"), result, card_path)
    validate_sqlite_role(card.get("sqlite_role"), result, path_join(card_path, "sqlite_role"))
    validate_design_memory_role(
        card.get("design_memory_role"), result, path_join(card_path, "design_memory_role")
    )
    validate_design_motif_evidence(
        card.get("design_motif_evidence"),
        result,
        path_join(card_path, "design_motif_evidence"),
    )
    warn_database_confidence_limitations(card, result, card_path)
    warn_weak_sqlite_tier_distribution(card, result, card_path)
    warn_suspicious_similarity_scores(card, result, card_path)
    warn_hysteresis_low_coverage(card, result, card_path)
    validate_mechanism_source_breakdown(
        card.get("mechanism_source_breakdown"),
        result,
        path_join(card_path, "mechanism_source_breakdown"),
    )
    validate_lkm_chain_scope(
        card.get("same_package_lkm_chains"),
        expected_scope="same_package",
        result=result,
        path=path_join(card_path, "same_package_lkm_chains"),
    )
    validate_lkm_chain_scope(
        card.get("cross_package_lkm_chains"),
        expected_scope="cross_package",
        result=result,
        path=path_join(card_path, "cross_package_lkm_chains"),
    )
    validate_lkm_chain_scope(
        card.get("ambiguous_lkm_chains"),
        expected_scope="ambiguous_package_scope",
        result=result,
        path=path_join(card_path, "ambiguous_lkm_chains"),
    )
    validate_lkm_failure_confidence(card, result, card_path)
    validate_sqlite_mechanism_limits(card, result, card_path)
    validate_outcome_matrix(
        card.get("outcome_matrix"), result, path_join(card_path, "outcome_matrix")
    )
    validate_gap_resolution_strategy(
        card.get("gap_resolution_strategy"),
        result,
        path_join(card_path, "gap_resolution_strategy"),
    )
    validate_synthesis_evidence_table(card, result, card_path)
    validate_semantic_matrix(card, result, card_path)
    validate_same_sample_bundle(
        card.get("same_sample_measurement_bundle"),
        result,
        path_join(card_path, "same_sample_measurement_bundle"),
    )
    validate_gaia_update_labels(
        card.get("gaia_evidence_node_mapping"),
        card,
        result,
        path_join(card_path, "gaia_evidence_node_mapping"),
    )
    validate_causal_isolation_controls(card, result, card_path)
    warn_readout_mappings(
        card.get("primary_readouts"), result, path_join(card_path, "primary_readouts")
    )
    warn_generic_device_context(
        card.get("source_device_context", card.get("device_context")),
        result,
        path_join(card_path, "source_device_context"),
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
    validate_forbidden_placeholders(card, result, card_path)
    validate_no_operational_recipe(card, result, card_path)

    return result


def validate_required_fields(
    card: dict[str, Any], required: list[str], result: ValidationResult, card_path: str
) -> None:
    """Validate card-level required fields with transitional aliases."""
    presence_only_fields = {
        "same_package_lkm_chains",
        "cross_package_lkm_chains",
        "ambiguous_lkm_chains",
    }
    for field_name in required:
        if (
            field_name == "source_device_context"
            and is_missing(card.get(field_name))
            and not is_missing(card.get("device_context"))
        ):
            result.warnings.append(
                f"{card_path}.source_device_context: missing canonical field; "
                "using legacy `device_context` as a transitional alias"
            )
            continue
        if (
            field_name == "gap_claim_belief"
            and is_missing(card.get(field_name))
            and not is_missing(card.get("current_belief"))
        ):
            result.warnings.append(
                f"{card_path}.gap_claim_belief: using legacy `current_belief` as "
                "a transitional alias"
            )
            continue
        if field_name in presence_only_fields:
            if field_name not in card:
                result.errors.append(f"{card_path}.{field_name}: required field is missing")
            continue
        if is_missing(card.get(field_name)):
            result.errors.append(f"{card_path}.{field_name}: required field is missing")


def validate_v2_planning_fields(
    card: dict[str, Any],
    result: ValidationResult,
    card_path: str,
    *,
    smoke_test: bool = False,
) -> None:
    """Warn on missing V2 planner fields and validate planning-level semantics."""
    for field_name in V2_RECOMMENDED_FIELDS:
        if is_missing(card.get(field_name)):
            if field_name == "planning_level" and stringify(card.get("package_mode")) == (
                "aggregate_corpus"
            ):
                result.warnings.append(
                    f"{card_path}.planning_level: aggregate card lacks planning_level"
                )
            else:
                result.warnings.append(f"{card_path}.{field_name}: V2 planner field is missing")

    planning_level = stringify(card.get("planning_level")).strip()
    if not planning_level:
        return
    if planning_level not in {"aggregate_roadmap", "implementation_candidate"}:
        result.errors.append(
            f"{card_path}.planning_level: must be aggregate_roadmap or implementation_candidate"
        )
        return

    package_mode = stringify(card.get("package_mode")).strip()
    if package_mode == "aggregate_corpus" and planning_level != "aggregate_roadmap":
        result.warnings.append(
            f"{card_path}.planning_level: aggregate_corpus cards should default to "
            "aggregate_roadmap"
        )
    if planning_level == "implementation_candidate" and not smoke_test:
        source_context = card.get("source_device_context", card.get("device_context"))
        if not isinstance(source_context, dict):
            result.errors.append(
                f"{card_path}.planning_level: implementation_candidate requires concrete "
                "source context"
            )
            return
        for field_name in DEVICE_CONTEXT_FIELDS:
            if is_missing(source_context.get(field_name)):
                result.errors.append(
                    f"{card_path}.planning_level: implementation_candidate requires "
                    f"source_device_context.{field_name}"
                )


def warn_legacy_current_belief(
    card: dict[str, Any], result: ValidationResult, card_path: str
) -> None:
    """Warn when the legacy belief field remains in a card."""
    if "current_belief" in card:
        result.warnings.append(f"{card_path}.current_belief: legacy field; use gap_claim_belief")


def validate_device_context(
    value: Any, result: ValidationResult, path: str, *, package_mode: str = "single_paper"
) -> None:
    """Require concrete device/intervention context in real-package mode."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping in real-package mode")
        return

    if package_mode == "aggregate_corpus":
        if value.get("package_mode") != "aggregate_corpus":
            result.errors.append(f"{path}.package_mode: aggregate source context must be explicit")
        if is_missing(value.get("corpus_level_distribution")) and is_missing(
            value.get("dominant_architecture_families")
        ):
            result.errors.append(
                f"{path}: aggregate_corpus mode requires corpus-level distribution "
                "or dominant architecture families"
            )
        return

    for field_name in DEVICE_CONTEXT_FIELDS:
        if is_missing(value.get(field_name)):
            result.errors.append(f"{path}.{field_name}: required device-context field is missing")


def validate_lab_translation_context(
    value: Any, source_context: Any, result: ValidationResult, path: str
) -> None:
    """Require the lab-preferred p-i-n translation context without overwriting source."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping")
        return

    for field_name in LAB_TRANSLATION_CONTEXT_FIELDS:
        if is_missing(value.get(field_name)):
            result.errors.append(f"{path}.{field_name}: required field is missing")

    preference_text = stringify(value.get("lab_preferred_device_architecture")).lower()
    if not contains_any(preference_text, PIN_MARKERS):
        result.errors.append(
            f"{path}.lab_preferred_device_architecture: must identify inverted p-i-n"
        )

    source_text = " ".join(text.lower() for _, text in iter_strings(source_context, path))
    translation_text = " ".join(text.lower() for _, text in iter_strings(value, path))
    if contains_any(source_text, NIP_MARKERS) and not (
        "translation" in translation_text or "adaptation" in translation_text
    ):
        result.errors.append(
            f"{path}.translation_note: n-i-p sources require an explicit p-i-n "
            "translation/adaptation note"
        )


def validate_device_orientation_policy(
    card: dict[str, Any], source_context: Any, result: ValidationResult, path: str
) -> None:
    """Validate p-i-n lab preference while preserving source-device context."""
    source_text = " ".join(text.lower() for _, text in iter_strings(source_context, path))
    lab_text = " ".join(
        text.lower() for _, text in iter_strings(card.get("lab_translation_context"), path)
    )
    controls_text = " ".join(text.lower() for _, text in iter_strings(card.get("controls"), path))

    if contains_any(source_text, NIP_MARKERS):
        for field_name in (
            "portability_risks_for_p_i_n",
            "architecture_sensitive_readouts",
            "what_not_to_generalize",
            "p_i_n_specific_controls",
            "p_i_n_specific_readouts",
            "p_i_n_specific_risks",
        ):
            if is_missing(card.get(field_name)):
                result.errors.append(
                    f"{path}.{field_name}: required when source architecture differs "
                    "from inverted p-i-n lab preference"
                )
        if not contains_any(lab_text, PIN_MARKERS):
            result.errors.append(
                f"{path}.lab_translation_context: must include inverted p-i-n adaptation"
            )
        pin_design_text = " ".join(
            text.lower()
            for _, text in iter_strings(
                {
                    "p_i_n_specific_controls": card.get("p_i_n_specific_controls"),
                    "p_i_n_specific_readouts": card.get("p_i_n_specific_readouts"),
                    "p_i_n_specific_risks": card.get("p_i_n_specific_risks"),
                    "what_not_to_generalize": card.get("what_not_to_generalize"),
                },
                path,
            )
        )
        for marker in ("baseline", "readout", "risk", "not as p-i-n proof"):
            if marker not in pin_design_text:
                result.errors.append(
                    f"{path}.p_i_n_specific_controls: p-i-n translation must include "
                    f"{marker} design content"
                )

    has_pin_lab_context = contains_any(lab_text, PIN_MARKERS)
    has_pin_matched_controls = contains_any(controls_text, ("matched", "p-i-n", "same stack"))
    if contains_any(source_text, PIN_MARKERS) and not (
        has_pin_lab_context and has_pin_matched_controls
    ):
        result.errors.append(
            f"{path}.controls: p-i-n source packages require matched p-i-n controls/readouts"
        )


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
        validate_similarity_score_breakdown(
            row.get("similarity_score"), result, path_join(row_path, "similarity_score")
        )


def validate_similarity_score_breakdown(value: Any, result: ValidationResult, path: str) -> None:
    """Validate V2 SQLite similarity-score breakdowns."""
    if isinstance(value, int | float):
        result.warnings.append(
            f"{path}: legacy numeric similarity_score; V2 expects a component breakdown"
        )
        return
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping with component scores")
        return
    for field_name in SIMILARITY_SCORE_FIELDS:
        if field_name not in value:
            result.errors.append(f"{path}.{field_name}: similarity component is missing")
            continue
        numeric = value.get(field_name)
        if not isinstance(numeric, int | float):
            result.errors.append(f"{path}.{field_name}: similarity component must be numeric")


def validate_sqlite_role(value: Any, result: ValidationResult, path: str) -> None:
    """Ensure SQLite is explicitly limited to precedent/delta background."""
    text = " ".join(item.lower() for _, item in iter_strings(value, path))
    if not text:
        return

    missing = [marker for marker in SQLITE_ROLE_MARKERS if marker not in text]
    if missing:
        result.errors.append(
            f"{path}: must state SQLite is for precedent discovery, stack/intervention "
            "matching, paired delta background, and not mechanism proof"
        )


def validate_design_memory_role(value: Any, result: ValidationResult, path: str) -> None:
    """Ensure design memory is motif guidance, not source-mechanism proof."""
    text = " ".join(item.lower() for _, item in iter_strings(value, path))
    if not text:
        return
    if "motif" not in text or "not treated as direct proof" not in text:
        result.errors.append(
            f"{path}: design memory must be limited to motif retrieval and not direct proof"
        )


def validate_design_motif_evidence(value: Any, result: ValidationResult, path: str) -> None:
    """Validate open-world design motif evidence shape."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping")
        return
    for field_name in (
        "retrieved_from_lkm",
        "retrieved_from_design_memory",
        "retrieved_from_sqlite_background",
        "motif_synthesis_summary",
    ):
        if is_missing(value.get(field_name)):
            result.errors.append(f"{path}.{field_name}: required field is missing")
    motif_text = " ".join(text.lower() for _, text in iter_strings(value, path))
    if "proof of the source-package mechanism" in motif_text and "not treated" not in motif_text:
        result.errors.append(f"{path}: design motifs cannot be direct source-mechanism proof")


def validate_mechanism_source_breakdown(value: Any, result: ValidationResult, path: str) -> None:
    """Require explicit source separation for mechanism attribution."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping")
        return

    for field_name in MECHANISM_SOURCE_FIELDS:
        if is_missing(value.get(field_name)):
            result.errors.append(f"{path}.{field_name}: required field is missing")

    sqlite_text = " ".join(
        text.lower()
        for _, text in iter_strings(value.get("sqlite_precedent_delta_background"), path)
    )
    if any(pattern in sqlite_text for pattern in ("proves", "primary mechanism")) or (
        "proof" in sqlite_text and "not mechanism proof" not in sqlite_text
    ):
        result.errors.append(
            f"{path}.sqlite_precedent_delta_background: SQLite cannot be mechanism proof"
        )


def validate_lkm_chain_scope(  # noqa: C901
    value: Any, *, expected_scope: str, result: ValidationResult, path: str
) -> None:
    """Validate same-package and cross-package LKM chain provenance."""
    if is_missing(value):
        return
    if not isinstance(value, list):
        result.errors.append(f"{path}: must be a list")
        return

    for index, chain in enumerate(value):
        chain_path = path_join(path, index)
        if not isinstance(chain, dict):
            result.errors.append(f"{chain_path}: chain summary must be a mapping")
            continue

        scope = stringify(
            first_present(chain, ("reasoning_scope", "scope", "chain_scope", "provenance_scope"))
        ).lower()
        cross_flag = chain.get("cross_package")
        if expected_scope == "cross_package":
            if scope and "cross" not in scope:
                result.errors.append(f"{chain_path}: cross-package chain mislabeled as {scope}")
            if cross_flag is False:
                result.errors.append(f"{chain_path}.cross_package: must not be false")
        elif expected_scope == "same_package":
            if scope and "same" not in scope:
                result.errors.append(f"{chain_path}: same-package chain mislabeled as {scope}")
            if cross_flag is True:
                result.errors.append(f"{chain_path}.cross_package: must not be true")
        else:
            if scope and not ("ambiguous" in scope or "unknown" in scope):
                result.errors.append(f"{chain_path}: ambiguous-scope chain mislabeled as {scope}")
            if cross_flag is True:
                result.errors.append(
                    f"{chain_path}.cross_package: ambiguous-scope chains must not be true"
                )

        if all(is_missing(chain.get(field_name)) for field_name in LKM_PROVENANCE_FIELDS):
            result.errors.append(
                f"{chain_path}: must preserve at least one LKM provenance field "
                "(source_package, paper_id, claim_id, conclusion_id, chain_id, title, score)"
            )


def validate_lkm_failure_confidence(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Cap confidence when LKM is unavailable or failed."""
    lkm_text = " ".join(
        text.lower()
        for _, text in iter_strings(
            {
                "lkm_role": card.get("lkm_role"),
                "lkm_evidence_summary": card.get("lkm_evidence_summary"),
                "lkm_queries_run": card.get("lkm_queries_run"),
            },
            path,
        )
    )
    if not any(marker in lkm_text for marker in LKM_FAILURE_MARKERS):
        return

    confidence = normalize_confidence(card.get("confidence"))
    if confidence == "high":
        result.errors.append(f"{path}.confidence: LKM failure cannot have high confidence")
        return

    if confidence == "moderate":
        local_text = mechanism_source_text(card, "package_local_gaia_evidence")
        has_local_support = (
            "package-local" in local_text or "package local" in local_text or "strong" in local_text
        )
        if not has_local_support:
            result.errors.append(
                f"{path}.confidence: LKM failure permits moderate confidence only with "
                "strong package-local Gaia mechanism reasoning"
            )


def validate_sqlite_mechanism_limits(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Reject SQLite-only mechanism closure or attribution."""
    all_text = " ".join(text.lower() for _, text in iter_strings(card, path))
    for pattern in SQLITE_FORBIDDEN_MECHANISM_PATTERNS:
        if pattern in all_text:
            result.errors.append(f"{path}: SQLite/delta evidence cannot prove mechanism")
            break

    lkm_failed = any(marker in all_text for marker in LKM_FAILURE_MARKERS)
    local_text = mechanism_source_text(card, "package_local_gaia_evidence")
    success_text = " ".join(
        text.lower()
        for _, text in iter_strings(card.get("success_criterion_for_closing_gap"), path)
    )
    if (
        lkm_failed
        and not local_text.strip()
        and ("mechanism gap closed" in success_text or "close mechanism gap" in success_text)
    ):
        result.errors.append(
            f"{path}.success_criterion_for_closing_gap: SQLite-only evidence cannot "
            "close a mechanism gap"
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


def validate_database_confidence(value: Any, result: ValidationResult, path: str) -> None:
    """Validate the structured V2 database-confidence limitation."""
    if is_missing(value):
        return
    if isinstance(value, str):
        result.warnings.append(
            f"{path}.database_confidence: legacy string value; V2 expects a mapping"
        )
        return
    if not isinstance(value, dict):
        result.errors.append(f"{path}.database_confidence: must be a mapping")
        return
    for field_name in ("overall", "metric_coverage", "interpretation_limit"):
        if is_missing(value.get(field_name)):
            result.errors.append(
                f"{path}.database_confidence.{field_name}: required field is missing"
            )
    limit_text = stringify(value.get("interpretation_limit")).lower()
    if limit_text and (
        "cannot raise mechanism confidence" not in limit_text or "close" not in limit_text
    ):
        result.warnings.append(
            f"{path}.database_confidence.interpretation_limit: should state SQLite "
            "cannot raise mechanism confidence or close mechanism nodes"
        )


def warn_weak_sqlite_tier_distribution(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Warn when broad-context SQLite rows dominate precedent tiers."""
    precedents = card.get("database_precedents")
    if not isinstance(precedents, dict):
        return
    tier1 = numeric_count(lookup_tier_count(precedents, "tier1_strong_precedent"))
    tier2 = numeric_count(lookup_tier_count(precedents, "tier2_related_precedent"))
    tier3 = numeric_count(lookup_tier_count(precedents, "tier3_broad_context"))
    rejected = numeric_count(lookup_tier_count(precedents, "rejected_or_unusable"))
    if tier3 + rejected > tier1 + tier2 and tier1 == 0:
        result.warnings.append(
            f"{path}.database_precedents.tier_counts: broad context or unusable SQLite "
            "rows dominate; keep confidence penalized"
        )


def warn_suspicious_similarity_scores(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Warn when multiple SQLite rows report a perfect total similarity."""
    rows = collect_precedent_rows(card.get("database_precedents"))
    perfect_rows = [
        row
        for row in rows
        if isinstance(row, dict) and similarity_total(row.get("similarity_score")) == 1.0
    ]
    if len(perfect_rows) >= 2:
        result.warnings.append(
            f"{path}.database_precedents.top_precedent_rows: repeated "
            "similarity_score.total == 1.0 is suspicious"
        )


def warn_hysteresis_low_coverage(card: dict[str, Any], result: ValidationResult, path: str) -> None:
    """Warn when hysteresis-focused cards have poor hysteresis parse coverage."""
    card_text = " ".join(
        text.lower()
        for _, text in iter_strings(
            {
                "gap_type": card.get("gap_type"),
                "gap_family": card.get("gap_family"),
                "mechanism_axes": card.get("mechanism_axes"),
                "primary_mechanism_axis": card.get("primary_mechanism_axis"),
                "original_evidence_gap_text": card.get("original_evidence_gap_text"),
            },
            path,
        )
    )
    if "hysteresis" not in card_text and "ion_migration" not in card_text:
        return
    precedents = card.get("database_precedents")
    if not isinstance(precedents, dict):
        return
    coverage = precedents.get("parse_coverage")
    if not isinstance(coverage, dict):
        return
    ratio = parse_coverage_ratio(coverage.get("hysteresis"))
    if ratio is not None and ratio < 0.5:
        result.warnings.append(
            f"{path}.database_precedents.parse_coverage.hysteresis: low hysteresis "
            "coverage penalizes ion-migration/hysteresis confidence"
        )


def parse_coverage_is_low(parse_coverage: dict[str, Any]) -> bool:
    """Return true when a parse-coverage mapping contains a low ratio."""
    for value in parse_coverage.values():
        ratio = parse_coverage_ratio(value)
        if ratio is not None and ratio < 0.5:
            return True
    return False


def parse_coverage_is_low_mapping(value: dict[str, Any]) -> bool:
    """Return true when an arbitrary retrieval entry has low SQLite coverage."""
    for key in ("parse_coverage", "sqlite_parse_coverage", "database_parse_coverage"):
        coverage = value.get(key)
        if isinstance(coverage, dict) and parse_coverage_is_low(coverage):
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


def numeric_count(value: Any) -> int:
    """Convert loose tier counts to integers."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def similarity_total(value: Any) -> float:
    """Read a V2 or legacy similarity score total."""
    if isinstance(value, dict):
        value = value.get("total")
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def lookup_tier_count(database_precedents: dict[str, Any], tier: str) -> Any:
    """Find a tier count across accepted tier-count shapes."""
    legacy_aliases = {
        "tier1_strong_precedent": ("tier1", "tier1_count"),
        "tier2_related_precedent": ("tier2", "tier2_count"),
        "tier3_broad_context": ("tier3", "tier3_count"),
        "rejected_or_unusable": ("rejected", "rejected_count"),
    }
    direct_names = (tier, f"{tier}_count", *legacy_aliases.get(tier, ()))
    for name in direct_names:
        if name in database_precedents:
            return database_precedents[name]

    tier_counts = database_precedents.get("tier_counts")
    if isinstance(tier_counts, dict):
        for name in direct_names:
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


def validate_gap_resolution_strategy(value: Any, result: ValidationResult, path: str) -> None:
    """Require a generic, extensible gap-resolution design strategy."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: must be a mapping")
        return

    required_fields = (
        "strategy_type",
        "uncertainty_to_resolve",
        "decomposition_axes",
        "confounders_to_bound",
        "decision_rules",
        "extension_hooks",
    )
    for field_name in required_fields:
        if is_missing(value.get(field_name)):
            result.errors.append(f"{path}.{field_name}: required field is missing")

    strategy_text = " ".join(text.lower() for _, text in iter_strings(value, path))
    if "ff_loss" in strategy_text or "ff-loss" in strategy_text:
        result.errors.append(f"{path}: strategy must not hard-code FF as a mandatory special case")

    axes = value.get("decomposition_axes")
    if isinstance(axes, list) and len(axes) < 2:
        result.errors.append(f"{path}.decomposition_axes: should include multiple alternatives")


def validate_synthesis_evidence_table(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Validate parsed SYNTHESIS_PLAN Evidence Table rows when present."""
    brief = card.get("package_evidence_brief")
    if not isinstance(brief, dict):
        return
    inputs = brief.get("inputs_read")
    inputs_text = " ".join(stringify(item) for item in as_iterable(inputs)).lower()
    rows = brief.get("synthesis_evidence_table")
    if "synthesis_plan.md" not in inputs_text and is_missing(rows):
        return
    if not isinstance(rows, list) or not rows:
        result.errors.append(
            f"{path}.package_evidence_brief.synthesis_evidence_table: "
            "SYNTHESIS_PLAN.md was read but no Evidence Table rows were parsed"
        )
        return

    for index, row in enumerate(rows):
        row_path = path_join(
            path_join(path, "package_evidence_brief.synthesis_evidence_table"),
            index,
        )
        if not isinstance(row, dict):
            result.errors.append(f"{row_path}: Evidence Table row must be a mapping")
            continue
        for field_name in SYNTHESIS_EVIDENCE_TABLE_FIELDS:
            if is_missing(row.get(field_name)):
                result.errors.append(f"{row_path}.{field_name}: parsed field is missing")


def validate_semantic_matrix(  # noqa: C901
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Validate concrete semantic matrix rows for aggregate planning."""
    matrix = card.get("minimal_discriminating_matrix")
    matrix_path = path_join(path, "minimal_discriminating_matrix")
    if not isinstance(matrix, list) or not matrix:
        result.errors.append(f"{matrix_path}: required non-empty matrix is missing")
        return

    semantic_rows = [
        row for row in matrix if isinstance(row, dict) and not is_missing(row.get("row_label"))
    ]
    package_mode = stringify(card.get("package_mode"))
    if package_mode == "aggregate_corpus":
        if not semantic_rows:
            result.errors.append(
                f"{matrix_path}: aggregate plans require concrete semantic rows, "
                "not only broad factor axes"
            )
        factor_groups = {
            stringify(row.get("factor_group"))
            for row in matrix
            if isinstance(row, dict) and not is_missing(row.get("factor_group"))
        }
        if not semantic_rows and factor_groups and factor_groups <= BROAD_FACTOR_GROUPS:
            result.errors.append(
                f"{matrix_path}: aggregate plan emits only broad factor axes without "
                "package-evidence semantic rows"
            )

    for index, row in enumerate(semantic_rows):
        row_path = path_join(matrix_path, index)
        for field_name in SEMANTIC_MATRIX_ROW_FIELDS:
            if is_missing(row.get(field_name)):
                result.errors.append(f"{row_path}.{field_name}: semantic matrix field is missing")
        interpretation = row.get("h_alt_interpretation")
        if isinstance(interpretation, dict):
            for branch in ("supports_H", "supports_Alt", "mixed_or_unresolved"):
                if is_missing(interpretation.get(branch)):
                    result.errors.append(f"{row_path}.h_alt_interpretation.{branch}: missing")

    if evidence_text_has_pbx2(card):
        labels = {stringify(row.get("row_label")) for row in semantic_rows}
        required = {
            "baseline",
            "Pb-rich only",
            "chloride-source only",
            "PbCl2 isolead substitution",
            "PbCl2 excess coupling",
            "chloride + Pb-rich combined",
            "high-boundary condition",
        }
        missing = sorted(required - labels)
        if missing:
            result.errors.append(
                f"{matrix_path}: PbX2/chloride evidence requires semantic rows {', '.join(missing)}"
            )


def validate_same_sample_bundle(value: Any, result: ValidationResult, path: str) -> None:
    """Require the mechanism-decomposition same-sample readout bundle classes."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: same-sample bundle must be a mapping")
        return
    for key in REQUIRED_BUNDLE_CLASSES:
        if is_missing(value.get(key)):
            result.errors.append(f"{path}.{key}: required same-sample bundle class is missing")


def validate_gaia_update_labels(
    value: Any, card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Require readable Gaia update labels instead of opaque E-style IDs."""
    if not isinstance(value, dict):
        result.errors.append(f"{path}: Gaia update mapping must be a mapping")
        return
    labels = value.get("readable_update_labels")
    if is_missing(labels):
        labels = value.get("update_targets")
    label_list = [stringify(item) for item in as_iterable(labels) if not is_missing(item)]
    if not label_list:
        result.errors.append(f"{path}.readable_update_labels: no readable update labels found")
        return
    for label in label_list:
        if re.fullmatch(r"E\d+", label.strip(), flags=re.I):
            result.errors.append(f"{path}.readable_update_labels: opaque update label `{label}`")
        if label in {"support_H", "support_Alt", "mixed_or_unresolved"}:
            result.errors.append(
                f"{path}.readable_update_labels: `{label}` is an outcome state, "
                "not a readable Gaia update label"
            )

    if evidence_text_has_pbx2(card):
        missing = [label for label in PBX2_REQUIRED_UPDATE_LABELS if label not in label_list]
        if missing:
            result.errors.append(
                f"{path}.readable_update_labels: PbX2/chloride evidence requires "
                f"{', '.join(missing)}"
            )


def evidence_text_has_pbx2(card: dict[str, Any]) -> bool:
    """Return true when card-local evidence contains PbX2/chloride synthesis motifs."""
    text = " ".join(
        text.lower() for _, text in iter_strings(card.get("package_evidence_brief"), "")
    )
    return contains_any(text, ("pbcl2", "pbi2", "pb-rich", "residual pb", "chloride-source"))


def as_iterable(value: Any) -> list[Any]:
    """Return a list from common scalar/list values."""
    if is_missing(value):
        return []
    if isinstance(value, list | tuple | set):
        return list(value)
    return [value]


def validate_causal_isolation_controls(
    card: dict[str, Any], result: ValidationResult, path: str
) -> None:
    """Require analog-control logic for causal-attribution gaps."""
    card_text = " ".join(
        text.lower()
        for _, text in iter_strings(
            {
                "gap_type": card.get("gap_type"),
                "scientific_uncertainty": card.get("scientific_uncertainty"),
                "original_evidence_gap_text": card.get("original_evidence_gap_text"),
                "mechanism_decomposition_question": card.get("mechanism_decomposition_question"),
            },
            path,
        )
    )
    if not any(marker in card_text for marker in CAUSAL_ATTRIBUTION_MARKERS):
        return

    analog_value = card.get("causal_isolation_controls")
    controls_text = " ".join(text.lower() for _, text in iter_strings(card.get("controls"), path))
    analog_text = " ".join(text.lower() for _, text in iter_strings(analog_value, path))
    combined = f"{controls_text} {analog_text}"
    if "analog" not in combined:
        result.errors.append(
            f"{path}.causal_isolation_controls: causal attribution gaps require "
            "functional analog-control logic"
        )
        return

    for marker in ANALOG_COVARIATE_MARKERS:
        if marker not in combined:
            result.errors.append(
                f"{path}.causal_isolation_controls: analog controls must bound {marker}"
            )

    if "follow-up narrowing" not in combined and "cannot close" not in combined:
        result.errors.append(
            f"{path}.causal_isolation_controls: must state that multi-variable analogs "
            "only narrow follow-up and cannot close the causal gap"
        )


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
    """Return precedent rows from top and demoted V2 surfaces."""
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        collected: list[Any] = []
        rows = lookup_top_rows(value)
        if isinstance(rows, list):
            collected.extend(rows)
        demoted = value.get("demoted_precedent_rows")
        if isinstance(demoted, list):
            collected.extend(demoted)
        return collected
    return []


def warn_generic_phrases(value: Any, result: ValidationResult, path: str) -> None:
    """Warn when generic non-decision phrases appear anywhere in a card."""
    for item_path, text in iter_strings(value, path):
        lowered = text.lower()
        for phrase in GENERIC_PHRASES:
            if phrase in lowered:
                result.warnings.append(f"{item_path}: generic phrase `{phrase}`")


def validate_forbidden_placeholders(value: Any, result: ValidationResult, path: str) -> None:
    """Reject known placeholder sentences from final outputs."""
    for item_path, text in iter_strings(value, path):
        for placeholder in FORBIDDEN_PLACEHOLDER_STRINGS:
            if placeholder in text:
                result.errors.append(f"{item_path}: forbidden placeholder text leaked")


def validate_no_operational_recipe(value: Any, result: ValidationResult, path: str) -> None:
    """Reject operational wet-lab recipe details."""
    for item_path, text in iter_strings(value, path):
        lowered = text.lower()
        if any(marker in lowered for marker in OPERATIONAL_RECIPE_MARKERS):
            result.errors.append(f"{item_path}: operational wet-lab recipe detail is not allowed")
            continue
        if any(pattern.search(text) for pattern in OPERATIONAL_RECIPE_PATTERNS):
            result.errors.append(f"{item_path}: operational wet-lab recipe detail is not allowed")


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


def contains_any(text: str, markers: tuple[str, ...]) -> bool:
    """Return true when ``text`` contains any marker."""
    return any(marker in text for marker in markers)


def normalize_confidence(value: Any) -> str:
    """Normalize confidence labels and simple numeric confidence values."""
    text = stringify(value).strip().lower()
    if text in {"high", "moderate", "medium", "low"}:
        return "moderate" if text == "medium" else text
    try:
        numeric = float(text)
    except ValueError:
        return text
    if numeric >= 0.8:
        return "high"
    if numeric >= 0.5:
        return "moderate"
    return "low"


def mechanism_source_text(card: dict[str, Any], field_name: str) -> str:
    """Return text from one mechanism-source-breakdown field."""
    breakdown = card.get("mechanism_source_breakdown")
    if not isinstance(breakdown, dict):
        return ""
    return " ".join(text.lower() for _, text in iter_strings(breakdown.get(field_name), field_name))


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
    parser.add_argument(
        "--retrieval-evidence",
        type=Path,
        help="Optional retrieval_evidence.yaml path to validate alongside experiments.yaml.",
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
    if args.retrieval_evidence is not None:
        result.extend(validate_retrieval_evidence_payload(load_yaml(args.retrieval_evidence)))
    print_result(result)
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
