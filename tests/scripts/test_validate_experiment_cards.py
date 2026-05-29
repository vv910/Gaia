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
        "gap_id": "experimental_gap_01_interface_ff",
        "source_package": "fa_cs_interface_gaia",
        "target_claims": ["fa_cs_interface::weak_ff_claim"],
        "affected_conclusions": ["fa_cs_interface::main_conclusion"],
        "current_belief": 0.42,
        "original_evidence_gap_text": "Evidence Gap: FF gain may be contact-limited.",
        "hypothesis_H": "Interface modulator reduces contact-limited recombination.",
        "alternative_Alt": "The apparent FF gain is dominated by absorber morphology differences.",
        "discriminating_observation": "Matched interface-sensitive readouts track FF delta.",
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
        },
        "lkm_evidence_summary": "LKM chains support recombination and contact Alt separation.",
        "device_context": {
            "solar_cell_structure": "n-i-p",
            "cell_stack_sequence": "FTO/SnO2/FA-Cs perovskite/Spiro/Au",
            "perovskite_composition": "FA0.85Cs0.15PbI3",
            "intervention_location": "ETL/perovskite interface",
            "modulator_material_or_family": "Lewis-base interfacial modulator",
        },
        "controls": ["matched no-modulator baseline"],
        "primary_readouts": [
            {
                "name": "FF and Voc paired delta",
                "maps_to_uncertainty": "contact-limited recombination versus morphology Alt",
                "supports_H_pattern": "FF and Voc improve without morphology-only trend.",
                "supports_Alt_pattern": "Morphology readouts shift while contact readouts do not.",
            }
        ],
        "expected_result_if_H": "Interface-sensitive readouts co-vary with FF and Voc.",
        "expected_result_if_Alt": "Absorber morphology shifts explain FF without interface trend.",
        "success_criterion_for_closing_gap": "H/Alt likelihood direction is identifiable.",
        "interpretation_decision_tree": "If interface readouts track FF, support H; otherwise Alt.",
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": "Interface readouts and FF/Voc deltas move together.",
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
                "observation_pattern": "FF improves but readouts split across mechanisms.",
                "interpretation": "The gap remains mechanism-ambiguous.",
                "next_step": "Separate contact and absorber controls in a follow-on campaign.",
            },
        },
        "safety_boundary_note": (
            "Planning only; implementation requires qualified lab supervision and "
            "institutional safety review."
        ),
        "confidence": "moderate",
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
    card["device_context"] = "perovskite solar cell"
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


def test_smoke_mode_relaxes_real_package_grounding() -> None:
    card = _valid_card()
    for key in (
        "source_package",
        "target_claims",
        "affected_conclusions",
        "current_belief",
        "original_evidence_gap_text",
        "device_context",
    ):
        del card[key]

    normal = validator.validate_payload([card])
    smoke = validator.validate_payload([card], smoke_test=True)

    assert any("source_package" in error for error in normal.errors)
    assert smoke.errors == []
