"""Photovoltaic metric-specific experiment-card templates.

This module intentionally owns fill-factor loss-budget detail so the generic
perovskite gap-to-experiment generator can remain a template dispatcher.
"""

from __future__ import annotations

from typing import Any

# ruff: noqa: E501


FF_LOSS_CHANNEL_BUDGET: dict[str, dict[str, str]] = {
    "recombination_passivation_linked_loss": {
        "branch_question": (
            "Does the FF gain track recombination/passivation-sensitive loss after "
            "contact and resistance terms are bounded?"
        ),
        "supports_H": (
            "Recombination-sensitive proxies improve in the same paired population "
            "where the FF-loss term decreases."
        ),
        "supports_Alt": (
            "Recombination-sensitive proxies are flat or too small while another "
            "loss branch accounts for the FF shift."
        ),
    },
    "series_resistance": {
        "branch_question": "Does reduced series-resistance-like loss dominate the FF change?",
        "supports_H": "Series-resistance contribution is bounded below the dominant FF-loss shift.",
        "supports_Alt": "Series-resistance-sensitive diagnostics account for most of the FF gain.",
    },
    "shunt_or_leakage": {
        "branch_question": "Does shunt or leakage suppression dominate the FF change?",
        "supports_H": "Dark leakage and shunt-sensitive response are bounded as secondary terms.",
        "supports_Alt": "Leakage or shunt-sensitive response explains the FF increase.",
    },
    "contact_resistance": {
        "branch_question": "Does contact resistance dominate the FF change?",
        "supports_H": "Contact-resistance contribution is bounded below the recombination branch.",
        "supports_Alt": "Contact-resistance-sensitive response accounts for the FF gain.",
    },
    "transport_or_contact_barrier": {
        "branch_question": "Does a transport or contact barrier dominate the FF change?",
        "supports_H": "Barrier-sensitive diagnostics do not show a dominant transport/contact barrier.",
        "supports_Alt": "Barrier-sensitive diagnostics explain the FF gain or expose a new bottleneck.",
    },
    "hysteresis_or_scan_history_contribution": {
        "branch_question": "Does scan history or hysteresis dominate the FF change?",
        "supports_H": "Scan-direction and bias-history contributions are bounded below the target branch.",
        "supports_Alt": "Scan-history or hysteresis response explains the apparent FF gain.",
    },
}


def build_ff_loss_budget_card(_gap: Any, context: dict[str, Any]) -> dict[str, Any]:
    """Return FF-loss-budget overrides for an experiment card."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "FF_LOSS_BUDGET_TEMPLATE",
        "template_resolution_status": "resolved_domain_specific",
        "gap_type_specific_title": "FF-loss budget and passivation/contact discrimination",
        "gap_type": "FF-loss budget discrimination",
        "hypothesis_H": (
            f"{modulator} reduces FF loss mainly through a recombination/passivation-linked "
            "branch, without introducing a dominant transport or contact barrier."
        ),
        "alternative_Alt": (
            "The FF gain is mainly explained by series resistance, shunt/leakage, "
            "contact resistance, a transport/contact barrier, or scan-history/hysteresis "
            "rather than passivation-linked loss."
        ),
        "scientific_uncertainty": (
            "Which photovoltaic loss branch accounts for the FF change, and whether the "
            "result can update the affected passivation or transport Gaia claim."
        ),
        "discriminating_observation": (
            "A branch-resolved FF-loss budget assigns the dominant FF-loss reduction to "
            "one channel while matched controls bound the other branches."
        ),
        "loss_channel_budget": FF_LOSS_CHANNEL_BUDGET,
        "variables_to_vary": [
            "intervention versus matched no-intervention population",
            "architecture-matched contact stack comparison",
            "scan-direction or bias-history condition when hysteresis is relevant",
        ],
        "primary_readouts": [
            {
                "name": "FF-loss decomposition from paired J-V and diode/contact analysis class",
                "maps_to_uncertainty": (
                    "separates recombination/passivation-linked FF loss from electrical "
                    "loss branches"
                ),
                "supports_H_pattern": (
                    "dominant FF-loss reduction maps to recombination/passivation-linked loss"
                ),
                "supports_Alt_pattern": (
                    "dominant FF-loss reduction maps to resistance, leakage, contact, "
                    "barrier, or scan-history terms"
                ),
            },
            {
                "name": "dark leakage and shunt-sensitive class",
                "maps_to_uncertainty": "tests whether leakage or shunt suppression explains FF",
                "supports_H_pattern": "leakage/shunt terms remain bounded",
                "supports_Alt_pattern": "leakage/shunt terms explain the FF shift",
            },
            {
                "name": "contact/transport barrier diagnostic class",
                "maps_to_uncertainty": "tests whether contact or transport barriers dominate",
                "supports_H_pattern": "barrier response is not the dominant FF-loss branch",
                "supports_Alt_pattern": "barrier response accounts for FF change",
            },
            {
                "name": "recombination-loss proxy class",
                "maps_to_uncertainty": "tests passivation-linked recombination loss",
                "supports_H_pattern": "recombination-loss proxy tracks the FF-loss reduction",
                "supports_Alt_pattern": "proxy does not track the FF gain after controls",
            },
        ],
        "secondary_readouts": [
            "same-device Voc/Jsc/PCE population context paired to FF-loss branches",
            "scan-history or hysteresis context when measurement history is relevant",
        ],
        "controls": [
            "matched no-intervention baseline",
            "same absorber-family and same architecture comparator",
            "contact-stack comparator that bounds contact resistance and barrier changes",
            "scan-protocol comparator when hysteresis can affect FF",
        ],
        "expected_result_if_H": (
            "The recombination/passivation-linked branch accounts for the dominant FF-loss "
            "reduction while resistance, leakage, contact, barrier, and scan-history "
            "branches remain bounded."
        ),
        "expected_result_if_Alt": (
            "One or more non-passivation branches account for the FF gain, so the "
            "passivation claim stays bounded."
        ),
        "success_criterion_for_closing_gap": (
            "Close only if the dominant FF-loss reduction is assigned to one branch well "
            "enough to update the affected Gaia claim; FF increase alone cannot close "
            "this gap."
        ),
        "failure_modes": [
            "FF rises while the branch budget remains mixed_or_unresolved.",
            "Contact or resistance terms dominate and prevent a passivation update.",
            "Scan-history or hysteresis changes explain the apparent FF gain.",
        ],
        "interpretation_decision_tree": (
            "If the branch-resolved budget assigns the dominant FF-loss reduction to "
            "recombination/passivation with bounded non-passivation branches, update "
            "toward H; if resistance, leakage, contact, barrier, or scan-history terms "
            "dominate, update toward Alt; otherwise keep mixed_or_unresolved."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": (
                    "Dominant FF-loss reduction is recombination/passivation-linked and "
                    "non-passivation branches are bounded."
                ),
                "interpretation": "Passivation-linked FF-loss reduction is favored.",
                "remaining_caveat": (
                    "The result still requires architecture-matched confirmation before "
                    "p-i-n transfer is treated as robust."
                ),
            },
            "supports_Alt": {
                "observation_pattern": (
                    "Series resistance, shunt/leakage, contact resistance, barrier, or "
                    "scan-history terms dominate the FF change."
                ),
                "interpretation": "A non-passivation FF-loss branch is favored.",
                "remaining_caveat": "A smaller passivation contribution may remain.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": (
                    "The FF-loss decomposition cannot assign a dominant branch."
                ),
                "interpretation": "The mechanism conclusion remains bounded.",
                "next_step": "Narrow the strongest unresolved branch with a targeted comparator.",
            },
        },
    }
