"""Tests for ``scripts/generate_experiment_plan.py``."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPO_ROOT / "scripts" / "generate_experiment_plan.py"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_experiment_cards.py"
EVIDENCE_TABLE_HEADER = (
    "| Candidate synthesis claim | Source package and source labels | Evidence class | "
    "Direction | Confidence tier | Over-counting risk |"
)
EVIDENCE_TABLE_SEPARATOR = "| --- | --- | --- | --- | --- | --- |"


def _load_module(name: str, path: Path) -> ModuleType:
    """Import a script as a module for testing."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = _load_module("generate_experiment_plan", GENERATOR_PATH)
validator = _load_module("validate_experiment_cards_for_generator", VALIDATOR_PATH)


def _write_package(root: Path, *, architecture: str = "n-i-p") -> None:
    """Create a minimal Gaia package surface for the generator."""
    root.mkdir()
    (root / "ANALYSIS.md").write_text(
        "\n".join(
            [
                "# Analysis",
                "",
                "Evidence Gap: passivation attribution is not isolated from "
                "morphology/contact alternative in the interface claim.",
            ]
        ),
        encoding="utf-8",
    )
    stack = (
        "ITO/NiOx/perovskite/C60/BCP/Ag"
        if "p-i-n" in architecture
        else "FTO/SnO2/perovskite/Spiro/Au"
    )
    context = {
        "source_package": "example_perovskite_gaia",
        "solar_cell_structure": architecture,
        "cell_stack_sequence": stack,
        "perovskite_composition": "FA-Cs perovskite",
        "intervention_location": "selective-contact/perovskite interface",
        "modulator_material_or_family": "multifunctional interfacial modulator",
        "lab_preferred_device_architecture": "inverted p-i-n",
    }
    (root / "experiment_context.yaml").write_text(
        yaml.safe_dump(context, sort_keys=False),
        encoding="utf-8",
    )


def _write_sqlite(path: Path) -> None:
    """Create a tiny precedent database with parseable metric columns."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE precedents (
                solar_cell_structure TEXT,
                perovskite_composition TEXT,
                interfacial_modulator_material_application_location TEXT,
                jv_reverse_scan_pce TEXT,
                jv_reverse_scan_ff TEXT,
                jv_reverse_scan_v_oc TEXT,
                jv_reverse_scan_j_sc TEXT,
                jv_hysteresis_index TEXT,
                title TEXT,
                doi TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO precedents VALUES (
                'n-i-p',
                'FA-Cs perovskite',
                'selective-contact/perovskite interface',
                '22.1',
                '0.81',
                '1.12',
                '24.3',
                '0.02',
                'Comparable interfacial precedent',
                '10.0000/precedent'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _write_sqlite_with_quality_rows(path: Path) -> None:
    """Create precedent rows with one usable PSC row and several rejected rows."""
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE precedents (
                solar_cell_structure TEXT,
                perovskite_composition TEXT,
                interfacial_modulator_material_application_location TEXT,
                jv_reverse_scan_pce TEXT,
                jv_reverse_scan_ff TEXT,
                jv_reverse_scan_v_oc TEXT,
                jv_reverse_scan_j_sc TEXT,
                jv_hysteresis_index TEXT,
                title TEXT,
                doi TEXT,
                mechanism_note TEXT
            )
            """
        )
        rows = [
            (
                "n-i-p",
                "FA-Cs perovskite",
                "selective-contact/perovskite interface",
                "22.1",
                "0.81",
                "1.12",
                "24.3",
                "0.02",
                "Comparable 11MA interface passivation precedent",
                "10.0000/good",
                "passivation and recombination background",
            ),
            (
                "n-i-p",
                "Ba2+ doped perovskite",
                "bulk doping",
                "20.0",
                "0.80",
                "1.05",
                "23.0",
                "0.04",
                "Low-similarity Ba2+ doping row",
                "10.0000/ba",
                "bulk doping",
            ),
            (
                "dye-sensitized solar cell",
                "unknown absorber",
                "electrolyte interface",
                "8.0",
                "0.65",
                "0.8",
                "15.0",
                "",
                "Non-PSC dye row",
                "10.0000/dssc",
                "dye sensitized",
            ),
        ]
        conn.executemany("INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


def _load_yaml(path: Path) -> object:
    """Load YAML output."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write_package_with_gap_table(root: Path, gaps: list[tuple[str, str]]) -> None:
    """Create a package with a Markdown Evidence Gaps table."""
    _write_package(root)
    rows = [
        "# Analysis",
        "",
        "## Evidence Gaps",
        "",
        "| Theme | Gap | Conclusions affected |",
        "| --- | --- | --- |",
    ]
    for gap_text, conclusion in gaps:
        rows.append(f"| Experimental | {gap_text} | {conclusion} |")
    (root / "ANALYSIS.md").write_text("\n".join(rows), encoding="utf-8")


def test_resolve_lkm_access_key_from_dotenv(tmp_path: Path, monkeypatch) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("LKM_ACCESS_KEY='secret-value-for-test'\n", encoding="utf-8")
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    credential = generator.resolve_lkm_access_key([dotenv])

    assert credential.access_key == "secret-value-for-test"
    assert "LKM_ACCESS_KEY" in credential.source
    assert "secret-value-for-test" not in credential.source


def test_generator_writes_valid_design_level_artifacts(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    for relative_path in (
        "experiments.yaml",
        "EXPERIMENT_PLAN.md",
        "retrieval_evidence.yaml",
        "lkm/experimental_gap_01_lkm_unavailable.json",
    ):
        assert (output / relative_path).exists()

    experiments = _load_yaml(output / "experiments.yaml")
    result = validator.validate_payload(experiments)
    assert result.errors == []
    assert all("legacy" not in warning for warning in result.warnings)

    card = experiments["experiments"][0]
    assert "gap_resolution_strategy" in card
    assert card["planning_level"] == "implementation_candidate"
    assert card["gap_claim_belief"] == "unknown"
    assert "current_belief" not in card
    assert card["lab_reference_stack"] == "ITO / SAM / perovskite / C60 / BCP / Ag"
    assert card["execution_phase"]
    assert card["depends_on"]
    assert card["enables"]
    assert card["package_evidence_brief"]["analysis_gap_count"] == 1
    assert card["mechanism_decomposition_question"]
    assert card["factor_decomposition"]["factor_groups"]
    assert card["minimal_discriminating_matrix"]
    assert card["route_designs"]
    assert card["morphology_normalization_strategy"]
    assert set(card["same_sample_measurement_bundle"]) >= {
        "phase_composition",
        "residual_phase_quantification",
        "recombination_trap",
        "transport_contact",
        "device_metrics",
        "stability",
        "stability_readout_history",
    }
    assert card["passivation_transport_tradeoff_logic"]
    assert card["boundary_condition_tests"]
    assert card["gaia_evidence_node_mapping"]["target_claims"]
    assert card["matrix_closure_rules"]
    assert card["matrix_non_closure_rules"]
    assert card["database_confidence"]["overall"] in {"low", "limited", "screening_only"}
    assert card["top_reasoning_chains"][0]["relevance"] == "lkm_unavailable"
    assert "ff_loss_budget" not in card
    assert card["confidence"] == "low"
    assert card["same_package_lkm_chains"] == []
    assert "lkm_unavailable" in str(card["lkm_role"])
    assert "spin coat" not in (output / "EXPERIMENT_PLAN.md").read_text(encoding="utf-8")

    retrieval = _load_yaml(output / "retrieval_evidence.yaml")
    retrieval_result = validator.validate_retrieval_evidence_payload(retrieval)
    assert retrieval_result.errors == []
    gap_evidence = retrieval["gaps"][0]
    assert "/search" in gap_evidence["failed_endpoints"]
    assert "architecture_translation_warning" in gap_evidence


def test_generator_splits_evidence_gap_table_rows(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    (package / "ANALYSIS.md").write_text(
        "\n".join(
            [
                "# Analysis",
                "",
                "## Evidence Gaps",
                "",
                "| Theme | Gap | Conclusions affected |",
                "| --- | --- | --- |",
                "| Experimental | Direct transient extraction timing is absent. "
                "| transport_claim |",
                "| Experimental | The additive does not isolate passivation from morphology. "
                "| causal_claim |",
            ]
        ),
        encoding="utf-8",
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    cards = experiments["experiments"]
    assert [card["gap_id"] for card in cards] == [
        "experimental_gap_01",
        "experimental_gap_02",
    ]
    assert "transient extraction timing" in cards[0]["original_evidence_gap_text"]
    assert cards[0]["template_id"] == "CHARGE_EXTRACTION_COLLECTION_TEMPLATE"
    assert cards[0]["gap_family"] == "charge_extraction_collection"
    assert "causal attribution" in cards[1]["gap_type"]


def test_generator_uses_readme_experimental_gaps_when_analysis_has_no_structured_gaps(
    tmp_path: Path, monkeypatch
) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    (package / "ANALYSIS.md").write_text(
        "# Analysis\n\nThe synthesis summarizes condition-dependent mechanism boundaries.",
        encoding="utf-8",
    )
    (package / "README.md").write_text(
        "\n".join(
            [
                "# Package",
                "",
                "## Evidence Gaps",
                "",
                "<details>",
                "<summary>Evidence Gaps & Future Work</summary>",
                "",
                "### Experimental gaps",
                "",
                "- Run factorial PbCl2/PbI2/MACl/additive series on the same device stack.",
                "- Measure depth-resolved Cl/Pb/I composition and quantified residual PbI2",
                "  on the same samples used for recombination and device readouts.",
                "- Add matched high-dose boundary tests where a paper currently reports only",
                "  a positive point, such as 0.15 M PbCl2 or 4% excess PbI2.",
                "",
                "### Computational gaps",
                "",
                "- This non-experimental bullet should not become a card.",
                "</details>",
            ]
        ),
        encoding="utf-8",
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    cards = experiments["experiments"]
    assert [card["gap_id"] for card in cards] == [
        "experimental_gap_01",
        "experimental_gap_02",
        "experimental_gap_03",
    ]
    rendered_yaml = (output / "experiments.yaml").read_text(encoding="utf-8")
    assert "Computational gaps" not in rendered_yaml
    assert "0.15 M" not in rendered_yaml
    assert "4% excess" not in rendered_yaml
    retrieval = _load_yaml(output / "retrieval_evidence.yaml")
    assert str(package / "README.md") in retrieval["preflight"]["inputs_read"]


def test_open_world_h_alt_uses_semantic_branches_without_package_special_case() -> None:
    classifier = generator.classify_gap_stage_a(
        "Run factorial PbCl2/PbI2/MACl/additive series on the same device stack."
    )

    hypothesis, alternative, observation = generator.synthesize_open_world_h_alt(
        "Run factorial PbCl2/PbI2/MACl/additive series on the same device stack.",
        {"source_package": "pvsk-gaia"},
        classifier,
    )

    combined = f"{hypothesis} {alternative} {observation}"
    assert "candidate mechanism branch" not in combined
    assert "halide-source or distribution branch" in combined
    assert "residual lead-halide phase branch" in combined
    assert "morphology" in combined
    assert "PbCl2 conclusion" not in combined


def test_missing_context_writes_preflight_only(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    _write_sqlite(db_path)
    (package / "experiment_context.yaml").unlink()
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 2
    assert (output / "context_missing_preflight.yaml").exists()
    assert not (output / "experiments.yaml").exists()


def test_pin_source_keeps_pin_translation_context(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package, architecture="inverted p-i-n")
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    card = experiments["experiments"][0]
    assert card["source_device_context"]["solar_cell_structure"] == "inverted p-i-n"
    assert "matched p-i-n" in str(card["controls"]).lower()
    assert "translation context" not in str(card["lab_translation_context"]).lower()


def test_missing_sqlite_is_strict_preflight_failure(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    _write_package(package)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(tmp_path / "missing.db")]
    )

    assert exit_code == 2
    preflight = _load_yaml(output / "context_missing_preflight.yaml")
    assert "sqlite_database" in preflight["context_missing_preflight"]["missing_fields"]


def test_gap_family_templates_are_domain_specific(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [
            ("FF loss budget is missing; FF alone does not prove passivation.", "main_answer"),
            (
                "Transient extraction timing and carrier collection dynamics are absent.",
                "transport",
            ),
            ("Ion migration and hysteresis scan-direction path is unresolved.", "hysteresis"),
            (
                "Sole cause attribution: passivation not isolated from morphology, "
                "crystallinity, and hydrophobicity.",
                "causal",
            ),
            (
                "Theoretical device model gap: trap/recombination parameters to FF "
                "remain qualitative.",
                "model",
            ),
            ("Stability aging readout is incomplete.", "stability"),
        ],
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    cards = experiments["experiments"]
    by_family = {card["gap_family"]: card for card in cards}
    assert by_family["ff_loss_budget"]["template_id"] == "FF_LOSS_BUDGET_TEMPLATE"
    assert set(by_family["ff_loss_budget"]["loss_channel_budget"]) == {
        "recombination_passivation_linked_loss",
        "series_resistance",
        "shunt_or_leakage",
        "contact_resistance",
        "transport_or_contact_barrier",
        "hysteresis_or_scan_history_contribution",
    }
    assert (
        by_family["charge_extraction_collection"]["template_id"]
        == "CHARGE_EXTRACTION_COLLECTION_TEMPLATE"
    )
    extraction_readouts = str(by_family["charge_extraction_collection"]["primary_readouts"]).lower()
    assert "carrier collection timing" in extraction_readouts
    assert (
        by_family["ion_migration_hysteresis"]["template_id"] == "ION_MIGRATION_HYSTERESIS_TEMPLATE"
    )
    assert "bias-history" in str(by_family["ion_migration_hysteresis"]["primary_readouts"]).lower()
    assert (
        by_family["functional_analog_causal_isolation"]["template_id"]
        == "FUNCTIONAL_ANALOG_CAUSAL_ISOLATION_TEMPLATE"
    )
    assert (
        "bounded_covariates"
        in by_family["functional_analog_causal_isolation"]["causal_isolation_controls"]
    )
    assert (
        by_family["model_mapping_quantification"]["template_id"]
        == "MODEL_MAPPING_QUANTIFICATION_TEMPLATE"
    )
    assert "model_inputs" in by_family["model_mapping_quantification"]
    assert (
        by_family["stability_degradation_pathway"]["template_id"]
        == "STABILITY_DEGRADATION_PATHWAY_TEMPLATE"
    )

    for family, card in by_family.items():
        if family != "ff_loss_budget":
            assert "loss_channel_budget" not in card
    assert (
        by_family["ff_loss_budget"]["priority"]
        > by_family["stability_degradation_pathway"]["priority"]
    )
    assert (
        by_family["functional_analog_causal_isolation"]["priority"]
        > by_family["stability_degradation_pathway"]["priority"]
    )

    rendered_yaml = (output / "experiments.yaml").read_text(encoding="utf-8")
    rendered_md = (output / "EXPERIMENT_PLAN.md").read_text(encoding="utf-8")
    for placeholder in validator.FORBIDDEN_PLACEHOLDER_STRINGS:
        assert placeholder not in rendered_yaml
        assert placeholder not in rendered_md
    assert "FF-loss decomposition" in rendered_md
    assert "functional analog" in rendered_md.lower()


def test_lkm_scope_resolver_uses_doi_and_keeps_unknown_scope() -> None:
    context = {
        "source_package": "10_1002-aenm_202100529-gaia",
        "source_dois": ["10.1002/aenm.202100529"],
    }
    same, cross, unknown = generator.summarize_lkm_provenance(
        [
            {
                "results": [
                    {
                        "doi": "10.1002/aenm.202100529",
                        "chain_id": "local_chain",
                        "claim_id": "local_claim",
                        "title": "Local paper",
                    },
                    {
                        "source_package": "other_perovskite_gaia",
                        "doi": "10.0000/other",
                        "local_id": "other_perovskite_gaia::claim",
                        "chain_id": "cross_chain",
                        "claim_id": "cross_claim",
                        "title": "Analogy paper",
                    },
                    {
                        "paper_id": "unresolved_paper",
                        "chain_id": "unknown_chain",
                        "claim_id": "unknown_claim",
                    },
                ]
            }
        ],
        context,
    )

    assert same[0]["chain_id"] == "local_chain"
    assert same[0]["reasoning_scope"] == "same_package"
    assert cross[0]["chain_id"] == "cross_chain"
    assert cross[0]["reasoning_scope"] == "cross_package"
    assert unknown[0]["chain_id"] == "unknown_chain"
    assert unknown[0]["reasoning_scope"] == "ambiguous_package_scope"


def test_sqlite_filters_low_quality_precedents(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    _write_sqlite_with_quality_rows(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    precedents = experiments["experiments"][0]["database_precedents"]
    rows = precedents["top_precedent_rows"]
    demoted = precedents["demoted_precedent_rows"]
    assert rows == []
    assert "10.0000/good" in [row["doi"] for row in demoted]
    assert "Ba2+" not in str(rows)
    assert "dye" not in str(rows + demoted).lower()


def test_weak_sqlite_does_not_block_domain_template(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [("Transient extraction timing and carrier collection dynamics are absent.", "transport")],
    )
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE precedents (
                solar_cell_structure TEXT,
                perovskite_composition TEXT,
                interfacial_modulator_material_application_location TEXT,
                jv_reverse_scan_pce TEXT,
                jv_reverse_scan_ff TEXT,
                jv_reverse_scan_v_oc TEXT,
                jv_reverse_scan_j_sc TEXT,
                jv_hysteresis_index TEXT,
                title TEXT,
                doi TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO precedents VALUES (
                'dye-sensitized solar cell', 'unknown absorber', 'electrolyte', '', '',
                '', '', '', 'Non-PSC row', '10.0000/nonpsc'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    card = experiments["experiments"][0]
    assert card["template_id"] == "CHARGE_EXTRACTION_COLLECTION_TEMPLATE"
    assert card["database_precedents"]["top_precedent_rows"] == []
    assert card["database_precedents"]["sqlite_precedent_quality"] == "unusable"
    retrieval = _load_yaml(output / "retrieval_evidence.yaml")
    assert retrieval["gaps"][0]["parse_coverage_warning"] is True


def test_nip_translation_block_contains_design_content(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package, architecture="n-i-p")
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    card = experiments["experiments"][0]
    assert card["source_device_context"]["solar_cell_structure"] == "n-i-p"
    assert card["lab_translation_context"]["translation_status"] == (
        "source_context_preserved_with_p_i_n_translation"
    )
    assert "not as p-i-n proof" in str(card["p_i_n_specific_controls"]).lower()
    assert "contact-selective" in str(card["p_i_n_specific_readouts"]).lower()
    assert "portability risk" in str(card["p_i_n_specific_risks"]).lower()


def test_ff_matcher_ignores_efficiency_different_effective_diffusion() -> None:
    """FF archetype should require explicit FF/J-V loss language."""
    non_ff_texts = [
        "Efficiency improves but the mechanism remains unresolved.",
        "Different interface additives change device behavior.",
        "Effective passivation evidence is incomplete.",
        "Diffusion length is reported without direct collection mapping.",
    ]

    for text in non_ff_texts:
        assert generator.classify_gap_stage_a(text).card_archetype != "ff_loss_budget"


def test_explicit_ff_terms_route_to_ff_loss_budget() -> None:
    """Standalone FF and resistance/loss terms route to the FF module."""
    ff_texts = [
        "FF loss branch is unresolved.",
        "fill factor increase alone is not mechanism proof.",
        "series resistance and Rsh ambiguity remains.",
        "J-V loss decomposition is missing.",
    ]

    for text in ff_texts:
        assert generator.classify_gap_stage_a(text).card_archetype == "ff_loss_budget"


def test_non_ff_mechanism_axes_route_to_non_ff_archetypes() -> None:
    """Representative non-FF gaps should select non-FF archetypes."""
    cases = {
        "Voc deficit and QFLS recombination loss mapping is missing.": (
            "recombination_loss_mapping"
        ),
        "Work function and band alignment evidence is not separated from contact barrier.": (
            "contact_energetics_interface_selectivity"
        ),
        "Morphology, crystallinity, and phase purity causality are unresolved.": (
            "morphology_phase_causality"
        ),
        "Operational stability under moisture and phase stability pathways are unresolved.": (
            "stability_degradation_pathway"
        ),
    }

    for text, expected in cases.items():
        assert generator.classify_gap_stage_a(text).card_archetype == expected


def test_rendered_plan_is_sorted_by_priority() -> None:
    """Markdown roadmap should use priority order, not gap-id order."""
    base = {
        "source_package": "pkg",
        "gap_type": "gap",
        "gap_type_specific_title": "title",
        "gap_family": "generic_uncertainty",
        "card_archetype": "generic_uncertainty",
        "template_id": "GENERIC_UNCERTAINTY_TEMPLATE",
        "template_resolution_status": "unresolved_generic_fallback",
        "hypothesis_H": "Specific H",
        "alternative_Alt": "Specific Alt",
        "discriminating_observation": "Specific observation",
        "primary_readouts": [{"name": "specific readout"}],
        "lab_translation_context": {"translation_note": "p-i-n note"},
        "sqlite_role": (
            "SQLite is for precedent discovery, stack/intervention matching, and paired "
            "delta background only; it is not mechanism proof."
        ),
        "sqlite_precedent_quality": "unusable",
        "sqlite_quality_warning": True,
        "lkm_scope_summary": {
            "same_package": 0,
            "cross_package": 0,
            "ambiguous_package_scope": 0,
        },
        "confidence": "low",
        "mechanism_attribution_limitations": "Specific limitation",
    }
    low = {**base, "gap_id": "experimental_gap_01", "priority": 50}
    high = {**base, "gap_id": "experimental_gap_02", "priority": 95}

    markdown = generator.render_plan([low, high])

    assert markdown.index("[95] experimental_gap_02") < markdown.index("[50] experimental_gap_01")


def test_aggregate_corpus_mode_does_not_require_single_locked_stack(
    tmp_path: Path, monkeypatch
) -> None:
    """Aggregate packages should not be forced into one locked device context."""
    package = tmp_path / "pvsk-gaia"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    package.mkdir()
    (package / "ANALYSIS.md").write_text(
        "# Analysis\n\nEvidence Gap: Stability degradation pathway is unresolved.",
        encoding="utf-8",
    )
    (package / "experiment_context.yaml").write_text(
        yaml.safe_dump(
            {
                "source_package": "pvsk-gaia",
                "package_mode": "aggregate_corpus",
                "corpus_level_distribution": "mixed PSC corpus with n-i-p and p-i-n families",
                "lab_preferred_device_architecture": "inverted p-i-n",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    experiments = _load_yaml(output / "experiments.yaml")
    card = experiments["experiments"][0]
    assert card["package_mode"] == "aggregate_corpus"
    assert card["planning_level"] == "aggregate_roadmap"
    assert card["source_device_context"]["package_mode"] == "aggregate_corpus"
    assert "solar_cell_structure" not in card["source_device_context"]
    retrieval = _load_yaml(output / "retrieval_evidence.yaml")
    assert retrieval["preflight"]["package_mode"] == "aggregate_corpus"


def test_unknown_gap_uses_open_world_design_mode(tmp_path: Path, monkeypatch) -> None:
    """Unknown mechanism gaps should not collapse into an empty generic card."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [("Unregistered interfacial memory effect lacks a causal test.", "novel_claim")],
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    assert card["classification_mode"] == "open_world_design"
    assert card["template_id"] == "OPEN_WORLD_DESIGN_TEMPLATE"
    assert card["hypothesis_H"]
    assert card["alternative_Alt"]
    assert card["primary_readouts"]
    assert card["controls"]
    assert card["non_closure_criteria"]
    assert card["emergent_gap_family"]["review_required"] is True
    assert card["design_motif_evidence"]["retrieved_from_design_memory"]


def test_conflicting_archetypes_use_mixed_archetype_mode(tmp_path: Path, monkeypatch) -> None:
    """Multiple known families should be motif-composed instead of hard-gated."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [
            (
                "Voc deficit recombination evidence conflicts with morphology "
                "crystallinity causality.",
                "mixed_claim",
            )
        ],
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    assert card["classification_mode"] == "mixed_archetype"
    assert len(card["gap_classifier_output"]["matched_archetypes"]) > 1
    assert "multiple_archetype_matches" in card["archetype_selection"]["conflict_reason"]
    motif_sources = [
        motif["source_id"]
        for motif in card["design_motif_evidence"]["retrieved_from_design_memory"]
    ]
    assert any("recombination_loss_mapping" in source for source in motif_sources)
    assert any("morphology_phase_causality" in source for source in motif_sources)


def test_lkm_design_reasoning_summary_populates_design_fields() -> None:
    """Mock LKM experiment-design payload should populate design reasoning."""
    payload = {
        "results": [
            {
                "source_package": "example_perovskite_gaia",
                "chain_id": "design_chain",
                "title": (
                    "Use readout measurement controls baseline comparator to separate "
                    "alternative covariate artifact."
                ),
            }
        ]
    }

    summary = generator.summarize_lkm_design_reasoning(
        payload,
        "experiment design query",
        {"source_package": "example_perovskite_gaia"},
    )

    assert summary["endpoint"] == "/reasoning/search"
    assert summary["readout_classes"]
    assert summary["controls"]
    assert summary["confounders"]
    assert summary["same_package"][0]["reasoning_scope"] == "same_package"


def test_mock_design_memory_motifs_influence_open_world_card(tmp_path: Path, monkeypatch) -> None:
    """Design motifs should shape readouts/controls without becoming proof."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [("Unregistered interface memory effect lacks a causal test.", "novel_claim")],
    )
    context = yaml.safe_load((package / "experiment_context.yaml").read_text(encoding="utf-8"))
    context["design_memory_motifs"] = [
        {
            "source_id": "mock-motif-1",
            "title": "Design-level memory-effect motif",
            "primary_readouts": ["bias-history resolved interfacial memory readout"],
            "controls_used": ["history-free matched interface comparator"],
            "confounders_addressed": ["bias history", "contact charging"],
            "decision_logic_supports_H": "memory readout tracks H",
            "decision_logic_supports_Alt": "contact charging explains Alt",
            "mixed_or_unresolved_logic": "keep unresolved when both track",
        }
    ]
    (package / "experiment_context.yaml").write_text(
        yaml.safe_dump(context, sort_keys=False), encoding="utf-8"
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    assert "bias-history resolved interfacial memory readout" in str(card["primary_readouts"])
    assert "history-free matched interface comparator" in str(card["controls"])
    assert "not treated as direct proof" in card["design_memory_role"]
    assert card["design_motif_evidence"]["retrieved_from_design_memory"][0][
        "wet_lab_detail_removed"
    ]


def test_design_memory_recipe_details_are_removed(tmp_path: Path, monkeypatch) -> None:
    """Design-memory retrieval must not leak operational recipe details."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [("Unregistered surface relaxation effect lacks a causal test.", "novel_claim")],
    )
    context = yaml.safe_load((package / "experiment_context.yaml").read_text(encoding="utf-8"))
    context["design_memory_motifs"] = [
        {
            "source_id": "mock-recipe-motif",
            "primary_readouts": ["spin coat in DMF at 1000 rpm"],
            "controls_used": ["anneal at 100 degC comparator"],
        }
    ]
    (package / "experiment_context.yaml").write_text(
        yaml.safe_dump(context, sort_keys=False), encoding="utf-8"
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    rendered_yaml = (output / "experiments.yaml").read_text(encoding="utf-8").lower()
    assert "spin coat" not in rendered_yaml
    assert "dmf" not in rendered_yaml
    assert "anneal at" not in rendered_yaml


def test_synthesis_plan_evidence_table_populates_package_brief(tmp_path: Path, monkeypatch) -> None:
    """Optional SYNTHESIS_PLAN.md Evidence Table should feed the package brief."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    (package / "SYNTHESIS_PLAN.md").write_text(
        "\n".join(
            [
                "# Synthesis",
                "",
                "## Evidence Table",
                "",
                EVIDENCE_TABLE_HEADER,
                EVIDENCE_TABLE_SEPARATOR,
                "| 0.15 M additive and 2 mol% co-additive improve a window "
                "but boundary is unclear. | "
                "`pkg-gaia`: `window_claim`, `dose_015m_claim`, "
                "`best_device_three_percent_metrics`, `recipe2_6_7_best_recipe_grid`, "
                "`boundary_claim` | direct | "
                "positive with unclear boundary | strong | shared device workflow |",
            ]
        ),
        encoding="utf-8",
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    rows = card["package_evidence_brief"]["synthesis_evidence_table"]
    assert rows
    assert rows[0]["candidate_synthesis_claim"].startswith("reported-dose additive")
    assert rows[0]["source_packages"] == ["pkg-gaia"]
    assert rows[0]["source_labels"] == [
        "window_claim",
        "pkg-gaia::window_claim",
        "dose_reported_dose_claim",
        "pkg-gaia::dose_reported_dose_claim",
        "best_device_reported_percentage_metrics",
        "pkg-gaia::best_device_reported_percentage_metrics",
        "recipe_grid_best_recipe_grid",
        "pkg-gaia::recipe_grid_best_recipe_grid",
        "boundary_claim",
        "pkg-gaia::boundary_claim",
    ]
    assert rows[0]["direction"] == "positive with unclear boundary"
    assert rows[0]["confidence_tier"] == "strong"
    assert rows[0]["over_counting_risk"] == "shared device workflow"
    assert rows[0]["parse_status"] == "complete"
    assert "0.15 M" not in str(rows)
    assert "2 mol%" not in str(rows)
    assert "015m" not in str(rows)
    assert "three_percent" not in str(rows)
    assert "recipe2_6_7" not in str(rows)
    retrieval = _load_yaml(output / "retrieval_evidence.yaml")
    assert str(package / "SYNTHESIS_PLAN.md") in retrieval["preflight"]["inputs_read"]
    assert retrieval["preflight"]["synthesis_evidence_table_required_fields_present"] is True


def test_pbx2_synthesis_table_generates_required_semantic_matrix_rows(
    tmp_path: Path, monkeypatch
) -> None:
    """PbX2/chloride evidence should produce concrete mechanism-decomposition rows."""
    package = tmp_path / "pvsk-gaia"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    package.mkdir()
    (package / "ANALYSIS.md").write_text(
        "# Analysis\n\nEvidence Gap: PbCl2 and residual PbI2 mechanisms need isolation.",
        encoding="utf-8",
    )
    (package / "experiment_context.yaml").write_text(
        yaml.safe_dump(
            {
                "source_package": "synthetic-pbx2-gaia",
                "package_mode": "aggregate_corpus",
                "corpus_level_distribution": "PbCl2, chloride, and residual PbI2 corpus",
                "perovskite_composition": "lead-halide perovskite corpus",
                "intervention_location": "bulk, grain-boundary, and interface corpus",
                "modulator_material_or_family": (
                    "PbCl2, chloride-source, and residual PbI2 families"
                ),
                "lab_preferred_device_architecture": "inverted p-i-n",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (package / "SYNTHESIS_PLAN.md").write_text(
        "\n".join(
            [
                "# Synthesis",
                "",
                "## Evidence Table",
                "",
                EVIDENCE_TABLE_HEADER,
                EVIDENCE_TABLE_SEPARATOR,
                "| PbCl2 replaces PbI2 in one comparison but excess PbCl2 has a high "
                "boundary. | `pbcl2-gaia`: `pbcl2_replaces_pbi2`, "
                "`pbcl2_overaddition_boundary` | direct window | mixed | strong | "
                "shared window workflow |",
                "| MACl and PbCl2 chloride-source behavior depends on chloride distribution "
                "and residual PbI2 coupling. | `chloride-gaia`: "
                "`chloride_distribution`, `residual_pbi2_coupling` | multimodal "
                "measurement | positive | strong | same additive family |",
                "| Residual PbI2 at the wrong location penalizes recombination and stability. | "
                "`residue-gaia`: `residual_pbi2_wrong_location`, `stability_penalty` | "
                "interface mapping | negative/mixed | moderate | same interface map |",
            ]
        ),
        encoding="utf-8",
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    labels = [row["row_label"] for row in card["minimal_discriminating_matrix"]]
    assert labels[:7] == [
        "baseline",
        "Pb-rich only",
        "chloride-source only",
        "PbCl2 isolead substitution",
        "PbCl2 excess coupling",
        "chloride + Pb-rich combined",
        "high-boundary condition",
    ]
    for row in card["minimal_discriminating_matrix"][:7]:
        assert row["evidence_basis"]
        assert row["source_labels"]
        assert row["variable_role"]
        assert row["held_constant_design_assumptions"]
        assert row["discriminating_readouts"]
        assert set(row["h_alt_interpretation"]) == {
            "supports_H",
            "supports_Alt",
            "mixed_or_unresolved",
        }
        assert row["closure_rule"]
        assert row["non_closure_rule"]

    assert set(card["same_sample_measurement_bundle"]) >= {
        "phase_composition",
        "residual_phase_quantification",
        "recombination_trap",
        "device_metrics",
        "stability_readout_history",
    }
    update_labels = card["gaia_evidence_node_mapping"]["readable_update_labels"]
    assert set(update_labels) >= {
        "chloride_distribution_isolated",
        "pb_rich_residue_effect_isolated",
        "morphology_normalization_survives",
        "wrong_location_residual_phase_penalty",
        "high_boundary_negative_case_confirmed",
    }
    rendered = (output / "EXPERIMENT_PLAN.md").read_text(encoding="utf-8")
    assert "| Row | Evidence basis | Source labels | Variable role |" in rendered
    assert "PbCl2 isolead substitution" in rendered
    assert "0.15 M" not in rendered
    assert "3%" not in rendered


def test_implementation_candidate_context_requirements_are_strict(
    tmp_path: Path, monkeypatch
) -> None:
    """implementation_candidate needs concrete package/stack/absorber/intervention context."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    context = yaml.safe_load((package / "experiment_context.yaml").read_text(encoding="utf-8"))
    context = {
        "source_package": context["source_package"],
        "package_mode": "aggregate_corpus",
        "planning_level": "implementation_candidate",
    }
    (package / "experiment_context.yaml").write_text(
        yaml.safe_dump(context, sort_keys=False), encoding="utf-8"
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 2
    preflight = _load_yaml(output / "context_missing_preflight.yaml")
    missing = preflight["context_missing_preflight"]["missing_fields"]
    assert "solar_cell_structure" in missing
    assert "cell_stack_sequence" in missing


def test_non_pbx2_package_generates_semantic_matrix(tmp_path: Path, monkeypatch) -> None:
    """Matrix synthesis should work for non-PbX2 mechanism motifs."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [
            (
                "Alkali surface-dipole passivation is not separated from transport "
                "and contact-selectivity alternatives.",
                "surface_dipole_claim",
            )
        ],
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    matrix_text = str(card["minimal_discriminating_matrix"])
    assert "intervention_family_axis" in matrix_text
    assert "morphology_normalization_axis" in matrix_text
    assert "PbCl2" not in matrix_text
    assert "PbI2" not in matrix_text


def test_unrelated_synthesis_table_does_not_emit_pb_specific_rows(
    tmp_path: Path, monkeypatch
) -> None:
    """Evidence-derived matrix rows should not use Pb labels for unrelated mechanisms."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package_with_gap_table(
        package,
        [
            (
                "Alkali surface-dipole passivation is not separated from transport "
                "and contact-selectivity alternatives.",
                "surface_dipole_claim",
            )
        ],
    )
    (package / "SYNTHESIS_PLAN.md").write_text(
        "\n".join(
            [
                "# Synthesis",
                "",
                "## Evidence Table",
                "",
                EVIDENCE_TABLE_HEADER,
                EVIDENCE_TABLE_SEPARATOR,
                "| Alkali surface-dipole passivation may change contact selectivity. | "
                "`alkali-gaia`: `surface_dipole_claim`, `transport_alt` | "
                "proxy/device mapping | mixed | moderate | same device workflow |",
            ]
        ),
        encoding="utf-8",
    )
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    card = _load_yaml(output / "experiments.yaml")["experiments"][0]
    matrix_text = str(card["minimal_discriminating_matrix"])
    assert "PbCl2" not in matrix_text
    assert "PbI2" not in matrix_text
    assert "Pb-rich only" not in matrix_text
    assert card["minimal_discriminating_matrix"][0]["row_label"] == "baseline"


def test_sqlite_v2_tiers_and_similarity_breakdown(tmp_path: Path, monkeypatch) -> None:
    """SQLite output should use V2 tier names and component scores."""
    package = tmp_path / "pkg"
    output = tmp_path / "out"
    db_path = tmp_path / "precedents.db"
    _write_package(package)
    _write_sqlite(db_path)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)

    exit_code = generator.main(
        [str(package), "--output-dir", str(output), "--sqlite-db", str(db_path), "--skip-lkm"]
    )

    assert exit_code == 0
    precedents = _load_yaml(output / "experiments.yaml")["experiments"][0]["database_precedents"]
    assert set(precedents["tier_counts"]) == {
        "tier1_strong_precedent",
        "tier2_related_precedent",
        "tier3_broad_context",
        "rejected_or_unusable",
    }
    demoted = precedents["demoted_precedent_rows"]
    assert demoted
    score = demoted[0]["similarity_score"]
    assert set(score) == {
        "architecture",
        "absorber",
        "intervention_location",
        "modulator_family",
        "paired_metric_completeness",
        "mechanism_relevance",
        "total",
    }
    assert demoted[0]["precedent_group"] in {
        "dose_series",
        "device_variant",
        "duplicate_extraction",
        "independent_paper",
    }


def test_lkm_top_reasoning_chains_summary() -> None:
    """Top reasoning-chain summaries should expose relevance, support, and limitations."""
    lkm = generator.LkmSummary(
        queries_run=["/reasoning/search: recombination"],
        role="LKM mechanism reasoning retrieved.",
        evidence_summary="LKM reasoning chain supports recombination branch.",
        mechanism_reasoning="same-package recombination mechanism reasoning",
        same_package_chains=[
            {
                "reasoning_scope": "same_package",
                "source_package": "example_perovskite_gaia",
                "chain_id": "chain_1",
                "title": "Trap passivation separates contact alternative.",
            }
        ],
        cross_package_chains=[],
        unknown_package_chains=[],
        successful_endpoints=["/reasoning/search"],
        failed_endpoints=[],
        sqlite_lkm_conflicts=[],
        confidence="moderate",
        design_reasoning={},
    )
    classifier = generator.classify_gap_stage_a("Trap recombination loss mapping is absent.")

    chains = generator.build_top_reasoning_chains(lkm, classifier)

    assert chains[0]["relevance"] == "direct_source_context"
    assert chains[0]["supports"] == "recombination_defect_passivation"
    assert "H-vs-Alt" in chains[0]["key_limitation"]
    assert chains[0]["provenance"]["chain_id"] == "chain_1"
