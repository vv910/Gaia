# SQLite Literature Retrieval

## Database Role And Gate

The local perovskite SQLite database is mandatory:

`/share/hwz/Perovskite_Database_Multiagents/literature_extraction/data_merger/merged_gpt5mini_data_with_chemical_data.db`

Use SQLite for precedent discovery, device/composition/intervention matching,
paired performance deltas, hysteresis evidence, and stability protocol
comparison. SQLite rows are literature precedents, not mechanism proofs.
Performance deltas can motivate or constrain H-vs-Alt hypotheses, but they do
not prove a mechanism by themselves.

Hard role boundary:

- SQLite must not be the primary source for mechanism attribution.
- SQLite tier1/tier2/tier3 evidence may change experiment priority,
  comparability, precedent strength, readout candidates, and risk notes only.
- SQLite deltas must never close a mechanism gap by themselves.
- If SQLite patterns conflict with Gaia package reasoning or LKM reasoning,
  preserve the H-vs-Alt outcome matrix, mark `sqlite_lkm_conflicts`, and do not
  let SQLite override the mechanism chain.
- Every card must include `sqlite_role` with this meaning: SQLite is for
  precedent discovery, stack/intervention matching, and paired delta background
  only; it is not mechanism proof.

For every experimental gap, query this database before drafting the experiment
card. If the database cannot be opened, stop and report the blocker. Do not
replace it with LKM, web search, or package-local citations.

Do not assume the table name. Discover tables first through `sqlite_master` and
columns through `PRAGMA table_info`.

```python
import sqlite3

db_path = "/share/hwz/Perovskite_Database_Multiagents/literature_extraction/data_merger/merged_gpt5mini_data_with_chemical_data.db"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

tables = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

for (table,) in tables:
    print("TABLE:", table)
    for col in cur.execute(f"PRAGMA table_info({table})").fetchall():
        print(col)
```

## Required Field Families

Use these columns when present. If a column is missing, record that absence in
the retrieval summary rather than silently dropping the evidence dimension.

Architecture:

- `solar_cell_structure`
- `cell_stack_sequence`
- `etl_stack_sequence`
- `htl_stack_sequence`

Absorber:

- `perovskite_composition`
- `perovskite_crystal_detail`
- `perovskite_band_gap`
- `perovskite_pl_max`

Intervention:

- `interfacial_material_abbreviation`
- `interfacial_material_full_name`
- `interfacial_modulator_material_type`
- `interfacial_modulator_material_application_location`
- `interfacial_modulator_application_method`
- `etl_additives_compounds`
- `htl_additives_compounds`

Matched-control performance:

- `jv_reverse_scan_pce_without_modulator`
- `jv_reverse_scan_pce`
- `jv_reverse_scan_j_sc_without_modulator`
- `jv_reverse_scan_j_sc`
- `jv_reverse_scan_v_oc_without_modulator`
- `jv_reverse_scan_v_oc`
- `jv_reverse_scan_ff_without_modulator`
- `jv_reverse_scan_ff`
- `jv_hysteresis_index_without_modulator`
- `jv_hysteresis_index`

Stability and metadata:

- `stability_protocol`
- `stability_measurement_condition`
- `stability_time_total_exposure`
- `stability_pce_end_of_experiment`
- `outdoor_stability_measured`
- `cell_area_measured`
- `jv_certification_institute`
- `jv_light_spectra`
- `title`
- `authors`
- `journal`
- `doi`
- `publication_date`

Chemical descriptors may help identify material families:

- `cas_number`
- `pubchem_id`
- `smiles`
- `molecular_formula`
- `molecular_weight`
- `h_bond_donors`
- `h_bond_acceptors`
- `rotatable_bonds`
- `tpsa`
- `log_p`

Solvent, concentration, and process fields are metadata only. Do not convert
them into actionable recipes or operating steps.

## Query Strategy Per Gap

For each Gaia gap, derive search terms from the locked experiment object:
source package, target device context, absorber, intervention location,
modulator material or family, target metrics, and mechanism terms.

Run tier-building query classes, storing SQL text or a human-readable query
summary in `database_queries_run`:

1. Exact candidate query: same or highly similar architecture, absorber, and
   intervention location.
2. Relaxed candidate query: same architecture or absorber family and same
   intervention location.
3. Modulator/mechanism query: same modulator family, material family, or
   mechanism keywords.
4. Stability query: required when the gap concerns stability, degradation, or
   retention.
5. Performance/contact query: required when the gap concerns an aggregate
   performance metric, transport, recombination, hysteresis, contacts, or
   charge extraction.

Use parameterized SQL for executable queries. Broad `LIKE` matching is allowed
for literature retrieval, but record the terms used and avoid presenting a
substring match as chemical equivalence.

Example retrieval skeleton:

```python
def like(term: str) -> str:
    return f"%{term.strip()}%"

rows = cur.execute(
    f"""
    SELECT *
    FROM {table}
    WHERE lower(coalesce(perovskite_composition, '')) LIKE lower(?)
      AND lower(coalesce(interfacial_modulator_material_application_location, '')) LIKE lower(?)
    LIMIT 200
    """,
    (like(absorber_family), like(interface_location)),
).fetchall()
```

## Numeric Parsing

Many numeric fields are stored as `TEXT`. Parse them defensively. The parser
must return:

- parsed numeric value, or `None`
- inferred unit or scale
- confidence
- original raw string

Required behavior:

- Parse examples such as `23.4%`, `0.81`, `81%`, and `25.1 mA cm-2`.
- Strip percent signs, common units, commas, and whitespace.
- Preserve unit or scale evidence: percent, fraction, voltage, current density,
  hours, unknown.
- Handle missing or unavailable strings without raising.
- Do not silently coerce impossible values, such as negative PCE or FF far
  outside plausible fraction/percent ranges.
- Report parse coverage per metric.

Example helper:

```python
from dataclasses import dataclass
import math
import re


MISSING = {"", "na", "n/a", "none", "null", "-", "--", "not available"}


@dataclass
class ParsedValue:
    value: float | None
    unit_or_scale: str
    confidence: float
    raw: str | None


def parse_numeric(raw: object, *, metric: str | None = None) -> ParsedValue:
    if raw is None:
        return ParsedValue(None, "missing", 0.0, None)
    text = str(raw).strip()
    if text.lower() in MISSING:
        return ParsedValue(None, "missing", 0.0, text)

    unit = "unknown"
    lower = text.lower()
    if "%" in text:
        unit = "percent"
    elif "ma" in lower:
        unit = "mA cm-2"
    elif "v" in lower and metric in {"voc", "voltage"}:
        unit = "V"
    elif "h" in lower and metric in {"stability_time", "time"}:
        unit = "h"

    cleaned = text.replace(",", "")
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", cleaned)
    if not match:
        return ParsedValue(None, unit, 0.0, text)

    value = float(match.group(0))
    if not math.isfinite(value):
        return ParsedValue(None, unit, 0.0, text)

    confidence = 0.8 if unit != "unknown" else 0.6

    if metric in {"pce", "ff", "hysteresis"}:
        if value < 0:
            return ParsedValue(None, unit, 0.0, text)
        if metric == "ff" and unit == "percent" and value > 100:
            return ParsedValue(None, unit, 0.0, text)
        if metric == "ff" and unit != "percent" and value > 1.5:
            # Might be a percent value missing the percent sign.
            unit = "percent_inferred"
            confidence = min(confidence, 0.45)
    if metric == "voc" and value < 0:
        return ParsedValue(None, unit, 0.0, text)
    if metric == "jsc" and value < 0:
        return ParsedValue(None, unit, 0.0, text)

    return ParsedValue(value, unit, confidence, text)
```

## Delta Computation

Compute matched-control deltas only when both values parse with nonzero
confidence. Store raw values, parsed values, unit/scale, and confidence.

- `Delta PCE = PCE_with_modulator - PCE_without_modulator`
- `Delta FF = FF_with_modulator - FF_without_modulator`
- `Delta Voc = Voc_with_modulator - Voc_without_modulator`
- `Delta Jsc = Jsc_with_modulator - Jsc_without_modulator`
- hysteresis improvement when both with/without values are parseable

For FF, normalize comparison scale before subtracting. If one value is a
fraction (`0.81`) and the other is a percent (`81%`), convert both to the same
scale and lower confidence if the scale inference is ambiguous.

Report parse coverage for every card:

```text
PCE delta coverage: 37/112 matched rows parseable (33%)
FF delta coverage: 28/112 matched rows parseable (25%)
Voc delta coverage: 31/112 matched rows parseable (28%)
Jsc delta coverage: 30/112 matched rows parseable (27%)
Hysteresis coverage: 14/112 matched rows parseable (13%)
```

## Tiered Precedent Filtering

Classify every retrieved row into exactly one evidence tier before using it in a
card.

Tier 1:

- same or highly similar `solar_cell_structure`
- similar `cell_stack_sequence`
- similar `perovskite_composition`
- same `interfacial_modulator_material_application_location`
- paired with/without modulator values exist
- parseable FF, Voc, and PCE when relevant

Tier 2:

- same architecture or same absorber family
- same intervention location
- at least two parseable paired metrics

Tier 3:

- same modulator family or same mechanism keywords only
- use for hypothesis generation, not strong support

Low-confidence / reject:

- unknown composition
- unknown stack
- no paired control
- unparseable key metrics
- intervention location missing when the gap is interface-specific

Rows may be useful as cautionary context after rejection, but rejected rows do
not raise confidence or precedent strength.

## Similarity Scoring

Within each tier, rank rows by a transparent `similarity_score` from 0.0 to
1.0. Use this order of importance unless the gap gives a stronger reason:

1. Similarity to target device stack.
2. Similarity to perovskite composition or absorber family.
3. Same intervention location.
4. Same modulator type, material family, or named material.
5. Presence of matched without/with modulator values.
6. Availability of FF, Voc, PCE, Jsc, hysteresis, and stability metrics
   relevant to the gap.
7. Certification, measured area, and light-spectrum metadata when relevant.
8. Citation/provenance metadata such as DOI, journal, and publication date.

Summarize the top precedents in `database_precedents` and the broader query
audit in `retrieval_evidence.yaml`. Include enough provenance to trace the row,
but do not turn solvent or concentration metadata into an actionable recipe.

## Required Card Evidence

Every experiment card must report:

- SQL query summaries in `database_queries_run`
- row counts by query class
- parse coverage for PCE, FF, Voc, Jsc, and hysteresis
- `tier1_count`, `tier2_count`, `tier3_count`, and `rejected_count`
- top precedent rows, each with:
  - `similarity_score`
  - `why_comparable`
  - `why_limited`
  - parsed deltas for available PCE, FF, Voc, Jsc, and hysteresis

For each gap, the database summary should state whether database patterns
support H, support Alt, are mixed, or are too sparse. If SQLite precedent
patterns conflict with LKM mechanism evidence, report the conflict explicitly
in both `database_precedents` and `lkm_evidence_summary`, lower confidence, and
design the experiment around resolving the conflict.

Do not write "SQLite proves", "database confirms the mechanism", or equivalent
mechanism-closure language. A SQLite pattern can raise priority or motivate a
readout; it cannot supply the causal mechanism attribution.

If SQLite is available but parse coverage is low, continue only with an
explicit `database_confidence` limitation in each affected card. The limitation
must say which metrics or tiers are weak and must not upgrade mechanism
confidence from performance deltas alone.
