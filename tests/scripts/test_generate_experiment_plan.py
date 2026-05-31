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
    assert result.warnings == []

    card = experiments["experiments"][0]
    assert "gap_resolution_strategy" in card
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
    assert cards[0]["template_id"] == "EXTRACTION_TIMING_TEMPLATE"
    assert cards[0]["gap_family"] == "extraction_timing"
    assert "causal attribution" in cards[1]["gap_type"]


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
    assert by_family["extraction_timing"]["template_id"] == "EXTRACTION_TIMING_TEMPLATE"
    extraction_readouts = str(by_family["extraction_timing"]["primary_readouts"]).lower()
    assert "carrier collection timing" in extraction_readouts
    assert (
        by_family["ion_migration_hysteresis"]["template_id"] == "ION_MIGRATION_HYSTERESIS_TEMPLATE"
    )
    assert "bias-history" in str(by_family["ion_migration_hysteresis"]["primary_readouts"]).lower()
    assert by_family["causal_isolation_analog"]["template_id"] == "CAUSAL_ISOLATION_ANALOG_TEMPLATE"
    assert "bounded_covariates" in by_family["causal_isolation_analog"]["causal_isolation_controls"]
    assert by_family["device_model_link"]["template_id"] == "DEVICE_MODEL_LINK_TEMPLATE"
    assert "model_inputs" in by_family["device_model_link"]
    assert by_family["generic_fallback"]["template_resolution_status"] == (
        "unresolved_generic_fallback"
    )

    for family, card in by_family.items():
        if family != "ff_loss_budget":
            assert "loss_channel_budget" not in card
    assert by_family["ff_loss_budget"]["priority"] > by_family["generic_fallback"]["priority"]
    assert (
        by_family["causal_isolation_analog"]["priority"] > by_family["generic_fallback"]["priority"]
    )
    assert by_family["generic_fallback"]["priority"] <= 70

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
    assert unknown[0]["reasoning_scope"] == "unknown_package_scope"


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
    rows = experiments["experiments"][0]["database_precedents"]["top_precedent_rows"]
    assert [row["doi"] for row in rows] == ["10.0000/good"]
    assert "Ba2+" not in str(rows)
    assert "dye" not in str(rows).lower()


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
    assert card["template_id"] == "EXTRACTION_TIMING_TEMPLATE"
    assert card["database_precedents"]["top_precedent_rows"] == []
    assert card["database_precedents"]["sqlite_precedent_quality"] == "weak_or_none"
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
