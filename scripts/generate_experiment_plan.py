"""Generate design-level experiment plans from Gaia Evidence Gaps.

This is the automation entrypoint for the ``gaia-gap-to-experiment-perovskite``
skill. It reads package artifacts, performs bounded SQLite precedent retrieval,
and writes ``experiments.yaml``, ``EXPERIMENT_PLAN.md``, and
``retrieval_evidence.yaml`` without emitting operational wet-lab recipes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

# ruff: noqa: E501

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from photovoltaic_metric_templates import (  # type: ignore[import-not-found]  # noqa: E402
    build_ff_loss_budget_card,
)

DEFAULT_DB_PATH = Path(
    "/share/hwz/Perovskite_Database_Multiagents/literature_extraction/data_merger/"
    "merged_gpt5mini_data_with_chemical_data.db"
)

REQUIRED_CONTEXT_FIELDS = (
    "source_package",
    "solar_cell_structure",
    "cell_stack_sequence",
    "perovskite_composition",
    "intervention_location",
    "modulator_material_or_family",
)

MECHANISM_AXES = (
    "recombination_defect_passivation",
    "charge_extraction_collection",
    "contact_energetics_barrier",
    "series_shunt_leakage_loss",
    "ion_migration_hysteresis",
    "morphology_crystallinity_phase",
    "stability_degradation_pathway",
    "hydrophobicity_environmental_resistance",
    "optical_absorption_jsc",
    "interface_selectivity",
    "dopant_additive_chemical_interaction",
    "scalability_reproducibility",
    "architecture_portability",
    "model_mapping_quantification",
)

CARD_ARCHETYPE_TITLES = {
    "ff_loss_budget": "FF-loss budget and device-loss decomposition",
    "recombination_loss_mapping": "Recombination-loss and device-metric mapping",
    "charge_extraction_collection": "Charge extraction and carrier-collection discrimination",
    "ion_migration_hysteresis": "Ion migration, hysteresis, and bias-history discrimination",
    "functional_analog_causal_isolation": "Functional analog controls for causal isolation",
    "stability_degradation_pathway": "Stability and degradation-pathway discrimination",
    "morphology_phase_causality": "Morphology, crystallinity, and phase-causality discrimination",
    "contact_energetics_interface_selectivity": "Contact energetics and interface selectivity",
    "p_i_n_architecture_translation": "p-i-n architecture translation and portability",
    "model_mapping_quantification": "Quantitative model mapping from mechanism proxy to device metric",
    "generic_uncertainty": "Unresolved mechanism uncertainty",
}

ARCHETYPE_TO_PRIMARY_AXIS = {
    "ff_loss_budget": "series_shunt_leakage_loss",
    "recombination_loss_mapping": "recombination_defect_passivation",
    "charge_extraction_collection": "charge_extraction_collection",
    "ion_migration_hysteresis": "ion_migration_hysteresis",
    "functional_analog_causal_isolation": "dopant_additive_chemical_interaction",
    "stability_degradation_pathway": "stability_degradation_pathway",
    "morphology_phase_causality": "morphology_crystallinity_phase",
    "contact_energetics_interface_selectivity": "contact_energetics_barrier",
    "p_i_n_architecture_translation": "architecture_portability",
    "model_mapping_quantification": "model_mapping_quantification",
    "generic_uncertainty": "architecture_portability",
}

ARCHETYPE_DEFAULT_AXES = {
    "ff_loss_budget": [
        "series_shunt_leakage_loss",
        "recombination_defect_passivation",
        "contact_energetics_barrier",
        "ion_migration_hysteresis",
    ],
    "recombination_loss_mapping": [
        "recombination_defect_passivation",
        "contact_energetics_barrier",
        "morphology_crystallinity_phase",
    ],
    "charge_extraction_collection": [
        "charge_extraction_collection",
        "interface_selectivity",
        "optical_absorption_jsc",
        "morphology_crystallinity_phase",
    ],
    "ion_migration_hysteresis": [
        "ion_migration_hysteresis",
        "contact_energetics_barrier",
        "recombination_defect_passivation",
    ],
    "functional_analog_causal_isolation": [
        "dopant_additive_chemical_interaction",
        "recombination_defect_passivation",
        "morphology_crystallinity_phase",
        "hydrophobicity_environmental_resistance",
        "contact_energetics_barrier",
    ],
    "stability_degradation_pathway": [
        "stability_degradation_pathway",
        "hydrophobicity_environmental_resistance",
        "ion_migration_hysteresis",
        "contact_energetics_barrier",
    ],
    "morphology_phase_causality": [
        "morphology_crystallinity_phase",
        "recombination_defect_passivation",
        "optical_absorption_jsc",
        "contact_energetics_barrier",
    ],
    "contact_energetics_interface_selectivity": [
        "contact_energetics_barrier",
        "interface_selectivity",
        "recombination_defect_passivation",
        "charge_extraction_collection",
    ],
    "p_i_n_architecture_translation": [
        "architecture_portability",
        "interface_selectivity",
        "contact_energetics_barrier",
    ],
    "model_mapping_quantification": [
        "model_mapping_quantification",
        "recombination_defect_passivation",
        "contact_energetics_barrier",
        "series_shunt_leakage_loss",
    ],
    "generic_uncertainty": ["architecture_portability"],
}

ARCHETYPE_PRIORITY_RANGES = {
    "ff_loss_budget": (94, 90, 98),
    "functional_analog_causal_isolation": (91, 88, 95),
    "recombination_loss_mapping": (88, 82, 94),
    "model_mapping_quantification": (87, 82, 92),
    "charge_extraction_collection": (86, 80, 92),
    "contact_energetics_interface_selectivity": (84, 78, 90),
    "stability_degradation_pathway": (83, 76, 90),
    "morphology_phase_causality": (82, 75, 88),
    "ion_migration_hysteresis": (81, 75, 88),
    "p_i_n_architecture_translation": (79, 72, 86),
    "generic_uncertainty": (62, 40, 70),
}

ARCHETYPE_REGISTRY: dict[str, dict[str, Any]] = {
    key: {
        "applicability_criteria": [title],
        "forbidden_when": [
            "the gap maps more specifically to another mechanism axis",
            "the required observable is absent from the package/LKM context",
        ],
        "mechanism_axes": ARCHETYPE_DEFAULT_AXES[key],
        "default_H_pattern": "archetype-specific H readouts support the primary mechanism axis",
        "default_Alt_pattern": "competing branch or covariate readouts explain the observation",
        "recommended_readout_classes": [title],
        "confounders_to_bound": [
            "architecture",
            "composition or absorber family",
            "intervention location",
            "measurement-history or proxy-only artifacts",
        ],
        "success_criterion_for_closing_gap": (
            "close only with direct H-vs-Alt readout logic and bounded confounders"
        ),
        "non_closure_criteria": [
            "readouts are proxy-only",
            "H and Alt branches remain mixed_or_unresolved",
            "SQLite precedent background is the only support",
        ],
        "failure_modes": ["covariates move with the target readout", "architecture transfer fails"],
        "p_i_n_translation_hooks": ["preserve source context", "add p-i-n matched controls"],
        "safety_boundary_note": (
            "Design-level planning only; no solvent, concentration, annealing, or fabrication recipe."
        ),
    }
    for key, title in CARD_ARCHETYPE_TITLES.items()
}

ARCHETYPE_MOTIF_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "ff_loss_budget": {
        "readout_motifs": [
            "branch-resolved J-V/device-loss budget",
            "dark leakage and shunt-sensitive readout",
            "contact/transport barrier diagnostic",
            "recombination-loss proxy paired to device population",
        ],
        "control_motifs": [
            "matched no-intervention device population",
            "contact-stack comparator",
            "scan-history comparator where relevant",
        ],
        "confounder_motifs": [
            "series resistance",
            "shunt/leakage",
            "contact resistance",
            "transport/contact barrier",
            "hysteresis/scan-history",
        ],
    },
    "recombination_loss_mapping": {
        "readout_motifs": [
            "trap/nonradiative-recombination proxy",
            "bulk versus interface recombination localization",
            "contact-mediated recombination bound",
        ],
        "control_motifs": [
            "same absorber-family device population",
            "contact-mediated recombination comparator",
            "morphology-bounded comparator",
        ],
        "confounder_motifs": [
            "bulk recombination",
            "interface recombination",
            "contact-mediated recombination",
            "morphology-induced lifetime change",
            "measurement-only proxy risk",
        ],
    },
    "charge_extraction_collection": {
        "readout_motifs": [
            "transient extraction or carrier-collection timing",
            "recombination lifetime context",
            "contact/transport proxy delta",
        ],
        "control_motifs": [
            "contact-only comparator",
            "morphology-matched comparator",
            "same-device metric population paired to timing readouts",
        ],
        "confounder_motifs": [
            "suppressed recombination during collection",
            "contact selectivity",
            "optical absorption/Jsc confounder",
            "morphology/mobility covariate",
        ],
    },
    "ion_migration_hysteresis": {
        "readout_motifs": [
            "paired hysteresis index and scan-direction delta",
            "bias-history response",
            "ion or interfacial charge accumulation-sensitive readout",
        ],
        "control_motifs": ["scan-direction comparator", "bias-history comparator"],
        "confounder_motifs": [
            "contact/barrier effect",
            "recombination effect",
            "scan-protocol artifact",
        ],
    },
    "functional_analog_causal_isolation": {
        "readout_motifs": [
            "target chemical-interaction readout",
            "trap/recombination-sensitive passivation readout",
            "morphology/crystallinity/hydrophobicity/contact covariate bounds",
        ],
        "control_motifs": [
            "functional analog preserving non-target covariate",
            "functional analog preserving target interaction where available",
            "same stack and absorber-family comparison",
        ],
        "confounder_motifs": [
            "morphology",
            "crystallinity",
            "hydrophobicity",
            "contact energetics",
            "process covariate",
        ],
    },
    "stability_degradation_pathway": {
        "readout_motifs": [
            "pathway-resolved stability retention",
            "hydrophobic/moisture-barrier discrimination",
            "phase/contact/ion-degradation pathway readout",
        ],
        "control_motifs": [
            "matched initial-performance baseline",
            "same stress-class comparator",
            "barrier or encapsulation/process comparator",
        ],
        "confounder_motifs": [
            "initial-performance bias",
            "hydrophobic barrier",
            "phase transition",
            "contact degradation",
            "ion migration",
            "encapsulation/process artifact",
        ],
    },
    "morphology_phase_causality": {
        "readout_motifs": [
            "morphology/crystallinity/phase readout",
            "passivation-sensitive bound",
            "optical/contact confounder readout",
        ],
        "control_motifs": [
            "processing-control comparator",
            "passivation-sensitive comparator",
            "optical absorption/contact comparator",
        ],
        "confounder_motifs": [
            "process artifact",
            "passivation covariate",
            "optical absorption/Jsc",
            "contact/interface effect",
        ],
    },
    "contact_energetics_interface_selectivity": {
        "readout_motifs": [
            "work-function/surface-potential/band-alignment readout",
            "interface selectivity and extraction-barrier readout",
            "contact resistance/recombination bound",
        ],
        "control_motifs": [
            "matched contact stack",
            "HTL-side versus ETL-side comparator",
            "transport/contact-resistance comparator",
        ],
        "confounder_motifs": [
            "recombination suppression",
            "transport barrier",
            "contact resistance",
            "architecture-specific interface effect",
        ],
    },
    "p_i_n_architecture_translation": {
        "readout_motifs": [
            "architecture-matched p-i-n mechanism readout",
            "p-i-n contact-selective extraction or barrier readout",
        ],
        "control_motifs": [
            "p-i-n baseline without intervention",
            "p-i-n intervention comparison with matched absorber family",
            "source architecture reference as provenance only",
        ],
        "confounder_motifs": [
            "source-stack contact specificity",
            "p-i-n interface reinterpretation",
            "high-performance baseline ceiling effect",
        ],
    },
    "model_mapping_quantification": {
        "readout_motifs": [
            "mechanism-proxy input population",
            "device-metric model output",
            "model residual and sensitivity analysis",
        ],
        "control_motifs": [
            "bounded alternative-channel input",
            "same absorber-family model population",
        ],
        "confounder_motifs": [
            "qualitative proxy risk",
            "model underdetermination",
            "alternative channel still open",
        ],
    },
    "generic_uncertainty": {
        "readout_motifs": ["gap-derived mechanism readout class"],
        "control_motifs": ["gap-derived source-context comparator"],
        "confounder_motifs": ["unregistered competing mechanism", "measurement artifact"],
    },
}

for archetype_name, motif_fields in ARCHETYPE_MOTIF_OVERRIDES.items():
    registry_entry = ARCHETYPE_REGISTRY[archetype_name]
    registry_entry.update(motif_fields)
    registry_entry.setdefault(
        "closure_rule_motifs",
        ["support H only when readouts separate H from Alt under bounded confounders"],
    )
    registry_entry.setdefault(
        "non_closure_rule_motifs",
        ["keep mixed_or_unresolved when readouts are proxy-only or branch assignment conflicts"],
    )
    registry_entry.setdefault(
        "architecture_translation_motifs",
        ["preserve source context and re-test in inverted p-i-n when architecture differs"],
    )
    registry_entry.setdefault(
        "failure_mode_motifs",
        ["covariates co-vary with the target readout", "architecture transfer changes the branch"],
    )

FF_LOSS_REGEXES = (
    re.compile(r"\bff\b", re.I),
    re.compile(r"\bfill[- ]factor\b", re.I),
    re.compile(r"\bj[- ]?v loss\b", re.I),
    re.compile(r"\bjv loss\b", re.I),
    re.compile(r"\bff loss\b", re.I),
    re.compile(r"\bseries resistance\b", re.I),
    re.compile(r"\bshunt\b", re.I),
    re.compile(r"\br_s\b", re.I),
    re.compile(r"\brsh\b", re.I),
    re.compile(r"\bcontact resistance\b", re.I),
    re.compile(r"\btransport barrier\b", re.I),
)


@dataclass(frozen=True)
class Gap:
    """Normalized experimental gap extracted from package artifacts."""

    gap_id: str
    text: str
    gap_family: str
    gap_type: str
    template_id: str
    hypothesis: str
    alternative: str


@dataclass(frozen=True)
class GapClassifierOutput:
    """Structured classifier output for one gap."""

    dominant_observable: str
    mechanism_axes: list[str]
    primary_mechanism_axis: str
    secondary_mechanism_axes: list[str]
    alternative_class: str
    architecture_sensitivity: str
    evidence_gap_kind: str
    source_claim_type: str
    device_metric_relevance: str
    direct_readout_available: str
    portability_to_p_i_n: str
    classifier_stage: str
    classifier_confidence: str
    classifier_warnings: list[str]
    card_archetype: str
    matched_archetypes: list[str]
    conflict_reason: str

    def as_dict(self) -> dict[str, Any]:
        """Return YAML-safe classifier output."""
        return {
            "dominant_observable": self.dominant_observable,
            "mechanism_axes": self.mechanism_axes,
            "primary_mechanism_axis": self.primary_mechanism_axis,
            "secondary_mechanism_axes": self.secondary_mechanism_axes,
            "alternative_class": self.alternative_class,
            "architecture_sensitivity": self.architecture_sensitivity,
            "evidence_gap_kind": self.evidence_gap_kind,
            "source_claim_type": self.source_claim_type,
            "device_metric_relevance": self.device_metric_relevance,
            "direct_readout_available": self.direct_readout_available,
            "portability_to_p_i_n": self.portability_to_p_i_n,
            "classifier_stage": self.classifier_stage,
            "classifier_confidence": self.classifier_confidence,
            "classifier_warnings": self.classifier_warnings,
            "card_archetype": self.card_archetype,
            "matched_archetypes": self.matched_archetypes,
            "conflict_reason": self.conflict_reason,
        }


@dataclass(frozen=True)
class RetrievalSummary:
    """Bounded SQLite retrieval summary for one gap."""

    queries_run: list[str]
    database_precedents: dict[str, Any]
    retrieval_evidence: dict[str, Any]


@dataclass(frozen=True)
class SQLiteQualityReport:
    """Central SQLite quality report reused across all outputs."""

    sqlite_precedent_quality: str
    sqlite_quality_warning: bool
    parse_coverage_warning: bool
    top_precedent_rows: list[dict[str, Any]]
    demoted_precedent_rows: list[dict[str, Any]]
    rejected_precedent_rows_summary: dict[str, int]
    parse_coverage: dict[str, str]
    sqlite_role: str

    def as_dict(self) -> dict[str, Any]:
        """Return YAML-safe report."""
        return {
            "sqlite_precedent_quality": self.sqlite_precedent_quality,
            "sqlite_quality_warning": self.sqlite_quality_warning,
            "parse_coverage_warning": self.parse_coverage_warning,
            "top_precedent_rows": self.top_precedent_rows,
            "demoted_precedent_rows": self.demoted_precedent_rows,
            "rejected_precedent_rows_summary": self.rejected_precedent_rows_summary,
            "parse_coverage": self.parse_coverage,
            "sqlite_role": self.sqlite_role,
        }


@dataclass(frozen=True)
class LkmSummary:
    """LKM retrieval and provenance summary for one gap."""

    queries_run: list[str]
    role: str
    evidence_summary: str
    mechanism_reasoning: str
    same_package_chains: list[dict[str, Any]]
    cross_package_chains: list[dict[str, Any]]
    unknown_package_chains: list[dict[str, Any]]
    successful_endpoints: list[str]
    failed_endpoints: list[str]
    sqlite_lkm_conflicts: list[str]
    confidence: str
    design_reasoning: dict[str, Any]


@dataclass(frozen=True)
class LkmCredential:
    """Resolved LKM access credential without exposing the secret value."""

    access_key: str | None
    source: str


@dataclass(frozen=True)
class DesignMotif:
    """Experiment-design motif retrieved from design memory or primitive library."""

    source_id: str
    doi: str
    title: str
    architecture: str
    material_system: str
    intervention: str
    intervention_location: str
    target_problem: str
    claimed_mechanism: str
    alternative_mechanisms_considered: list[str]
    controls_used: list[str]
    primary_readouts: list[str]
    secondary_readouts: list[str]
    confounders_addressed: list[str]
    confounders_not_addressed: list[str]
    causal_strength: str
    decision_logic_supports_H: str
    decision_logic_supports_Alt: str
    mixed_or_unresolved_logic: str
    portability_notes: list[str]
    wet_lab_detail_removed: bool

    def as_dict(self) -> dict[str, Any]:
        """Return YAML-safe motif evidence."""
        return {
            "source_id": self.source_id,
            "doi": self.doi,
            "title": self.title,
            "architecture": self.architecture,
            "material_system": self.material_system,
            "intervention": self.intervention,
            "intervention_location": self.intervention_location,
            "target_problem": self.target_problem,
            "claimed_mechanism": self.claimed_mechanism,
            "alternative_mechanisms_considered": self.alternative_mechanisms_considered,
            "controls_used": self.controls_used,
            "primary_readouts": self.primary_readouts,
            "secondary_readouts": self.secondary_readouts,
            "confounders_addressed": self.confounders_addressed,
            "confounders_not_addressed": self.confounders_not_addressed,
            "causal_strength": self.causal_strength,
            "decision_logic_supports_H": self.decision_logic_supports_H,
            "decision_logic_supports_Alt": self.decision_logic_supports_Alt,
            "mixed_or_unresolved_logic": self.mixed_or_unresolved_logic,
            "portability_notes": self.portability_notes,
            "wet_lab_detail_removed": self.wet_lab_detail_removed,
        }


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Load a YAML mapping, returning an empty mapping when the file is absent."""
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected a YAML mapping")
    return payload


def extract_gaps(analysis_text: str) -> list[Gap]:
    """Extract experimental gaps from ``ANALYSIS.md`` text."""
    table_gaps = extract_evidence_gap_table_rows(analysis_text)
    if table_gaps:
        return [build_gap(index, block) for index, block in enumerate(table_gaps, start=1)]

    blocks: list[str] = []
    current: list[str] = []
    in_gap = False
    for raw_line in analysis_text.splitlines():
        line = raw_line.strip()
        lower = line.lower()
        starts_gap = "evidence gap" in lower or lower.startswith("gap:")
        if starts_gap:
            if current:
                blocks.append(" ".join(current).strip())
            current = [line]
            in_gap = True
            continue
        if in_gap:
            if line.startswith("#") and current:
                blocks.append(" ".join(current).strip())
                current = []
                in_gap = False
            elif line:
                current.append(line)
    if current:
        blocks.append(" ".join(current).strip())

    if not blocks:
        blocks = [
            line.strip()
            for line in analysis_text.splitlines()
            if "experiment" in line.lower() or "validation" in line.lower()
        ]

    return [build_gap(index, block) for index, block in enumerate(blocks, start=1)]


def extract_evidence_gap_table_rows(analysis_text: str) -> list[str]:
    """Extract per-row gaps from a Markdown table under ``Evidence Gaps``."""
    lines = analysis_text.splitlines()
    in_section = False
    header: list[str] = []
    gaps: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        lower = line.lower()
        if line.startswith("#"):
            in_section = "evidence gaps" in lower
            header = []
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = split_markdown_table_row(line)
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if not header:
            header = [cell.lower() for cell in cells]
            continue
        row = dict(zip(header, cells, strict=False))
        gap_text = row.get("gap") or row.get("evidence gap") or row.get("experimental gap")
        if not gap_text:
            continue
        theme = row.get("theme", "")
        conclusions = row.get("conclusions affected", "") or row.get("affected conclusions", "")
        parts = [f"Evidence Gap: {gap_text}"]
        if theme:
            parts.append(f"Theme: {theme}.")
        if conclusions:
            parts.append(f"Affected conclusions: {conclusions}.")
        gaps.append(" ".join(parts))
    return gaps


def split_markdown_table_row(line: str) -> list[str]:
    """Split a simple Markdown table row into stripped cells."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def build_gap(index: int, text: str) -> Gap:
    """Build a normalized gap using Stage A lightweight classification."""
    classifier = classify_gap_stage_a(text)
    gap_family = classifier.card_archetype
    gap_type = archetype_gap_type(gap_family)
    template_id = archetype_template_id(gap_family)
    hypothesis = default_hypothesis_for_archetype(gap_family)
    alternative = default_alternative_for_archetype(gap_family)
    return Gap(
        gap_id=f"experimental_gap_{index:02d}",
        text=text,
        gap_family=gap_family,
        gap_type=gap_type,
        template_id=template_id,
        hypothesis=hypothesis,
        alternative=alternative,
    )


def classify_gap_stage_a(text: str) -> GapClassifierOutput:
    """Stage A: package-local, pre-retrieval gap classification."""
    return build_classifier_output(
        text=text,
        context={},
        lkm=None,
        classifier_stage="pre_retrieval",
    )


def classify_gap_stage_b(
    gap: Gap,
    context: dict[str, Any],
    retrieval: RetrievalSummary,
    lkm: LkmSummary,
) -> GapClassifierOutput:
    """Stage B: evidence-aware final gap classification."""
    evidence_text = " ".join(
        [
            gap.text,
            " ".join(stringify(item) for item in as_list(context.get("target_claims"), default="")),
            " ".join(
                stringify(item) for item in as_list(context.get("affected_conclusions"), default="")
            ),
            lkm.evidence_summary,
            lkm.mechanism_reasoning,
            " ".join(
                stringify(row.get("title", ""))
                for row in retrieval.database_precedents.get("top_precedent_rows", [])
                if isinstance(row, dict)
            ),
        ]
    )
    return build_classifier_output(
        text=evidence_text,
        context=context,
        lkm=lkm,
        classifier_stage="evidence_aware_final",
    )


def build_classifier_output(
    *,
    text: str,
    context: dict[str, Any],
    lkm: LkmSummary | None,
    classifier_stage: str,
) -> GapClassifierOutput:
    """Classify a gap into a mechanism axis and card archetype."""
    lowered = text.lower()
    source_arch = normalize_architecture(context.get("solar_cell_structure", ""))
    architecture_mismatch = bool(context) and source_arch != "p-i-n"
    matched_archetypes = matched_archetypes_for_text(
        lowered, architecture_mismatch=architecture_mismatch
    )
    archetype = choose_card_archetype(
        lowered,
        architecture_mismatch=architecture_mismatch,
        matched_archetypes=matched_archetypes,
    )
    axes = ARCHETYPE_DEFAULT_AXES[archetype]
    primary_axis = ARCHETYPE_TO_PRIMARY_AXIS[archetype]
    warnings: list[str] = []
    if archetype == "generic_uncertainty":
        warnings.append("No supported mechanism archetype was confidently matched.")
    if len(matched_archetypes) > 1:
        warnings.append(
            "Multiple archetypes matched; use motif synthesis rather than a hard family gate."
        )
    if lkm is not None and lkm.unknown_package_chains:
        warnings.append("Ambiguous LKM provenance lowers mechanism-attribution weight.")
    if is_ff_like_text(lowered) and archetype != "ff_loss_budget":
        warnings.append("FF terms were present but a more specific non-FF archetype dominated.")
    conflict_reason = (
        "multiple_archetype_matches: " + ", ".join(matched_archetypes)
        if len(matched_archetypes) > 1
        else "none"
    )
    return GapClassifierOutput(
        dominant_observable=dominant_observable_for_archetype(archetype),
        mechanism_axes=axes,
        primary_mechanism_axis=primary_axis,
        secondary_mechanism_axes=[axis for axis in axes if axis != primary_axis],
        alternative_class=alternative_class_for_archetype(archetype),
        architecture_sensitivity=(
            "architecture_sensitive" if architecture_mismatch else "architecture_matched_or_unknown"
        ),
        evidence_gap_kind=evidence_gap_kind_for_archetype(archetype),
        source_claim_type=source_claim_type_for_archetype(archetype),
        device_metric_relevance=device_metric_relevance_for_archetype(archetype),
        direct_readout_available=direct_readout_available_for_archetype(archetype),
        portability_to_p_i_n=(
            "translation_required" if architecture_mismatch else "source_already_p_i_n_or_unknown"
        ),
        classifier_stage=classifier_stage,
        classifier_confidence="low" if archetype == "generic_uncertainty" else "moderate",
        classifier_warnings=warnings,
        card_archetype=archetype,
        matched_archetypes=matched_archetypes,
        conflict_reason=conflict_reason,
    )


def matched_archetypes_for_text(text: str, *, architecture_mismatch: bool) -> list[str]:
    """Return all known archetypes matched by the classifier text."""
    matched: list[str] = []
    _ = architecture_mismatch
    if is_architecture_translation_text(text):
        matched.append("p_i_n_architecture_translation")
    if is_model_mapping_text(text):
        matched.append("model_mapping_quantification")
    if is_recombination_text(text):
        matched.append("recombination_loss_mapping")
    if is_charge_extraction_text(text):
        matched.append("charge_extraction_collection")
    if is_ion_hysteresis_text(text):
        matched.append("ion_migration_hysteresis")
    if is_functional_analog_text(text):
        matched.append("functional_analog_causal_isolation")
    if is_stability_text(text):
        matched.append("stability_degradation_pathway")
    if is_morphology_phase_text(text):
        matched.append("morphology_phase_causality")
    if is_contact_energetics_text(text):
        matched.append("contact_energetics_interface_selectivity")
    if is_ff_like_text(text):
        matched.append("ff_loss_budget")
    return list(dict.fromkeys(matched))


def choose_card_archetype(
    text: str, *, architecture_mismatch: bool, matched_archetypes: list[str] | None = None
) -> str:
    """Choose the best card archetype from classifier text."""
    matched = matched_archetypes or matched_archetypes_for_text(
        text, architecture_mismatch=architecture_mismatch
    )
    if not matched:
        return "generic_uncertainty"
    for preferred in (
        "model_mapping_quantification",
        "recombination_loss_mapping",
        "charge_extraction_collection",
        "ion_migration_hysteresis",
        "functional_analog_causal_isolation",
        "stability_degradation_pathway",
        "morphology_phase_causality",
        "contact_energetics_interface_selectivity",
        "ff_loss_budget",
        "p_i_n_architecture_translation",
    ):
        if preferred in matched:
            return preferred
    return matched[0]


def is_ff_like_text(text: str) -> bool:
    """Return true only for explicit FF/J-V loss terms."""
    return any(pattern.search(text) for pattern in FF_LOSS_REGEXES)


def is_model_mapping_text(text: str) -> bool:
    """Return true for quantitative model-mapping gaps."""
    markers = (
        "theoretical gap",
        "device model",
        "model mapping",
        "quantitative mechanism mapping",
        "model underdetermination",
        "trap/recombination parameters",
        "trap/recombination-to",
        "qualitative proxy",
    )
    return any(marker in text for marker in markers)


def is_recombination_text(text: str) -> bool:
    """Return true for recombination/trap/proxy-to-device gaps."""
    markers = (
        "trap density",
        "trpl",
        "plqy",
        "qfls",
        "voc deficit",
        "nonradiative recombination",
        "non-radiative recombination",
        "lifetime",
        "recombination loss",
        "interface recombination",
        "bulk recombination",
    )
    return any(marker in text for marker in markers)


def is_charge_extraction_text(text: str) -> bool:
    """Return true for extraction, collection, mobility, and transport-timing gaps."""
    markers = (
        "transient extraction",
        "carrier collection",
        "extraction timing",
        "collection dynamics",
        "mobility",
        "transport timing",
        "jsc",
        "charge extraction",
    )
    return any(marker in text for marker in markers)


def is_ion_hysteresis_text(text: str) -> bool:
    """Return true for ion migration and hysteresis gaps."""
    return bool(
        re.search(
            r"\b(?:ion|ions|ionic)\b|ion[- ]migration|mobile ion|hysteresis|scan-direction|"
            r"bias-history|interfacial charge accumulation",
            text,
        )
    )


def is_functional_analog_text(text: str) -> bool:
    """Return true for multifunctional additive causal-isolation gaps."""
    markers = (
        "sole cause attribution",
        "sole cause",
        "passivation not isolated",
        "not isolate",
        "not isolated",
        "control additive",
        "single function",
        "multifunctional intervention",
        "multifunctional",
        "passivation_evidence_bundle",
        "functional analog",
    )
    return any(marker in text for marker in markers)


def is_stability_text(text: str) -> bool:
    """Return true for stability and degradation-pathway gaps."""
    markers = (
        "moisture",
        "humidity",
        "thermal",
        "light soaking",
        "oxygen",
        "operational stability",
        "phase stability",
        "stability",
        "degradation",
        "retention",
        "aging",
    )
    return any(marker in text for marker in markers)


def is_morphology_phase_text(text: str) -> bool:
    """Return true for morphology, phase, crystallinity, and microstructure gaps."""
    markers = (
        "morphology",
        "crystallinity",
        "grain size",
        "orientation",
        "phase purity",
        "strain",
        "microstructure",
        "phase transition",
    )
    return any(marker in text for marker in markers)


def is_contact_energetics_text(text: str) -> bool:
    """Return true for contact energetics and interface-selectivity gaps."""
    markers = (
        "work function",
        "band alignment",
        "surface potential",
        "contact barrier",
        "selectivity",
        "interface selectivity",
        "energetic alignment",
        "etl interface",
        "htl interface",
        "contact energetics",
    )
    return any(marker in text for marker in markers)


def is_architecture_translation_text(text: str) -> bool:
    """Return true for architecture portability and p-i-n translation gaps."""
    markers = (
        "architecture portability",
        "architecture translation",
        "p-i-n translation",
        "pin translation",
        "reverse-structure translation",
        "portability to p-i-n",
    )
    return any(marker in text for marker in markers)


def archetype_gap_type(archetype: str) -> str:
    """Return a readable gap type for an archetype."""
    return CARD_ARCHETYPE_TITLES.get(archetype, CARD_ARCHETYPE_TITLES["generic_uncertainty"])


def archetype_template_id(archetype: str) -> str:
    """Return legacy-compatible template id for an archetype."""
    return archetype.upper() + "_TEMPLATE"


def default_hypothesis_for_archetype(archetype: str) -> str:
    """Return a Stage-A hypothesis scaffold for LKM query construction."""
    hypotheses = {
        "ff_loss_budget": "The target device metric change is explained by a resolved photovoltaic loss branch.",
        "recombination_loss_mapping": "The target claim is explained by reduced nonradiative recombination or defect-mediated loss.",
        "charge_extraction_collection": "The target claim is explained by improved charge extraction or carrier collection.",
        "ion_migration_hysteresis": "The target claim is explained by reduced ion migration or interfacial charge accumulation.",
        "functional_analog_causal_isolation": "The target chemical interaction remains causal after multifunctional covariates are bounded.",
        "stability_degradation_pathway": "The target claim is explained by a specific stability or degradation-pathway improvement.",
        "morphology_phase_causality": "The target claim is explained by morphology, crystallinity, or phase-state changes.",
        "contact_energetics_interface_selectivity": "The target claim is explained by contact energetics or interface selectivity.",
        "p_i_n_architecture_translation": "The target mechanism is portable to inverted p-i-n under explicit architecture assumptions.",
        "model_mapping_quantification": "The measured mechanism proxy quantitatively accounts for the device metric.",
    }
    return hypotheses.get(
        archetype,
        "The package-local target mechanism explains the affected Gaia claim.",
    )


def default_alternative_for_archetype(archetype: str) -> str:
    """Return a Stage-A alternative scaffold for LKM query construction."""
    alternatives = {
        "ff_loss_budget": "A different device-loss branch or measurement-history effect explains the metric change.",
        "recombination_loss_mapping": "Contact-mediated recombination, morphology, or proxy-only measurement risk explains the observation.",
        "charge_extraction_collection": "Recombination, contact selectivity, optical absorption, or morphology explains the collection trend.",
        "ion_migration_hysteresis": "Contact/barrier, recombination, or scan-protocol artifact explains the hysteresis trend.",
        "functional_analog_causal_isolation": "Morphology, crystallinity, hydrophobicity, contact, or process covariates explain the device trend.",
        "stability_degradation_pathway": "Barrier, phase, contact degradation, ion migration, or encapsulation/process artifact explains stability.",
        "morphology_phase_causality": "Passivation, optical absorption, contact/interface effects, or processing artifacts explain the trend.",
        "contact_energetics_interface_selectivity": "Recombination suppression, transport barrier, contact resistance, or architecture-specific effects explain it.",
        "p_i_n_architecture_translation": "The source-stack mechanism does not port to inverted p-i-n and remains architecture-specific.",
        "model_mapping_quantification": "The proxy is qualitative or underdetermined and alternative channels remain open.",
    }
    return alternatives.get(
        archetype,
        "A competing mechanism or uncontrolled covariate explains the observation.",
    )


def dominant_observable_for_archetype(archetype: str) -> str:
    """Return the dominant observable class for an archetype."""
    mapping = {
        "ff_loss_budget": "fill-factor or J-V loss branch",
        "recombination_loss_mapping": "Voc, QFLS, PL/TRPL, lifetime, or trap-sensitive proxy",
        "charge_extraction_collection": "extraction timing, carrier collection, Jsc, or mobility proxy",
        "ion_migration_hysteresis": "hysteresis index, scan-direction delta, or bias-history response",
        "functional_analog_causal_isolation": "functional analog response and bounded covariates",
        "stability_degradation_pathway": "stability retention or degradation-pathway readout",
        "morphology_phase_causality": "morphology, crystallinity, phase, orientation, or strain readout",
        "contact_energetics_interface_selectivity": "work function, surface potential, barrier, or selectivity readout",
        "p_i_n_architecture_translation": "architecture-matched p-i-n transfer readout",
        "model_mapping_quantification": "quantitative model residual and sensitivity readout",
    }
    return mapping.get(archetype, "unresolved observable")


def alternative_class_for_archetype(archetype: str) -> str:
    """Return the competing explanation class for an archetype."""
    mapping = {
        "ff_loss_budget": "alternate photovoltaic loss branch",
        "recombination_loss_mapping": "contact, bulk/interface location, morphology, or proxy-only alternative",
        "charge_extraction_collection": "recombination/contact/optical/morphology confounder",
        "ion_migration_hysteresis": "contact/barrier/recombination/scan-protocol alternative",
        "functional_analog_causal_isolation": "multifunctional covariate alternative",
        "stability_degradation_pathway": "barrier/phase/contact/ion/process stability alternative",
        "morphology_phase_causality": "passivation/process/optical/contact alternative",
        "contact_energetics_interface_selectivity": "recombination/transport/contact-resistance/architecture alternative",
        "p_i_n_architecture_translation": "architecture-specific non-portability alternative",
        "model_mapping_quantification": "model underdetermination or alternate-channel alternative",
    }
    return mapping.get(archetype, "unresolved alternative class")


def evidence_gap_kind_for_archetype(archetype: str) -> str:
    """Return the kind of evidence gap."""
    if archetype == "generic_uncertainty":
        return "unresolved_template_selection"
    if archetype == "model_mapping_quantification":
        return "quantitative_mapping_gap"
    if archetype == "functional_analog_causal_isolation":
        return "causal_isolation_gap"
    return "mechanism_discrimination_gap"


def source_claim_type_for_archetype(archetype: str) -> str:
    """Return the likely source claim type."""
    if archetype in {"ff_loss_budget", "charge_extraction_collection"}:
        return "device_metric_or_transport_claim"
    if archetype in {"stability_degradation_pathway"}:
        return "stability_claim"
    if archetype == "p_i_n_architecture_translation":
        return "architecture_portability_claim"
    return "mechanism_claim"


def device_metric_relevance_for_archetype(archetype: str) -> str:
    """Return device-metric relevance."""
    if archetype == "ff_loss_budget":
        return "direct_ff_or_jv_loss_relevance"
    if archetype in {
        "recombination_loss_mapping",
        "charge_extraction_collection",
        "model_mapping_quantification",
    }:
        return "indirect_device_metric_mapping_required"
    if archetype == "generic_uncertainty":
        return "unknown_device_metric_relevance"
    return "mechanism_specific_metric_context_required"


def direct_readout_available_for_archetype(archetype: str) -> str:
    """Return readout availability class."""
    if archetype == "generic_uncertainty":
        return "not_resolved"
    return "archetype_specific_readout_classes_available"


def check_context(context: dict[str, Any]) -> list[str]:
    """Return missing required context fields."""
    if package_mode_from_context(context) == "aggregate_corpus":
        return [field for field in ("source_package",) if not context.get(field)]
    return [field for field in REQUIRED_CONTEXT_FIELDS if not context.get(field)]


def package_mode_from_context(context: dict[str, Any]) -> str:
    """Infer single-paper versus aggregate-corpus package mode."""
    explicit = stringify(context.get("package_mode")).strip().lower()
    if explicit in {"single_paper", "aggregate_corpus"}:
        return explicit
    source = stringify(context.get("source_package")).lower()
    if "aggregate" in source or "corpus" in source or source in {"pvsk-gaia", "pvsk_gaia"}:
        return "aggregate_corpus"
    if context.get("corpus_level_device_context") or context.get("corpus_level_distribution"):
        return "aggregate_corpus"
    return "single_paper"


def write_preflight(output_dir: Path, missing: list[str], sources_checked: list[str]) -> None:
    """Write strict-preflight diagnostics."""
    payload = {
        "context_missing_preflight": {
            "missing_fields": missing,
            "sources_checked": sources_checked,
            "minimum_context_needed": list(REQUIRED_CONTEXT_FIELDS),
        }
    }
    write_yaml(output_dir / "context_missing_preflight.yaml", payload)


def augment_context_with_source_identifiers(  # noqa: C901
    package: Path, context: dict[str, Any]
) -> dict[str, Any]:
    """Add source DOI/package identifiers from package artifacts when available."""
    augmented = dict(context)
    source_dois: set[str] = set()
    source_package_identifiers: set[str] = set()
    source_local_ids: set[str] = set()
    source_paper_ids: set[str] = set()

    for key in ("source_package", "package_name", "package_id"):
        add_normalized_identifier(source_package_identifiers, augmented.get(key))
    for key in ("source_doi", "doi"):
        add_normalized_identifier(source_dois, augmented.get(key), doi=True)

    for path in (package / "README.md", package / "ANALYSIS.md"):
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for doi in extract_dois(text):
                source_dois.add(doi)

    for path in (
        package / ".gaia" / "beliefs.json",
        package / ".github-output" / "docs" / "public" / "data" / "graph.json",
    ):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        source_dois.update(extract_dois(json.dumps(payload, ensure_ascii=False)))
        collect_source_ids_from_payload(
            payload,
            source_package_identifiers=source_package_identifiers,
            source_local_ids=source_local_ids,
            source_paper_ids=source_paper_ids,
        )

    if source_dois:
        augmented["source_dois"] = sorted(source_dois)
        augmented.setdefault("source_doi", sorted(source_dois)[0])
    if source_package_identifiers:
        augmented["source_package_identifiers"] = sorted(source_package_identifiers)
    if source_local_ids:
        augmented["source_local_ids"] = sorted(source_local_ids)
    if source_paper_ids:
        augmented["source_paper_ids"] = sorted(source_paper_ids)
    return augmented


def extract_dois(text: str) -> set[str]:
    """Extract normalized DOI strings from free text."""
    return {
        normalize_identifier(match.group(0), doi=True)
        for match in re.finditer(r"10\.\d{4,9}/[^\s\"'<>]+", text, flags=re.I)
    }


def collect_source_ids_from_payload(
    payload: Any,
    *,
    source_package_identifiers: set[str],
    source_local_ids: set[str],
    source_paper_ids: set[str],
) -> None:
    """Collect package/local/paper identifiers from package artifacts."""
    for node in iter_dict_values(payload):
        for key in ("source_package", "package", "package_id", "packageId"):
            add_normalized_identifier(source_package_identifiers, node.get(key))
        for key in ("local_id", "localId", "id", "qid"):
            add_normalized_identifier(source_local_ids, node.get(key))
        for key in ("paper_id", "paperId", "paper"):
            add_normalized_identifier(source_paper_ids, node.get(key))


def retrieve_sqlite(gap: Gap, context: dict[str, Any], db_path: Path) -> RetrievalSummary:
    """Run bounded SQLite precedent retrieval for a gap."""
    if not db_path.exists():
        return RetrievalSummary(
            queries_run=[f"SQLite unavailable at {db_path}"],
            database_precedents=empty_database_precedents("SQLite database unavailable"),
            retrieval_evidence={
                "gap_id": gap.gap_id,
                "successful_endpoints": [],
                "failed_endpoints": [f"sqlite:{db_path}:unavailable"],
                "same_package_lkm_chains": [],
                "cross_package_lkm_chains": [],
                "ambiguous_lkm_chains": [],
                "unknown_package_lkm_chains": [],
                "sqlite_precedent_quality": "unusable",
                "sqlite_quality_warning": True,
                "parse_coverage_warning": True,
                "parse_coverage_warning_reason": "SQLite database unavailable; confidence is low.",
            },
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table = first_table(conn)
        columns = table_columns(conn, table)
        rows = query_precedents(conn, table, columns, context)
        quality_report = build_sqlite_quality_report(rows, columns, context, gap)
    finally:
        conn.close()

    precedent_summary = {
        "tier_counts": {
            "tier1": min(len(quality_report.top_precedent_rows), 1),
            "tier2": max(min(len(quality_report.top_precedent_rows) - 1, 3), 0),
            "tier3": max(len(quality_report.top_precedent_rows) - 4, 0),
            "rejected": sum(quality_report.rejected_precedent_rows_summary.values()),
        },
        "source_role": (
            "SQLite is for precedent discovery, stack/intervention matching, and "
            "paired delta background only; it is not mechanism proof."
        ),
        **quality_report.as_dict(),
    }
    return RetrievalSummary(
        queries_run=[
            (
                f"bounded SQLite precedent query on {table} using "
                "architecture/composition/context terms"
            )
        ],
        database_precedents=precedent_summary,
        retrieval_evidence={
            "gap_id": gap.gap_id,
            "successful_endpoints": [f"sqlite:{table}:bounded_precedent_query"],
            "failed_endpoints": [],
            "same_package_lkm_chains": [],
            "cross_package_lkm_chains": [],
            "ambiguous_lkm_chains": [],
            "unknown_package_lkm_chains": [],
            "sqlite_parse_coverage": quality_report.parse_coverage,
            "sqlite_precedent_quality": quality_report.sqlite_precedent_quality,
            "sqlite_quality_warning": quality_report.sqlite_quality_warning,
            "parse_coverage_warning": quality_report.parse_coverage_warning,
            "demoted_precedent_rows": quality_report.demoted_precedent_rows,
            "rejected_precedent_rows_summary": quality_report.rejected_precedent_rows_summary,
        },
    )


def retrieve_lkm(
    gap: Gap,
    context: dict[str, Any],
    output_dir: Path,
    *,
    live: bool,
    dotenv_paths: list[Path],
) -> LkmSummary:
    """Retrieve LKM reasoning when configured, otherwise emit auditable diagnostics."""
    mechanism_query = build_lkm_mechanism_query(gap, context)
    design_query = build_lkm_design_query(gap, context)
    lkm_dir = output_dir / "lkm"
    lkm_dir.mkdir(parents=True, exist_ok=True)

    credential = resolve_lkm_access_key(dotenv_paths)
    if not live or not credential.access_key:
        reason = "live LKM retrieval disabled" if not live else "no LKM access key configured"
        diagnostic = {
            "status": "lkm_unavailable",
            "reason": reason,
            "credential_source": credential.source,
            "gap_id": gap.gap_id,
            "mechanism_query": mechanism_query,
            "experiment_design_query": design_query,
            "successful_endpoints": [],
            "failed_endpoints": ["/search", "/reasoning/search"],
        }
        write_json(lkm_dir / f"{gap.gap_id}_lkm_unavailable.json", diagnostic)
        return LkmSummary(
            queries_run=["lkm_unavailable: /search and /reasoning/search not executed"],
            role="lkm_unavailable: no auditable LKM mechanism chains were retrieved.",
            evidence_summary=(
                f"LKM unavailable ({reason}); confidence is lowered and mechanism "
                "attribution remains bounded."
            ),
            mechanism_reasoning=(
                "lkm_unavailable: no LKM mechanism reasoning available for this gap."
            ),
            same_package_chains=[],
            cross_package_chains=[],
            unknown_package_chains=[],
            successful_endpoints=[],
            failed_endpoints=["/search", "/reasoning/search"],
            sqlite_lkm_conflicts=["No LKM conflict assessed because LKM was unavailable."],
            confidence="low",
            design_reasoning=build_lkm_design_unavailable_summary(design_query, reason),
        )

    successful: list[str] = []
    failed: list[str] = []
    payloads: list[dict[str, Any]] = []

    try:
        from gaia.cli.commands.search.lkm._client import LKMClient
    except Exception as exc:  # pragma: no cover - defensive import guard
        diagnostic = {
            "status": "lkm_unavailable",
            "reason": f"failed to import LKM client: {exc}",
            "gap_id": gap.gap_id,
            "mechanism_query": mechanism_query,
            "experiment_design_query": design_query,
        }
        write_json(lkm_dir / f"{gap.gap_id}_lkm_unavailable.json", diagnostic)
        return LkmSummary(
            queries_run=["lkm_unavailable: LKM client import failed"],
            role="lkm_unavailable: LKM client import failed.",
            evidence_summary=(
                "LKM unavailable because the local client could not be imported; "
                "confidence is lowered."
            ),
            mechanism_reasoning="lkm_unavailable: no LKM mechanism reasoning available.",
            same_package_chains=[],
            cross_package_chains=[],
            unknown_package_chains=[],
            successful_endpoints=[],
            failed_endpoints=["/search", "/reasoning/search"],
            sqlite_lkm_conflicts=["No LKM conflict assessed because LKM was unavailable."],
            confidence="low",
            design_reasoning=build_lkm_design_unavailable_summary(
                design_query, f"failed to import LKM client: {exc}"
            ),
        )

    with LKMClient(access_key=credential.access_key) as client:
        knowledge_body = {
            "query": mechanism_query,
            "retrieval_mode": "hybrid",
            "scopes": ["claim"],
            "reasoning_only": True,
            "limit": 10,
            "filters": {"visibility": "public"},
        }
        try:
            knowledge_payload = client.request("POST", "/search", json_body=knowledge_body)
        except Exception as exc:  # pragma: no cover - live network path
            failed.append(f"/search: {exc}")
        else:  # pragma: no cover - live network path
            successful.append("/search")
            payloads.append(knowledge_payload)
            write_json(
                lkm_dir / f"{gap.gap_id}_search.json",
                {
                    "credential_source": credential.source,
                    "request": redact_lkm_request(knowledge_body),
                    "response": knowledge_payload,
                },
            )

        reasoning_body = {
            "query": mechanism_query,
            "retrieval_mode": "hybrid",
            "offset": 0,
            "limit": 10,
        }
        try:
            reasoning_payload = client.request(
                "POST", "/reasoning/search", json_body=reasoning_body
            )
        except Exception as exc:  # pragma: no cover - live network path
            failed.append(f"/reasoning/search: {exc}")
        else:  # pragma: no cover - live network path
            successful.append("/reasoning/search")
            payloads.append(reasoning_payload)
            write_json(
                lkm_dir / f"{gap.gap_id}_reasoning_search.json",
                {
                    "credential_source": credential.source,
                    "request": redact_lkm_request(reasoning_body),
                    "response": reasoning_payload,
                },
            )

        design_body = {
            "query": design_query,
            "retrieval_mode": "hybrid",
            "offset": 0,
            "limit": 10,
        }
        try:
            design_payload = client.request("POST", "/reasoning/search", json_body=design_body)
        except Exception as exc:  # pragma: no cover - live network path
            failed.append(f"/reasoning/search experiment-design: {exc}")
            design_reasoning = build_lkm_design_unavailable_summary(design_query, str(exc))
        else:  # pragma: no cover - live network path
            successful.append("/reasoning/search:experiment-design")
            payloads.append(design_payload)
            design_reasoning = summarize_lkm_design_reasoning(design_payload, design_query, context)
            write_json(
                lkm_dir / f"{gap.gap_id}_design_reasoning_search.json",
                {
                    "credential_source": credential.source,
                    "request": redact_lkm_request(design_body),
                    "response": design_payload,
                },
            )

    same, cross, unknown = summarize_lkm_provenance(payloads, context)
    if not successful:
        write_json(
            lkm_dir / f"{gap.gap_id}_lkm_unavailable.json",
            {
                "status": "lkm_unavailable",
                "gap_id": gap.gap_id,
                "mechanism_query": mechanism_query,
                "experiment_design_query": design_query,
                "credential_source": credential.source,
                "failed_endpoints": failed,
            },
        )
        return LkmSummary(
            queries_run=["lkm_unavailable: all LKM endpoints failed"],
            role="lkm_unavailable: all live LKM endpoints failed.",
            evidence_summary=(
                "LKM failed for all requested endpoints; confidence is lowered and "
                "mechanism attribution remains bounded."
            ),
            mechanism_reasoning="lkm_unavailable: no LKM mechanism reasoning available.",
            same_package_chains=[],
            cross_package_chains=[],
            unknown_package_chains=[],
            successful_endpoints=[],
            failed_endpoints=failed,
            sqlite_lkm_conflicts=["No LKM conflict assessed because LKM retrieval failed."],
            confidence="low",
            design_reasoning=build_lkm_design_unavailable_summary(
                design_query, "all LKM endpoints failed"
            ),
        )

    confidence = "moderate" if same or cross or unknown else "low"
    evidence_summary = (
        "LKM retrieval returned auditable mechanism-reasoning candidates with provenance retained."
        if same or cross or unknown
        else "LKM endpoints succeeded but returned no provenance-bearing chains; "
        "mechanism attribution remains bounded."
    )
    return LkmSummary(
        queries_run=[
            f"{endpoint}: {design_query if 'experiment-design' in endpoint else mechanism_query}"
            for endpoint in successful
        ],
        role=(
            "LKM supplies auditable mechanism reasoning, measurement-class design, "
            "and causal-chain checks; it remains provenance-scoped."
        ),
        evidence_summary=evidence_summary,
        mechanism_reasoning=evidence_summary,
        same_package_chains=same,
        cross_package_chains=cross,
        unknown_package_chains=unknown,
        successful_endpoints=successful,
        failed_endpoints=failed,
        sqlite_lkm_conflicts=["No SQLite/LKM conflict detected by the generator summary."],
        confidence=confidence,
        design_reasoning=design_reasoning,
    )


def build_lkm_query(gap: Gap, context: dict[str, Any]) -> str:
    """Backward-compatible mechanism query wrapper."""
    return build_lkm_mechanism_query(gap, context)


def build_lkm_mechanism_query(gap: Gap, context: dict[str, Any]) -> str:
    """Build a natural-language LKM query from package context and H-vs-Alt terms."""
    pieces = [
        str(context.get("perovskite_composition", "")),
        str(context.get("solar_cell_structure", "")),
        str(context.get("intervention_location", "")),
        str(context.get("modulator_material_or_family", "")),
        gap.text,
        gap.hypothesis,
        gap.alternative,
        "What readout classes distinguish the hypothesis from the alternative?",
    ]
    return " ".join(piece for piece in pieces if piece.strip())


def build_lkm_design_query(gap: Gap, context: dict[str, Any]) -> str:
    """Build the experiment-design LKM query for controls/readouts/closure logic."""
    pieces = [
        str(context.get("perovskite_composition", "")),
        str(context.get("solar_cell_structure", "")),
        str(context.get("intervention_location", "")),
        str(context.get("modulator_material_or_family", "")),
        gap.text,
        "What measurement classes distinguish H from Alt?",
        "What controls isolate one mechanism branch from competing explanations?",
        "What observations support H, support Alt, or remain mixed_or_unresolved?",
        "What evidence would be insufficient for mechanism closure?",
        "How should this be translated to inverted p-i-n architecture?",
    ]
    return " ".join(piece for piece in pieces if piece.strip())


def build_lkm_design_unavailable_summary(query: str, reason: str) -> dict[str, Any]:
    """Return a structured LKM design-reasoning diagnostic."""
    return {
        "endpoint": "/reasoning/search",
        "query": query,
        "status": "lkm_unavailable",
        "reason": reason,
        "readout_classes": [],
        "controls": [],
        "confounders": [],
        "closure_rules": [],
        "non_closure_rules": ["LKM design reasoning unavailable; do not raise confidence."],
        "portability_notes": [],
        "provenance": [],
        "same_package": [],
        "cross_package": [],
        "ambiguous": [],
    }


def summarize_lkm_design_reasoning(
    payload: dict[str, Any], query: str, context: dict[str, Any]
) -> dict[str, Any]:
    """Summarize LKM experiment-design reasoning into motif-like fields."""
    same, cross, ambiguous = summarize_lkm_provenance([payload], context)
    text = " ".join(stringify(value) for _, value in iter_strings_from_json(payload))
    return {
        "endpoint": "/reasoning/search",
        "query": query,
        "status": "retrieved",
        "readout_classes": extract_lkm_design_terms(
            text,
            (
                "readout",
                "measurement",
                "spectroscopy",
                "transient",
                "hysteresis",
                "stability",
                "model",
            ),
            fallback=["LKM-retrieved experiment-design readout class"],
        ),
        "controls": extract_lkm_design_terms(
            text,
            ("control", "baseline", "comparator", "analog"),
            fallback=["LKM-retrieved source-context comparator"],
        ),
        "confounders": extract_lkm_design_terms(
            text,
            ("confounder", "alternative", "covariate", "artifact"),
            fallback=["LKM-retrieved competing explanation class"],
        ),
        "closure_rules": ["Use only H-vs-Alt discriminating observations with provenance."],
        "non_closure_rules": [
            "Do not close when evidence is proxy-only, analogical only, or scope-ambiguous."
        ],
        "portability_notes": ["Re-evaluate contact/selectivity readouts in inverted p-i-n."],
        "provenance": same + cross + ambiguous,
        "same_package": same,
        "cross_package": cross,
        "ambiguous": ambiguous,
    }


def extract_lkm_design_terms(
    text: str, markers: tuple[str, ...], *, fallback: list[str]
) -> list[str]:
    """Extract compact design phrases from LKM text with safe fallbacks."""
    lowered = text.lower()
    terms = [marker for marker in markers if marker in lowered]
    if not terms:
        return fallback
    return [f"LKM-mentioned {term} class" for term in terms[:4]]


def iter_strings_from_json(value: Any) -> list[tuple[str, str]]:
    """Collect strings from JSON-like values without importing validator helpers."""
    if isinstance(value, str):
        return [("", value)]
    if isinstance(value, dict):
        strings: list[tuple[str, str]] = []
        for key, item in value.items():
            strings.extend((str(key), text) for _, text in iter_strings_from_json(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(iter_strings_from_json(item))
        return strings
    return []


def resolve_lkm_access_key(dotenv_paths: list[Path]) -> LkmCredential:
    """Resolve LKM access from env vars or local ``.env`` files without printing it."""
    for name in ("GAIA_LKM_ACCESS_KEY", "LKM_ACCESS_KEY"):
        value = os.environ.get(name)
        if value:
            return LkmCredential(access_key=value, source=f"environment variable {name}")

    seen: set[Path] = set()
    for path in dotenv_paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        env_values = parse_dotenv_lkm_keys(resolved)
        for name in ("GAIA_LKM_ACCESS_KEY", "LKM_ACCESS_KEY"):
            value = env_values.get(name)
            if value:
                return LkmCredential(access_key=value, source=f"{name} in {resolved}")
    return LkmCredential(access_key=None, source="not configured")


def parse_dotenv_lkm_keys(path: Path) -> dict[str, str]:
    """Read only supported LKM key variables from a dotenv file."""
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        name, value = line.split("=", 1)
        name = name.strip()
        if name not in {"GAIA_LKM_ACCESS_KEY", "LKM_ACCESS_KEY"}:
            continue
        values[name] = clean_dotenv_value(value)
    return values


def clean_dotenv_value(value: str) -> str:
    """Normalize a simple dotenv value."""
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned


def redact_lkm_request(value: dict[str, Any]) -> dict[str, Any]:
    """Return a secret-free request summary."""
    return {key: item for key, item in value.items() if key.lower() not in {"accesskey", "key"}}


def summarize_lkm_provenance(
    payloads: list[dict[str, Any]], context: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract package-scoped chain summaries from LKM payloads."""
    resolver = build_source_resolver(context)
    same: list[dict[str, Any]] = []
    cross: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for payload in payloads:
        for item in iter_dict_values(payload):
            if is_lkm_collection_node(item):
                continue
            summary = summarize_lkm_item(item, resolver)
            if not summary:
                continue
            if summary["reasoning_scope"] == "same_package":
                same.append(summary)
            elif summary["reasoning_scope"] == "cross_package":
                cross.append(summary)
            else:
                ambiguous.append(summary)
            if len(same) + len(cross) + len(ambiguous) >= 10:
                return same, cross, ambiguous
    return same, cross, ambiguous


def is_lkm_collection_node(item: dict[str, Any]) -> bool:
    """Return true for collection wrappers rather than individual LKM items."""
    collection_keys = {"results", "items", "data", "matches"}
    has_collection = any(isinstance(item.get(key), list) for key in collection_keys)
    if not has_collection:
        return False
    provenance_keys = {
        "source_package",
        "sourcePackage",
        "package",
        "package_id",
        "paper_id",
        "paperId",
        "claim_id",
        "claimId",
        "chain_id",
        "chainId",
        "doi",
        "DOI",
    }
    return not any(key in item for key in provenance_keys)


def summarize_lkm_item(item: dict[str, Any], resolver: dict[str, set[str]]) -> dict[str, Any]:
    """Summarize one provenance-bearing LKM item."""
    provenance_fields = (
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
    aliases = {
        "source_package": (
            "source_package",
            "sourcePackage",
            "package",
            "package_id",
            "packageId",
        ),
        "paper_id": ("paper_id", "paperId", "paper", "paperIdStr", "paper_id_str"),
        "claim_id": ("claim_id", "claimId", "id", "provider_id"),
        "conclusion_id": ("conclusion_id", "conclusionId"),
        "chain_id": ("chain_id", "chainId", "reasoning_chain_id", "reasoningChainId"),
        "local_id": ("local_id", "localId", "lcn_id", "lcnId"),
        "doi": ("doi", "DOI"),
        "title": ("title", "paper_title", "paperTitle"),
        "score": ("score",),
        "rerank_score": ("rerank_score", "rerankScore"),
        "endpoint": ("endpoint", "_endpoint"),
    }
    summary: dict[str, Any] = {}
    for canonical, keys in aliases.items():
        value = first_present_deep(item, keys)
        if not is_blank(value):
            summary[canonical] = value

    if not any(field in summary for field in provenance_fields):
        return {}

    scope = canonicalize_lkm_provenance(summary, resolver)
    if scope == "same_package":
        summary["reasoning_scope"] = "same_package"
        summary["cross_package"] = False
    elif scope == "cross_package":
        summary["reasoning_scope"] = "cross_package"
        summary["cross_package"] = True
    else:
        summary["reasoning_scope"] = "ambiguous_package_scope"
        summary["cross_package"] = None
    summary.setdefault("endpoint", "unknown_lkm_endpoint")
    summary.setdefault(
        "why_used",
        "Retrieved for H-vs-Alt mechanism reasoning and measurement-class design.",
    )
    summary.setdefault(
        "limitations",
        (
            "LKM reasoning is provenance-scoped and cannot close a mechanism gap "
            "without discriminating package-local readouts."
        ),
    )
    return summary


def build_source_resolver(context: dict[str, Any]) -> dict[str, set[str]]:
    """Build normalized source identifiers for same/cross-package LKM checks."""
    resolver: dict[str, set[str]] = {
        "packages": set(),
        "dois": set(),
        "local_ids": set(),
        "paper_ids": set(),
    }
    for key in ("source_package", "package_name", "package_id"):
        add_normalized_identifier(resolver["packages"], context.get(key))
    for key in ("source_doi", "doi"):
        add_normalized_identifier(resolver["dois"], context.get(key), doi=True)
    for key in ("source_local_id", "local_id"):
        add_normalized_identifier(resolver["local_ids"], context.get(key))
    for key in ("source_paper_id", "paper_id"):
        add_normalized_identifier(resolver["paper_ids"], context.get(key))

    for value in context.get("source_dois", []) or []:
        add_normalized_identifier(resolver["dois"], value, doi=True)
    for value in context.get("source_package_identifiers", []) or []:
        add_normalized_identifier(resolver["packages"], value)
    for value in context.get("source_local_ids", []) or []:
        add_normalized_identifier(resolver["local_ids"], value)
    for value in context.get("source_paper_ids", []) or []:
        add_normalized_identifier(resolver["paper_ids"], value)
    return resolver


def add_normalized_identifier(target: set[str], value: Any, *, doi: bool = False) -> None:
    """Add one or more normalized identifiers to ``target``."""
    if is_blank(value):
        return
    if isinstance(value, list | tuple | set):
        for item in value:
            add_normalized_identifier(target, item, doi=doi)
        return
    text = normalize_identifier(value, doi=doi)
    if text:
        target.add(text)


def normalize_identifier(value: Any, *, doi: bool = False) -> str:
    """Normalize package, DOI, local, or paper identifiers for comparison."""
    text = str(value).strip().lower()
    if not text:
        return ""
    text = text.removeprefix("doi:").removeprefix("https://doi.org/")
    text = text.removeprefix("http://doi.org/")
    text = text.strip(" `\"'<>.,;()[]{}")
    if doi:
        match = re.search(r"10\.\d{4,9}/[^\s\"'<>]+", text)
        if match:
            return match.group(0).rstrip(".,;)")
    return text


def canonicalize_lkm_provenance(summary: dict[str, Any], resolver: dict[str, set[str]]) -> str:
    """Return same_package, cross_package, or ambiguous_package_scope."""
    votes: list[str] = []
    comparable_identifiers = 0
    source_package = normalize_identifier(summary.get("source_package", ""))
    doi = normalize_identifier(summary.get("doi", ""), doi=True)
    local_id = normalize_identifier(summary.get("local_id", ""))

    if source_package:
        comparable_identifiers += 1
        votes.append(
            "same"
            if identifier_matches(source_package, resolver["packages"])
            else "outside"
            if resolver["packages"]
            else "ambiguous"
        )
    if doi:
        comparable_identifiers += 1
        votes.append(
            "same"
            if identifier_matches(doi, resolver["dois"])
            else "outside"
            if resolver["dois"]
            else "ambiguous"
        )
    if local_id:
        comparable_identifiers += 1
        votes.append(
            "same"
            if identifier_matches(local_id, resolver["local_ids"])
            or starts_with_any_identifier(local_id, resolver["packages"])
            else "outside"
            if resolver["local_ids"] or resolver["packages"]
            else "ambiguous"
        )

    if not votes:
        return "ambiguous_package_scope"
    if "same" in votes and "outside" in votes:
        return "ambiguous_package_scope"
    if "ambiguous" in votes and len(set(votes)) > 1:
        return "ambiguous_package_scope"
    if "same" in votes:
        return "same_package"
    if "outside" in votes:
        return "cross_package" if comparable_identifiers >= 2 else "ambiguous_package_scope"
    return "ambiguous_package_scope"


def starts_with_any_identifier(value: str, candidates: set[str]) -> bool:
    """Return true when an LKM local id starts with a source package id."""
    if not value or not candidates:
        return False
    return any(value.startswith(candidate) for candidate in candidates)


def identifier_matches(value: str, candidates: set[str]) -> bool:
    """Return true when ``value`` matches or contains any source identifier."""
    if not value or not candidates:
        return False
    return any(
        candidate == value or candidate in value or value in candidate for candidate in candidates
    )


def iter_dict_values(value: Any) -> list[dict[str, Any]]:
    """Return nested dictionaries from arbitrary JSON-like payloads."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(iter_dict_values(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(iter_dict_values(child))
    return found


def first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-blank value for any key."""
    for key in keys:
        if key in mapping and not is_blank(mapping[key]):
            return mapping[key]
    return None


def first_present_deep(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first non-blank value for aliases in nested dictionaries."""
    for node in iter_dict_values(mapping):
        value = first_present(node, keys)
        if not is_blank(value):
            return value
    return None


def is_blank(value: Any) -> bool:
    """Return true for absent or empty values."""
    return value is None or (isinstance(value, str) and not value.strip())


def stringify(value: Any) -> str:
    """Return a safe string representation."""
    return "" if value is None else str(value)


def empty_database_precedents(reason: str) -> dict[str, Any]:
    """Return a validator-shaped empty precedent summary."""
    return {
        "tier_counts": {"tier1": 0, "tier2": 0, "tier3": 0, "rejected": 0},
        "parse_coverage": {
            "pce": "0/0",
            "ff": "0/0",
            "voc": "0/0",
            "jsc": "0/0",
            "hysteresis": "0/0",
        },
        "top_precedent_rows": [],
        "demoted_precedent_rows": [],
        "rejected_precedent_rows_summary": {},
        "sqlite_precedent_quality": "unusable",
        "sqlite_quality_warning": True,
        "parse_coverage_warning": True,
        "sqlite_role": (
            "SQLite is for precedent discovery, stack/intervention matching, and paired "
            "delta background only; it is not mechanism proof."
        ),
        "empty_reason": reason,
    }


def first_table(conn: sqlite3.Connection) -> str:
    """Return the first user table in a SQLite database."""
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchone()
    if row is None:
        raise SystemExit("SQLite database contains no tables")
    return str(row[0])


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return column names for ``table``."""
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({quote_identifier(table)})")}


def query_precedents(
    conn: sqlite3.Connection, table: str, columns: set[str], context: dict[str, Any]
) -> list[sqlite3.Row]:
    """Run bounded context-matching SQL without assuming every column exists."""
    clauses: list[str] = []
    params: list[str] = []
    for column, context_key in (
        ("solar_cell_structure", "solar_cell_structure"),
        ("perovskite_composition", "perovskite_composition"),
        ("interfacial_modulator_material_application_location", "intervention_location"),
    ):
        value = str(context.get(context_key, "")).strip()
        if column in columns and value:
            clauses.append(f"lower(coalesce({quote_identifier(column)}, '')) LIKE lower(?)")
            params.append(f"%{compact_term(value)}%")

    where = " OR ".join(clauses) if clauses else "1=1"
    query = f"SELECT * FROM {quote_identifier(table)} WHERE {where} LIMIT 50"
    return list(conn.execute(query, params))


def build_sqlite_quality_report(
    rows: list[sqlite3.Row], columns: set[str], context: dict[str, Any], gap: Gap
) -> SQLiteQualityReport:
    """Build one central SQLite quality report for all output surfaces."""
    top_rows: list[dict[str, Any]] = []
    demoted_rows: list[dict[str, Any]] = []
    rejected: dict[str, int] = {}
    for row in rows:
        action, reason = sqlite_row_action(row, columns, context, gap)
        if action == "accept":
            top_rows.append(summarize_row(row, columns, context, gap))
        elif action == "demote":
            demoted = summarize_row(row, columns, context, gap)
            demoted["demotion_reason"] = reason
            demoted_rows.append(demoted)
        else:
            rejected[reason] = rejected.get(reason, 0) + 1

    top_rows = dedupe_precedent_rows(top_rows)[:5]
    demoted_rows = dedupe_precedent_rows(demoted_rows)[:5]
    parse_coverage = build_parse_coverage(rows, columns)
    hysteresis_ratio = parse_coverage_ratio(parse_coverage.get("hysteresis"))
    parse_warning = parse_coverage_is_low(parse_coverage) or (
        gap.gap_family == "ion_migration_hysteresis"
        and hysteresis_ratio is not None
        and hysteresis_ratio < 0.5
    )
    quality = sqlite_quality_label(top_rows, demoted_rows, parse_warning)
    quality_warning = quality in {"weak_screening_only", "unusable"} or parse_warning
    return SQLiteQualityReport(
        sqlite_precedent_quality=quality,
        sqlite_quality_warning=quality_warning,
        parse_coverage_warning=parse_warning,
        top_precedent_rows=top_rows,
        demoted_precedent_rows=demoted_rows,
        rejected_precedent_rows_summary=rejected,
        parse_coverage=parse_coverage,
        sqlite_role=(
            "SQLite is for precedent discovery, stack/intervention matching, and paired "
            "delta background only; it is not mechanism proof."
        ),
    )


def sqlite_row_action(
    row: sqlite3.Row, columns: set[str], context: dict[str, Any], gap: Gap
) -> tuple[str, str]:
    """Return accept/demote/reject and reason for a SQLite row."""
    if not is_perovskite_solar_cell_row(row, columns):
        return "reject", "not_perovskite_solar_cell_experiment"
    text = row_text(row, columns)
    if any(marker in text for marker in ("kesterite", "czts", "oxide-only", "generic review")):
        return "reject", "cross_domain_or_review"
    axes = precedent_matched_axes(row, columns, context, gap)
    score = similarity_score_from_axes(axes)
    if score < 0.65 or len(axes) < 2:
        return "reject", "low_similarity"
    if "architecture" in axes and not any(
        axis in axes for axis in ("composition", "intervention", "mechanism")
    ):
        return "demote", "architecture_match_without_intervention_or_mechanism_axis"
    metric_status = parsed_metric_status(row, columns)
    if metric_status == "no_usable_metric":
        return "demote", "no_paired_psc_device_metric"
    if metric_status == "screening_only":
        return "demote", "screening_only_without_usable_metric_delta"
    return "accept", "usable_background"


def parsed_metric_status(row: sqlite3.Row, columns: set[str]) -> str:
    """Classify metric usability in one SQLite row."""
    metric_columns = (
        "jv_reverse_scan_pce",
        "jv_reverse_scan_ff",
        "jv_reverse_scan_v_oc",
        "jv_reverse_scan_j_sc",
        "jv_hysteresis_index",
    )
    parsed = [
        column
        for column in metric_columns
        if column in columns and parse_numeric(row[column]) is not None
    ]
    if not parsed:
        return "no_usable_metric"
    # The current merged DB mostly stores row-level metrics, not audited paired deltas.
    return "screening_only"


def sqlite_quality_label(
    top_rows: list[dict[str, Any]], demoted_rows: list[dict[str, Any]], parse_warning: bool
) -> str:
    """Return strong/usable/weak/unusable quality label."""
    if top_rows and not parse_warning:
        return "usable_background"
    if top_rows:
        return "weak_screening_only"
    if demoted_rows:
        return "weak_screening_only"
    return "unusable"


def dedupe_precedent_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate repeated DOI/title rows."""
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (
            stringify(row.get("doi", "")).lower(),
            stringify(row.get("title", "")).lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def filter_precedent_rows(
    rows: list[sqlite3.Row], columns: set[str], context: dict[str, Any], gap: Gap
) -> list[sqlite3.Row]:
    """Keep only PSC-relevant, sufficiently comparable SQLite precedents."""
    qualified: list[sqlite3.Row] = []
    for row in rows:
        if not is_perovskite_solar_cell_row(row, columns):
            continue
        axes = precedent_matched_axes(row, columns, context, gap)
        score = similarity_score_from_axes(axes)
        if score < 0.65 or len(axes) < 2:
            continue
        if not any(axis in axes for axis in ("composition", "intervention", "mechanism")):
            continue
        qualified.append(row)
    return qualified


def is_perovskite_solar_cell_row(row: sqlite3.Row, columns: set[str]) -> bool:
    """Return true when a row has explicit PSC or perovskite-device context."""
    text = row_text(row, columns)
    if any(marker in text for marker in ("dye-sensitized", "dye sensitized", "dssc")):
        return False
    structure = stringify(row["solar_cell_structure"] if "solar_cell_structure" in columns else "")
    composition = stringify(
        row["perovskite_composition"] if "perovskite_composition" in columns else ""
    )
    combined = f"{structure} {composition} {text}".lower()
    if "perovskite" in combined:
        return True
    return any(marker in combined for marker in ("p-i-n", "n-i-p", "inverted", "psc"))


def precedent_similarity(
    row: sqlite3.Row, columns: set[str], context: dict[str, Any], gap: Gap
) -> tuple[float, int]:
    """Score rough comparability across architecture/composition/intervention axes."""
    axes = precedent_matched_axes(row, columns, context, gap)
    return similarity_score_from_axes(axes), len(axes)


def precedent_matched_axes(
    row: sqlite3.Row, columns: set[str], context: dict[str, Any], gap: Gap
) -> set[str]:
    """Return comparability axes matched by a SQLite row."""
    axes: set[str] = set()
    if architecture_matches(row, columns, context):
        axes.add("architecture")
    if composition_matches(row, columns, context):
        axes.add("composition")
    if intervention_location_matches(row, columns, context):
        axes.add("intervention")
    if mechanism_family_matches(row, columns, gap, context):
        axes.add("mechanism")
    if metric_family_matches(row, columns, gap):
        axes.add("metric")
    return axes


def similarity_score_from_axes(axes: set[str]) -> float:
    """Convert matched axes into a bounded screening score."""
    return min(0.45 + 0.10 * len(axes), 0.95)


def architecture_matches(row: sqlite3.Row, columns: set[str], context: dict[str, Any]) -> bool:
    """Return true when source and precedent architecture families match."""
    row_arch = normalize_architecture(
        row["solar_cell_structure"] if "solar_cell_structure" in columns else ""
    )
    source_arch = normalize_architecture(context.get("solar_cell_structure", ""))
    return bool(row_arch and source_arch and row_arch == source_arch)


def normalize_architecture(value: Any) -> str:
    """Normalize photovoltaic architecture text."""
    text = stringify(value).lower()
    if any(marker in text for marker in ("p-i-n", "pin", "inverted", "reverse")):
        return "p-i-n"
    if any(marker in text for marker in ("n-i-p", "nip", "regular")):
        return "n-i-p"
    return ""


def composition_matches(row: sqlite3.Row, columns: set[str], context: dict[str, Any]) -> bool:
    """Return true when absorber/composition family overlaps."""
    row_comp = stringify(
        row["perovskite_composition"] if "perovskite_composition" in columns else ""
    )
    source_comp = stringify(context.get("perovskite_composition", ""))
    source_tokens = composition_tokens(source_comp)
    row_tokens = composition_tokens(row_comp)
    overlap = (source_tokens & row_tokens) - {"perovskite"}
    return bool(source_tokens and row_tokens and overlap)


def composition_tokens(value: str) -> set[str]:
    """Extract coarse absorber-family tokens."""
    text = value.lower()
    tokens = set(re.findall(r"\b(?:fa|cs|ma|rb|pb|sn|br|cl|mixed|wide|narrow)\b", text))
    if "perovskite" in text:
        tokens.add("perovskite")
    return tokens


def intervention_location_matches(
    row: sqlite3.Row, columns: set[str], context: dict[str, Any]
) -> bool:
    """Return true when intervention location matches coarsely."""
    row_location = stringify(
        row["interfacial_modulator_material_application_location"]
        if "interfacial_modulator_material_application_location" in columns
        else ""
    ).lower()
    source_location = stringify(context.get("intervention_location", "")).lower()
    if not row_location or not source_location:
        return False
    source_terms = set(
        re.findall(r"interface|surface|grain|gb|contact|etl|htl|bulk", source_location)
    )
    row_terms = set(re.findall(r"interface|surface|grain|gb|contact|etl|htl|bulk", row_location))
    return bool(source_terms & row_terms)


def mechanism_family_matches(
    row: sqlite3.Row, columns: set[str], gap: Gap, context: dict[str, Any]
) -> bool:
    """Return true when precedent text overlaps the gap's coarse mechanism family."""
    text = f"{row_text(row, columns)} {context.get('modulator_material_or_family', '')}".lower()
    families = {
        "functional_analog_causal_isolation": (
            "passivation",
            "trap",
            "coordination",
            "morphology",
            "hydrophobic",
        ),
        "ff_loss_budget": ("ff", "fill factor", "recombination", "contact", "resistance"),
        "recombination_loss_mapping": (
            "trap",
            "recombination",
            "pl",
            "trpl",
            "qfls",
            "voc",
        ),
        "charge_extraction_collection": ("extraction", "collection", "transport", "transient"),
        "ion_migration_hysteresis": ("ion", "hysteresis", "bias", "scan"),
        "stability_degradation_pathway": (
            "stability",
            "degradation",
            "moisture",
            "humidity",
            "thermal",
        ),
        "morphology_phase_causality": (
            "morphology",
            "crystallinity",
            "grain",
            "phase",
            "strain",
        ),
        "contact_energetics_interface_selectivity": (
            "work function",
            "band alignment",
            "contact",
            "selectivity",
            "barrier",
        ),
        "p_i_n_architecture_translation": ("p-i-n", "pin", "inverted", "architecture"),
        "model_mapping_quantification": ("trap", "recombination", "model", "quantitative"),
    }
    markers = families.get(gap.gap_family, ("passivation", "contact", "recombination"))
    return any(marker in text for marker in markers)


def metric_family_matches(row: sqlite3.Row, columns: set[str], gap: Gap) -> bool:
    """Return true when parsed metrics or row text cover the gap family."""
    text = row_text(row, columns)
    if gap.gap_family == "ff_loss_budget":
        return ("jv_reverse_scan_ff" in columns and not is_blank(row["jv_reverse_scan_ff"])) or (
            "fill factor" in text or " ff " in f" {text} "
        )
    if gap.gap_family == "ion_migration_hysteresis":
        return ("jv_hysteresis_index" in columns and not is_blank(row["jv_hysteresis_index"])) or (
            "hysteresis" in text
        )
    if gap.gap_family == "recombination_loss_mapping":
        return any(marker in text for marker in ("voc", "qfls", "plqy", "trpl", "lifetime"))
    if gap.gap_family == "charge_extraction_collection":
        return any(marker in text for marker in ("jsc", "collection", "extraction", "mobility"))
    if gap.gap_family == "stability_degradation_pathway":
        return any(marker in text for marker in ("stability", "retention", "aging"))
    return any(
        column in columns and not is_blank(row[column])
        for column in ("jv_reverse_scan_pce", "jv_reverse_scan_v_oc", "jv_reverse_scan_j_sc")
    )


def row_text(row: sqlite3.Row, columns: set[str]) -> str:
    """Concatenate row values for coarse screening without recipe use."""
    return " ".join(
        stringify(row[column]).lower() for column in columns if not is_blank(row[column])
    )


def compact_term(value: str) -> str:
    """Return a short LIKE term to avoid over-specific context matching."""
    return re.split(r"[/,; ]+", value)[0]


def quote_identifier(value: str) -> str:
    """Quote a SQLite identifier."""
    return '"' + value.replace('"', '""') + '"'


def build_parse_coverage(rows: list[sqlite3.Row], columns: set[str]) -> dict[str, str]:
    """Build simple parse coverage for common performance metrics."""
    metric_columns = {
        "pce": "jv_reverse_scan_pce",
        "ff": "jv_reverse_scan_ff",
        "voc": "jv_reverse_scan_v_oc",
        "jsc": "jv_reverse_scan_j_sc",
        "hysteresis": "jv_hysteresis_index",
    }
    coverage: dict[str, str] = {}
    for metric, column in metric_columns.items():
        if column not in columns:
            coverage[metric] = f"0/{len(rows)}"
            continue
        parsed = sum(1 for row in rows if parse_numeric(row[column]) is not None)
        coverage[metric] = f"{parsed}/{len(rows)}"
    return coverage


def summarize_row(
    row: sqlite3.Row, columns: set[str], context: dict[str, Any], gap: Gap
) -> dict[str, Any]:
    """Summarize one SQLite precedent row without recipe details."""
    composition = (
        row["perovskite_composition"] if "perovskite_composition" in columns else "unknown"
    )
    structure = row["solar_cell_structure"] if "solar_cell_structure" in columns else "unknown"
    title = row["title"] if "title" in columns else "untitled precedent"
    doi = row["doi"] if "doi" in columns else "unknown"
    score, matched_axes = precedent_similarity(row, columns, context, gap)
    return {
        "title": title,
        "doi": doi,
        "solar_cell_structure": structure,
        "perovskite_composition": composition,
        "similarity_score": round(score, 2),
        "matched_comparability_axes": matched_axes,
        "why_comparable": (
            "Passed PSC screening and matched at least two architecture, absorber, "
            "intervention, mechanism, or metric-family axes."
        ),
        "why_limited": "SQLite rows are precedent background and not mechanism proof.",
        "parsed_deltas": {"status": parsed_metric_status(row, columns)},
    }


def parse_numeric(value: Any) -> float | None:
    """Parse a loose numeric value when possible."""
    if value is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    if match is None:
        return None
    return float(match.group(0))


def build_source_device_context(context: dict[str, Any], package_mode: str) -> dict[str, Any]:
    """Build source-device context without inventing a single stack for aggregates."""
    if package_mode == "aggregate_corpus":
        corpus_context = context.get("corpus_level_device_context")
        if isinstance(corpus_context, dict):
            source_context = dict(corpus_context)
        else:
            source_context = {
                "corpus_level_distribution": context.get(
                    "corpus_level_distribution",
                    "aggregate-corpus package; no single locked device stack",
                ),
                "dominant_architecture_families": as_list(
                    context.get("dominant_architecture_families"),
                    default=context.get(
                        "solar_cell_structure", "mixed or unresolved PSC architectures"
                    ),
                ),
                "dominant_absorber_families": as_list(
                    context.get("dominant_absorber_families"),
                    default=context.get("perovskite_composition", "mixed perovskite absorbers"),
                ),
                "dominant_intervention_families": as_list(
                    context.get("dominant_intervention_families"),
                    default=context.get("modulator_material_or_family", "mixed interventions"),
                ),
            }
        source_context["package_mode"] = "aggregate_corpus"
        source_context.setdefault(
            "mechanism_proof_limit",
            "Aggregate trends are corpus-level context and not single-paper mechanism proof.",
        )
        return source_context

    return {
        "package_mode": "single_paper",
        "solar_cell_structure": context["solar_cell_structure"],
        "cell_stack_sequence": context["cell_stack_sequence"],
        "perovskite_composition": context["perovskite_composition"],
        "intervention_location": context["intervention_location"],
        "modulator_material_or_family": context["modulator_material_or_family"],
    }


def build_design_memory_query(
    gap: Gap, context: dict[str, Any], classifier: GapClassifierOutput
) -> str:
    """Build a query for experiment-design motif retrieval."""
    pieces = [
        gap.text,
        classifier.primary_mechanism_axis,
        classifier.alternative_class,
        stringify(context.get("perovskite_composition", "")),
        stringify(context.get("intervention_location", "")),
        stringify(context.get("modulator_material_or_family", "")),
        "experimental motif controls readouts confounders closure non-closure",
    ]
    return " ".join(piece for piece in pieces if piece.strip())


def retrieve_design_motifs(query: str, context: dict[str, Any]) -> list[DesignMotif]:
    """Retrieve design motifs from context-provided mocks or primitive library.

    This is an interface boundary for the future 40k+ perovskite design-memory
    index. It does not treat retrieved motifs as mechanism proof.
    """
    provided = context.get("design_memory_motifs")
    if isinstance(provided, list) and provided:
        return [design_motif_from_mapping(item) for item in provided if isinstance(item, dict)]

    classifier_text = query.lower()
    archetypes = matched_archetypes_for_text(
        classifier_text,
        architecture_mismatch=normalize_architecture(context.get("solar_cell_structure", ""))
        != "p-i-n",
    )
    if not archetypes:
        archetypes = ["generic_uncertainty"]
    return [design_motif_from_archetype(archetype, context) for archetype in archetypes[:3]]


def design_motif_from_mapping(mapping: dict[str, Any]) -> DesignMotif:
    """Build a sanitized DesignMotif from external/mock design-memory data."""
    return DesignMotif(
        source_id=sanitize_design_text(mapping.get("source_id", "mock_design_memory")),
        doi=sanitize_design_text(mapping.get("doi", "unknown")),
        title=sanitize_design_text(mapping.get("title", "Design-memory motif")),
        architecture=sanitize_design_text(mapping.get("architecture", "unknown")),
        material_system=sanitize_design_text(mapping.get("material_system", "perovskite PSC")),
        intervention=sanitize_design_text(mapping.get("intervention", "unspecified intervention")),
        intervention_location=sanitize_design_text(
            mapping.get("intervention_location", "unspecified location")
        ),
        target_problem=sanitize_design_text(mapping.get("target_problem", "mechanism gap")),
        claimed_mechanism=sanitize_design_text(
            mapping.get("claimed_mechanism", "candidate mechanism")
        ),
        alternative_mechanisms_considered=sanitize_design_list(
            mapping.get("alternative_mechanisms_considered", [])
        ),
        controls_used=sanitize_design_list(mapping.get("controls_used", [])),
        primary_readouts=sanitize_design_list(mapping.get("primary_readouts", [])),
        secondary_readouts=sanitize_design_list(mapping.get("secondary_readouts", [])),
        confounders_addressed=sanitize_design_list(mapping.get("confounders_addressed", [])),
        confounders_not_addressed=sanitize_design_list(
            mapping.get("confounders_not_addressed", [])
        ),
        causal_strength=sanitize_design_text(mapping.get("causal_strength", "motif_only")),
        decision_logic_supports_H=sanitize_design_text(
            mapping.get("decision_logic_supports_H", "motif readout supports H branch")
        ),
        decision_logic_supports_Alt=sanitize_design_text(
            mapping.get("decision_logic_supports_Alt", "motif readout supports Alt branch")
        ),
        mixed_or_unresolved_logic=sanitize_design_text(
            mapping.get("mixed_or_unresolved_logic", "keep unresolved when branches conflict")
        ),
        portability_notes=sanitize_design_list(mapping.get("portability_notes", [])),
        wet_lab_detail_removed=True,
    )


def design_motif_from_archetype(archetype: str, context: dict[str, Any]) -> DesignMotif:
    """Create a design-memory motif from the soft primitive library."""
    entry = ARCHETYPE_REGISTRY[archetype]
    return DesignMotif(
        source_id=f"primitive_library::{archetype}",
        doi="not_applicable",
        title=CARD_ARCHETYPE_TITLES[archetype],
        architecture=stringify(context.get("solar_cell_structure", "architecture_unspecified")),
        material_system=stringify(context.get("perovskite_composition", "perovskite PSC")),
        intervention=stringify(context.get("modulator_material_or_family", "intervention")),
        intervention_location=stringify(
            context.get("intervention_location", "intervention location")
        ),
        target_problem=CARD_ARCHETYPE_TITLES[archetype],
        claimed_mechanism=ARCHETYPE_TO_PRIMARY_AXIS[archetype],
        alternative_mechanisms_considered=list(entry.get("confounder_motifs", [])),
        controls_used=list(entry.get("control_motifs", [])),
        primary_readouts=list(entry.get("readout_motifs", [])),
        secondary_readouts=list(entry.get("architecture_translation_motifs", [])),
        confounders_addressed=list(entry.get("confounder_motifs", [])),
        confounders_not_addressed=["motif is a design primitive and not direct proof"],
        causal_strength="design_motif_only",
        decision_logic_supports_H=stringify(entry.get("closure_rule_motifs", [""])[0]),
        decision_logic_supports_Alt="Alternative branch motifs explain the observation.",
        mixed_or_unresolved_logic=stringify(entry.get("non_closure_rule_motifs", [""])[0]),
        portability_notes=list(entry.get("architecture_translation_motifs", [])),
        wet_lab_detail_removed=True,
    )


def sanitize_design_list(value: Any) -> list[str]:
    """Sanitize design-memory list fields to design-level motifs."""
    items = value if isinstance(value, list) else [value]
    sanitized = [sanitize_design_text(item) for item in items if not is_blank(item)]
    return sanitized or ["not specified in retrieved motif"]


def sanitize_design_text(value: Any) -> str:
    """Remove operational recipe details from design-memory text."""
    text = stringify(value)
    recipe_markers = (
        "spin coat",
        "spin-coat",
        "antisolvent",
        "anneal",
        "dmf",
        "dmso",
        "chlorobenzene",
        "toluene",
        "rpm",
    )
    lowered = text.lower()
    if any(marker in lowered for marker in recipe_markers) or re.search(
        r"\b\d+(?:\.\d+)?\s*(?:mg/ml|mm|mM|ul|uL|ml|mL|°c|degc|rpm)\b",
        text,
        re.I,
    ):
        return "wet-lab operational detail removed; retain only design-level motif"
    return text


def determine_classification_mode(classifier: GapClassifierOutput, context: dict[str, Any]) -> str:
    """Return closed-set, mixed-archetype, or open-world classification mode."""
    if should_use_open_world_design_mode(classifier, context):
        return "open_world_design"
    if len(classifier.matched_archetypes) > 1:
        return "mixed_archetype"
    return "closed_set_archetype"


def should_use_open_world_design_mode(
    classifier: GapClassifierOutput, context: dict[str, Any]
) -> bool:
    """Return true when fixed archetype routing should not be the design gate."""
    if classifier.classifier_confidence == "low":
        return True
    if classifier.card_archetype == "generic_uncertainty":
        return True
    return package_mode_from_context(context) == "aggregate_corpus" and not context.get(
        "solar_cell_structure"
    )


def build_archetype_selection(classifier: GapClassifierOutput) -> dict[str, Any]:
    """Explain selected/rejected archetype routing without making it a hard gate."""
    selected = classifier.card_archetype
    rejected = [item for item in classifier.matched_archetypes if item != selected]
    if selected == "generic_uncertainty":
        rejected = [item for item in CARD_ARCHETYPE_TITLES if item != selected]
    return {
        "selected": selected,
        "rejected": rejected,
        "conflict_reason": classifier.conflict_reason,
        "classifier_confidence": classifier.classifier_confidence,
        "soft_routing_note": (
            "Family labels route design primitives; they are not hard requirements "
            "for generating a full experiment card."
        ),
    }


def build_design_motif_evidence(
    motifs: list[DesignMotif],
    lkm: LkmSummary,
    retrieval: RetrievalSummary,
) -> dict[str, Any]:
    """Build role-separated design motif evidence."""
    return {
        "retrieved_from_lkm": lkm.design_reasoning,
        "retrieved_from_design_memory": [motif.as_dict() for motif in motifs],
        "retrieved_from_sqlite_background": {
            "sqlite_precedent_quality": retrieval.database_precedents.get(
                "sqlite_precedent_quality", "unusable"
            ),
            "sqlite_quality_warning": retrieval.database_precedents.get(
                "sqlite_quality_warning", True
            ),
            "role": retrieval.database_precedents.get(
                "sqlite_role",
                "SQLite background only; not mechanism proof.",
            ),
        },
        "motif_synthesis_summary": (
            "Design motifs inform readout/control/confounder/closure-rule selection. "
            "They are not treated as proof of the source-package mechanism."
        ),
    }


def build_emergent_gap_family(
    gap: Gap,
    classifier: GapClassifierOutput,
    motifs: list[DesignMotif],
    classification_mode: str,
) -> dict[str, Any] | None:
    """Propose an emergent family when closed-set routing is insufficient."""
    if (
        classification_mode != "open_world_design"
        or classifier.card_archetype != "generic_uncertainty"
    ):
        return None
    keyword = slugify_gap_keyword(gap.text)
    return {
        "proposed_name": f"emergent_{keyword}_mechanism_discrimination",
        "reason_existing_families_are_insufficient": (
            "Stage B did not identify a registered archetype with enough confidence; "
            "the card is generated from causal uncertainty, LKM/design motifs, and "
            "source context instead of a fixed template."
        ),
        "closest_existing_families": classifier.matched_archetypes or ["generic_uncertainty"],
        "mechanism_axes": classifier.mechanism_axes,
        "design_motif_sources": [motif.source_id for motif in motifs],
        "confidence": "low",
        "review_required": True,
    }


def slugify_gap_keyword(text: str) -> str:
    """Return a compact keyword for emergent family naming."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]*", text.lower())
    stop = {"evidence", "gap", "claim", "mechanism", "unresolved", "missing"}
    filtered = [word.strip("_+-") for word in words if word not in stop]
    return "_".join(filtered[:4]) if filtered else "unregistered"


def build_open_world_design_template(
    gap: Gap,
    context: dict[str, Any],
    classifier: GapClassifierOutput,
    motifs: list[DesignMotif],
    lkm_design_reasoning: dict[str, Any],
) -> dict[str, Any]:
    """Synthesize a full experiment card without a hard family template."""
    uncertainty = extract_causal_uncertainty(gap)
    motif_readouts = merge_lists(
        *(motif.primary_readouts for motif in motifs),
        lkm_design_reasoning.get("readout_classes", []),
    )
    motif_controls = merge_lists(
        *(motif.controls_used for motif in motifs),
        lkm_design_reasoning.get("controls", []),
    )
    confounders = merge_lists(
        *(motif.confounders_addressed for motif in motifs),
        lkm_design_reasoning.get("confounders", []),
        classifier.alternative_class,
    )
    primary_readouts = [
        {
            "name": readout,
            "maps_to_uncertainty": uncertainty,
            "supports_H_pattern": "readout moves with the proposed mechanism branch under bounded confounders",
            "supports_Alt_pattern": "readout remains flat or follows the competing branch",
        }
        for readout in motif_readouts[:4]
    ] or [
        {
            "name": "gap-derived discriminating readout class",
            "maps_to_uncertainty": uncertainty,
            "supports_H_pattern": "readout supports the mechanism branch named in the gap",
            "supports_Alt_pattern": "readout supports the named alternative or covariate branch",
        }
    ]
    controls = motif_controls[:5] or ["gap-derived matched baseline/control class"]
    return {
        "template_id": "OPEN_WORLD_DESIGN_TEMPLATE",
        "template_resolution_status": "resolved_open_world_design",
        "gap_type_specific_title": "Open-world mechanism-discrimination design",
        "gap_type": "open-world mechanism-discrimination gap",
        "scientific_uncertainty": uncertainty,
        "hypothesis_H": (
            f"The {context.get('source_package', 'source-package')} claim is explained by the candidate mechanism branch "
            f"described in the gap: {uncertainty}"
        ),
        "alternative_Alt": (
            "A competing mechanism, architecture-specific effect, measurement artifact, "
            "or uncontrolled covariate explains the same observation."
        ),
        "discriminating_observation": (
            "A motif-synthesized readout/control set separates the candidate mechanism "
            "branch from the strongest competing branch while preserving source context."
        ),
        "variables_to_vary": [
            "source-package intervention axis",
            "candidate mechanism axis",
            "strongest competing mechanism or covariate axis",
        ],
        "controls": controls,
        "primary_readouts": primary_readouts,
        "secondary_readouts": merge_lists(
            *(motif.secondary_readouts for motif in motifs),
            lkm_design_reasoning.get("portability_notes", []),
        )[:5],
        "observable_to_mechanism_mapping": {
            "candidate_mechanism_branch": "primary readout supports H under matched controls",
            "competing_branch": "alternative readout or confounder explains the observation",
            "motif_source_limit": "design motifs guide experimental logic but do not prove the source mechanism",
        },
        "expected_result_if_H": (
            "The primary readout pattern follows the candidate mechanism branch while "
            "the listed confounders are bounded."
        ),
        "expected_result_if_Alt": (
            "A competing mechanism, architecture-specific branch, artifact, or covariate "
            "explains the observation better than the candidate mechanism."
        ),
        "success_criterion_for_closing_gap": (
            "Close only the named Gaia uncertainty when H-vs-Alt readouts separate the "
            "candidate branch from the competing branch; design motifs alone cannot close it."
        ),
        "non_closure_criteria": merge_lists(
            lkm_design_reasoning.get("non_closure_rules", []),
            "readouts remain proxy-only",
            "motifs are analogical without package-local discrimination",
            "confounders remain unbounded: "
            + ", ".join(stringify(item) for item in confounders[:5]),
        ),
        "failure_modes": [
            "motif-derived readouts do not map cleanly to the source-package uncertainty",
            "competing mechanisms remain unbounded",
            "p-i-n translation changes the dominant mechanism branch",
        ],
        "interpretation_decision_tree": (
            "Update toward H if motif-derived readouts support the candidate branch under "
            "bounded confounders; update toward Alt if a competing branch explains the "
            "observation; otherwise keep mixed_or_unresolved and propose emergent family review."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Candidate mechanism readouts support H while confounders are bounded."
                ),
                "interpretation": "Candidate mechanism branch is favored for the Gaia update.",
                "remaining_caveat": "Open-world family requires review before becoming a registry archetype.",
            },
            "supports_Alt": {
                "observation_pattern": "Competing branch or covariate readouts explain the observation.",
                "interpretation": "Alternative branch is favored.",
                "remaining_caveat": "The candidate branch may remain secondary.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Readouts are proxy-only, analogical, or branch-conflicted.",
                "interpretation": "Mechanism attribution remains unresolved.",
                "next_step": "Review emergent family and add a narrower motif/control set.",
            },
        },
        "recommended_experiment_class": "Open-world motif-synthesized H-vs-Alt design",
        "open_questions": [
            "Which retrieved motif should be promoted to a reviewed archetype?",
            "Which package-local readout can directly separate the candidate branch from Alt?",
        ],
    }


def extract_causal_uncertainty(gap: Gap) -> str:
    """Extract a concise causal uncertainty from the gap text."""
    text = re.sub(r"\s+", " ", gap.text).strip()
    text = re.sub(r"^Evidence Gap:\s*", "", text, flags=re.I)
    return text[:260] if text else "Unregistered mechanism uncertainty from Gaia gap."


def build_card(
    gap: Gap, context: dict[str, Any], retrieval: RetrievalSummary, lkm: LkmSummary
) -> dict[str, Any]:
    """Build one experiment-design card."""
    package_mode = package_mode_from_context(context)
    source_context = build_source_device_context(context, package_mode)
    classifier = classify_gap_stage_b(gap, context, retrieval, lkm)
    classification_mode = determine_classification_mode(classifier, context)
    design_memory_query = build_design_memory_query(gap, context, classifier)
    design_motifs = retrieve_design_motifs(design_memory_query, context)
    translation = build_device_translation_policy(context)
    if classification_mode == "open_world_design":
        domain = with_domain_defaults(
            build_open_world_design_template(
                gap,
                context,
                classifier,
                design_motifs,
                lkm.design_reasoning,
            ),
            classifier,
        )
    else:
        domain = build_domain_specific_template(gap, context, classifier)
    controls = merge_lists(domain.get("controls", []), translation["p_i_n_specific_controls"])
    causal_controls = domain.get("causal_isolation_controls") or build_causal_isolation_controls(
        gap
    )
    if causal_controls:
        controls = merge_lists(
            controls,
            [
                (
                    "functional analog-control class bounding morphology, crystallinity, "
                    "hydrophobicity, contact energetics, and recombination/trap-sensitive "
                    "readouts; multi-variable analogs cannot close the causal gap and only "
                    "support follow-up narrowing"
                )
            ],
        )

    parse_coverage = retrieval.database_precedents.get("parse_coverage")
    low_parse_coverage = isinstance(parse_coverage, dict) and parse_coverage_is_low(parse_coverage)
    sqlite_quality = stringify(
        retrieval.database_precedents.get("sqlite_precedent_quality", "unusable")
    )
    sqlite_weak = sqlite_quality in {"weak_screening_only", "unusable", "weak_or_none"}
    priority = score_priority(classifier, context, lkm, sqlite_weak=sqlite_weak)
    confidence = determine_card_confidence(classifier, lkm, sqlite_weak=sqlite_weak)
    card = {
        "gap_id": gap.gap_id,
        "package_mode": package_mode,
        "gap_family": classifier.card_archetype,
        "template_id": domain["template_id"],
        "template_resolution_status": domain["template_resolution_status"],
        "gap_type_specific_title": domain["gap_type_specific_title"],
        "source_package": context["source_package"],
        "target_claims": as_list(
            context.get("target_claims", context.get("target_claim")),
            default=f"{context['source_package']}::{gap.gap_id}",
        ),
        "affected_conclusions": as_list(
            context.get("affected_conclusions", context.get("affected_conclusion")),
            default=f"{context['source_package']}::main_conclusion",
        ),
        "current_belief": context.get("current_belief", "unknown"),
        "original_evidence_gap_text": gap.text,
        "gap_type": domain["gap_type"],
        "gap_classifier_output": classifier.as_dict(),
        "mechanism_axes": classifier.mechanism_axes,
        "primary_mechanism_axis": classifier.primary_mechanism_axis,
        "secondary_mechanism_axes": classifier.secondary_mechanism_axes,
        "card_archetype": classifier.card_archetype,
        "classification_mode": classification_mode,
        "archetype_selection": build_archetype_selection(classifier),
        "design_motif_evidence": build_design_motif_evidence(
            design_motifs,
            lkm,
            retrieval,
        ),
        "lkm_design_reasoning": lkm.design_reasoning,
        "design_memory_role": (
            "Design memory is used for experimental motif retrieval and control/readout "
            "design. It is not treated as direct proof of the source-package mechanism."
        ),
        "priority": priority,
        "priority_rationale": build_priority_rationale(
            classifier, priority, context, lkm, sqlite_weak=sqlite_weak
        ),
        "scientific_uncertainty": domain["scientific_uncertainty"],
        "hypothesis_H": domain["hypothesis_H"],
        "alternative_Alt": domain["alternative_Alt"],
        "discriminating_observation": domain["discriminating_observation"],
        "database_queries_run": retrieval.queries_run,
        "database_precedents": retrieval.database_precedents,
        "sqlite_precedent_quality": sqlite_quality,
        "sqlite_quality_warning": bool(
            retrieval.database_precedents.get("sqlite_quality_warning", sqlite_weak)
        ),
        "database_confidence": (
            "SQLite parse coverage is low; precedent rows and paired deltas remain "
            "background only and cannot increase mechanism-attribution confidence."
            if low_parse_coverage
            else "SQLite parse coverage is sufficient for precedent screening only."
        ),
        "sqlite_role": (
            "SQLite is for precedent discovery, stack/intervention matching, and "
            "paired delta background only; it is not mechanism proof."
        ),
        "sqlite_weight_or_role": (
            "weak background only: precedent discovery, comparability, readout suggestions, "
            "and risk flags; never mechanism proof or gap closure"
        ),
        "lkm_queries_run": lkm.queries_run,
        "lkm_role": lkm.role,
        "lkm_weight_or_role": (
            "same-package LKM reasoning can raise mechanism relevance; cross-package "
            "chains are analogies; ambiguous chains are audit-only."
        ),
        "lkm_evidence_summary": lkm.evidence_summary,
        "mechanism_source_breakdown": {
            "package_local_gaia_evidence": (
                "Package-local Gaia evidence supplies the target gap, affected conclusion, "
                "locked source-device context, and unresolved causal link."
            ),
            "lkm_mechanism_reasoning": lkm.mechanism_reasoning,
            "sqlite_precedent_delta_background": (
                "SQLite contributes comparable precedent and paired delta background, "
                "not mechanism proof."
            ),
        },
        "same_package_lkm_chains": lkm.same_package_chains,
        "cross_package_lkm_chains": lkm.cross_package_chains,
        "unknown_package_lkm_chains": lkm.unknown_package_chains,
        "ambiguous_lkm_chains": lkm.unknown_package_chains,
        "sqlite_lkm_conflicts": lkm.sqlite_lkm_conflicts,
        "mechanism_attribution_limitations": (
            build_mechanism_limitations(classifier, lkm, sqlite_weak=sqlite_weak)
        ),
        "gap_resolution_strategy": build_gap_resolution_strategy(gap),
        "recommended_experiment_class": domain["recommended_experiment_class"],
        "source_device_context": source_context,
        "lab_translation_context": translation["lab_translation_context"],
        "p_i_n_adaptation_design": translation["p_i_n_adaptation_design"],
        "portability_risks_for_p_i_n": translation["p_i_n_specific_risks"],
        "architecture_sensitive_readouts": merge_lists(
            translation["p_i_n_specific_readouts"],
            domain.get("architecture_sensitive_readouts", []),
        ),
        "what_not_to_generalize": translation["what_not_to_generalize"],
        "p_i_n_specific_controls": translation["p_i_n_specific_controls"],
        "p_i_n_specific_readouts": translation["p_i_n_specific_readouts"],
        "p_i_n_specific_risks": translation["p_i_n_specific_risks"],
        "variables_to_vary": domain["variables_to_vary"],
        "controls": controls,
        "primary_readouts": domain["primary_readouts"],
        "secondary_readouts": domain["secondary_readouts"],
        "observable_to_mechanism_mapping": domain["observable_to_mechanism_mapping"],
        "expected_result_if_H": domain["expected_result_if_H"],
        "expected_result_if_Alt": domain["expected_result_if_Alt"],
        "success_criterion_for_closing_gap": domain["success_criterion_for_closing_gap"],
        "non_closure_criteria": domain["non_closure_criteria"],
        "minimum_replicate_logic": (
            "Use independent matched device populations and batch-separated comparisons; "
            "this planning card intentionally omits operational preparation parameters."
        ),
        "statistics_or_comparison_logic": domain["statistics_or_comparison_logic"],
        "failure_modes": domain["failure_modes"],
        "interpretation_decision_tree": domain["interpretation_decision_tree"],
        "outcome_matrix": domain["outcome_matrix"],
        "belief_update_target": "Update the target Gaia claim or H-vs-Alt likelihood direction.",
        "belief_update_contract": (
            "Update only the named Gaia claim direction supported by the outcome matrix; "
            "do not treat analogical LKM or SQLite background as source-paper proof."
        ),
        "feasibility_notes": "Generated as design-level planning, not an operational protocol.",
        "safety_boundary_note": (
            "Planning only; implementation requires qualified lab supervision and "
            "institutional safety review."
        ),
        "confidence": confidence,
        "open_questions": domain["open_questions"],
        "lkm_scope_summary": summarize_lkm_scope_counts(lkm),
    }
    emergent_family = build_emergent_gap_family(
        gap,
        classifier,
        design_motifs,
        classification_mode,
    )
    if emergent_family is not None:
        card["emergent_gap_family"] = emergent_family
    for optional_key in (
        "loss_channel_budget",
        "causal_isolation_controls",
        "model_inputs",
        "model_outputs",
        "falsification_criterion",
        "p_i_n_closure_rule",
        "p_i_n_non_closure_rule",
    ):
        if optional_key in domain:
            card[optional_key] = domain[optional_key]
    if causal_controls:
        card["causal_isolation_controls"] = causal_controls
    return card


def build_domain_specific_template(
    gap: Gap, context: dict[str, Any], classifier: GapClassifierOutput
) -> dict[str, Any]:
    """Dispatch gap families to domain-specific experiment-card templates."""
    archetype = classifier.card_archetype
    if archetype == "ff_loss_budget":
        template = build_ff_loss_budget_card(gap, context)
    elif archetype == "recombination_loss_mapping":
        template = build_recombination_loss_mapping_template(context)
    elif archetype == "charge_extraction_collection":
        template = build_extraction_timing_template(context)
    elif archetype == "ion_migration_hysteresis":
        template = build_ion_migration_hysteresis_template(context)
    elif archetype == "functional_analog_causal_isolation":
        template = build_causal_isolation_analog_template(context)
    elif archetype == "stability_degradation_pathway":
        template = build_stability_degradation_pathway_template(context)
    elif archetype == "morphology_phase_causality":
        template = build_morphology_phase_causality_template(context)
    elif archetype == "contact_energetics_interface_selectivity":
        template = build_contact_energetics_interface_selectivity_template(context)
    elif archetype == "p_i_n_architecture_translation":
        template = build_p_i_n_architecture_translation_template(context)
    elif archetype == "model_mapping_quantification":
        template = build_device_model_link_template(context)
    else:
        template = build_unresolved_generic_template(gap)
    return with_domain_defaults(template, classifier)


def with_domain_defaults(
    template: dict[str, Any], classifier: GapClassifierOutput
) -> dict[str, Any]:
    """Fill common card fields not owned by a domain module."""
    defaults: dict[str, Any] = {
        "template_id": archetype_template_id(classifier.card_archetype),
        "template_resolution_status": (
            "unresolved_generic_fallback"
            if classifier.card_archetype == "generic_uncertainty"
            else "resolved_domain_specific"
        ),
        "gap_type_specific_title": CARD_ARCHETYPE_TITLES[classifier.card_archetype],
        "gap_type": archetype_gap_type(classifier.card_archetype),
        "recommended_experiment_class": "Design-level H-vs-Alt discriminating campaign",
        "observable_to_mechanism_mapping": {
            "dominant_observable": classifier.dominant_observable,
            "primary_mechanism_axis": classifier.primary_mechanism_axis,
            "alternative_class": classifier.alternative_class,
            "closure_logic": (
                "Readouts must map the observable to the primary mechanism axis while "
                "bounding the named alternative class."
            ),
        },
        "non_closure_criteria": [
            "readouts remain proxy-only",
            "H and Alt readouts are both plausible or mixed_or_unresolved",
            "SQLite background is the only support",
            "architecture translation is untested for the lab p-i-n context",
        ],
        "statistics_or_comparison_logic": (
            "Compare paired direction, uncertainty, and covariate-bounded consistency "
            "across the declared H/Alt branches."
        ),
        "open_questions": [
            "Which available lab readout has the strongest direct mapping to the unresolved branch?"
        ],
        "architecture_sensitive_readouts": ["architecture-matched contact/selectivity readout"],
    }
    merged = dict(defaults)
    merged.update(template)
    return merged


def build_recombination_loss_mapping_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for recombination, trap, lifetime, PL/TRPL, QFLS, and Voc gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "RECOMBINATION_LOSS_MAPPING_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Recombination-loss mapping and proxy-to-device discrimination",
        "gap_type": "recombination / trap-loss mapping gap",
        "scientific_uncertainty": (
            "Whether trap, PL/TRPL, QFLS, Voc-deficit, or nonradiative-recombination "
            "proxies identify a device-relevant recombination-loss branch rather than a "
            "bulk/interface/contact location ambiguity or measurement-only proxy."
        ),
        "hypothesis_H": (
            f"{modulator} reduces device-relevant nonradiative recombination through a "
            "trap-passivation or interface-recombination branch that maps to the affected "
            "Gaia claim."
        ),
        "alternative_Alt": (
            "The proxy trend reflects bulk recombination, contact-mediated recombination, "
            "morphology-induced lifetime change, or a measurement-only proxy that does not "
            "explain the device claim."
        ),
        "discriminating_observation": (
            "Location-aware recombination readouts and device-population context assign the "
            "proxy shift to trap passivation, bulk, interface, contact-mediated, or "
            "morphology-induced branches."
        ),
        "variables_to_vary": [
            "intervention versus matched no-intervention population",
            "interface-local versus bulk-sensitive recombination context",
            "morphology-bounded comparator where the proxy can co-vary with microstructure",
        ],
        "controls": [
            "matched no-intervention baseline",
            "same absorber-family population with device metrics paired to recombination proxies",
            "contact-mediated recombination comparator",
            "morphology-bounded comparator when lifetime or PL proxies may shift with film quality",
        ],
        "primary_readouts": [
            {
                "name": "trap-passivation and nonradiative-recombination proxy class",
                "maps_to_uncertainty": "trap passivation versus proxy-only interpretation",
                "supports_H_pattern": "trap/recombination proxy improves with paired device relevance",
                "supports_Alt_pattern": "proxy improves without device-relevant mapping",
            },
            {
                "name": "bulk versus interface recombination localization class",
                "maps_to_uncertainty": "bulk recombination versus interface recombination branch",
                "supports_H_pattern": "readout localizes the effect to the claimed interface or defect branch",
                "supports_Alt_pattern": "bulk or off-target recombination branch explains the proxy",
            },
            {
                "name": "contact-mediated recombination bounding class",
                "maps_to_uncertainty": "contact-mediated recombination alternative",
                "supports_H_pattern": "contact-mediated contribution is bounded below the target branch",
                "supports_Alt_pattern": "contact-mediated recombination accounts for the device trend",
            },
        ],
        "secondary_readouts": [
            "Voc/QFLS/device-population context",
            "morphology or crystallinity context when lifetime proxies may co-vary",
        ],
        "observable_to_mechanism_mapping": {
            "trap_passivation": "trap-sensitive proxy improves with device-relevant recombination loss",
            "bulk_recombination": "bulk-sensitive readout explains the proxy shift",
            "interface_recombination": "interface-local readout explains the proxy shift",
            "contact_mediated_recombination": "contact-sensitive branch explains the device trend",
            "morphology_induced_lifetime_change": "morphology/crystallinity shift explains lifetime proxy",
            "measurement_only_proxy_risk": "proxy changes without paired device-metric mapping",
        },
        "expected_result_if_H": (
            "Trap or interface recombination readouts improve in the same population where "
            "the affected device claim shifts, while contact and morphology alternatives "
            "remain bounded."
        ),
        "expected_result_if_Alt": (
            "Bulk, contact-mediated, morphology-induced, or proxy-only branches explain the "
            "recombination signal better than the claimed passivation branch."
        ),
        "success_criterion_for_closing_gap": (
            "Close only if recombination-sensitive readouts localize the branch and map to "
            "the affected device claim under bounded contact and morphology alternatives."
        ),
        "non_closure_criteria": [
            "PL/TRPL/QFLS/Voc proxy improves without paired device relevance",
            "bulk/interface/contact location remains unresolved",
            "morphology-induced lifetime changes are not bounded",
        ],
        "failure_modes": [
            "Proxy signal improves but device-population mapping is absent.",
            "Bulk, interface, contact, and morphology branches remain non-identifiable.",
        ],
        "interpretation_decision_tree": (
            "Update toward H when location-aware recombination readouts map to the device "
            "claim with bounded contact/morphology alternatives; update toward Alt when "
            "bulk, contact-mediated, morphology, or proxy-only branches dominate; otherwise "
            "keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Device-relevant trap/interface recombination reduction appears with "
                    "bounded contact and morphology alternatives."
                ),
                "interpretation": "Target recombination/passivation branch is favored.",
                "remaining_caveat": "Architecture-specific contact recombination still needs p-i-n check.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Bulk, contact-mediated, morphology-induced, or proxy-only readouts "
                    "account for the observed trend."
                ),
                "interpretation": "Non-target recombination or proxy alternative is favored.",
                "remaining_caveat": "A smaller trap-passivation effect may remain.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Recombination proxies improve but branch location is unresolved.",
                "interpretation": "Mechanism attribution remains bounded.",
                "next_step": "Add localization or contact/morphology-bounding readouts.",
            },
        },
    }


def build_extraction_timing_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for transient extraction and carrier-collection gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "CHARGE_EXTRACTION_COLLECTION_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Transient extraction and carrier-collection timing",
        "gap_type": "transient extraction / carrier-collection timing gap",
        "scientific_uncertainty": (
            "Whether carrier extraction or collection timing contributes to the affected "
            "device-performance claim after recombination and contact proxies are bounded."
        ),
        "hypothesis_H": (
            f"{modulator} improves the affected device claim partly by improving carrier "
            "extraction or collection dynamics at the relevant perovskite/contact region."
        ),
        "alternative_Alt": (
            "The device gain is mostly from recombination, morphology, static contact "
            "energetics, or contact-only shifts while extraction timing remains unchanged."
        ),
        "discriminating_observation": (
            "Extraction-sensitive timing or carrier-collection readouts track the matched "
            "device-performance delta after recombination and contact proxies are bounded."
        ),
        "variables_to_vary": [
            "intervention versus no-intervention baseline",
            "contact-only comparator",
            "morphology-matched comparator where available",
        ],
        "controls": [
            "no-intervention baseline",
            "contact-only comparator",
            "morphology-matched comparator where available",
            "same-device FF/Voc/Jsc/PCE population paired to extraction readouts",
        ],
        "primary_readouts": [
            {
                "name": "transient extraction / carrier collection timing readout class",
                "maps_to_uncertainty": "extraction or collection dynamics versus non-extraction alternatives",
                "supports_H_pattern": "extraction timing shifts in the direction paired with the device delta",
                "supports_Alt_pattern": "extraction timing remains unchanged after matched controls",
            },
            {
                "name": "recombination lifetime context",
                "maps_to_uncertainty": "separates extraction timing from recombination lifetime changes",
                "supports_H_pattern": "lifetime context cannot alone explain the device delta",
                "supports_Alt_pattern": "lifetime or recombination trend explains the device delta",
            },
            {
                "name": "contact/transport proxy deltas",
                "maps_to_uncertainty": "bounds static contact or transport shifts",
                "supports_H_pattern": "contact/transport proxies remain secondary to extraction timing",
                "supports_Alt_pattern": "contact/transport proxies dominate while extraction is flat",
            },
        ],
        "secondary_readouts": [
            "steady-state population metrics paired to timing readouts",
            "contact-selective comparison in the translated p-i-n stack",
        ],
        "observable_to_mechanism_mapping": {
            "faster_extraction": "extraction timing shifts with the device delta",
            "suppressed_recombination_during_collection": (
                "lifetime/recombination context explains the collection trend"
            ),
            "contact_selectivity": "contact-selective proxy dominates the device trend",
            "optical_absorption_jsc_confounder": "optical/Jsc context explains collection changes",
            "morphology_mobility_covariate": "morphology or mobility co-varies with timing",
        },
        "expected_result_if_H": (
            "Extraction-sensitive timing changes co-vary with the device delta while "
            "recombination, morphology, and contact-only proxies remain bounded."
        ),
        "expected_result_if_Alt": (
            "Recombination, morphology, or static contact proxies explain the device delta "
            "without an extraction-timing shift."
        ),
        "success_criterion_for_closing_gap": (
            "Resolve toward extraction only if extraction-sensitive readouts track the "
            "performance delta after recombination and contact proxies are bounded."
        ),
        "non_closure_criteria": [
            "extraction timing changes but recombination/contact/morphology proxies co-vary",
            "Jsc or optical absorption confounds the carrier-collection interpretation",
            "timing readouts are not paired to the same device population",
        ],
        "failure_modes": [
            "Timing readouts shift but morphology/contact proxies shift in parallel.",
            "Timing and recombination proxies are both plausible and remain inseparable.",
        ],
        "interpretation_decision_tree": (
            "If timing readouts track the paired device delta with bounded recombination "
            "and contact proxies, update toward extraction; if contact, morphology, or "
            "recombination proxies dominate, update toward Alt; otherwise keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Extraction or collection timing changes track the paired device delta "
                    "after recombination/contact proxies are bounded."
                ),
                "interpretation": "Extraction or collection dynamics contribution is favored.",
                "remaining_caveat": "Architecture-specific contact transfer still requires p-i-n checks.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Extraction timing is unchanged while recombination, morphology, or "
                    "contact proxies explain the device delta."
                ),
                "interpretation": "A non-extraction alternative is favored.",
                "remaining_caveat": "A smaller extraction contribution may remain below resolution.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Timing, recombination, and contact proxies do not separate cleanly.",
                "interpretation": "Extraction contribution remains unresolved.",
                "next_step": "Add a narrower contact-selective or morphology-bounded comparator.",
            },
        },
    }


def build_ion_migration_hysteresis_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for ion-migration and hysteresis gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "ION_MIGRATION_HYSTERESIS_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Ion migration, hysteresis, and bias-history discrimination",
        "gap_type": "ion-migration / hysteresis discrimination gap",
        "scientific_uncertainty": (
            "Whether the hysteresis-linked device response reflects mobile-ion or "
            "interfacial charge accumulation rather than contact, barrier, recombination, "
            "or scan-protocol effects."
        ),
        "hypothesis_H": (
            f"{modulator} reduces mobile-ion or interfacial charge-accumulation effects, "
            "reducing hysteresis-linked device loss."
        ),
        "alternative_Alt": (
            "The hysteresis reduction is mainly a contact, barrier, recombination, or "
            "scan-protocol effect."
        ),
        "discriminating_observation": (
            "Hysteresis index, scan-direction delta, and bias-history response assign the "
            "device loss toward ion/charge accumulation or toward the contact/barrier alternative."
        ),
        "variables_to_vary": [
            "matched intervention versus no-intervention population",
            "scan direction and scan-history state",
            "bias-history condition",
        ],
        "controls": [
            "matched no-intervention baseline",
            "scan-direction comparator",
            "bias-history comparator",
            "contact/barrier comparator that does not treat hysteresis as mechanism proof",
        ],
        "primary_readouts": [
            {
                "name": "paired hysteresis index and FF/PCE scan-direction delta",
                "maps_to_uncertainty": "ion/charge accumulation versus scan-protocol/contact alternative",
                "supports_H_pattern": "hysteresis index and scan-direction delta shrink with bounded contact proxies",
                "supports_Alt_pattern": "scan-direction delta follows contact or protocol state instead",
            },
            {
                "name": "ion or interfacial charge accumulation-sensitive readout class",
                "maps_to_uncertainty": "mobile-ion or charge-accumulation branch",
                "supports_H_pattern": "charge-accumulation-sensitive signal decreases with the device delta",
                "supports_Alt_pattern": "charge-accumulation signal is flat or inconsistent",
            },
            {
                "name": "bias-history response class",
                "maps_to_uncertainty": "bias-history sensitivity versus static contact/barrier alternative",
                "supports_H_pattern": "bias-history response is suppressed in the intervention population",
                "supports_Alt_pattern": "bias-history response maps to contact/barrier changes",
            },
        ],
        "secondary_readouts": [
            "temperature-dependent hysteresis analysis class",
            "operando potential mapping class",
        ],
        "observable_to_mechanism_mapping": {
            "true_ion_migration_suppression": (
                "hysteresis, scan-direction delta, and charge-accumulation-sensitive "
                "readouts decrease together"
            ),
            "contact_barrier_effect": "contact or barrier readouts explain the hysteresis trend",
            "recombination_effect": "recombination-sensitive readouts explain hysteresis-linked loss",
            "scan_protocol_artifact": "protocol state changes the apparent hysteresis branch",
        },
        "expected_result_if_H": (
            "Hysteresis-linked device loss decreases with ion or charge-accumulation "
            "readouts while contact/barrier alternatives are bounded."
        ),
        "expected_result_if_Alt": (
            "Contact/barrier, recombination, or scan-protocol response explains the "
            "hysteresis trend without ion/charge accumulation support."
        ),
        "success_criterion_for_closing_gap": (
            "Resolve only if hysteresis-linked device loss is assigned toward ion/charge "
            "accumulation or toward the contact/barrier alternative; otherwise record "
            "mixed_or_unresolved."
        ),
        "non_closure_criteria": [
            "hysteresis changes only under one scan protocol",
            "contact/barrier and ion/charge accumulation readouts point to different branches",
            "charge-accumulation-sensitive readout is absent",
        ],
        "failure_modes": [
            "Scan-direction response changes without a charge-accumulation-sensitive signal.",
            "Bias-history and contact/barrier readouts point to different branches.",
        ],
        "interpretation_decision_tree": (
            "If hysteresis, bias-history, and charge-accumulation-sensitive readouts "
            "cohere, update toward H; if contact/barrier or protocol response explains "
            "the trend, update toward Alt; otherwise keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Hysteresis index, scan-direction delta, and bias-history response "
                    "decrease with charge-accumulation-sensitive support."
                ),
                "interpretation": "Ion or interfacial charge accumulation branch is favored.",
                "remaining_caveat": "Contact-stack portability to p-i-n remains architecture-sensitive.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Contact/barrier, recombination, or scan-protocol response explains "
                    "the hysteresis trend."
                ),
                "interpretation": "A non-ion-migration alternative is favored.",
                "remaining_caveat": "Mobile-ion contribution may remain secondary.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Hysteresis and contact/bias-history signals conflict.",
                "interpretation": "Hysteresis mechanism remains mixed_or_unresolved.",
                "next_step": "Separate scan protocol and contact-barrier comparators.",
            },
        },
    }


def build_causal_isolation_analog_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for multifunctional intervention causal-isolation gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "FUNCTIONAL_ANALOG_CAUSAL_ISOLATION_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Functional analog controls for causal isolation",
        "gap_type": "causal attribution / multifunctional intervention gap",
        "scientific_uncertainty": (
            "Whether the target coordination/passivation branch remains causal after "
            "morphology, crystallinity, hydrophobicity, contact energetics, and "
            "trap/recombination-sensitive covariates are bounded."
        ),
        "hypothesis_H": (
            f"{modulator} coordination/passivation remains a causal device contributor "
            "after morphology, hydrophobicity, crystallinity, and contact covariates "
            "are bounded."
        ),
        "alternative_Alt": (
            "The device gain is mainly explained by morphology, crystallinity, "
            "hydrophobicity, contact changes, or process covariates co-varying with "
            "the intervention."
        ),
        "discriminating_observation": (
            "Functional analog controls separate the coordination/passivation branch "
            "from bounded morphology, crystallinity, hydrophobicity, contact, and "
            "trap/recombination covariates."
        ),
        "variables_to_vary": [
            "target intervention versus matched no-intervention baseline",
            "functional analog preserving hydrophobic or morphology effects",
            "functional analog preserving coordination tendency where available",
        ],
        "controls": [
            "matched no-intervention baseline",
            (
                "functional analog preserving hydrophobic/morphology effects without "
                "comparable coordination to the relevant perovskite site"
            ),
            (
                "functional analog preserving coordination tendency without the same "
                "hydrophobic/morphology contribution where available"
            ),
            "same device-stack and absorber-family comparison logic",
        ],
        "primary_readouts": [
            {
                "name": "trap/recombination-sensitive passivation readout class",
                "maps_to_uncertainty": "coordination/passivation branch versus covariate alternatives",
                "supports_H_pattern": "trap/recombination response tracks coordination analog logic",
                "supports_Alt_pattern": "trap/recombination response follows morphology/contact covariates",
            },
            {
                "name": "morphology and crystallinity bounding class",
                "maps_to_uncertainty": "morphology/crystallinity alternative",
                "supports_H_pattern": "morphology and crystallinity remain bounded across decisive comparison",
                "supports_Alt_pattern": "morphology or crystallinity shifts explain the device delta",
            },
            {
                "name": "hydrophobicity and contact-energetics bounding class",
                "maps_to_uncertainty": "hydrophobicity/contact alternative",
                "supports_H_pattern": "hydrophobicity and contact energetics do not account for the device delta",
                "supports_Alt_pattern": "hydrophobicity or contact shifts track the device delta",
            },
        ],
        "secondary_readouts": [
            "same-stack population metric context",
            "architecture-matched p-i-n contact-selective comparator",
        ],
        "observable_to_mechanism_mapping": {
            "chemical_interaction_branch": (
                "coordination/passivation-sensitive readout remains decisive after "
                "covariates are bounded"
            ),
            "morphology_branch": "morphology readouts explain the device trend",
            "crystallinity_branch": "crystallinity or phase quality explains the device trend",
            "hydrophobicity_branch": "environmental or wetting proxy explains the outcome",
            "contact_energetics_branch": "contact/selectivity readouts explain the outcome",
            "follow_up_narrowing": (
                "multi-variable analogs cannot close the causal gap and only narrow it"
            ),
        },
        "causal_isolation_controls": {
            "analog_control_class": "design-level functional analog comparator class",
            "bounded_covariates": [
                "morphology",
                "crystallinity",
                "hydrophobicity",
                "contact energetics",
                "recombination/trap-sensitive readouts",
            ],
            "limitation": (
                "If analog controls also change multiple variables, they cannot close the "
                "causal gap and only support follow-up narrowing."
            ),
        },
        "expected_result_if_H": (
            "Coordination/passivation-sensitive readouts track the device response while "
            "morphology, crystallinity, hydrophobicity, and contact covariates remain bounded."
        ),
        "expected_result_if_Alt": (
            "One or more covariate classes track the device response better than the "
            "coordination/passivation readouts."
        ),
        "success_criterion_for_closing_gap": (
            "Resolve toward causal attribution only if analog-control logic bounds the "
            "declared covariates; multi-variable analogs support follow-up narrowing "
            "rather than causal closure."
        ),
        "non_closure_criteria": [
            "functional analog controls also change multiple covariates",
            "morphology, crystallinity, hydrophobicity, or contact energetics remain unbounded",
            "only aggregate device metrics separate the comparison",
        ],
        "failure_modes": [
            "Analog controls change multiple covariates and cannot isolate the branch.",
            "Hydrophobicity, morphology, and contact-energetic responses co-vary.",
        ],
        "interpretation_decision_tree": (
            "If analog controls preserve the target passivation signature while bounded "
            "covariates cannot explain the device delta, update toward H; if covariates "
            "track the delta, update toward Alt; if analogs remain multi-variable, keep "
            "mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Coordination/passivation readouts remain decisive after morphology, "
                    "crystallinity, hydrophobicity, contact, and trap/recombination "
                    "covariates are bounded."
                ),
                "interpretation": "Target coordination/passivation branch is favored.",
                "remaining_caveat": "Analog class must remain design-level and not a recipe.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Morphology, crystallinity, hydrophobicity, contact energetics, or "
                    "process covariates explain the device delta."
                ),
                "interpretation": "A co-varying alternative branch is favored.",
                "remaining_caveat": "A smaller passivation contribution may remain.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Functional analogs perturb multiple covariates at once.",
                "interpretation": "Causal attribution remains unresolved.",
                "next_step": "Use a narrower analog class or add a separate covariate-bounding comparator.",
            },
        },
    }


def build_stability_degradation_pathway_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for stability and degradation-pathway gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "STABILITY_DEGRADATION_PATHWAY_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Stability and degradation-pathway discrimination",
        "gap_type": "stability / degradation-pathway gap",
        "scientific_uncertainty": (
            "Whether the stability claim follows a chemical-passivation pathway, "
            "hydrophobic/moisture-barrier pathway, phase pathway, contact degradation, "
            "ion migration, or an encapsulation/process artifact."
        ),
        "hypothesis_H": (
            f"{modulator} improves the relevant stability outcome through the claimed "
            "chemical passivation or local degradation-pathway suppression under matched "
            "stress context."
        ),
        "alternative_Alt": (
            "The apparent stability benefit is explained by hydrophobic/moisture barrier "
            "effects, phase segregation or transition, contact degradation differences, "
            "ion migration, initial-performance bias, encapsulation, or process artifacts."
        ),
        "discriminating_observation": (
            "Stress-linked degradation readouts assign the retention trend to a specific "
            "pathway rather than treating initial PCE/FF improvement as stability proof."
        ),
        "variables_to_vary": [
            "matched intervention versus no-intervention population under the same stress class",
            "barrier/hydrophobicity comparator",
            "phase/contact/ion-migration pathway comparator where relevant",
        ],
        "controls": [
            "matched initial-performance baseline to avoid initial-PCE bias",
            "same absorber-family and same architecture stability comparator",
            "hydrophobicity or barrier-effect comparator",
            "contact-degradation and phase-pathway comparator when those alternatives are plausible",
        ],
        "primary_readouts": [
            {
                "name": "pathway-resolved stability retention readout class",
                "maps_to_uncertainty": "chemical passivation stability versus non-chemical stability branch",
                "supports_H_pattern": "degradation pathway tied to claimed chemical/passivation branch is suppressed",
                "supports_Alt_pattern": "retention follows barrier, phase, contact, ion, or process branch",
            },
            {
                "name": "hydrophobicity or moisture-barrier discrimination class",
                "maps_to_uncertainty": "hydrophobic/moisture barrier alternative",
                "supports_H_pattern": "barrier proxy is bounded below the chemical-passivation branch",
                "supports_Alt_pattern": "barrier proxy explains retention",
            },
            {
                "name": "phase/contact/ion-degradation pathway class",
                "maps_to_uncertainty": "phase transition, contact degradation, or ion migration alternative",
                "supports_H_pattern": "phase/contact/ion alternatives remain secondary",
                "supports_Alt_pattern": "one pathway explains the degradation trend",
            },
        ],
        "secondary_readouts": [
            "initial device-metric population context",
            "architecture-matched p-i-n degradation-pathway comparator",
        ],
        "observable_to_mechanism_mapping": {
            "chemical_passivation_stability": "claimed passivation pathway remains stable under stress",
            "hydrophobic_moisture_barrier": "barrier or wetting response explains retention",
            "phase_segregation_or_transition": "phase readouts explain degradation",
            "contact_degradation": "contact-sensitive degradation explains retention",
            "ion_migration": "bias-history or ion-sensitive degradation explains retention",
            "encapsulation_process_artifact": "packaging/process covariate explains retention",
        },
        "expected_result_if_H": (
            "The claimed chemical/passivation degradation pathway is selectively suppressed "
            "while hydrophobicity, phase, contact, ion, and process alternatives are bounded."
        ),
        "expected_result_if_Alt": (
            "Barrier, phase, contact, ion-migration, initial-performance, or process "
            "artifacts explain the stability trend."
        ),
        "success_criterion_for_closing_gap": (
            "Close only if stability-linked readouts identify the dominant degradation "
            "pathway; initial PCE or FF improvement alone cannot close a stability gap."
        ),
        "non_closure_criteria": [
            "only initial device metrics improve",
            "stress protocol or encapsulation/process covariates differ",
            "barrier, phase, contact, and ion pathways remain unresolved",
        ],
        "failure_modes": [
            "Retention improves but initial-performance matching is absent.",
            "Multiple degradation pathways change together.",
        ],
        "interpretation_decision_tree": (
            "Update toward H when the claimed passivation/degradation pathway is selectively "
            "suppressed under matched controls; update toward Alt when barrier, phase, "
            "contact, ion, or process branches explain retention; otherwise keep "
            "mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Claimed chemical/passivation pathway is selectively stabilized with "
                    "bounded barrier, phase, contact, ion, and process alternatives."
                ),
                "interpretation": "Target stability pathway is favored.",
                "remaining_caveat": "Architecture-specific degradation still needs p-i-n transfer check.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Barrier, phase, contact, ion, initial-performance, or process branch "
                    "explains retention."
                ),
                "interpretation": "Alternative stability pathway is favored.",
                "remaining_caveat": "Chemical passivation may remain a secondary contributor.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Retention changes without pathway assignment.",
                "interpretation": "Stability mechanism remains unresolved.",
                "next_step": "Add pathway-specific comparator or initial-performance matched population.",
            },
        },
    }


def build_morphology_phase_causality_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for morphology, crystallinity, phase, orientation, and strain gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "MORPHOLOGY_PHASE_CAUSALITY_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Morphology, crystallinity, and phase-causality discrimination",
        "gap_type": "morphology / phase causality gap",
        "scientific_uncertainty": (
            "Whether morphology, crystallinity, phase purity, orientation, or strain is "
            "the causal device branch, or whether those observables are process covariates "
            "co-moving with passivation, optical absorption, or contact/interface effects."
        ),
        "hypothesis_H": (
            f"{modulator} changes morphology, crystallinity, phase state, orientation, or "
            "strain in a way that causally explains the affected claim under bounded "
            "passivation, optical, and contact alternatives."
        ),
        "alternative_Alt": (
            "The device trend is instead explained by passivation, processing artifacts, "
            "optical absorption/Jsc confounding, or contact/interface effects while "
            "morphology or phase is correlative."
        ),
        "discriminating_observation": (
            "Morphology/phase readouts track the affected claim after passivation, optical, "
            "processing, and contact/interface alternatives are bounded."
        ),
        "variables_to_vary": [
            "intervention versus matched no-intervention population",
            "morphology- or phase-shift comparator with bounded passivation where available",
            "optical/contact comparator when device metrics can co-vary",
        ],
        "controls": [
            "matched no-intervention baseline",
            "processing-control comparator for morphology/phase changes",
            "passivation-sensitive comparator",
            "optical absorption or Jsc confounder comparator",
            "contact/interface comparator",
        ],
        "primary_readouts": [
            {
                "name": "morphology/crystallinity/phase readout class",
                "maps_to_uncertainty": "morphology-caused device gain versus correlative morphology",
                "supports_H_pattern": "morphology or phase branch tracks the device claim under bounded alternatives",
                "supports_Alt_pattern": "morphology or phase readout is correlative or secondary",
            },
            {
                "name": "passivation-sensitive bounding class",
                "maps_to_uncertainty": "passivation causing device gain instead of morphology",
                "supports_H_pattern": "passivation readout remains secondary",
                "supports_Alt_pattern": "passivation readout explains the device trend",
            },
            {
                "name": "optical/contact confounder class",
                "maps_to_uncertainty": "optical absorption/Jsc or contact/interface effect",
                "supports_H_pattern": "optical and contact branches remain bounded",
                "supports_Alt_pattern": "optical or contact branch explains the trend",
            },
        ],
        "secondary_readouts": [
            "strain or orientation context where relevant",
            "p-i-n architecture-matched contact/interface context",
        ],
        "observable_to_mechanism_mapping": {
            "morphology_causing_device_gain": "morphology/phase readout tracks device gain",
            "passivation_causing_device_gain": "passivation readout explains device gain",
            "processing_artifact": "process comparator explains morphology and device shifts",
            "optical_absorption_confounder": "optical/Jsc branch explains the device metric",
            "contact_interface_effect": "contact/interface readout explains the trend",
        },
        "expected_result_if_H": (
            "Morphology, crystallinity, phase, orientation, or strain readouts track the "
            "affected claim while passivation, optical, process, and contact alternatives "
            "remain bounded."
        ),
        "expected_result_if_Alt": (
            "Passivation, processing, optical absorption, or contact/interface readouts "
            "explain the device trend better than morphology/phase causality."
        ),
        "success_criterion_for_closing_gap": (
            "Close only if morphology/phase causality is separated from passivation, "
            "processing, optical, and contact/interface alternatives."
        ),
        "non_closure_criteria": [
            "morphology or phase changes are only correlative",
            "processing artifact is not bounded",
            "optical or contact confounders remain open",
        ],
        "failure_modes": [
            "Morphology and passivation readouts co-vary.",
            "Optical absorption or contact changes explain the metric.",
        ],
        "interpretation_decision_tree": (
            "Update toward H when morphology/phase readouts remain decisive under bounded "
            "alternatives; update toward Alt when passivation, process, optical, or contact "
            "branches explain the claim; otherwise keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Morphology/phase branch tracks the affected claim with bounded "
                    "passivation, process, optical, and contact alternatives."
                ),
                "interpretation": "Morphology/phase causality is favored.",
                "remaining_caveat": "Translation to p-i-n may change contact/interface weighting.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Passivation, process artifact, optical absorption, or contact branch "
                    "explains the device trend."
                ),
                "interpretation": "A non-morphology alternative is favored.",
                "remaining_caveat": "Morphology may remain a secondary covariate.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Morphology/phase and alternative readouts co-vary.",
                "interpretation": "Causality remains unresolved.",
                "next_step": "Add a comparator that decouples morphology/phase from the strongest covariate.",
            },
        },
    }


def build_contact_energetics_interface_selectivity_template(
    context: dict[str, Any],
) -> dict[str, Any]:
    """Template for work-function, band-alignment, barrier, and selectivity gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "CONTACT_ENERGETICS_INTERFACE_SELECTIVITY_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Contact energetics and interface-selectivity discrimination",
        "gap_type": "contact energetics / interface selectivity gap",
        "scientific_uncertainty": (
            "Whether work-function, band-alignment, surface-potential, barrier, or "
            "interface-selectivity changes explain the affected claim, rather than "
            "recombination suppression, contact resistance, transport barriers, or "
            "architecture-specific interface effects."
        ),
        "hypothesis_H": (
            f"{modulator} improves contact energetics or interface selectivity at the "
            "relevant PSC interface in a way that explains the affected claim."
        ),
        "alternative_Alt": (
            "The observed trend is instead recombination suppression, transport barrier, "
            "contact-resistance change, or an architecture-specific interface effect that "
            "does not generalize."
        ),
        "discriminating_observation": (
            "Energetic/selectivity readouts separate true alignment improvement from "
            "recombination, resistance, barrier, and architecture-specific alternatives."
        ),
        "variables_to_vary": [
            "intervention versus matched no-intervention contact stack",
            "HTL-side versus ETL-side interface comparator where relevant",
            "architecture-matched p-i-n contact-selective comparator",
        ],
        "controls": [
            "matched no-intervention contact stack",
            "contact-selective comparator for HTL-side versus ETL-side effects",
            "recombination-sensitive comparator",
            "transport/contact resistance comparator",
        ],
        "primary_readouts": [
            {
                "name": "work-function / surface-potential / band-alignment readout class",
                "maps_to_uncertainty": "true energetic alignment improvement",
                "supports_H_pattern": "energetic shift is directionally consistent and device-relevant",
                "supports_Alt_pattern": "energetic shift is absent, inconsistent, or secondary",
            },
            {
                "name": "interface selectivity and extraction-barrier class",
                "maps_to_uncertainty": "selectivity improvement versus transport barrier",
                "supports_H_pattern": "selectivity improves without a dominant barrier",
                "supports_Alt_pattern": "barrier or selectivity loss explains the trend",
            },
            {
                "name": "contact resistance / recombination bounding class",
                "maps_to_uncertainty": "contact resistance or recombination alternative",
                "supports_H_pattern": "resistance and recombination alternatives remain bounded",
                "supports_Alt_pattern": "resistance or recombination explains the device trend",
            },
        ],
        "secondary_readouts": [
            "architecture-sensitive p-i-n interface readout",
            "same absorber-family device-population context",
        ],
        "observable_to_mechanism_mapping": {
            "energetic_alignment_improvement": "work-function/band-alignment shift is device-relevant",
            "recombination_suppression": "recombination readouts explain the trend",
            "transport_barrier": "barrier-sensitive readout explains the trend",
            "contact_resistance": "contact-resistance branch explains the trend",
            "architecture_specific_interface_effect": "effect depends on source contact stack",
        },
        "expected_result_if_H": (
            "Energetic/selectivity readouts explain the affected claim while recombination, "
            "resistance, barrier, and architecture-specific alternatives remain bounded."
        ),
        "expected_result_if_Alt": (
            "Recombination, contact resistance, transport barrier, or source-stack-specific "
            "interface behavior explains the claim."
        ),
        "success_criterion_for_closing_gap": (
            "Close only if contact energetics or interface selectivity is directly linked "
            "to the affected claim under bounded recombination, resistance, barrier, and "
            "architecture alternatives."
        ),
        "non_closure_criteria": [
            "only static energetic shift is observed without device relevance",
            "transport barrier or contact resistance remains open",
            "source-stack interface effect is used as p-i-n proof",
        ],
        "failure_modes": [
            "Energetic shift is measured but contact resistance dominates.",
            "p-i-n translation changes the interface of interest.",
        ],
        "interpretation_decision_tree": (
            "Update toward H when energetic/selectivity readouts explain the claim with "
            "bounded recombination/resistance/barrier alternatives; update toward Alt when "
            "those alternatives dominate or architecture transfer fails; otherwise keep "
            "mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Energetic/selectivity readouts are directionally consistent, "
                    "device-relevant, and alternatives are bounded."
                ),
                "interpretation": "Contact energetics/interface selectivity is favored.",
                "remaining_caveat": "Interface identity must be re-evaluated in p-i-n translation.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Recombination, contact resistance, barrier, or architecture-specific "
                    "interface behavior explains the trend."
                ),
                "interpretation": "Non-energetic or architecture-specific branch is favored.",
                "remaining_caveat": "A secondary alignment contribution may remain.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Energetic and alternative readouts conflict.",
                "interpretation": "Contact mechanism remains unresolved.",
                "next_step": "Add contact-selective p-i-n matched comparator.",
            },
        },
    }


def build_p_i_n_architecture_translation_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for architecture-portability gaps."""
    source_arch = str(context.get("solar_cell_structure", "source architecture"))
    return {
        "template_id": "P_I_N_ARCHITECTURE_TRANSLATION_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "p-i-n architecture translation and portability",
        "gap_type": "architecture-portability / p-i-n translation gap",
        "scientific_uncertainty": (
            "Whether a source-package mechanism remains valid when translated to the "
            "lab-preferred inverted p-i-n architecture without treating the source stack as "
            "p-i-n proof."
        ),
        "hypothesis_H": (
            f"The source mechanism from {source_arch} is portable to inverted p-i-n after "
            "the interface of interest, contact-selective extraction, and loss/readout "
            "mapping are re-evaluated."
        ),
        "alternative_Alt": (
            "The source mechanism is architecture-specific: contact stack, interface identity, "
            "barrier/selectivity, or loss-channel ranking changes in inverted p-i-n."
        ),
        "discriminating_observation": (
            "Architecture-matched p-i-n readouts reproduce the mechanism-local branch while "
            "source-stack contact/extraction claims remain provenance only."
        ),
        "variables_to_vary": [
            "source-context mechanism claim versus p-i-n translation context",
            "p-i-n baseline versus p-i-n intervention comparison",
            "contact-selective p-i-n interface comparator",
        ],
        "controls": [
            "p-i-n baseline without intervention",
            "p-i-n intervention comparison with matched absorber family",
            "contact-selective comparator for HTL-side versus ETL-side effects",
            "source architecture reference only as provenance, not as p-i-n proof",
        ],
        "primary_readouts": [
            {
                "name": "architecture-matched p-i-n mechanism readout class",
                "maps_to_uncertainty": "mechanism portability versus source-stack specificity",
                "supports_H_pattern": "p-i-n readout supports the same local mechanism branch",
                "supports_Alt_pattern": "p-i-n readout redirects to contact or architecture-specific branch",
            },
            {
                "name": "p-i-n contact-selective extraction or barrier class",
                "maps_to_uncertainty": "contact-stack transfer assumption",
                "supports_H_pattern": "contact-selective branch is bounded in p-i-n",
                "supports_Alt_pattern": "p-i-n contact/barrier branch dominates",
            },
        ],
        "secondary_readouts": [
            "p-i-n recombination/trap-sensitive context",
            "p-i-n hysteresis/bias-history context when relevant",
        ],
        "observable_to_mechanism_mapping": {
            "architecture_transfer_assumption": "local mechanism survives contact-stack translation",
            "p_i_n_interface_of_interest": "HTL-side or ETL-side branch is reinterpreted for p-i-n",
            "source_stack_specificity": "source contact/extraction behavior does not port",
            "p_i_n_non_closure": "source result alone cannot close p-i-n mechanism",
        },
        "expected_result_if_H": (
            "p-i-n matched controls reproduce the mechanism-local readout while contact, "
            "barrier, and architecture-specific alternatives remain bounded."
        ),
        "expected_result_if_Alt": (
            "p-i-n matched readouts show that contact stack, interface identity, or "
            "loss/readout mapping changes the mechanism interpretation."
        ),
        "success_criterion_for_closing_gap": (
            "Close only for the p-i-n translation claim when architecture-matched p-i-n "
            "readouts support the mechanism; source-package results alone cannot close it."
        ),
        "non_closure_criteria": [
            "source n-i-p result is treated as p-i-n proof",
            "p-i-n interface of interest is not specified",
            "contact-selective extraction or barrier alternatives remain open",
        ],
        "p_i_n_closure_rule": (
            "p-i-n closure requires architecture-matched p-i-n controls and readouts."
        ),
        "p_i_n_non_closure_rule": (
            "Source-stack evidence alone is provenance and cannot close the p-i-n mechanism."
        ),
        "failure_modes": [
            "Architecture-specific contact mechanism does not port.",
            "p-i-n baseline ceiling effect masks the translated mechanism.",
        ],
        "interpretation_decision_tree": (
            "Update toward H when p-i-n controls reproduce the mechanism-local branch; "
            "update toward Alt when contact stack or interface identity changes the branch; "
            "otherwise keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Architecture-matched p-i-n readouts support the same local mechanism "
                    "with bounded contact alternatives."
                ),
                "interpretation": "p-i-n portability is favored for the translated claim.",
                "remaining_caveat": "This is lab translation, not source-paper proof.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "p-i-n contact stack or interface identity changes the mechanism branch."
                ),
                "interpretation": "Architecture-specific alternative is favored.",
                "remaining_caveat": "Source-paper mechanism may remain valid in its own stack.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "p-i-n matched readouts are absent or conflicting.",
                "interpretation": "Architecture portability remains unresolved.",
                "next_step": "Add p-i-n matched control/readout set before mechanism update.",
            },
        },
    }


def build_device_model_link_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for trap/recombination-to-device-model gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "MODEL_MAPPING_QUANTIFICATION_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "Trap/recombination-to-device-model mapping",
        "gap_type": "device-model link gap",
        "scientific_uncertainty": (
            "Whether measured trap or recombination reductions quantitatively account "
            "for the affected device metric once transport/contact losses are bounded."
        ),
        "hypothesis_H": (
            f"Measured trap/recombination reductions from {modulator} quantitatively "
            "account for the device-performance improvement under bounded transport "
            "and contact losses."
        ),
        "alternative_Alt": (
            "The measured trap/recombination changes are insufficient to explain the "
            "device improvement, and contact, resistance, or barrier terms dominate."
        ),
        "discriminating_observation": (
            "A device-model mapping reproduces the observed metric change from "
            "trap/recombination inputs without requiring dominant contact, resistance, "
            "or barrier terms."
        ),
        "model_inputs": [
            "trap/recombination-sensitive proxies",
            "Voc/Jsc/FF/PCE population data",
            "photovoltaic loss-channel terms",
            "contact/resistance bounds",
        ],
        "model_outputs": [
            "predicted device-metric change",
            "residual unexplained performance loss",
            "sensitivity of the metric to recombination versus transport/contact terms",
        ],
        "variables_to_vary": [
            "matched intervention versus no-intervention population",
            "bounded contact/resistance comparison",
            "trap/recombination proxy population",
        ],
        "controls": [
            "matched no-intervention baseline",
            "contact/resistance-bound comparator",
            "same absorber-family population for model input consistency",
        ],
        "primary_readouts": [
            {
                "name": "trap/recombination-sensitive proxy class",
                "maps_to_uncertainty": "measured trap/recombination change versus model-required change",
                "supports_H_pattern": "measured proxy magnitude is sufficient in the device model",
                "supports_Alt_pattern": "proxy magnitude is too small or poorly coupled to the device metric",
            },
            {
                "name": "population device-metric input class",
                "maps_to_uncertainty": "observed metric distribution for model fitting",
                "supports_H_pattern": "model predicts the paired population shift with bounded residual",
                "supports_Alt_pattern": "model residual remains large without contact/resistance terms",
            },
            {
                "name": "contact/resistance bound class",
                "maps_to_uncertainty": "transport/contact dominance versus recombination-driven model",
                "supports_H_pattern": "contact/resistance terms remain bounded",
                "supports_Alt_pattern": "contact/resistance terms dominate model sensitivity",
            },
        ],
        "secondary_readouts": [
            "architecture-matched p-i-n model check",
            "sensitivity analysis separating recombination and transport/contact terms",
        ],
        "observable_to_mechanism_mapping": {
            "qualitative_proxy": "proxy direction supports a mechanism but not quantitative closure",
            "quantitative_mechanism_mapping": (
                "measured proxy magnitude predicts the affected device metric within bounds"
            ),
            "model_underdetermination": "multiple parameter sets reproduce the observation",
            "alternative_channel_still_open": "contact/resistance/barrier terms remain necessary",
        },
        "expected_result_if_H": (
            "The model reproduces the observed device-metric gain from measured "
            "trap/recombination changes without invoking dominant contact or resistance terms."
        ),
        "expected_result_if_Alt": (
            "The model cannot reproduce the gain without contact, resistance, or barrier "
            "terms, so trap/recombination support remains qualitative."
        ),
        "success_criterion_for_closing_gap": (
            "Resolve toward the model link only if measured trap/recombination inputs "
            "quantitatively account for the device-metric change under bounded "
            "transport/contact losses."
        ),
        "non_closure_criteria": [
            "model reproduces the metric only with contact/resistance/barrier terms",
            "proxy magnitude is qualitative or underdetermined",
            "sensitivity analysis cannot separate recombination from transport/contact terms",
        ],
        "falsification_criterion": (
            "If the model cannot reproduce the device-metric gain without invoking "
            "contact, resistance, or barrier terms, do not strengthen the "
            "trap/recombination-to-device claim."
        ),
        "failure_modes": [
            "Model sensitivity is dominated by contact/resistance terms.",
            "Trap/recombination proxy magnitude is insufficient for the observed metric shift.",
        ],
        "interpretation_decision_tree": (
            "If the model predicts the device-metric shift from measured trap/recombination "
            "inputs with bounded contact terms, update toward H; if contact/resistance "
            "terms dominate sensitivity, update toward Alt; otherwise keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Measured trap/recombination inputs reproduce the device-metric shift "
                    "with bounded contact/resistance sensitivity."
                ),
                "interpretation": "Quantitative trap/recombination-to-device link is favored.",
                "remaining_caveat": "Model structure and p-i-n transfer assumptions remain auditable limits.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Contact, resistance, or barrier terms dominate model sensitivity or "
                    "are required to reproduce the metric shift."
                ),
                "interpretation": "Transport/contact dominated model explanation is favored.",
                "remaining_caveat": "Trap/recombination changes may remain secondary.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Model inputs are insufficient or sensitivities are non-identifiable.",
                "interpretation": "Device-model link remains unresolved.",
                "next_step": "Add a bounded contact/resistance input or stronger trap/recombination proxy.",
            },
        },
    }


def build_unresolved_generic_template(gap: Gap) -> dict[str, Any]:
    """Fallback that is explicit about unresolved template status."""
    return {
        "template_id": "GENERIC_GAP_TEMPLATE",
        "template_resolution_status": "unresolved_generic_fallback",
        "gap_type_specific_title": "Unresolved generic H-vs-Alt planning card",
        "gap_type": gap.gap_type,
        "scientific_uncertainty": (
            "The gap did not map to a supported domain template, so the mechanism "
            "assignment remains low-confidence until a concrete readout class is chosen."
        ),
        "hypothesis_H": gap.hypothesis,
        "alternative_Alt": gap.alternative,
        "discriminating_observation": (
            "A domain-specific readout has not been resolved; this card remains a "
            "flag for follow-up template selection."
        ),
        "variables_to_vary": [
            "source-package intervention axis",
            "explicitly named competing mechanism axis",
        ],
        "controls": ["source-package matched baseline", "named alternative-mechanism comparator"],
        "primary_readouts": [
            {
                "name": "unresolved readout selection needed",
                "maps_to_uncertainty": "template fallback cannot assign a mechanism-specific readout",
                "supports_H_pattern": "requires manual selection of a concrete readout class",
                "supports_Alt_pattern": "requires manual selection of an alternative-specific readout",
            }
        ],
        "secondary_readouts": ["package-local evidence audit", "LKM mechanism-chain audit"],
        "expected_result_if_H": (
            "A future domain template names an H-specific readout and it supports the "
            "package-local mechanism while bounding the named alternative."
        ),
        "expected_result_if_Alt": (
            "A future domain template names an alternative-specific readout and it "
            "explains the affected claim."
        ),
        "success_criterion_for_closing_gap": (
            "Do not resolve this card as mechanism-supported until a domain-specific "
            "template supplies concrete readouts and controls."
        ),
        "failure_modes": [
            "Template remains unresolved and confidence stays low.",
            "No concrete readout can distinguish the named H/Alt branches.",
        ],
        "interpretation_decision_tree": (
            "Keep mixed_or_unresolved until a supported domain template supplies "
            "readouts, controls, and branch-specific decision rules."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": "No supported H pattern is assigned by the fallback.",
                "interpretation": "No mechanism update is made from this fallback alone.",
                "remaining_caveat": "Requires domain-template resolution.",
            },
            "supports_Alt": {
                "observation_pattern": "No supported Alt pattern is assigned by the fallback.",
                "interpretation": "No alternative update is made from this fallback alone.",
                "remaining_caveat": "Requires domain-template resolution.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "The gap lacks a resolved domain template.",
                "interpretation": "The card remains a low-confidence planning placeholder.",
                "next_step": "Classify the gap into a supported experimental family or add a new module.",
            },
        },
        "recommended_experiment_class": "Unresolved template-selection task",
        "open_questions": ["Which supported domain template should own this gap?"],
    }


def build_device_translation_policy(context: dict[str, Any]) -> dict[str, Any]:
    """Build p-i-n translation fields without overwriting source context."""
    source_architecture = normalize_architecture(context.get("solar_cell_structure", ""))
    lab_preference = str(context.get("lab_preferred_device_architecture", "inverted p-i-n"))
    source_is_pin = source_architecture == "p-i-n"
    source_claim = context.get("target_claim") or context.get("target_claims") or "source claim"
    p_i_n_interface = (
        "HTL-side or ETL-side interface selected by the translated mechanism, not copied "
        "blindly from the source stack"
    )
    if source_is_pin:
        lab_translation_context = {
            "lab_preferred_device_architecture": lab_preference,
            "translation_status": "source_already_p_i_n",
            "translation_note": (
                "Source package is already p-i-n aligned; use p-i-n matched controls "
                "and readouts while preserving the locked stack context."
            ),
            "translation_targets": [
                "strengthen architecture-matched p-i-n controls",
                "keep absorber/passivator mechanism local to the source stack",
                "separate passivation-local effects from p-i-n contact-selective effects",
            ],
        }
        controls = [
            "matched p-i-n baseline without intervention",
            "p-i-n intervention comparison with matched absorber family",
            "p-i-n same-stack comparator for contact-selective effects",
        ]
        risks = [
            "p-i-n source context is preserved, but contact-stack interpretation remains stack-specific."
        ]
        what_not = [
            "Do not generalize beyond the locked p-i-n contact stack without matched controls."
        ]
        p_i_n_adaptation_design = {
            "source_claim_to_translate": source_claim,
            "architecture_transfer_assumptions": [
                "source context already uses p-i-n architecture",
                "mechanism still needs matched p-i-n controls rather than cross-stack extrapolation",
            ],
            "p_i_n_interface_of_interest": p_i_n_interface,
            "p_i_n_specific_alt_branches": [
                "p-i-n contact selectivity change",
                "p-i-n contact resistance or barrier branch",
                "high-performance baseline ceiling effect",
            ],
            "high_performance_baseline_ceiling_effect": (
                "High-performing p-i-n baselines may compress observable device-metric deltas; "
                "mechanism readouts must remain discriminating."
            ),
            "p_i_n_specific_controls": controls,
            "p_i_n_specific_readouts": [
                "architecture-matched mechanism readout for the selected card archetype",
                "contact-selective extraction or barrier diagnostic class",
                "recombination/trap-sensitive readout in p-i-n stack",
            ],
            "p_i_n_closure_rule": (
                "Close the p-i-n claim only with source-matched p-i-n controls and direct "
                "H-vs-Alt readouts."
            ),
            "p_i_n_non_closure_rule": (
                "Do not close p-i-n mechanism when only aggregate device metrics or "
                "off-architecture analogies support the claim."
            ),
            "what_not_to_generalize": what_not,
        }
    else:
        lab_translation_context = {
            "lab_preferred_device_architecture": lab_preference,
            "translation_status": "source_context_preserved_with_p_i_n_translation",
            "translation_note": (
                "Source package context is preserved; inverted p-i-n is a lab translation "
                "target, not source-paper proof."
            ),
            "translation_targets": [
                "preserve absorber/passivator chemical mechanism if it is local to perovskite surface/GB",
                "re-evaluate contact-selective extraction because n-i-p contact stacks do not map directly",
                "separate passivation-local effects from architecture-specific contact effects",
            ],
        }
        controls = [
            "matched p-i-n baseline without intervention",
            "p-i-n intervention comparison with matched absorber family",
            "contact-selective comparator for HTL-side versus ETL-side effects",
            "source n-i-p reference only as provenance, not as p-i-n proof",
        ]
        risks = [
            "portability risk: source-stack contact mechanism may not port directly",
            "portability risk: passivation effect may survive while extraction/contact contribution changes",
            "portability risk: device-metric loss-channel ranking may differ between n-i-p and p-i-n",
        ]
        what_not = [
            "do not generalize source n-i-p contact/extraction mechanism as p-i-n proof",
            "do not treat p-i-n translation as source-paper evidence",
        ]
        p_i_n_adaptation_design = {
            "source_claim_to_translate": source_claim,
            "architecture_transfer_assumptions": [
                "local absorber/passivator chemistry may port if it is local to the perovskite surface or grain boundary",
                "n-i-p contact extraction and barrier interpretation must be re-evaluated in p-i-n",
                "source n-i-p result cannot close p-i-n mechanism without p-i-n matched readouts",
            ],
            "p_i_n_interface_of_interest": p_i_n_interface,
            "p_i_n_specific_alt_branches": [
                "HTL-side versus ETL-side contact-selective effect",
                "p-i-n contact resistance or barrier branch",
                "architecture-specific extraction branch",
                "high-performance baseline ceiling effect",
            ],
            "high_performance_baseline_ceiling_effect": (
                "Existing high-efficiency p-i-n baselines can reduce metric headroom; "
                "mechanism readouts and controls should not rely on large aggregate gains."
            ),
            "p_i_n_specific_controls": controls,
            "p_i_n_specific_readouts": [
                "architecture-matched mechanism readout for the selected card archetype",
                "contact-selective extraction or barrier diagnostic class",
                "recombination/trap-sensitive readout in p-i-n stack",
                "hysteresis/bias-history readout if relevant to the selected archetype",
            ],
            "p_i_n_closure_rule": (
                "Close p-i-n translation only when inverted p-i-n matched controls and "
                "readouts support the mechanism; source n-i-p evidence is provenance only."
            ),
            "p_i_n_non_closure_rule": (
                "Source n-i-p results, cross-package analogies, or SQLite precedents alone "
                "cannot close the p-i-n mechanism."
            ),
            "what_not_to_generalize": what_not,
        }
    readouts = [
        "architecture-matched mechanism readout for the selected card archetype",
        "contact-selective extraction or barrier diagnostic class",
        "recombination/trap-sensitive readout in p-i-n stack",
        "hysteresis/bias-history readout if relevant",
    ]
    return {
        "lab_translation_context": lab_translation_context,
        "p_i_n_adaptation_design": p_i_n_adaptation_design,
        "p_i_n_specific_controls": controls,
        "p_i_n_specific_readouts": readouts,
        "p_i_n_specific_risks": risks,
        "what_not_to_generalize": what_not,
    }


def merge_lists(*values: Any) -> list[Any]:
    """Merge list-like values while preserving order and string identity."""
    merged: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if is_blank(value):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            key = (
                json.dumps(item, sort_keys=True, ensure_ascii=False)
                if isinstance(item, dict)
                else str(item)
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def as_list(value: Any, *, default: str) -> list[Any]:
    """Return a non-empty list from context values."""
    if is_blank(value):
        return [default]
    if isinstance(value, list):
        return value
    return [value]


def score_priority(
    classifier: GapClassifierOutput, context: dict[str, Any], lkm: LkmSummary, *, sqlite_weak: bool
) -> int:
    """Score card priority by gap family and evidence-source support."""
    base, lower, upper = ARCHETYPE_PRIORITY_RANGES.get(
        classifier.card_archetype, ARCHETYPE_PRIORITY_RANGES["generic_uncertainty"]
    )
    score = base
    affected_text = " ".join(
        stringify(item)
        for item in as_list(
            context.get("affected_conclusions", context.get("affected_conclusion")),
            default="",
        )
    ).lower()
    if "main" in affected_text or "main_answer" in affected_text:
        score += 2
    if lkm.same_package_chains:
        score += 2
    elif lkm.cross_package_chains:
        score += 1
    if normalize_architecture(context.get("solar_cell_structure", "")) == "p-i-n":
        score += 1
    if sqlite_weak:
        score -= 1
    if classifier.direct_readout_available == "not_resolved":
        score -= 2
    if classifier.card_archetype == "generic_uncertainty":
        score = min(score, 70)
    return max(lower, min(score, upper))


def build_priority_rationale(
    classifier: GapClassifierOutput,
    priority: int,
    context: dict[str, Any],
    lkm: LkmSummary,
    *,
    sqlite_weak: bool,
) -> str:
    """Return a concrete rationale for priority ranking."""
    family_reasons = {
        "ff_loss_budget": "directly decomposes the photovoltaic metric branch that can otherwise masquerade as mechanism support",
        "functional_analog_causal_isolation": "tests whether a multifunctional intervention has a causal contribution after covariates are bounded",
        "recombination_loss_mapping": "maps recombination or trap proxies to a device-relevant mechanism branch while bounding proxy-only risk",
        "model_mapping_quantification": "checks whether mechanism proxies quantitatively support the device-level conclusion",
        "charge_extraction_collection": "tests carrier-collection timing as a separable branch from recombination, optical, morphology, and contact alternatives",
        "ion_migration_hysteresis": "assigns hysteresis-linked loss toward ion/charge accumulation or contact/protocol alternatives",
        "stability_degradation_pathway": "assigns a stability trend to a degradation pathway instead of initial metric improvement",
        "morphology_phase_causality": "tests morphology or phase causality against passivation, process, optical, and contact alternatives",
        "contact_energetics_interface_selectivity": "tests energetic/selectivity claims against recombination, barrier, resistance, and architecture alternatives",
        "p_i_n_architecture_translation": "tests whether the source mechanism can be translated to the lab p-i-n context without overwriting source facts",
        "generic_uncertainty": "lacks a resolved domain template and is capped until a concrete module owns it",
    }
    lkm_reason = (
        "same-package LKM chains increase mechanism relevance"
        if lkm.same_package_chains
        else "cross-package LKM is analogy only"
        if lkm.cross_package_chains
        else "LKM support is unavailable or scope-unknown"
    )
    sqlite_reason = (
        "SQLite precedent quality is weak and does not raise mechanism confidence"
        if sqlite_weak
        else "SQLite supplies only background comparability"
    )
    source_arch = stringify(context.get("solar_cell_structure", "unknown architecture"))
    return (
        f"Priority {priority}: this {classifier.card_archetype} card "
        f"{family_reasons[classifier.card_archetype]}; "
        f"{lkm_reason}; {sqlite_reason}; source architecture is {source_arch} with "
        "inverted p-i-n translation considered separately."
    )


def determine_card_confidence(
    classifier: GapClassifierOutput, lkm: LkmSummary, *, sqlite_weak: bool
) -> str:
    """Set mechanism confidence without letting SQLite raise attribution strength."""
    if classifier.card_archetype == "generic_uncertainty":
        return "low"
    if "lkm_unavailable" in " ".join(lkm.queries_run).lower():
        return "low"
    if lkm.same_package_chains:
        return "moderate" if not sqlite_weak else "low"
    if lkm.cross_package_chains:
        return "moderate"
    if lkm.unknown_package_chains:
        return "low"
    return "low"


def build_mechanism_limitations(
    classifier: GapClassifierOutput, lkm: LkmSummary, *, sqlite_weak: bool
) -> str:
    """Explain the limits on mechanism attribution for the card."""
    parts = [
        "Mechanism attribution requires the declared H-vs-Alt readouts; SQLite precedent "
        "or paired deltas cannot close the mechanism gap."
    ]
    if lkm.cross_package_chains:
        parts.append("Cross-package LKM chains are transfer analogies, not source-paper proof.")
    if lkm.unknown_package_chains:
        parts.append(
            "Ambiguous-scope LKM chains are retained for audit but do not raise proof status."
        )
    if sqlite_weak:
        parts.append("SQLite precedent quality is weak for this gap.")
    if classifier.card_archetype == "generic_uncertainty":
        parts.append("The unresolved generic fallback cannot support a mechanism update.")
    return " ".join(parts)


def summarize_lkm_scope_counts(lkm: LkmSummary) -> dict[str, int]:
    """Return compact LKM scope counts for Markdown/YAML display."""
    return {
        "same_package": len(lkm.same_package_chains),
        "cross_package": len(lkm.cross_package_chains),
        "ambiguous_package_scope": len(lkm.unknown_package_chains),
    }


def build_gap_resolution_strategy(gap: Gap) -> dict[str, Any]:
    """Build the generic resolution strategy for one gap."""
    return {
        "strategy_type": "generic H-vs-Alt causal-discrimination strategy",
        "uncertainty_to_resolve": gap.text,
        "decomposition_axes": [
            "target mechanism axis",
            "competing alternative axis",
            "architecture or stack portability axis",
            "measurement artifact or covariate axis",
        ],
        "confounders_to_bound": [
            "device architecture",
            "composition or absorber family",
            "intervention location",
            "measurement history",
        ],
        "decision_rules": [
            "support_H only when direct readouts distinguish H from Alt",
            "support_Alt when alternative-specific readouts explain the observation",
            "mixed_or_unresolved when axes conflict or controls are insufficient",
        ],
        "extension_hooks": [
            "domain modules can add metric-specific, stability, ion-migration, "
            "energetic, or morphology axes"
        ],
    }


def build_causal_isolation_controls(gap: Gap) -> dict[str, Any]:
    """Return functional analog-control logic when causal isolation is required."""
    text = f"{gap.text} {gap.gap_type}".lower()
    markers = (
        "sole cause attribution",
        "passivation not isolated",
        "morphology/contact alternative",
        "hydrophobicity alternative",
        "multifunctional",
        "causal attribution",
        "causal isolation",
        "causal-isolation",
    )
    if not any(marker in text for marker in markers):
        return {}
    return {
        "analog_control_class": "design-level functional analog comparator class",
        "bounded_covariates": [
            "morphology",
            "crystallinity",
            "hydrophobicity",
            "contact energetics",
            "recombination/trap-sensitive readouts",
        ],
        "limitation": (
            "If an analog also changes multiple variables, it cannot close the "
            "causal gap and only supports follow-up narrowing."
        ),
    }


def render_plan(cards: list[dict[str, Any]]) -> str:
    """Render a Markdown experiment roadmap with scientific card detail."""
    ranked_cards = sorted(cards, key=lambda card: int(card.get("priority", 0)), reverse=True)
    lines = [
        "# Experiment Plan",
        "",
        "SQLite is for precedent discovery, stack/intervention matching, and paired "
        "delta background only; it is not mechanism proof.",
        "",
        "## Ranked Roadmap",
    ]
    for card in ranked_cards:
        lines.extend(
            [
                "",
                (
                    f"### [{card['priority']}] {card['gap_id']}: "
                    f"{card.get('gap_type_specific_title', card['gap_type'])}"
                ),
                "",
                f"- Source package: {card['source_package']}",
                (f"- Family/archetype: {card.get('gap_family')} / {card.get('card_archetype')}"),
                f"- Template: {card.get('template_id')} ({card.get('template_resolution_status')})",
                f"- Hypothesis H: {card['hypothesis_H']}",
                f"- Alternative Alt: {card['alternative_Alt']}",
                f"- Discriminating observation: {card['discriminating_observation']}",
                "- Primary readout classes: "
                + "; ".join(readout_names(card.get("primary_readouts", []))),
                f"- p-i-n translation note: {translation_note(card)}",
                (
                    f"- SQLite role: {card['sqlite_role']} "
                    f"(quality: {card.get('sqlite_precedent_quality')}, "
                    f"warning: {card.get('sqlite_quality_warning')})"
                ),
                f"- LKM scope summary: {format_lkm_scope_summary(card)}",
                f"- Confidence: {card['confidence']}",
                f"- Mechanism limitation: {card['mechanism_attribution_limitations']}",
            ]
        )
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "This is a design-level planning artifact, not an operational synthesis "
            "or device-fabrication protocol.",
        ]
    )
    return "\n".join(lines) + "\n"


def readout_names(readouts: Any) -> list[str]:
    """Return display names for readout entries."""
    if not isinstance(readouts, list):
        return []
    names: list[str] = []
    for readout in readouts:
        if isinstance(readout, dict):
            name = stringify(readout.get("name")).strip()
        else:
            name = stringify(readout).strip()
        if name:
            names.append(name)
    return names


def translation_note(card: dict[str, Any]) -> str:
    """Return the p-i-n translation note for Markdown."""
    context = card.get("lab_translation_context")
    if isinstance(context, dict):
        return stringify(context.get("translation_note"))
    return "No lab translation context recorded."


def format_lkm_scope_summary(card: dict[str, Any]) -> str:
    """Format same/cross/unknown LKM scope counts."""
    summary = card.get("lkm_scope_summary")
    if not isinstance(summary, dict):
        summary = {
            "same_package": len(card.get("same_package_lkm_chains") or []),
            "cross_package": len(card.get("cross_package_lkm_chains") or []),
            "ambiguous_package_scope": len(card.get("ambiguous_lkm_chains") or []),
        }
    return (
        f"same={summary.get('same_package', 0)}, "
        f"cross={summary.get('cross_package', 0)}, "
        f"ambiguous={summary.get('ambiguous_package_scope', 0)}"
    )


def build_retrieval_evidence(
    gap: Gap,
    context: dict[str, Any],
    sqlite_retrieval: RetrievalSummary,
    lkm: LkmSummary,
) -> dict[str, Any]:
    """Combine SQLite and LKM diagnostics for one gap."""
    evidence = dict(sqlite_retrieval.retrieval_evidence)
    evidence["gap_id"] = gap.gap_id
    evidence["successful_endpoints"] = list(
        dict.fromkeys(evidence.get("successful_endpoints", []) + lkm.successful_endpoints)
    )
    evidence["failed_endpoints"] = list(
        dict.fromkeys(evidence.get("failed_endpoints", []) + lkm.failed_endpoints)
    )
    evidence["same_package_lkm_chains"] = lkm.same_package_chains
    evidence["cross_package_lkm_chains"] = lkm.cross_package_chains
    evidence["ambiguous_lkm_chains"] = lkm.unknown_package_chains
    evidence["unknown_package_lkm_chains"] = lkm.unknown_package_chains
    evidence["sqlite_lkm_conflicts"] = lkm.sqlite_lkm_conflicts

    parse_coverage = sqlite_retrieval.database_precedents.get("parse_coverage")
    if isinstance(parse_coverage, dict):
        evidence["sqlite_parse_coverage"] = parse_coverage
        if sqlite_retrieval.database_precedents.get("sqlite_quality_warning"):
            evidence["parse_coverage_warning"] = True
            evidence["parse_coverage_warning_reason"] = (
                "SQLite parse coverage or precedent quality warning is active; "
                "precedent deltas cannot carry mechanism confidence."
            )
    evidence["sqlite_precedent_quality"] = sqlite_retrieval.database_precedents.get(
        "sqlite_precedent_quality", "unusable"
    )
    evidence["sqlite_quality_warning"] = sqlite_retrieval.database_precedents.get(
        "sqlite_quality_warning", True
    )
    evidence["demoted_precedent_rows"] = sqlite_retrieval.database_precedents.get(
        "demoted_precedent_rows", []
    )
    evidence["rejected_precedent_rows_summary"] = sqlite_retrieval.database_precedents.get(
        "rejected_precedent_rows_summary", {}
    )

    source_architecture = str(context.get("solar_cell_structure", "")).lower()
    lab_architecture = str(
        context.get("lab_preferred_device_architecture", "inverted p-i-n")
    ).lower()
    if source_architecture and lab_architecture and source_architecture not in lab_architecture:
        evidence["architecture_translation_warning"] = (
            f"Source architecture `{context.get('solar_cell_structure')}` is preserved; "
            "lab translation target is "
            f"`{context.get('lab_preferred_device_architecture', 'inverted p-i-n')}`."
        )
    return evidence


def parse_coverage_is_low(parse_coverage: dict[str, Any]) -> bool:
    """Return true when any parse-coverage value is below 50%."""
    for value in parse_coverage.values():
        ratio = parse_coverage_ratio(value)
        if ratio is not None and ratio < 0.5:
            return True
    return False


def parse_coverage_ratio(value: Any) -> float | None:
    """Parse coverage values like ``2/5`` into a ratio."""
    if not isinstance(value, str) or "/" not in value:
        return None
    numerator, denominator = value.split("/", 1)
    try:
        parsed = float(numerator)
        total = float(denominator)
    except ValueError:
        return None
    if total <= 0:
        return None
    return parsed / total


def write_yaml(path: Path, payload: Any) -> None:
    """Write YAML with stable key ordering disabled."""
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    """Write JSON with stable indentation."""
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, nargs="?", default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--context", type=Path, default=None)
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--allow-missing-sqlite",
        action="store_true",
        help="Trial mode only: emit low-confidence cards when SQLite is unavailable.",
    )
    parser.add_argument(
        "--skip-lkm",
        action="store_true",
        help="Skip live LKM retrieval and emit lkm_unavailable diagnostics.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Generate experiment-plan artifacts."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    package = args.package.resolve()
    output_dir = (args.output_dir or package).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis_path = package / "ANALYSIS.md"
    if not analysis_path.exists():
        write_preflight(output_dir, ["ANALYSIS.md"], [str(analysis_path)])
        return 2

    context_path = args.context or package / "experiment_context.yaml"
    context = load_yaml_mapping(context_path)
    context = augment_context_with_source_identifiers(package, context)
    package_mode = package_mode_from_context(context)
    missing = check_context(context)
    if missing:
        write_preflight(output_dir, missing, [str(analysis_path), str(context_path)])
        return 2

    if not args.sqlite_db.exists() and not args.allow_missing_sqlite:
        write_preflight(
            output_dir,
            ["sqlite_database"],
            [str(analysis_path), str(context_path), str(args.sqlite_db)],
        )
        return 2

    gaps = extract_gaps(analysis_path.read_text(encoding="utf-8"))
    if not gaps:
        write_preflight(output_dir, ["experimental_gap"], [str(analysis_path)])
        return 2

    dotenv_paths = [
        package / ".env",
        output_dir / ".env",
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]
    lkm_credential = resolve_lkm_access_key(dotenv_paths)
    preflight_summary = {
        "strict_preflight_passed": True,
        "package": str(package),
        "package_mode": package_mode,
        "inputs_read": [str(analysis_path), str(context_path)],
        "context_missing_preflight_generated": False,
        "sqlite_available": args.sqlite_db.exists(),
        "lkm_credential_loaded": bool(lkm_credential.access_key) and not args.skip_lkm,
        "lab_preferred_device_architecture": context.get(
            "lab_preferred_device_architecture", "inverted p-i-n"
        ),
    }
    retrievals = [retrieve_sqlite(gap, context, args.sqlite_db) for gap in gaps]
    lkm_summaries = [
        retrieve_lkm(
            gap,
            context,
            output_dir,
            live=not args.skip_lkm,
            dotenv_paths=dotenv_paths,
        )
        for gap in gaps
    ]
    cards = [
        build_card(gap, context, retrieval, lkm)
        for gap, retrieval, lkm in zip(gaps, retrievals, lkm_summaries, strict=True)
    ]
    retrieval_evidence = {
        "preflight": preflight_summary,
        "gaps": [
            build_retrieval_evidence(gap, context, retrieval, lkm)
            for gap, retrieval, lkm in zip(gaps, retrievals, lkm_summaries, strict=True)
        ],
    }

    write_yaml(output_dir / "experiments.yaml", {"experiments": cards})
    write_yaml(output_dir / "retrieval_evidence.yaml", retrieval_evidence)
    (output_dir / "EXPERIMENT_PLAN.md").write_text(render_plan(cards), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
