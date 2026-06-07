"""Tests for ``scripts/validate_experiment_cards.py``."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validate_experiment_cards.py"


def _load_validator() -> ModuleType:
    """Import ``scripts/validate_experiment_cards.py`` as a module for testing."""
    spec = importlib.util.spec_from_file_location("validate_experiment_cards", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_validator()


def _valid_card() -> dict[str, object]:
    """Return a complete real-package experiment card."""
    return {
        "gap_id": "experimental_gap_01_interface_mechanism",
        "package_mode": "single_paper",
        "source_package": "fa_cs_interface_gaia",
        "target_claims": ["fa_cs_interface::weak_interface_claim"],
        "affected_conclusions": ["fa_cs_interface::main_conclusion"],
        "current_belief": 0.42,
        "original_evidence_gap_text": (
            "Evidence Gap: passivation attribution is not isolated from "
            "morphology or contact alternatives."
        ),
        "gap_type": "multifunctional additive causal-isolation gap",
        "gap_classifier_output": {
            "dominant_observable": "functional analog response and bounded covariates",
            "mechanism_axes": [
                "dopant_additive_chemical_interaction",
                "recombination_defect_passivation",
                "morphology_crystallinity_phase",
            ],
            "primary_mechanism_axis": "dopant_additive_chemical_interaction",
            "secondary_mechanism_axes": [
                "recombination_defect_passivation",
                "morphology_crystallinity_phase",
            ],
            "alternative_class": "multifunctional covariate alternative",
            "architecture_sensitivity": "architecture_sensitive",
            "evidence_gap_kind": "causal_isolation_gap",
            "source_claim_type": "mechanism_claim",
            "device_metric_relevance": "mechanism_specific_metric_context_required",
            "direct_readout_available": "archetype_specific_readout_classes_available",
            "portability_to_p_i_n": "translation_required",
            "classifier_stage": "evidence_aware_final",
            "classifier_confidence": "moderate",
            "classifier_warnings": [],
            "card_archetype": "functional_analog_causal_isolation",
            "matched_archetypes": ["functional_analog_causal_isolation"],
            "conflict_reason": "none",
        },
        "mechanism_axes": [
            "dopant_additive_chemical_interaction",
            "recombination_defect_passivation",
            "morphology_crystallinity_phase",
        ],
        "primary_mechanism_axis": "dopant_additive_chemical_interaction",
        "secondary_mechanism_axes": [
            "recombination_defect_passivation",
            "morphology_crystallinity_phase",
        ],
        "card_archetype": "functional_analog_causal_isolation",
        "classification_mode": "closed_set_archetype",
        "archetype_selection": {
            "selected": "functional_analog_causal_isolation",
            "rejected": [],
            "conflict_reason": "none",
            "classifier_confidence": "moderate",
            "soft_routing_note": (
                "Family labels route design primitives; they are not hard requirements "
                "for generating a full experiment card."
            ),
        },
        "priority": 82,
        "priority_rationale": (
            "High Gaia impact, strong discriminating power, useful SQLite precedent "
            "background, and relevant LKM mechanism chains."
        ),
        "scientific_uncertainty": (
            "The observed device improvement could reflect passivation, contact "
            "energetics, morphology, crystallinity, hydrophobicity, or "
            "measurement-history contributions."
        ),
        "hypothesis_H": "Interface modulator reduces contact-limited recombination.",
        "alternative_Alt": (
            "The apparent benefit is dominated by absorber morphology or "
            "contact-energetic differences."
        ),
        "discriminating_observation": (
            "Matched mechanism-specific readouts track the target interface response "
            "while morphology and contact covariates remain bounded."
        ),
        "database_queries_run": [
            "tier1 query: n-i-p FA/Cs stack, ETL/perovskite interface, modulator family"
        ],
        "database_precedents": {
            "tier_counts": {"tier1": 2, "tier2": 3, "tier3": 4, "rejected": 5},
            "parse_coverage": {
                "pce": "2/2",
                "ff": "2/2",
                "voc": "2/2",
                "jsc": "1/2",
                "hysteresis": "1/2",
            },
            "top_precedent_rows": [
                {
                    "doi": "10.0000/example",
                    "perovskite_composition": "FA0.85Cs0.15PbI3",
                    "similarity_score": 0.91,
                    "why_comparable": "Same n-i-p stack and same intervention location.",
                    "why_limited": "Different HTL stack limits direct stability comparison.",
                    "parsed_deltas": {"pce": 1.2, "ff": 0.04, "voc": 0.02},
                }
            ],
            "demoted_precedent_rows": [],
            "rejected_precedent_rows_summary": {},
            "sqlite_precedent_quality": "usable_background",
            "sqlite_quality_warning": False,
            "parse_coverage_warning": False,
        },
        "sqlite_precedent_quality": "usable_background",
        "sqlite_quality_warning": False,
        "sqlite_role": (
            "SQLite is for precedent discovery, stack/intervention matching, and "
            "paired delta background only; it is not mechanism proof."
        ),
        "lkm_queries_run": [
            "/search hybrid claim query",
            "/reasoning/search H-vs-Alt mechanism query",
        ],
        "lkm_role": (
            "LKM mechanism reasoning supplies auditable chains for H-vs-Alt logic, "
            "measurement class design, and causal-chain checks."
        ),
        "lkm_evidence_summary": (
            "LKM reasoning chains support recombination and contact Alt separation "
            "with same-package and cross-package provenance retained."
        ),
        "lkm_design_reasoning": {
            "endpoint": "/reasoning/search",
            "query": "mechanism design query",
            "readout_classes": ["interface readout class"],
            "controls": ["interface-specific comparator control"],
            "confounders": ["morphology"],
            "closure_rules": ["close only with H-vs-Alt readout"],
            "non_closure_rules": ["do not close with proxy-only evidence"],
            "portability_notes": ["re-test in inverted p-i-n"],
            "provenance": [],
            "same_package": [],
            "cross_package": [],
            "ambiguous": [],
        },
        "design_motif_evidence": {
            "retrieved_from_lkm": {
                "endpoint": "/reasoning/search",
                "query": "mechanism design query",
                "readout_classes": ["interface readout class"],
                "controls": ["interface-specific comparator control"],
                "confounders": ["morphology"],
                "closure_rules": ["close only with H-vs-Alt readout"],
                "non_closure_rules": ["do not close with proxy-only evidence"],
                "portability_notes": ["re-test in inverted p-i-n"],
                "provenance": [],
            },
            "retrieved_from_design_memory": [
                {
                    "source_id": "primitive_library::functional_analog_causal_isolation",
                    "doi": "not_applicable",
                    "title": "Functional analog controls for causal isolation",
                    "architecture": "n-i-p",
                    "material_system": "FA-Cs perovskite",
                    "intervention": "Lewis-base interfacial modulator",
                    "intervention_location": "ETL/perovskite interface",
                    "target_problem": "causal isolation",
                    "claimed_mechanism": "dopant_additive_chemical_interaction",
                    "alternative_mechanisms_considered": ["morphology"],
                    "controls_used": ["functional analog control"],
                    "primary_readouts": ["trap/recombination readout"],
                    "secondary_readouts": ["p-i-n portability check"],
                    "confounders_addressed": ["morphology"],
                    "confounders_not_addressed": ["motif is not proof"],
                    "causal_strength": "design_motif_only",
                    "decision_logic_supports_H": "readout supports H",
                    "decision_logic_supports_Alt": "readout supports Alt",
                    "mixed_or_unresolved_logic": "keep unresolved when mixed",
                    "portability_notes": ["p-i-n check required"],
                    "wet_lab_detail_removed": True,
                }
            ],
            "retrieved_from_sqlite_background": {
                "sqlite_precedent_quality": "usable_background",
                "sqlite_quality_warning": False,
                "role": "SQLite background only; not mechanism proof.",
            },
            "motif_synthesis_summary": (
                "Design motifs inform readout/control/confounder/closure-rule selection. "
                "They are not treated as proof of the source-package mechanism."
            ),
        },
        "design_memory_role": (
            "Design memory is used for experimental motif retrieval and control/readout "
            "design. It is not treated as direct proof of the source-package mechanism."
        ),
        "mechanism_source_breakdown": {
            "package_local_gaia_evidence": (
                "Package-local Gaia evidence identifies the weak interface-mechanism claim "
                "and affected conclusion."
            ),
            "lkm_mechanism_reasoning": (
                "LKM chain lkm_chain_01 supports recombination/contact separation."
            ),
            "sqlite_precedent_delta_background": (
                "SQLite contributes comparable precedent and paired delta background, "
                "not mechanism proof."
            ),
        },
        "same_package_lkm_chains": [
            {
                "reasoning_scope": "same_package",
                "source_package": "fa_cs_interface_gaia",
                "paper_id": "paper_local_01",
                "claim_id": "claim_interface_mechanism",
                "conclusion_id": "main_conclusion",
                "chain_id": "lkm_chain_01",
                "title": "Local interface mechanism reasoning",
                "rerank_score": 0.88,
            }
        ],
        "cross_package_lkm_chains": [
            {
                "reasoning_scope": "cross_package",
                "source_package": "related_pin_passivation_gaia",
                "paper_id": "paper_related_01",
                "claim_id": "claim_contact_alt",
                "chain_id": "lkm_chain_cross_01",
                "title": "Related contact-barrier mechanism",
                "score": 0.74,
                "cross_package": True,
            }
        ],
        "ambiguous_lkm_chains": [],
        "unknown_package_lkm_chains": [],
        "sqlite_lkm_conflicts": [
            "No direct conflict; SQLite deltas are treated only as background."
        ],
        "mechanism_attribution_limitations": (
            "Mechanism attribution requires H-vs-Alt readout agreement; SQLite "
            "deltas alone cannot close this gap."
        ),
        "gap_resolution_strategy": {
            "strategy_type": "generic causal-discrimination matrix",
            "uncertainty_to_resolve": (
                "Separate the target mechanism from competing contact, transport, "
                "morphology, and measurement-history alternatives."
            ),
            "decomposition_axes": [
                "recombination/passivation-linked response",
                "contact or transport response",
                "morphology or crystallinity response",
                "measurement-history artifact response",
            ],
            "confounders_to_bound": [
                "device architecture",
                "absorber morphology",
                "contact energetics",
                "measurement history",
            ],
            "decision_rules": [
                "Close the gap only when the discriminating readouts separate H from Alt.",
                "Use mixed_or_unresolved when decomposition axes disagree.",
            ],
            "extension_hooks": [
                "Add domain modules for stability, ion migration, energetics, or aggregate metrics."
            ],
        },
        "source_device_context": {
            "solar_cell_structure": "n-i-p",
            "cell_stack_sequence": "FTO/SnO2/FA-Cs perovskite/Spiro/Au",
            "perovskite_composition": "FA0.85Cs0.15PbI3",
            "intervention_location": "ETL/perovskite interface",
            "modulator_material_or_family": "Lewis-base interfacial modulator",
        },
        "lab_translation_context": {
            "lab_preferred_device_architecture": "inverted p-i-n",
            "translation_status": "source_context_preserved_with_p_i_n_translation",
            "translation_note": (
                "Translate the n-i-p source mechanism into a p-i-n adaptation; "
                "this is not source-paper proof."
            ),
            "translation_targets": [
                (
                    "preserve absorber/passivator chemical mechanism if local to the "
                    "perovskite surface"
                ),
                "re-evaluate contact-selective extraction in p-i-n",
                "separate local passivation from architecture-specific contact effects",
            ],
            "htl_etl_contact_interpretation": (
                "Re-map ETL-side contact language to p-i-n selective-contact comparisons."
            ),
        },
        "p_i_n_adaptation_design": {
            "source_claim_to_translate": "fa_cs_interface::weak_interface_claim",
            "architecture_transfer_assumptions": [
                "source n-i-p result cannot close p-i-n mechanism without matched readouts"
            ],
            "p_i_n_interface_of_interest": "HTL-side or ETL-side translated interface",
            "p_i_n_specific_alt_branches": [
                "p-i-n contact resistance or barrier branch",
                "high-performance baseline ceiling effect",
            ],
            "high_performance_baseline_ceiling_effect": (
                "High-performance p-i-n baselines may compress device-metric headroom."
            ),
            "p_i_n_specific_controls": [
                "p-i-n baseline without intervention",
                "source n-i-p reference only as provenance, not as p-i-n proof",
            ],
            "p_i_n_specific_readouts": [
                "architecture-matched mechanism readout",
                "contact-selective extraction or barrier diagnostic class",
            ],
            "p_i_n_closure_rule": "Close only with p-i-n matched H-vs-Alt readouts.",
            "p_i_n_non_closure_rule": ("Source n-i-p result alone cannot close p-i-n mechanism."),
            "what_not_to_generalize": ["Do not treat p-i-n translation as source-paper evidence."],
        },
        "portability_risks_for_p_i_n": [
            "The source n-i-p contact stack may make contact-barrier "
            "interpretation architecture-sensitive."
        ],
        "architecture_sensitive_readouts": ["Suns-Voc", "contact-selectivity comparison"],
        "what_not_to_generalize": [
            "Do not generalize n-i-p ETL contact proof as p-i-n HTL-side mechanism proof.",
            "Use source n-i-p reference only as provenance, not as p-i-n proof.",
        ],
        "p_i_n_specific_controls": [
            "p-i-n baseline without intervention",
            "p-i-n intervention comparison with matched absorber family",
            "source n-i-p reference only as provenance, not as p-i-n proof",
        ],
        "p_i_n_specific_readouts": [
            "architecture-matched readout",
            "contact-selective extraction or barrier diagnostic class",
        ],
        "p_i_n_specific_risks": [
            "source-stack contact mechanism may not port directly as a p-i-n risk"
        ],
        "recommended_experiment_class": "Design-level causal-discrimination campaign",
        "variables_to_vary": ["interface location", "contact-layer comparison"],
        "controls": [
            "matched no-modulator baseline",
            (
                "functional analog-control class bounding morphology, crystallinity, "
                "hydrophobicity, contact energetics, and recombination/trap readouts; "
                "multi-variable analogs cannot close the causal gap and only support "
                "follow-up narrowing"
            ),
        ],
        "primary_readouts": [
            {
                "name": "interface recombination and covariate-bounded response",
                "maps_to_uncertainty": (
                    "target passivation/contact response versus morphology or contact-energetic Alt"
                ),
                "supports_H_pattern": (
                    "Trap-sensitive and interface-sensitive readouts move with bounded "
                    "morphology, crystallinity, hydrophobicity, and contact energetics."
                ),
                "supports_Alt_pattern": "Morphology readouts shift while contact readouts do not.",
            }
        ],
        "secondary_readouts": ["morphology screen", "dark JV context"],
        "observable_to_mechanism_mapping": {
            "chemical_interaction_branch": "interface/trap readout supports H",
            "morphology_branch": "morphology explains Alt",
            "contact_energetics_branch": "contact energetics explains Alt",
        },
        "expected_result_if_H": (
            "Interface-sensitive and trap-sensitive readouts support H while bounded "
            "covariates do not explain the result."
        ),
        "expected_result_if_Alt": (
            "Absorber morphology or contact-energetic shifts explain the device trend "
            "without an H-specific interface response."
        ),
        "success_criterion_for_closing_gap": (
            "The H/Alt likelihood direction is identifiable from direct readout "
            "agreement, while mixed patterns remain unresolved."
        ),
        "non_closure_criteria": [
            "H and Alt readouts remain mixed_or_unresolved",
            "SQLite precedent background is the only support",
        ],
        "minimum_replicate_logic": (
            "Use independent matched devices and batches as comparison logic without "
            "operational preparation parameters."
        ),
        "statistics_or_comparison_logic": (
            "Compare paired direction and consistency across the declared decomposition axes."
        ),
        "failure_modes": [
            "Morphology shifts co-vary with contact readouts.",
            "Mechanism-axis decomposition remains mixed_or_unresolved.",
        ],
        "interpretation_decision_tree": (
            "If H-specific interface readouts move while covariates are bounded, support H; "
            "otherwise support Alt or mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Interface/trap readouts move with bounded morphology, crystallinity, "
                    "hydrophobicity, and contact energetics."
                ),
                "interpretation": "Contact/recombination mechanism is favored.",
                "remaining_caveat": "Stability mechanism remains separate.",
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Morphology shifts dominate while interface readouts are flat."
                ),
                "interpretation": "Absorber morphology explanation is favored.",
                "remaining_caveat": "A smaller interface contribution may remain.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Readouts split across mechanism and covariate axes.",
                "interpretation": "The gap remains mechanism-ambiguous.",
                "next_step": "Separate contact and absorber controls in a follow-on campaign.",
            },
        },
        "belief_update_target": (
            "Update fa_cs_interface::weak_interface_claim likelihood toward H or Alt."
        ),
        "belief_update_contract": (
            "Update only the named Gaia claim direction supported by the outcome matrix."
        ),
        "feasibility_notes": "Design-level readout classes are available without recipe details.",
        "safety_boundary_note": (
            "Planning only; implementation requires qualified lab supervision and "
            "institutional safety review."
        ),
        "confidence": "moderate",
        "open_questions": ["Whether p-i-n contact translation preserves the same bottleneck."],
    }


def test_valid_real_package_card_passes() -> None:
    result = validator.validate_payload([_valid_card()])
    assert result.errors == []
    assert result.warnings == []


def test_missing_required_fields_fail() -> None:
    card = _valid_card()
    del card["source_package"]
    del card["outcome_matrix"]
    card["database_precedents"] = {"tier_counts": {"tier1": 1}}

    result = validator.validate_payload([card])

    assert any("source_package" in error for error in result.errors)
    assert any("outcome_matrix" in error for error in result.errors)
    assert any("parse_coverage" in error for error in result.errors)
    assert any("tier2" in error for error in result.errors)


def test_outcome_matrix_branch_fields_are_required() -> None:
    card = _valid_card()
    card["outcome_matrix"] = {
        "supports_H": {"observation_pattern": "pattern"},
        "supports_Alt": {"observation_pattern": "pattern", "interpretation": "alt"},
        "mixed_or_unresolved": {"next_step": "split controls"},
    }

    result = validator.validate_payload([card])

    assert any("supports_H.interpretation" in error for error in result.errors)
    assert any("supports_Alt.remaining_caveat" in error for error in result.errors)
    assert any("mixed_or_unresolved.observation_pattern" in error for error in result.errors)


def test_warning_conditions_are_reported() -> None:
    card = _valid_card()
    card["source_device_context"] = "perovskite solar cell"
    card["primary_readouts"] = ["do more characterization"]
    card["confidence"] = "high"
    card["database_precedents"] = {
        "tier_counts": {"tier1": 0, "tier2": 2, "tier3": 1, "rejected": 0},
        "parse_coverage": {
            "pce": "2/2",
            "ff": "2/2",
            "voc": "2/2",
            "jsc": "2/2",
            "hysteresis": "2/2",
        },
        "top_precedent_rows": [
            {
                "perovskite_composition": "Unknown",
                "similarity_score": 0.3,
                "why_comparable": "Same modulator family.",
                "why_limited": "Unknown absorber.",
                "parsed_deltas": {"pce": 0.4},
            },
            {
                "perovskite_composition": "Unknown",
                "similarity_score": 0.31,
                "why_comparable": "Same modulator family.",
                "why_limited": "Unknown absorber.",
                "parsed_deltas": {"ff": 0.02},
            },
        ],
    }

    result = validator.validate_payload([card], smoke_test=True)

    assert result.errors == []
    assert any("generic perovskite" in warning for warning in result.warnings)
    assert any("lacks an H/Alt mapping" in warning for warning in result.warnings)
    assert any("unknown composition" in warning for warning in result.warnings)
    assert any("do more characterization" in warning for warning in result.warnings)


def test_strict_mode_rejects_readme_fallback() -> None:
    card = _valid_card()
    card["original_evidence_gap_text"] = (
        "README Evidence Gaps fallback was used because ANALYSIS.md was absent."
    )

    strict = validator.validate_payload([card])
    permissive = validator.validate_payload([card], allow_readme_fallback=True)

    assert any("README Evidence Gap fallback" in error for error in strict.errors)
    assert permissive.errors == []
    assert any("confidence must be downgraded" in warning for warning in permissive.warnings)


def test_weak_lkm_summary_warns() -> None:
    card = _valid_card()
    card["lkm_evidence_summary"] = "available"

    result = validator.validate_payload([card])

    assert result.errors == []
    assert any("explicit LKM failure reason" in warning for warning in result.warnings)


def test_vague_success_criterion_warns() -> None:
    card = _valid_card()
    card["success_criterion_for_closing_gap"] = "Close the gap."

    result = validator.validate_payload([card])

    assert result.errors == []
    assert any("success criterion is vague" in warning for warning in result.warnings)


def test_low_parse_coverage_requires_database_confidence_note() -> None:
    card = _valid_card()
    assert isinstance(card["database_precedents"], dict)
    parse_coverage = card["database_precedents"]["parse_coverage"]
    assert isinstance(parse_coverage, dict)
    parse_coverage["hysteresis"] = "0/2"

    missing_note = validator.validate_payload([card])
    card["database_confidence"] = (
        "Hysteresis parse coverage is low; mechanism confidence is limited."
    )
    with_note = validator.validate_payload([card])

    assert any("database_confidence" in warning for warning in missing_note.warnings)
    assert not any("database_confidence" in warning for warning in with_note.warnings)


def test_sqlite_only_evidence_cannot_close_mechanism_gap() -> None:
    card = _valid_card()
    card["lkm_role"] = "lkm_unavailable: access key missing"
    card["lkm_evidence_summary"] = "LKM unavailable; failed before reasoning/search."
    card["same_package_lkm_chains"] = []
    card["cross_package_lkm_chains"] = []
    card["mechanism_source_breakdown"] = {
        "package_local_gaia_evidence": "",
        "lkm_mechanism_reasoning": "lkm_unavailable",
        "sqlite_precedent_delta_background": "SQLite paired deltas are background only.",
    }
    card["success_criterion_for_closing_gap"] = (
        "SQLite deltas close mechanism gap if a paired aggregate metric improves."
    )
    card["confidence"] = "moderate"

    result = validator.validate_payload([card])

    assert any("SQLite-only evidence cannot" in error for error in result.errors)
    assert any("LKM failure permits moderate confidence" in error for error in result.errors)


def test_lkm_reasoning_preserves_chain_provenance() -> None:
    card = _valid_card()
    card["same_package_lkm_chains"] = [{"reasoning_scope": "same_package"}]

    result = validator.validate_payload([card])

    assert any(
        "must preserve at least one LKM provenance field" in error for error in result.errors
    )


def test_cross_package_lkm_chain_must_be_marked_cross_package() -> None:
    card = _valid_card()
    card["cross_package_lkm_chains"] = [
        {
            "reasoning_scope": "same_package",
            "source_package": "other_package",
            "chain_id": "cross_chain",
            "cross_package": False,
        }
    ]

    result = validator.validate_payload([card])

    assert any("cross-package chain mislabeled" in error for error in result.errors)
    assert any("cross_package" in error for error in result.errors)


def test_nip_source_generates_pin_translation_without_overwriting_source() -> None:
    card = _valid_card()

    result = validator.validate_payload([card])

    assert result.errors == []
    assert isinstance(card["source_device_context"], dict)
    assert card["source_device_context"]["solar_cell_structure"] == "n-i-p"
    assert "p-i-n" in str(card["lab_translation_context"]).lower()


def test_pin_source_keeps_pin_context_and_requires_pin_matched_controls() -> None:
    card = _valid_card()
    card["source_device_context"] = {
        "solar_cell_structure": "inverted p-i-n",
        "cell_stack_sequence": "ITO/NiOx/perovskite/C60/BCP/Ag",
        "perovskite_composition": "FA-Cs perovskite",
        "intervention_location": "HTL/perovskite interface",
        "modulator_material_or_family": "Lewis-base interfacial modulator",
    }
    card["controls"] = ["generic no-modulator baseline"]

    result = validator.validate_payload([card])
    card["controls"] = [
        "matched p-i-n same stack no-modulator baseline",
        (
            "functional analog-control class bounding morphology, crystallinity, "
            "hydrophobicity, contact energetics, and recombination/trap readouts; "
            "multi-variable analogs cannot close the causal gap and only support "
            "follow-up narrowing"
        ),
    ]
    fixed = validator.validate_payload([card])

    assert any("p-i-n source packages require" in error for error in result.errors)
    assert fixed.errors == []


def test_cards_require_generic_gap_resolution_strategy() -> None:
    card = _valid_card()
    del card["gap_resolution_strategy"]

    result = validator.validate_payload([card])

    assert any("gap_resolution_strategy" in error for error in result.errors)


def test_gap_resolution_strategy_rejects_mandatory_ff_special_case() -> None:
    card = _valid_card()
    assert isinstance(card["gap_resolution_strategy"], dict)
    card["gap_resolution_strategy"]["strategy_type"] = "mandatory FF-loss budget"

    result = validator.validate_payload([card])

    assert any("must not hard-code FF" in error for error in result.errors)


def test_causal_attribution_gap_requires_analog_control_logic() -> None:
    card = _valid_card()
    card["gap_type"] = "causal attribution gap"
    card["scientific_uncertainty"] = (
        "sole cause attribution: passivation not isolated from morphology/contact "
        "alternative or hydrophobicity alternative."
    )
    card["causal_isolation_controls"] = {
        "analog_control_class": "functional analog set",
        "bounded_covariates": [
            "morphology",
            "crystallinity",
            "hydrophobicity",
            "contact energetics",
            "recombination/trap-sensitive readouts",
        ],
        "limitation": (
            "If analogs also shift multiple variables, they cannot close the "
            "causal gap and only support follow-up narrowing."
        ),
    }

    result = validator.validate_payload([card])
    del card["causal_isolation_controls"]
    card["controls"] = ["matched no-modulator baseline"]
    missing = validator.validate_payload([card])

    assert result.errors == []
    assert any("functional analog-control" in error for error in missing.errors)


def test_failed_lkm_call_creates_diagnostics_and_lowers_confidence() -> None:
    card = _valid_card()
    card["lkm_role"] = "lkm_unavailable: /reasoning/search timed out"
    card["lkm_evidence_summary"] = "LKM failed with timeout; lkm_unavailable diagnostic emitted."
    card["confidence"] = "high"

    result = validator.validate_payload([card])

    assert any("LKM failure cannot have high confidence" in error for error in result.errors)


def test_no_operational_wet_lab_recipe_is_emitted() -> None:
    card = _valid_card()
    card["variables_to_vary"] = ["spin coat in DMF at 1000 rpm"]

    result = validator.validate_payload([card])

    assert any("operational wet-lab recipe detail" in error for error in result.errors)


def test_retrieval_evidence_requires_endpoint_diagnostics() -> None:
    payload = {
        "gaps": [
            {
                "gap_id": "experimental_gap_01_interface_mechanism",
                "successful_endpoints": ["/reasoning/search"],
                "failed_endpoints": ["/search timeout"],
                "same_package_lkm_chains": [{"chain_id": "lkm_chain_01"}],
                "cross_package_lkm_chains": [],
                "ambiguous_lkm_chains": [],
                "unknown_package_lkm_chains": [],
                "parse_coverage": {"ff": "0/2"},
            }
        ]
    }

    result = validator.validate_retrieval_evidence_payload(payload)

    assert result.errors == []
    assert any("parse_coverage_warning" in warning for warning in result.warnings)


def test_smoke_mode_relaxes_real_package_grounding() -> None:
    card = _valid_card()
    for key in (
        "source_package",
        "target_claims",
        "affected_conclusions",
        "current_belief",
        "original_evidence_gap_text",
        "source_device_context",
        "portability_risks_for_p_i_n",
    ):
        del card[key]

    normal = validator.validate_payload([card])
    smoke = validator.validate_payload([card], smoke_test=True)

    assert any("source_package" in error for error in normal.errors)
    assert smoke.errors == []
