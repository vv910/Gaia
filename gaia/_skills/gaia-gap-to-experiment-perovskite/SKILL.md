---
name: gaia-gap-to-experiment-perovskite
description: |
  Use after gaia-formalize-fine has produced ANALYSIS.md, .gaia/beliefs.json,
  graph.json or rendered docs data, and package DSL source for a perovskite
  solar-cell knowledge package. Converts broad Gaia Evidence Gaps into
  concrete, ranked perovskite experiment-design cards grounded in Gaia weak
  nodes, local SQLite literature precedents, LKM claim/reasoning-chain
  retrieval, and perovskite readout mappings. This skill requires querying the
  local perovskite SQLite database before drafting experiment cards.
---

# Perovskite Gap-To-Experiment Cards

## Purpose

Turn Gaia Evidence Gaps into concrete research-planning cards for perovskite
solar-cell experiments. Gaia identifies the weak nodes and affected
conclusions; the local SQLite database supplies same-family literature
precedents and matched-control deltas; LKM supplies mechanism claims and
reasoning chains; this skill synthesizes those inputs into ranked cards.

This is a planning skill, not an operational wet-lab protocol generator. It may
discuss variables, controls, readout types, decision criteria, and literature
precedents. It must not output hazardous chemical recipes, exact synthesis
protocols, detailed solvent/concentration instructions, or step-by-step
laboratory procedures. If database fields contain solvent or concentration
values, treat them as literature metadata for matching and provenance only.
Every output must state that implementation requires qualified lab supervision
and institutional safety review.

## Required Inputs

- `ANALYSIS.md` from `gaia-formalize-fine`
- `.gaia/beliefs.json`
- `.github-output/docs/public/data/graph.json`, when available
- `src/<package>/*.py`
- `artifacts/references.json`, when available
- optional `experiment_context.yaml`
- local SQLite database:
  `/share/hwz/Perovskite_Database_Multiagents/literature_extraction/data_merger/merged_gpt5mini_data_with_chemical_data.db`
- optional `LKM_ACCESS_KEY` environment variable for LKM API calls

Do not treat the database as optional. For every experimental gap, local SQLite
retrieval must run before drafting the experiment card.

Use LKM as a complementary evidence source. If `LKM_ACCESS_KEY` is available,
perform LKM retrieval for every gap. If LKM is unavailable or fails, continue
only after marking the LKM evidence gap in the card, lowering confidence, and
explaining that the card is database-grounded but not LKM-validated.

## Real-Package Mode

Real-package mode is the default. Smoke-test mode is allowed only when it is
explicitly requested for synthetic gaps or fixtures.

Every non-smoke-test experiment card must bind to a concrete Gaia package and
device/intervention object. Before drafting cards, recover these fields from
`ANALYSIS.md`, `.gaia/beliefs.json`, `graph.json`, `src/<package>/*.py`, the
SQLite database, `experiment_context.yaml`, or user-provided context:

- `source_package`
- target weak claim or gap node, emitted as `target_claims`
- `affected_conclusions`
- `current_belief`
- original Evidence Gap text from `ANALYSIS.md`, emitted as
  `original_evidence_gap_text`
- `device_context.solar_cell_structure`
- `device_context.cell_stack_sequence` or enough stack detail to name the
  architecture
- `device_context.perovskite_composition`
- `device_context.intervention_location`
- `device_context.modulator_material_or_family`

If any required field cannot be recovered, do not emit a generic experiment
card. Emit a `context_missing_preflight` section instead. The preflight must
list the missing fields, the sources checked, and the minimum user/package
context needed to unlock card generation.

`device_context` must be package-specific. A card whose device context only
says "perovskite solar cell" is not acceptable in real-package mode.

## `experiment_context.yaml`

An optional `experiment_context.yaml` file may lock the experimental object
before cards are generated. Use canonical snake_case keys downstream:

```yaml
source_package:
solar_cell_structure:
cell_stack_sequence:
etl_stack_sequence:
htl_stack_sequence:
perovskite_composition:
perovskite_band_gap:
intervention_location:
modulator_material_or_family:
target_metrics:
available_readouts:
```

The loader may accept obvious human aliases at input time, such as
`solar cell structure` for `solar_cell_structure`, `cell stack sequence` for
`cell_stack_sequence`, `intervention location` for `intervention_location`, and
`modulator material or family` for `modulator_material_or_family`. Normalize
aliases immediately after loading. All generated `experiments.yaml` cards and
reports must use canonical snake_case only.

If both a canonical key and an alias are present with conflicting values, raise
a context preflight error rather than guessing.

## Outputs

- `EXPERIMENT_PLAN.md`: human-readable ranked roadmap
- `experiments.yaml`: machine-readable experiment cards
- optional `retrieval_evidence/`: database query summaries, parse coverage
  reports, and LKM retrieval summaries

## Workflow

1. Inspect package state.
   - Read `ANALYSIS.md` and extract every experimental gap.
   - Read `experiment_context.yaml` when present, normalize aliases, and use it
     to lock the source package, device stack, absorber, intervention location,
     modulator family, target metrics, and available readouts.
   - Read `.gaia/beliefs.json` to attach current beliefs to target claims.
   - Read `graph.json` or package DSL source to map weak nodes to exported
     conclusions and identify bottleneck nodes shared by multiple conclusions.
   - Read `references.json` when available to resolve provenance names.

2. Normalize each gap into the handoff fields required by
   `gaia-formalize-fine`: target node, affected conclusions, gap type, H, Alt,
   discriminating observation, minimum experiment class, controls, readouts,
   and closure criterion. In real-package mode, do not infer placeholders for
   required package/device/intervention fields. If those fields remain missing,
   emit `context_missing_preflight` and stop before card generation.

3. Load the relevant references for this skill:
   - Database retrieval: [references/database-retrieval.md](references/database-retrieval.md)
   - LKM retrieval: [references/lkm-retrieval.md](references/lkm-retrieval.md)
   - Card schema and scoring: [references/experiment-card-schema.md](references/experiment-card-schema.md)
   - Gap taxonomy: [references/perovskite-gap-taxonomy.md](references/perovskite-gap-taxonomy.md)
   - Readout map: [references/perovskite-readout-map.md](references/perovskite-readout-map.md)

4. Classify each gap with the perovskite taxonomy. Select the most specific
   gap type that explains the H-vs-Alt uncertainty. If multiple categories
   apply, choose the primary category for `gap_type` and record secondary
   mechanisms in `scientific_uncertainty` and `secondary_readouts`.

5. Query the local SQLite database for every gap before drafting the card.
   Retrieve and tier precedents by package-specific architecture, absorber,
   intervention location, modulator family, paired with/without values, and
   parseable performance/stability metrics. Compute parse coverage and
   normalized deltas where possible. Record tier1/tier2/tier3/rejected counts
   and top precedent rows with `similarity_score`, `why_comparable`,
   `why_limited`, and parsed deltas.

6. Query LKM for every gap when access is available.
   Retrieve hybrid claim matches, reasoning-chain matches, claim reasoning
   chains, paper graphs, and hydrated variables when returned IDs make that
   useful. Summarize supported mechanisms, competing explanations, premises,
   discriminating observations, provenance papers, and agreement or conflict
   with database patterns.

7. Draft one complete experiment card per experimental gap.
   Do not emit vague suggestions such as "do more characterization" or "study
   stability further." Every card must say what uncertainty is being resolved,
   what H and Alt are, what observation distinguishes them, which controls are
   required, which readouts are primary, how each primary readout maps to a
   specific uncertainty or alternative explanation, and how the result would
   update Gaia interpretation. Include an `outcome_matrix` with
   `supports_H`, `supports_Alt`, and `mixed_or_unresolved`.

8. Rank cards with the 0-100 priority formula in
   `experiment-card-schema.md`. Sort `experiments.yaml` and the roadmap by
   descending priority. Preserve per-gap traceability even when multiple gaps
   can be bundled into one experimental campaign.

9. Write `EXPERIMENT_PLAN.md`, `experiments.yaml`, and optional
   `retrieval_evidence/`. Include safety and feasibility boundaries in both
   human-readable and YAML outputs.

## Hard Gates

- No SQLite retrieval, no experiment card.
- No real-package context, no experiment card. Emit `context_missing_preflight`
  instead of a generic card.
- No card may omit H, Alt, discriminating observation, required controls,
  primary readouts, outcome matrix, and the Gaia belief update target.
- No orphan readouts: every primary readout must map to the uncertainty or
  alternative explanation it discriminates.
- No operational recipes or step-by-step lab procedures.
- No priority score without a rationale tied to Gaia impact, database
  precedent strength, LKM support, discriminating power, and feasibility.
- SQLite performance deltas are precedent evidence only. Do not claim they
  prove a mechanism without LKM or package-local reasoning evidence.
