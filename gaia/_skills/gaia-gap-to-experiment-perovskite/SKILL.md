---
name: gaia-gap-to-experiment-perovskite
description: |
  Use after formalization, prior assignment, inference, review, render,
  publish, README/ANALYSIS/docs writing, and publish-readiness checks are
  complete, but before git commit and git push. Converts finished Gaia Evidence
  Gaps into concrete, ranked perovskite experiment-design cards grounded in
  Gaia weak nodes, local SQLite literature precedents, LKM
  claim/reasoning-chain retrieval, and perovskite readout mappings. This skill
  requires querying the local perovskite SQLite database before drafting
  experiment cards.
---

# Perovskite Gap-To-Experiment Cards

## Purpose

Turn Gaia Evidence Gaps into concrete research-planning cards for perovskite
solar-cell experiments. Gaia identifies the weak nodes and affected
conclusions; the local SQLite database supplies same-family literature
precedents and matched-control deltas; LKM supplies mechanism claims and
reasoning chains; this skill synthesizes those inputs into ranked cards.

This is a reusable skill-level policy. Do not write package-specific hotfixes,
special cases, or hard-coded rules for one generated Gaia package. Package
facts may lock context, but the conversion strategy must remain configurable
and reusable for future perovskite Gaia packages.

The primary deliverable is automated experiment-plan generation. SQLite
retrieval, LKM retrieval, context extraction, and validation are intermediate
steps whose purpose is to produce `EXPERIMENT_PLAN.md`, `experiments.yaml`,
`retrieval_evidence.yaml`, and LKM diagnostics.

Normal invocation point: after review and publish, before commit and push. This
skill consumes finished publish artifacts. It is not part of the core
formalization pass, and it must not rewrite `README.md` unless the user
explicitly asks.

This is a planning skill, not an operational wet-lab protocol generator. It may
discuss variables, controls, readout types, decision criteria, and literature
precedents. It must not output hazardous chemical recipes, exact synthesis
protocols, detailed solvent/concentration instructions, or step-by-step
laboratory procedures. If database fields contain solvent or concentration
values, treat them as literature metadata for matching and provenance only.
Every output must state that implementation requires qualified lab supervision
and institutional safety review.

## Evidence Source Policy

Treat evidence sources as role-separated:

- Package-local Gaia evidence identifies target claims, affected conclusions,
  current beliefs, mechanism chains already formalized in the package, missing
  causal links, and the H-vs-Alt uncertainty to resolve.
- LKM mechanism reasoning supplies auditable cross-paper/package mechanism
  chains, competing explanations, causal-chain checks, and measurement-class
  logic. LKM is not a black box: preserve provenance fields whenever returned,
  including `source_package`, paper id, claim id, conclusion id, chain id,
  title, score, and rerank score.
- SQLite is for precedent discovery, stack/intervention matching, paired
  delta background, rough comparability screening, readout candidates, and
  risk flags only; it is not mechanism proof.

Hard constraints:

- SQLite rows must not be the primary evidence for mechanism attribution.
- SQLite deltas must not close a mechanism gap by themselves.
- SQLite tier1/tier2/tier3 evidence may affect priority, precedent strength,
  readout candidates, comparability, and risk notes only.
- If SQLite patterns conflict with Gaia/LKM reasoning, do not use SQLite to
  overwrite the mechanism chain. Preserve the H-vs-Alt outcome matrix and add
  `sqlite_lkm_conflicts`.
- Every card and `EXPERIMENT_PLAN.md` must state: "SQLite is for precedent
  discovery, stack/intervention matching, and paired delta background only; it
  is not mechanism proof."
- If LKM is unavailable or fails, emit `lkm_unavailable` diagnostics in
  `lkm_role`, `lkm_evidence_summary`, `retrieval_evidence.yaml`, or the
  relevant `lkm/*.json` artifact. Do not pretend retrieval succeeded. Cap
  mechanism attribution confidence at `low` unless strong package-local Gaia
  mechanism reasoning justifies at most `moderate` overall card confidence.

For every experimental gap, first extract from Gaia package artifacts and LKM
reasoning chains where available:

- target claims
- affected conclusions
- hypothesis H
- alternative Alt
- mechanism chain
- missing causal link
- discriminating measurement/readout classes
- conflicting mechanisms

Use LKM `/search` for relevant claims, papers, and package discovery. Use LKM
`/reasoning/search` for H-vs-Alt mechanism reasoning, measurement-class design,
and causal-chain checks. Mark LKM chains as `same_package_lkm_chains` when they
come from the source paper/package and `cross_package_lkm_chains` when they
come from another paper/package. Never present cross-package reasoning as
proof internal to the source paper.

## Device-Orientation Policy

Default `lab_preferred_device_architecture` is `inverted p-i-n`.

Do not overwrite the package's locked device context. If the source package is
n-i-p or otherwise differs from the lab preference:

- preserve the original package facts in `source_device_context`
- add a `lab_translation_context` for inverted p-i-n adaptation
- add `portability_risks_for_p_i_n`
- add `architecture_sensitive_readouts`
- add `what_not_to_generalize`
- state that p-i-n adaptation is translation, not source-paper proof

If the package itself is p-i-n, keep the p-i-n source context and strengthen
p-i-n matched controls, readout classes, and comparator logic. In all cases,
plans stay design-level and must not include wet-lab recipes, solvents,
concentrations, annealing parameters, or stepwise preparation instructions.

## Required Inputs

- finished `README.md`
- `ANALYSIS.md` from `gaia-formalize-fine`
- `.gaia/beliefs.json`
- `.github-output/docs/public/data/graph.json`, when available
- `src/<package>/*.py`
- `artifacts/references.json`, when available
- optional `experiment_context.yaml`
- local SQLite database:
  `/share/hwz/Perovskite_Database_Multiagents/literature_extraction/data_merger/merged_gpt5mini_data_with_chemical_data.db`
- optional LKM access key for LKM API calls. Accept `GAIA_LKM_ACCESS_KEY` or
  `LKM_ACCESS_KEY` from the process environment, the package `.env`, the
  output-directory `.env`, the current working directory `.env`, or the Gaia
  repo `.env`. In this local workspace, the expected shared location is
  `/personal/Gaia-v0.5/.env`. Never print, copy, commit, or persist the key
  value in generated artifacts.

Do not treat the database as optional. For every experimental gap, local SQLite
retrieval must run before drafting the experiment card.

Use LKM as a complementary evidence source. If `GAIA_LKM_ACCESS_KEY` or
`LKM_ACCESS_KEY` is available directly or through one of the supported `.env`
files, perform LKM retrieval for every gap. If LKM is unavailable or fails,
continue only after marking the LKM evidence gap in the card, lowering
confidence, and explaining that the card is database-grounded but not
LKM-validated.

## Preflight And Invocation Point

Run preflight before generating cards. Git status may be dirty because this is
a final pre-commit step, but this skill must not commit or push unless the user
explicitly instructs it to do so.

Strict mode is the default for real packages. Check:

- `README.md` exists and has no obvious placeholder comments such as
  `<!-- ... -->` or TODO markers.
- `ANALYSIS.md` exists. In strict mode, do not silently use README Evidence
  Gaps when `ANALYSIS.md` is absent.
- `.gaia/beliefs.json` exists and is fresh relative to `src/<package>/*.py`.
  If source files are newer, rerun inference before planning.
- Published docs or graph data are available when the package is expected to
  have `.github-output/docs/public/data/graph.json` or
  `docs/detailed-reasoning.md`.
- `src/<package>/*.py` exists.
- The SQLite database exists at
  `/share/hwz/Perovskite_Database_Multiagents/literature_extraction/data_merger/merged_gpt5mini_data_with_chemical_data.db`.
- `GAIA_LKM_ACCESS_KEY` or `LKM_ACCESS_KEY` is available when LKM retrieval is
  requested. Check process env and supported `.env` paths, especially
  `/personal/Gaia-v0.5/.env` in this workspace.
- No output contains secrets, including access-key values, `.env` values, or
  raw credential headers. It is acceptable to record the credential source
  path/variable name, but never the value.

Strict-mode stop rules:

- If `ANALYSIS.md` is absent, write `context_missing_preflight.yaml` and stop.
  README Evidence Gaps fallback is allowed only in permissive/trial mode and
  must downgrade card confidence.
- If required package, gap, device, composition, intervention, or modulator
  context cannot be recovered, write `context_missing_preflight.yaml` and stop
  before generating generic experiment cards.
- If the SQLite database is unavailable, stop in strict mode.
- If SQLite is available but parse coverage is low, continue only with
  `database_confidence` limitations on every card.
- If LKM claim search times out but reasoning search and paper graph retrieval
  succeed, record that partial failure in `retrieval_evidence.yaml`, add a
  confidence caveat to the relevant cards, and continue.

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
lab_preferred_device_architecture: inverted p-i-n
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
- `retrieval_evidence.yaml`: database query summaries, row counts, tier counts,
  parse coverage, successful/failed endpoints per gap, same/cross-package LKM
  chain summaries, SQLite/LKM conflicts, architecture translation warnings, and
  parse coverage warnings
- `context_missing_preflight.yaml`: written when strict-mode context is missing
  and card generation stops
- `lkm/*.json`: LKM retrieval artifacts when LKM retrieval is used and the
  outputs are audit artifacts, reasonably sized, and not secret-bearing

## Workflow

1. Inspect package state and run preflight.
   - Confirm `README.md`, `ANALYSIS.md`, `.gaia/beliefs.json`, package source,
     docs/graph outputs when expected, and SQLite are present and fresh enough.
   - Confirm `README.md` has no obvious placeholder comments.
   - Read `ANALYSIS.md` and extract every experimental gap. In strict mode, do
     not fall back to README Evidence Gaps when `ANALYSIS.md` is absent.
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
   Extract package-local Gaia mechanism evidence first, including mechanism
   chains, missing causal links, conflicting mechanisms, and measurement logic.

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
   `why_limited`, and parsed deltas. Record SQLite role as precedent/delta
   background only; never use it as mechanism proof.

6. Query LKM for every gap when access is available.
   Retrieve hybrid claim matches, reasoning-chain matches, claim reasoning
   chains, paper graphs, and hydrated variables when returned IDs make that
   useful. Summarize supported mechanisms, competing explanations, premises,
   discriminating observations, provenance papers, and agreement or conflict
   with database patterns. Separate same-package from cross-package reasoning
   and retain provenance fields in `lkm/*.json`, `retrieval_evidence.yaml`, and
   card summaries. If LKM fails, emit `lkm_unavailable` diagnostics and lower
   confidence.

7. Draft one complete experiment card per experimental gap.
   Do not emit vague suggestions such as "do more characterization" or "study
   stability further." Every card must say what uncertainty is being resolved,
   what H and Alt are, what observation distinguishes them, which controls are
   required, which readouts are primary, how each primary readout maps to a
   specific uncertainty or alternative explanation, and how the result would
   update Gaia interpretation. Include an `outcome_matrix` with
   `supports_H`, `supports_Alt`, and `mixed_or_unresolved`. Add a generic
   `gap_resolution_strategy` for every card, using extensible decomposition
   axes and decision rules rather than hard-coded metric-specific modules. Add
   analog-control logic for causal attribution or multifunctional-passivator
   gaps.

8. Rank cards with the 0-100 priority formula in
   `experiment-card-schema.md`. Sort `experiments.yaml` and the roadmap by
   descending priority. Preserve per-gap traceability even when multiple gaps
   can be bundled into one experimental campaign.

9. Write `EXPERIMENT_PLAN.md`, `experiments.yaml`,
   `retrieval_evidence.yaml`, and `lkm/*.json` artifacts when LKM retrieval is
   used. If strict-mode context is missing, write
   `context_missing_preflight.yaml` instead of cards. Include safety and
   feasibility boundaries in both human-readable and YAML outputs.

10. Use the automation entrypoint when a package has `ANALYSIS.md` and either
   recovered context or `experiment_context.yaml`:

   ```bash
   uv run python scripts/generate_experiment_plan.py . --output-dir .
   ```

   Trial runs that intentionally skip live LKM retrieval must use `--skip-lkm`
   and will emit `lkm_unavailable` diagnostics with lowered confidence. Strict
   real-package mode stops when SQLite is missing; `--allow-missing-sqlite` is
   for smoke tests or exploratory dry runs only.

11. Validate `experiments.yaml` before handoff:

   ```bash
   uv run python scripts/validate_experiment_cards.py experiments.yaml \
     --retrieval-evidence retrieval_evidence.yaml
   ```

## Hard Gates

- No SQLite retrieval, no experiment card.
- No real-package context, no experiment card. Emit `context_missing_preflight`
  instead of a generic card.
- In strict mode, no `ANALYSIS.md`, no experiment card. README fallback is
  permissive/trial-only and must be marked as lower confidence.
- No card may omit H, Alt, discriminating observation, required controls,
  primary readouts, outcome matrix, and the Gaia belief update target.
- No orphan readouts: every primary readout must map to the uncertainty or
  alternative explanation it discriminates.
- No operational recipes or step-by-step lab procedures.
- No commits or pushes from this skill unless explicitly instructed.
- No priority score without a rationale tied to Gaia impact, database
  precedent strength, LKM support, discriminating power, and feasibility.
- SQLite performance deltas are precedent evidence only. Do not claim they
  prove a mechanism without LKM or package-local reasoning evidence.
- No cross-package LKM chain may be represented as same-package/source-paper
  proof.
- No package locked context may be overwritten by the p-i-n lab translation.
- No single aggregate metric improvement may be treated as mechanism proof.
