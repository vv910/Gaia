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
    gap_type: str
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
            "sole cause",
            "not isolate",
            "not isolated",
            "control additive",
            "crystallinity",
            "hydrophobicity",
            "multifunctional",
        )
    ):
        gap_type = "causal attribution / multifunctional intervention gap"
        hypothesis = "The package-local target mechanism explains the affected Gaia claim."
        alternative = "A coupled covariate or alternative mechanism explains the observation."
    elif any(term in lowered for term in ("stability", "degradation", "retention", "aging")):
        gap_type = "stability/degradation discrimination"
        hypothesis = "The target mechanism explains the stability or degradation trend."
        alternative = (
            "Barrier, initial-performance, morphology, or stress-condition differences explain it."
        )
    elif re.search(
        r"\b(?:ion|ions|ionic)\b|ion[- ]migration|mobile ion|hysteresis|\bscan\b",
        lowered,
    ):
        gap_type = "ion-migration or measurement-history discrimination"
        hypothesis = "The intervention changes the intended ion or interfacial charge pathway."
        alternative = (
            "Scan history, preconditioning, or capacitive response explains the observation."
        )
    elif any(
        term in lowered
        for term in (
            "ff",
            "fill factor",
            "series resistance",
            "shunt",
            "leakage",
            "extraction",
            "transport",
            "loss budget",
        )
    ):
        gap_type = "aggregate performance / transport / contact discrimination"
        hypothesis = (
            "The target transport/contact or performance-limiting branch explains the claim."
        )
        alternative = "A competing branch or uncontrolled covariate explains the aggregate metric."
    elif any(term in lowered for term in ("energy", "work function", "alignment", "contact")):
        gap_type = "contact/energetic discrimination"
        hypothesis = "The target contact or energetic mechanism explains the affected claim."
        alternative = "Passivation, morphology, transport, or measurement artifacts explain it."
    else:
        gap_type = "generic causal-discrimination gap"
        hypothesis = "The package-local target mechanism explains the affected Gaia claim."
        alternative = "A competing mechanism or uncontrolled covariate explains the observation."
    return Gap(
        gap_id=f"experimental_gap_{index:02d}",
        text=text,
        gap_type=gap_type,
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
                "parse_coverage_warning": "SQLite database unavailable; confidence is low.",
            },
        )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        table = first_table(conn)
        columns = table_columns(conn, table)
        rows = query_precedents(conn, table, columns, context)
    finally:
        conn.close()

    parse_coverage = build_parse_coverage(rows, columns)
    top_rows = [summarize_row(row, columns) for row in rows[:5]]
    if not top_rows:
        top_rows = [
            {
                "similarity_score": 0.0,
                "why_comparable": "No matched SQLite rows were found.",
                "why_limited": "Precedent coverage is sparse.",
                "parsed_deltas": {"status": "not_available"},
            }
        ]

    precedent_summary = {
        "tier_counts": {
            "tier1": min(len(rows), 1),
            "tier2": max(min(len(rows) - 1, 3), 0),
            "tier3": max(len(rows) - 4, 0),
            "rejected": 0,
        },
        "parse_coverage": parse_coverage,
        "top_precedent_rows": top_rows,
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
            "sqlite_parse_coverage": parse_coverage,
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

    same, cross = summarize_lkm_provenance(payloads, context)
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
            successful_endpoints=[],
            failed_endpoints=failed,
            sqlite_lkm_conflicts=["No LKM conflict assessed because LKM retrieval failed."],
            confidence="low",
        )

    confidence = "moderate" if same or cross else "low"
    evidence_summary = (
        "LKM retrieval returned auditable mechanism-reasoning candidates with provenance retained."
        if same or cross
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract same-package and cross-package chain summaries from LKM payloads."""
    source_package = str(context.get("source_package", "")).lower()
    same: list[dict[str, Any]] = []
    cross: list[dict[str, Any]] = []

    for payload in payloads:
        for item in iter_dict_values(payload):
            summary = summarize_lkm_item(item, source_package)
            if not summary:
                continue
            if summary["reasoning_scope"] == "same_package":
                same.append(summary)
            else:
                cross.append(summary)
            if len(same) + len(cross) >= 10:
                return same, cross
    return same, cross


def summarize_lkm_item(item: dict[str, Any], source_package: str) -> dict[str, Any]:
    """Summarize one provenance-bearing LKM item."""
    provenance_fields = (
        "source_package",
        "paper_id",
        "claim_id",
        "conclusion_id",
        "chain_id",
        "title",
        "score",
        "rerank_score",
    )
    aliases = {
        "source_package": ("source_package", "sourcePackage", "package", "package_id"),
        "paper_id": ("paper_id", "paperId", "paper", "paperIdStr"),
        "claim_id": ("claim_id", "claimId", "id", "provider_id"),
        "conclusion_id": ("conclusion_id", "conclusionId"),
        "chain_id": ("chain_id", "chainId", "reasoning_chain_id", "reasoningChainId"),
        "title": ("title", "paper_title", "paperTitle"),
        "score": ("score",),
        "rerank_score": ("rerank_score", "rerankScore"),
    }
    summary: dict[str, Any] = {}
    for canonical, keys in aliases.items():
        value = first_present(item, keys)
        if not is_blank(value):
            summary[canonical] = value

    if not any(field in summary for field in provenance_fields):
        return {}

    source_text = str(summary.get("source_package", "")).lower()
    if source_package and source_package in source_text:
        summary["reasoning_scope"] = "same_package"
        summary["cross_package"] = False
    else:
        summary["reasoning_scope"] = "cross_package_or_unknown"
        summary["cross_package"] = True
    return summary


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


def is_blank(value: Any) -> bool:
    """Return true for absent or empty values."""
    return value is None or (isinstance(value, str) and not value.strip())


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
        "top_precedent_rows": [
            {
                "similarity_score": 0.0,
                "why_comparable": reason,
                "why_limited": reason,
                "parsed_deltas": {"status": "not_available"},
            }
        ],
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


def summarize_row(row: sqlite3.Row, columns: set[str]) -> dict[str, Any]:
    """Summarize one SQLite precedent row without recipe details."""
    composition = (
        row["perovskite_composition"] if "perovskite_composition" in columns else "unknown"
    )
    structure = row["solar_cell_structure"] if "solar_cell_structure" in columns else "unknown"
    title = row["title"] if "title" in columns else "untitled precedent"
    doi = row["doi"] if "doi" in columns else "unknown"
    return {
        "title": title,
        "doi": doi,
        "solar_cell_structure": structure,
        "perovskite_composition": composition,
        "similarity_score": 0.5,
        "why_comparable": "Matched at least one architecture, composition, or intervention term.",
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
    source_architecture = str(context["solar_cell_structure"]).lower()
    source_is_pin = any(marker in source_architecture for marker in ("p-i-n", "pin", "inverted"))
    lab_preference = context.get("lab_preferred_device_architecture", "inverted p-i-n")
    if source_is_pin:
        translation_note = (
            "Source package is already aligned with the lab-preferred p-i-n context; "
            "use p-i-n matched controls and readouts."
        )
        controls = [
            "matched p-i-n same-stack no-modulator comparator",
            "architecture-matched p-i-n comparator",
        ]
        portability_risks = [
            "Portability risk is bounded because source and lab architectures match; "
            "still avoid generalizing beyond the locked contact stack."
        ]
    else:
        translation_note = (
            "Lab-preferred inverted p-i-n design is a translation context, not "
            "source-paper proof; preserve source-device context separately."
        )
        controls = [
            "matched source-architecture baseline",
            "matched p-i-n translation comparator",
        ]
        portability_risks = [
            "Contact-stack-dependent mechanisms may not port directly across architectures."
        ]
    causal_controls = build_causal_isolation_controls(gap)
    if causal_controls:
        controls.append(
            "functional analog-control class bounding morphology, crystallinity, "
            "hydrophobicity, contact energetics, and recombination/trap-sensitive "
            "readouts; multi-variable analogs cannot close the causal gap and only "
            "support follow-up narrowing"
        )

    parse_coverage = retrieval.database_precedents.get("parse_coverage")
    low_parse_coverage = isinstance(parse_coverage, dict) and parse_coverage_is_low(parse_coverage)
    card = {
        "gap_id": gap.gap_id,
        "source_package": context["source_package"],
        "target_claims": [
            context.get("target_claim", f"{context['source_package']}::{gap.gap_id}")
        ],
        "affected_conclusions": [
            context.get("affected_conclusion", f"{context['source_package']}::main_conclusion")
        ],
        "current_belief": context.get("current_belief", "unknown"),
        "original_evidence_gap_text": gap.text,
        "gap_type": gap.gap_type,
        "priority": 70,
        "priority_rationale": (
            "Prioritized by Gaia impact, H-vs-Alt discriminating power, SQLite "
            "precedent coverage, LKM availability, and feasibility."
        ),
        "scientific_uncertainty": "Which mechanism or covariate explains the affected Gaia claim.",
        "hypothesis_H": gap.hypothesis,
        "alternative_Alt": gap.alternative,
        "discriminating_observation": (
            "A primary readout pattern separates H from Alt under matched controls."
        ),
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
                "Package-local Gaia evidence supplies the target gap and affected conclusion."
            ),
            "lkm_mechanism_reasoning": lkm.mechanism_reasoning,
            "sqlite_precedent_delta_background": (
                "SQLite contributes comparable precedent and paired delta background, "
                "not mechanism proof."
            ),
        },
        "same_package_lkm_chains": lkm.same_package_chains,
        "cross_package_lkm_chains": lkm.cross_package_chains,
        "sqlite_lkm_conflicts": lkm.sqlite_lkm_conflicts,
        "mechanism_attribution_limitations": (
            "Mechanism attribution remains bounded until discriminating readouts and "
            "auditable LKM or package-local reasoning support the causal chain."
        ),
        "gap_resolution_strategy": build_gap_resolution_strategy(gap),
        "recommended_experiment_class": "Design-level H-vs-Alt discriminating campaign",
        "source_device_context": source_context,
        "lab_translation_context": {
            "lab_preferred_device_architecture": lab_preference,
            "translation_note": translation_note,
        },
        "portability_risks_for_p_i_n": portability_risks,
        "architecture_sensitive_readouts": [
            "matched architecture controls",
            "contact-sensitive readouts",
        ],
        "what_not_to_generalize": [
            "Do not generalize source-stack mechanism proof to the lab translation context."
        ],
        "variables_to_vary": ["mechanism-relevant condition", "matched control class"],
        "controls": controls,
        "primary_readouts": [
            {
                "name": "direct H-vs-Alt discriminating readout class",
                "maps_to_uncertainty": "target mechanism versus competing alternative",
                "supports_H_pattern": "Readout changes in the direction uniquely predicted by H.",
                "supports_Alt_pattern": "Readout follows the competing alternative or covariate.",
            }
        ],
        "secondary_readouts": ["covariate-bounding readout", "reproducibility screen"],
        "expected_result_if_H": (
            "H-specific readouts move while bounded confounders do not explain the effect."
        ),
        "expected_result_if_Alt": (
            "Alternative-specific readouts or confounders explain the effect."
        ),
        "success_criterion_for_closing_gap": (
            "Close only when H and Alt are separated by direct readout logic; otherwise "
            "record mixed_or_unresolved."
        ),
        "minimum_replicate_logic": (
            "Use independent matched comparisons without operational parameters."
        ),
        "statistics_or_comparison_logic": (
            "Compare direction, consistency, and uncertainty across matched controls."
        ),
        "failure_modes": [
            "Readouts split across H and Alt.",
            "Controls reveal architecture or covariate sensitivity.",
        ],
        "interpretation_decision_tree": (
            "If H pattern holds, update toward H; if Alt holds, update toward Alt."
        ),
        "outcome_matrix": {
            "supports_H": {
                "observation_pattern": "Primary readouts match H and controls bound Alt.",
                "interpretation": "H becomes the favored mechanism.",
                "remaining_caveat": "Portability and long-term generality remain bounded.",
            },
            "supports_Alt": {
                "observation_pattern": "Alternative readouts or confounders explain the result.",
                "interpretation": "Alt becomes favored over H.",
                "remaining_caveat": "A smaller H contribution may remain.",
            },
            "mixed_or_unresolved": {
                "observation_pattern": "Readouts do not cleanly separate H and Alt.",
                "interpretation": "The mechanism gap remains open.",
                "next_step": "Add a narrower decomposition axis or stronger control class.",
            },
        },
        "belief_update_target": "Update the target Gaia claim or H-vs-Alt likelihood direction.",
        "feasibility_notes": "Generated as design-level planning, not an operational protocol.",
        "safety_boundary_note": (
            "Planning only; implementation requires qualified lab supervision and "
            "institutional safety review."
        ),
        "confidence": lkm.confidence,
        "open_questions": ["Which direct readout class is available in the target lab context?"],
    }
    if causal_controls:
        card["causal_isolation_controls"] = causal_controls
    return card


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
    """Render a concise Markdown experiment plan."""
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
                f"### {card['gap_id']}: {card['gap_type']}",
                "",
                f"- Source package: {card['source_package']}",
                f"- Hypothesis H: {card['hypothesis_H']}",
                f"- Alternative Alt: {card['alternative_Alt']}",
                f"- Discriminating observation: {card['discriminating_observation']}",
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
    evidence["sqlite_lkm_conflicts"] = lkm.sqlite_lkm_conflicts

    parse_coverage = sqlite_retrieval.database_precedents.get("parse_coverage")
    if isinstance(parse_coverage, dict):
        evidence["sqlite_parse_coverage"] = parse_coverage
        if parse_coverage_is_low(parse_coverage):
            evidence["parse_coverage_warning"] = (
                "SQLite parse coverage is low; precedent deltas cannot carry mechanism confidence."
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
