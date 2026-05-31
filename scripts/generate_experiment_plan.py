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

import yaml

# ruff: noqa: E501

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from photovoltaic_metric_templates import build_ff_loss_budget_card  # noqa: E402

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
class RetrievalSummary:
    """Bounded SQLite retrieval summary for one gap."""

    queries_run: list[str]
    database_precedents: dict[str, Any]
    retrieval_evidence: dict[str, Any]


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


@dataclass(frozen=True)
class LkmCredential:
    """Resolved LKM access credential without exposing the secret value."""

    access_key: str | None
    source: str


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
    """Build a normalized gap from raw evidence-gap text."""
    lowered = text.lower()
    if any(
        term in lowered
        for term in (
            "theoretical gap",
            "device model",
            "trap/recombination parameters",
            "trap_recombination_supports_ff",
            "reduced nonradiative recombination to ff",
            "trap/recombination-to-ff",
        )
    ):
        gap_family = "device_model_link"
        gap_type = "device-model link gap"
        template_id = "DEVICE_MODEL_LINK_TEMPLATE"
        hypothesis = (
            "Measured trap/recombination reductions quantitatively account for the "
            "affected device-performance claim under bounded contact and transport losses."
        )
        alternative = (
            "Measured trap/recombination changes are insufficient, and contact, "
            "resistance, or barrier terms dominate the affected claim."
        )
    elif any(
        term in lowered
        for term in (
            "transient extraction",
            "carrier collection",
            "extraction timing",
            "transport_extraction_supports_ff",
            "collection dynamics",
        )
    ):
        gap_family = "extraction_timing"
        gap_type = "transient extraction / carrier-collection timing gap"
        template_id = "EXTRACTION_TIMING_TEMPLATE"
        hypothesis = (
            "The intervention improves the affected claim partly by improving extraction "
            "or carrier-collection dynamics."
        )
        alternative = (
            "The affected performance trend is mostly recombination, morphology, static "
            "contact energetics, or contact-only shifts while extraction timing is unchanged."
        )
    elif re.search(
        r"\b(?:ion|ions|ionic)\b|ion[- ]migration|mobile ion|hysteresis|scan-direction|"
        r"bias-history|hysteresis_ion_migration_path|hysteresis_path_supports_ff",
        lowered,
    ):
        gap_family = "ion_migration_hysteresis"
        gap_type = "ion-migration / hysteresis discrimination gap"
        template_id = "ION_MIGRATION_HYSTERESIS_TEMPLATE"
        hypothesis = (
            "The intervention reduces mobile-ion or interfacial charge-accumulation "
            "effects that contribute to hysteresis-linked device loss."
        )
        alternative = (
            "The hysteresis or scan-history response is mainly a contact, barrier, "
            "recombination, or protocol effect."
        )
    elif any(
        term in lowered
        for term in (
            "sole cause attribution",
            "sole cause",
            "passivation not isolated",
            "not isolate",
            "not isolated",
            "control additive",
            "single function",
            "multifunctional intervention",
            "multifunctional",
            "morphology",
            "crystallinity",
            "hydrophobicity",
            "passivation_evidence_bundle",
        )
    ):
        gap_family = "causal_isolation_analog"
        gap_type = "causal attribution / multifunctional intervention gap"
        template_id = "CAUSAL_ISOLATION_ANALOG_TEMPLATE"
        hypothesis = (
            "The target coordination/passivation mechanism remains a causal contributor "
            "after morphology, hydrophobicity, crystallinity, and contact covariates "
            "are bounded."
        )
        alternative = (
            "The affected performance gain is mainly explained by morphology, "
            "crystallinity, hydrophobicity, contact changes, or process covariates."
        )
    elif any(term in lowered for term in ("stability", "degradation", "retention", "aging")):
        gap_family = "generic_fallback"
        gap_type = "stability/degradation discrimination"
        template_id = "GENERIC_GAP_TEMPLATE"
        hypothesis = "The target mechanism explains the stability or degradation trend."
        alternative = (
            "Barrier, initial-performance, morphology, or stress-condition differences explain it."
        )
    elif any(
        term in lowered
        for term in (
            "ff",
            "fill factor",
            "ff loss",
            "loss budget",
            "series resistance",
            "shunt",
            "leakage",
            "contact resistance",
            "transport barrier",
            "no_negative_transport_barrier_reported",
            "ff_alone_does_not_prove_passivation",
        )
    ):
        gap_family = "ff_loss_budget"
        gap_type = "FF-loss budget discrimination"
        template_id = "FF_LOSS_BUDGET_TEMPLATE"
        hypothesis = (
            "The intervention reduces fill-factor loss mainly through the target "
            "photovoltaic loss branch."
        )
        alternative = (
            "Another photovoltaic loss branch or measurement-history contribution explains "
            "the aggregate FF change."
        )
    elif any(term in lowered for term in ("energy", "work function", "alignment", "contact")):
        gap_family = "generic_fallback"
        gap_type = "contact/energetic discrimination"
        template_id = "GENERIC_GAP_TEMPLATE"
        hypothesis = "The target contact or energetic mechanism explains the affected claim."
        alternative = "Passivation, morphology, transport, or measurement artifacts explain it."
    else:
        gap_family = "generic_fallback"
        gap_type = "generic causal-discrimination gap"
        template_id = "GENERIC_GAP_TEMPLATE"
        hypothesis = "The package-local target mechanism explains the affected Gaia claim."
        alternative = "A competing mechanism or uncontrolled covariate explains the observation."
    return Gap(
        gap_id=f"experimental_gap_{index:02d}",
        text=text,
        gap_family=gap_family,
        gap_type=gap_type,
        template_id=template_id,
        hypothesis=hypothesis,
        alternative=alternative,
    )


def check_context(context: dict[str, Any]) -> list[str]:
    """Return missing required context fields."""
    return [field for field in REQUIRED_CONTEXT_FIELDS if not context.get(field)]


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
                "unknown_package_lkm_chains": [],
                "parse_coverage_warning": "SQLite database unavailable; confidence is low.",
            },
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table = first_table(conn)
        columns = table_columns(conn, table)
        rows = query_precedents(conn, table, columns, context)
        qualified_rows = filter_precedent_rows(rows, columns, context, gap)
    finally:
        conn.close()

    parse_coverage = build_parse_coverage(qualified_rows, columns)
    top_rows = [summarize_row(row, columns, context, gap) for row in qualified_rows[:5]]
    sqlite_precedent_quality = "usable_background" if top_rows else "weak_or_none"

    precedent_summary = {
        "tier_counts": {
            "tier1": min(len(qualified_rows), 1),
            "tier2": max(min(len(qualified_rows) - 1, 3), 0),
            "tier3": max(len(qualified_rows) - 4, 0),
            "rejected": max(len(rows) - len(qualified_rows), 0),
        },
        "parse_coverage": parse_coverage,
        "top_precedent_rows": top_rows,
        "sqlite_precedent_quality": sqlite_precedent_quality,
        "parse_coverage_warning": sqlite_precedent_quality == "weak_or_none",
        "source_role": (
            "SQLite is for precedent discovery, stack/intervention matching, and "
            "paired delta background only; it is not mechanism proof."
        ),
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
            "unknown_package_lkm_chains": [],
            "sqlite_parse_coverage": parse_coverage,
            "sqlite_precedent_quality": sqlite_precedent_quality,
            "parse_coverage_warning": sqlite_precedent_quality == "weak_or_none",
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
    query = build_lkm_query(gap, context)
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
            "query": query,
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
            "query": query,
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
        )

    with LKMClient(access_key=credential.access_key) as client:
        knowledge_body = {
            "query": query,
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
            "query": query,
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

    same, cross, unknown = summarize_lkm_provenance(payloads, context)
    if not successful:
        write_json(
            lkm_dir / f"{gap.gap_id}_lkm_unavailable.json",
            {
                "status": "lkm_unavailable",
                "gap_id": gap.gap_id,
                "query": query,
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
        )

    confidence = "moderate" if same or cross or unknown else "low"
    evidence_summary = (
        "LKM retrieval returned auditable mechanism-reasoning candidates with provenance retained."
        if same or cross or unknown
        else "LKM endpoints succeeded but returned no provenance-bearing chains; "
        "mechanism attribution remains bounded."
    )
    return LkmSummary(
        queries_run=[f"{endpoint}: {query}" for endpoint in successful],
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
    )


def build_lkm_query(gap: Gap, context: dict[str, Any]) -> str:
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
    unknown: list[dict[str, Any]] = []

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
                unknown.append(summary)
            if len(same) + len(cross) + len(unknown) >= 10:
                return same, cross, unknown
    return same, cross, unknown


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
    }
    summary: dict[str, Any] = {}
    for canonical, keys in aliases.items():
        value = first_present_deep(item, keys)
        if not is_blank(value):
            summary[canonical] = value

    if not any(field in summary for field in provenance_fields):
        return {}

    scope = resolve_lkm_scope(summary, resolver)
    if scope == "same_package":
        summary["reasoning_scope"] = "same_package"
        summary["cross_package"] = False
    elif scope == "cross_package":
        summary["reasoning_scope"] = "cross_package"
        summary["cross_package"] = True
    else:
        summary["reasoning_scope"] = "unknown_package_scope"
        summary["cross_package"] = None
    return summary


def build_source_resolver(context: dict[str, Any]) -> dict[str, set[str]]:
    """Build normalized source identifiers for same/cross-package LKM checks."""
    resolver = {"packages": set(), "dois": set(), "local_ids": set(), "paper_ids": set()}
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


def resolve_lkm_scope(summary: dict[str, Any], resolver: dict[str, set[str]]) -> str:
    """Return same_package, cross_package, or unknown_package_scope."""
    same_checks = (
        ("source_package", "packages", False),
        ("local_id", "local_ids", False),
        ("doi", "dois", True),
        ("paper_id", "paper_ids", False),
    )
    comparable_seen = False
    for field_name, resolver_key, is_doi in same_checks:
        value = summary.get(field_name)
        if is_blank(value):
            continue
        comparable_seen = True
        normalized = normalize_identifier(value, doi=is_doi)
        candidates = resolver.get(resolver_key, set())
        if normalized and identifier_matches(normalized, candidates):
            return "same_package"
        if resolver_key in {"packages", "dois"} and candidates:
            return "cross_package"
    return "cross_package" if comparable_seen and resolver["paper_ids"] else "unknown_package_scope"


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
        "sqlite_precedent_quality": "weak_or_none",
        "parse_coverage_warning": True,
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
        "causal_isolation_analog": ("passivation", "trap", "coordination", "morphology"),
        "ff_loss_budget": ("ff", "fill factor", "passivation", "recombination", "contact"),
        "extraction_timing": ("extraction", "collection", "transport", "transient"),
        "ion_migration_hysteresis": ("ion", "hysteresis", "bias", "scan"),
        "device_model_link": ("trap", "recombination", "model", "ff"),
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
        "parsed_deltas": {"status": "screening_only"},
    }


def parse_numeric(value: Any) -> float | None:
    """Parse a loose numeric value when possible."""
    if value is None:
        return None
    match = re.search(r"[-+]?\d*\.?\d+", str(value))
    if match is None:
        return None
    return float(match.group(0))


def build_card(
    gap: Gap, context: dict[str, Any], retrieval: RetrievalSummary, lkm: LkmSummary
) -> dict[str, Any]:
    """Build one experiment-design card."""
    source_context = {
        "solar_cell_structure": context["solar_cell_structure"],
        "cell_stack_sequence": context["cell_stack_sequence"],
        "perovskite_composition": context["perovskite_composition"],
        "intervention_location": context["intervention_location"],
        "modulator_material_or_family": context["modulator_material_or_family"],
    }
    translation = build_device_translation_policy(context)
    domain = build_domain_specific_template(gap, context)
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
    sqlite_weak = retrieval.database_precedents.get("sqlite_precedent_quality") == "weak_or_none"
    priority = score_priority(gap, context, lkm, sqlite_weak=sqlite_weak)
    confidence = determine_card_confidence(gap, lkm, sqlite_weak=sqlite_weak)
    card = {
        "gap_id": gap.gap_id,
        "gap_family": gap.gap_family,
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
        "priority": priority,
        "priority_rationale": build_priority_rationale(
            gap, priority, context, lkm, sqlite_weak=sqlite_weak
        ),
        "scientific_uncertainty": domain["scientific_uncertainty"],
        "hypothesis_H": domain["hypothesis_H"],
        "alternative_Alt": domain["alternative_Alt"],
        "discriminating_observation": domain["discriminating_observation"],
        "database_queries_run": retrieval.queries_run,
        "database_precedents": retrieval.database_precedents,
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
        "lkm_queries_run": lkm.queries_run,
        "lkm_role": lkm.role,
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
        "sqlite_lkm_conflicts": lkm.sqlite_lkm_conflicts,
        "mechanism_attribution_limitations": (
            build_mechanism_limitations(gap, lkm, sqlite_weak=sqlite_weak)
        ),
        "gap_resolution_strategy": build_gap_resolution_strategy(gap),
        "recommended_experiment_class": domain["recommended_experiment_class"],
        "source_device_context": source_context,
        "lab_translation_context": translation["lab_translation_context"],
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
        "expected_result_if_H": domain["expected_result_if_H"],
        "expected_result_if_Alt": domain["expected_result_if_Alt"],
        "success_criterion_for_closing_gap": domain["success_criterion_for_closing_gap"],
        "minimum_replicate_logic": (
            "Use independent matched device populations and batch-separated comparisons; "
            "this planning card intentionally omits operational preparation parameters."
        ),
        "statistics_or_comparison_logic": domain["statistics_or_comparison_logic"],
        "failure_modes": domain["failure_modes"],
        "interpretation_decision_tree": domain["interpretation_decision_tree"],
        "outcome_matrix": domain["outcome_matrix"],
        "belief_update_target": "Update the target Gaia claim or H-vs-Alt likelihood direction.",
        "feasibility_notes": "Generated as design-level planning, not an operational protocol.",
        "safety_boundary_note": (
            "Planning only; implementation requires qualified lab supervision and "
            "institutional safety review."
        ),
        "confidence": confidence,
        "open_questions": domain["open_questions"],
        "lkm_scope_summary": summarize_lkm_scope_counts(lkm),
    }
    for optional_key in (
        "loss_channel_budget",
        "causal_isolation_controls",
        "model_inputs",
        "model_outputs",
        "falsification_criterion",
    ):
        if optional_key in domain:
            card[optional_key] = domain[optional_key]
    if causal_controls:
        card["causal_isolation_controls"] = causal_controls
    return card


def build_domain_specific_template(gap: Gap, context: dict[str, Any]) -> dict[str, Any]:
    """Dispatch gap families to domain-specific experiment-card templates."""
    if gap.gap_family == "ff_loss_budget":
        template = build_ff_loss_budget_card(gap, context)
    elif gap.gap_family == "extraction_timing":
        template = build_extraction_timing_template(context)
    elif gap.gap_family == "ion_migration_hysteresis":
        template = build_ion_migration_hysteresis_template(context)
    elif gap.gap_family == "causal_isolation_analog":
        template = build_causal_isolation_analog_template(context)
    elif gap.gap_family == "device_model_link":
        template = build_device_model_link_template(context)
    else:
        template = build_unresolved_generic_template(gap)
    return with_domain_defaults(template, gap)


def with_domain_defaults(template: dict[str, Any], gap: Gap) -> dict[str, Any]:
    """Fill common card fields not owned by a domain module."""
    defaults: dict[str, Any] = {
        "template_id": gap.template_id,
        "template_resolution_status": (
            "unresolved_generic_fallback"
            if gap.gap_family == "generic_fallback"
            else "resolved_domain_specific"
        ),
        "gap_type_specific_title": gap.gap_type,
        "gap_type": gap.gap_type,
        "recommended_experiment_class": "Design-level H-vs-Alt discriminating campaign",
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


def build_extraction_timing_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for transient extraction and carrier-collection gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "EXTRACTION_TIMING_TEMPLATE",
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
        "template_id": "CAUSAL_ISOLATION_ANALOG_TEMPLATE",
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


def build_device_model_link_template(context: dict[str, Any]) -> dict[str, Any]:
    """Template for trap/recombination-to-device-model gaps."""
    modulator = str(context.get("modulator_material_or_family", "the intervention"))
    return {
        "template_id": "DEVICE_MODEL_LINK_TEMPLATE",
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
    if source_is_pin:
        lab_translation_context = {
            "lab_preferred_device_architecture": lab_preference,
            "translation_status": "source_context_already_p_i_n",
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
    readouts = [
        "architecture-matched photovoltaic loss-budget readout",
        "contact-selective extraction or barrier diagnostic class",
        "recombination/trap-sensitive readout in p-i-n stack",
        "hysteresis/bias-history readout if relevant",
    ]
    return {
        "lab_translation_context": lab_translation_context,
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


def score_priority(gap: Gap, context: dict[str, Any], lkm: LkmSummary, *, sqlite_weak: bool) -> int:
    """Score card priority by gap family and evidence-source support."""
    base_ranges = {
        "ff_loss_budget": (94, 90, 98),
        "causal_isolation_analog": (91, 88, 95),
        "device_model_link": (87, 82, 92),
        "extraction_timing": (86, 80, 92),
        "ion_migration_hysteresis": (81, 75, 88),
        "generic_fallback": (62, 40, 70),
    }
    base, lower, upper = base_ranges.get(gap.gap_family, (62, 40, 70))
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
    if gap.gap_family == "generic_fallback":
        score = min(score, 70)
    return max(lower, min(score, upper))


def build_priority_rationale(
    gap: Gap,
    priority: int,
    context: dict[str, Any],
    lkm: LkmSummary,
    *,
    sqlite_weak: bool,
) -> str:
    """Return a concrete rationale for priority ranking."""
    family_reasons = {
        "ff_loss_budget": "directly decomposes the photovoltaic metric branch that can otherwise masquerade as mechanism support",
        "causal_isolation_analog": "tests whether a multifunctional intervention has a causal passivation contribution after covariates are bounded",
        "device_model_link": "checks whether trap/recombination evidence quantitatively supports the device-level conclusion",
        "extraction_timing": "tests carrier-collection timing as a separable branch from recombination and contact alternatives",
        "ion_migration_hysteresis": "assigns hysteresis-linked loss toward ion/charge accumulation or contact/protocol alternatives",
        "generic_fallback": "lacks a resolved domain template and is capped until a concrete module owns it",
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
        f"Priority {priority}: this {gap.gap_family} card {family_reasons[gap.gap_family]}; "
        f"{lkm_reason}; {sqlite_reason}; source architecture is {source_arch} with "
        "inverted p-i-n translation considered separately."
    )


def determine_card_confidence(gap: Gap, lkm: LkmSummary, *, sqlite_weak: bool) -> str:
    """Set mechanism confidence without letting SQLite raise attribution strength."""
    if gap.gap_family == "generic_fallback":
        return "low"
    if "lkm_unavailable" in " ".join(lkm.queries_run).lower():
        return "low"
    if lkm.same_package_chains:
        return "moderate" if not sqlite_weak else "low"
    if lkm.cross_package_chains or lkm.unknown_package_chains:
        return "moderate" if not sqlite_weak else "low"
    return "low"


def build_mechanism_limitations(gap: Gap, lkm: LkmSummary, *, sqlite_weak: bool) -> str:
    """Explain the limits on mechanism attribution for the card."""
    parts = [
        "Mechanism attribution requires the declared H-vs-Alt readouts; SQLite precedent "
        "or paired deltas cannot close the mechanism gap."
    ]
    if lkm.cross_package_chains:
        parts.append("Cross-package LKM chains are transfer analogies, not source-paper proof.")
    if lkm.unknown_package_chains:
        parts.append(
            "Unknown-scope LKM chains are retained for audit but do not raise proof status."
        )
    if sqlite_weak:
        parts.append("SQLite precedent quality is weak_or_none for this gap.")
    if gap.gap_family == "generic_fallback":
        parts.append("The unresolved generic fallback cannot support a mechanism update.")
    return " ".join(parts)


def summarize_lkm_scope_counts(lkm: LkmSummary) -> dict[str, int]:
    """Return compact LKM scope counts for Markdown/YAML display."""
    return {
        "same_package": len(lkm.same_package_chains),
        "cross_package": len(lkm.cross_package_chains),
        "unknown_package_scope": len(lkm.unknown_package_chains),
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
    lines = [
        "# Experiment Plan",
        "",
        "SQLite is for precedent discovery, stack/intervention matching, and paired "
        "delta background only; it is not mechanism proof.",
        "",
        "## Ranked Roadmap",
    ]
    for card in cards:
        lines.extend(
            [
                "",
                f"### {card['gap_id']}: {card.get('gap_type_specific_title', card['gap_type'])}",
                "",
                f"- Source package: {card['source_package']}",
                f"- Template: {card.get('template_id')} ({card.get('template_resolution_status')})",
                f"- Hypothesis H: {card['hypothesis_H']}",
                f"- Alternative Alt: {card['alternative_Alt']}",
                f"- Discriminating observation: {card['discriminating_observation']}",
                "- Primary readout classes: "
                + "; ".join(readout_names(card.get("primary_readouts", []))),
                f"- p-i-n translation note: {translation_note(card)}",
                f"- SQLite role: {card['sqlite_role']}",
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
            "unknown_package_scope": len(card.get("unknown_package_lkm_chains") or []),
        }
    return (
        f"same={summary.get('same_package', 0)}, "
        f"cross={summary.get('cross_package', 0)}, "
        f"unknown={summary.get('unknown_package_scope', 0)}"
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
    evidence["unknown_package_lkm_chains"] = lkm.unknown_package_chains
    evidence["sqlite_lkm_conflicts"] = lkm.sqlite_lkm_conflicts

    parse_coverage = sqlite_retrieval.database_precedents.get("parse_coverage")
    if isinstance(parse_coverage, dict):
        evidence["sqlite_parse_coverage"] = parse_coverage
        if parse_coverage_is_low(parse_coverage) or (
            sqlite_retrieval.database_precedents.get("sqlite_precedent_quality") == "weak_or_none"
        ):
            evidence["parse_coverage_warning"] = True
            evidence["parse_coverage_warning_reason"] = (
                "SQLite parse coverage is low or precedent quality is weak_or_none; "
                "precedent deltas cannot carry mechanism confidence."
            )
    evidence["sqlite_precedent_quality"] = sqlite_retrieval.database_precedents.get(
        "sqlite_precedent_quality", "weak_or_none"
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
        if not isinstance(value, str) or "/" not in value:
            continue
        numerator, denominator = value.split("/", 1)
        try:
            parsed = float(numerator)
            total = float(denominator)
        except ValueError:
            continue
        if total > 0 and parsed / total < 0.5:
            return True
    return False


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
        "gaps": [
            build_retrieval_evidence(gap, context, retrieval, lkm)
            for gap, retrieval, lkm in zip(gaps, retrievals, lkm_summaries, strict=True)
        ]
    }

    write_yaml(output_dir / "experiments.yaml", {"experiments": cards})
    write_yaml(output_dir / "retrieval_evidence.yaml", retrieval_evidence)
    (output_dir / "EXPERIMENT_PLAN.md").write_text(render_plan(cards), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
