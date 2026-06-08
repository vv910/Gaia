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

# Perovskite Mechanism-Decomposition Planner

## Purpose

Turn Gaia Evidence Gaps into design-level mechanism-decomposition plans for
perovskite solar-cell experiments. Gaia identifies weak nodes and affected
conclusions; optional `SYNTHESIS_PLAN.md` and package artifacts supply the
evidence brief; LKM supplies mechanism claims and reasoning chains; the local
SQLite database supplies precedent/background only. The skill synthesizes
those inputs into ranked plans with semantic factor groups, execution
sequencing, minimal discriminating matrices, route logic, same-sample readout
bundles, confidence penalties, and Gaia evidence-node update targets.

This is a reusable skill-level policy. Do not write package-specific hotfixes,
special cases, or hard-coded rules for one generated Gaia package. Package
facts may lock context, but the conversion strategy must remain configurable
and reusable for future perovskite Gaia packages.

The primary deliverable is automated mechanism-decomposition planning. SQLite
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
- SQLite `tier1_strong_precedent`, `tier2_related_precedent`,
  `tier3_broad_context`, and `rejected_or_unusable` evidence may affect
  priority, precedent strength, readout candidates, comparability, and risk
  notes only.
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

## Mechanism-Gap Classification Policy

This skill is a general mechanism-gap-to-discriminating-experiment generator.
It must not use FF/passivation-to-FF as the default spine. FF-loss budget is
one conditional archetype selected only when a gap explicitly concerns FF,
fill factor, J-V loss decomposition, series/shunt/leakage, contact resistance,
transport/contact barrier, or LKM/Gaia reasoning identifies FF-loss-channel
ambiguity.

Classify each Evidence Gap in two stages:

1. Stage A, pre-retrieval lightweight classification, uses only package-local
   gap text, target claims, and affected conclusions. Its purpose is to build
   SQLite/LKM queries, not to finalize the card.
2. Stage B, evidence-aware final classification, runs after SQLite and LKM
   retrieval. It combines package-local Gaia artifacts, LKM reasoning chains,
   SQLite precedent quality as background only, source device context, and
   p-i-n translation needs to decide final `card_archetype`, mechanism axes,
   priority, and confidence.

Every classifier result must expose:

- `dominant_observable`
- `mechanism_axes`
- `primary_mechanism_axis`
- `secondary_mechanism_axes`
- `alternative_class`
- `architecture_sensitivity`
- `evidence_gap_kind`
- `source_claim_type`
- `device_metric_relevance`
- `direct_readout_available`
- `portability_to_p_i_n`
- `classifier_stage`
- `classifier_confidence`
- `classifier_warnings`
- `matched_archetypes`
- `conflict_reason`

Mechanism axes:

- `recombination_defect_passivation`
- `charge_extraction_collection`
- `contact_energetics_barrier`
- `series_shunt_leakage_loss`
- `ion_migration_hysteresis`
- `morphology_crystallinity_phase`
- `stability_degradation_pathway`
- `hydrophobicity_environmental_resistance`
- `optical_absorption_jsc`
- `interface_selectivity`
- `dopant_additive_chemical_interaction`
- `scalability_reproducibility`
- `architecture_portability`
- `model_mapping_quantification`

## Card-Archetype Registry And Open-World Design

Do not emit generic H-vs-Alt placeholder cards when the gap maps to a
supported archetype. The generator uses family labels as soft routing aids,
not as hard requirements. Known archetypes provide reusable design primitives;
unknown or conflicting gaps must still receive complete H-vs-Alt cards.

Supported archetypes:

- `ff_loss_budget`: FF/J-V loss decomposition. The generic generator may only
  call `build_ff_loss_budget_card()` when final classification returns this
  archetype. Detailed FF channels are owned by the photovoltaic metric module.
- `recombination_loss_mapping`: trap density, PL/TRPL, PLQY, QFLS, Voc
  deficit, lifetime, and nonradiative-recombination proxy-to-device gaps.
- `charge_extraction_collection`: extraction, collection, transport timing,
  mobility, and carrier-collection gaps.
- `ion_migration_hysteresis`: mobile ions, hysteresis, scan-direction,
  bias-history, and interfacial charge-accumulation gaps.
- `functional_analog_causal_isolation`: multifunctional additives/passivators
  and causal attribution gaps requiring analog-control logic.
- `stability_degradation_pathway`: humidity, thermal, light soaking,
  operational stability, phase stability, and degradation-pathway gaps.
- `morphology_phase_causality`: morphology, crystallinity, grain size,
  orientation, phase purity, strain, and microstructure-causality gaps.
- `contact_energetics_interface_selectivity`: work function, surface
  potential, band alignment, HTL/ETL interface, barrier, and selectivity gaps.
- `p_i_n_architecture_translation`: source-to-lab inverted p-i-n portability
  gaps.
- `model_mapping_quantification`: gaps asking whether characterization
  proxies quantitatively explain device metrics.
- `generic_uncertainty`: explicit unresolved fallback.

Each archetype declares design primitives rather than owning the only possible
card:

- `readout_motifs`
- `control_motifs`
- `confounder_motifs`
- `closure_rule_motifs`
- `non_closure_rule_motifs`
- `architecture_translation_motifs`
- `failure_mode_motifs`

Open-world design mode is triggered when Stage B classifier confidence is low,
no known archetype matches, an aggregate-corpus package lacks one source stack,
LKM/design evidence points to an unregistered mechanism, or the target claim
cannot be covered by existing families. Multiple known matches use
`classification_mode: mixed_archetype`; unresolved or low-confidence matches
use `classification_mode: open_world_design`.

Open-world design mode must not emit an empty generic card. It must:

1. extract causal uncertainty from the gap,
2. generate H and Alt,
3. use LKM mechanism and experiment-design reasoning where available,
4. retrieve design motifs from the design-memory interface or primitive
   library,
5. synthesize readout classes, controls, confounders, closure rules, and
   non-closure rules,
6. optionally propose an `emergent_gap_family`, and
7. produce a complete H-vs-Alt experiment card.

If no supported archetype matches, use `generic_uncertainty` only as a label
for routing and review; it is not permission to output vague content. Do not
allow these placeholder sentences in final
`experiments.yaml` or `EXPERIMENT_PLAN.md`:

- "The target transport/contact or performance-limiting branch explains the claim."
- "A competing branch or uncontrolled covariate explains the aggregate metric."
- "direct H-vs-Alt discriminating readout class"
- "mechanism-relevant condition"
- "matched control class"
- "A primary readout pattern separates H from Alt under matched controls."
- "H becomes the favored mechanism."

Priority is family-sensitive. FF-loss budget and causal-isolation cards should
rank above generic fallbacks; same-package LKM support may raise relevance,
but SQLite support must not raise mechanism confidence.

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

For n-i-p or otherwise non-p-i-n source packages, `lab_translation_context`
must include:

- `translation_status: source_context_preserved_with_p_i_n_translation`
- translation targets that preserve local absorber/passivator chemistry while
  re-evaluating contact-selective extraction and separating passivation-local
  effects from architecture-specific contact effects
- `p_i_n_specific_controls`, `p_i_n_specific_readouts`, and
  `p_i_n_specific_risks`
- `what_not_to_generalize`, including that p-i-n translation is not
  source-paper proof

For p-i-n source packages, use
`translation_status: source_context_already_p_i_n` and strengthen p-i-n
matched controls/readouts without adding an architecture-mismatch warning.

## SQLite Precedent Quality Gate

SQLite rows are screened by one central `SQLiteQualityReport` before any output
is written. Reuse the same report in `experiments.yaml`,
`retrieval_evidence.yaml`, and `EXPERIMENT_PLAN.md`; do not recalculate warning
state separately per output file.

Reject or demote rows when they are not PSC experiments, are kesterite or
otherwise cross-domain PV/material rows, have no paired PSC device metric,
carry only screening-level parsed deltas, match architecture but not
intervention/mechanism axis, repeat DOI/title metadata without a distinct
comparison, or otherwise fall below `similarity_score < 0.65`. A usable top
precedent must match at least two comparability axes and include a substantive
composition, intervention-location, mechanism-family, or metric-family match.

Emit:

- `sqlite_precedent_quality: strong | usable_background | weak_screening_only | unusable`
- `sqlite_quality_warning`
- `top_precedent_rows`
- `demoted_precedent_rows`
- `rejected_precedent_rows_summary`
- `parse_coverage_warning`
- the fixed SQLite role sentence

If no qualified precedent remains, keep `top_precedent_rows: []` rather than
forcing low-quality rows into the plan. SQLite must never raise mechanism
confidence, close a mechanism gap, or override Gaia/LKM reasoning.

## Design Memory Interface

Design memory is separate from SQLite paired-delta retrieval. SQLite remains a
hard precedent/background gate. Design memory is used to retrieve experimental
motifs: how prior perovskite studies structured controls, readouts,
confounder bounds, and decision logic. It is not direct proof of the
source-package mechanism.

Interface:

```python
retrieve_design_motifs(query, context) -> list[DesignMotif]
```

`DesignMotif` schema:

- `source_id`
- `doi`
- `title`
- `architecture`
- `material_system`
- `intervention`
- `intervention_location`
- `target_problem`
- `claimed_mechanism`
- `alternative_mechanisms_considered`
- `controls_used`
- `primary_readouts`
- `secondary_readouts`
- `confounders_addressed`
- `confounders_not_addressed`
- `causal_strength`
- `decision_logic_supports_H`
- `decision_logic_supports_Alt`
- `mixed_or_unresolved_logic`
- `portability_notes`
- `wet_lab_detail_removed`

When the external design-memory index is unavailable, the generator may use
the reviewed primitive library as a local fallback. If design-memory text
contains recipe-level details, strip them and set `wet_lab_detail_removed:
true`.

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

## Package Modes

Real-package mode is the default. Smoke-test mode is allowed only when it is
explicitly requested for synthetic gaps or fixtures. Every generated card must
declare `package_mode`:

- `single_paper`: bind to the locked source paper/package context.
- `aggregate_corpus`: bind to a corpus-level package such as `pvsk-gaia`
  without inventing one locked stack.

Every generated card must also declare `planning_level`:

- `aggregate_roadmap`: default for `aggregate_corpus` packages. It decomposes
  corpus-level mechanism axes, orders work, and selects implementation
  candidates without inventing one locked stack.
- `implementation_candidate`: requires a concrete source package/stack,
  absorber family, intervention location, and modulator or intervention
  family. Use this only when the package context is locked enough to design
  a same-sample matrix for a specific candidate.

Before drafting cards, recover these fields from `ANALYSIS.md`,
`.gaia/beliefs.json`, `graph.json`, `src/<package>/*.py`, the SQLite database,
`experiment_context.yaml`, or user-provided context:

- `source_package`
- target weak claim or gap node, emitted as `target_claims`
- `affected_conclusions`
- `gap_claim_belief`
- original Evidence Gap text from `ANALYSIS.md`, emitted as
  `original_evidence_gap_text`

For `single_paper`, also recover:

- `source_device_context.solar_cell_structure`
- `source_device_context.cell_stack_sequence` or enough stack detail to name
  the architecture
- `source_device_context.perovskite_composition`
- `source_device_context.intervention_location`
- `source_device_context.modulator_material_or_family`

For `aggregate_corpus`, do not require one locked stack. Use a corpus-level
distribution or dominant families instead. LKM chains and SQLite precedents
must distinguish package-local, corpus-level, cross-package, and ambiguous
scope. Do not present aggregate trends as single-paper mechanism proof.

If any required field cannot be recovered, do not emit a generic experiment
card. Emit a `context_missing_preflight` section instead. The preflight must
list the missing fields, the sources checked, and the minimum user/package
context needed to unlock card generation.

`source_device_context` must be package-specific in single-paper mode. A card
whose source context only says "perovskite solar cell" is not acceptable there.

## `experiment_context.yaml`

An optional `experiment_context.yaml` file may lock the experimental object
before cards are generated. Use canonical snake_case keys downstream:

```yaml
source_package:
package_mode: single_paper
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
corpus_level_distribution:
dominant_architecture_families:
dominant_absorber_families:
dominant_intervention_families:
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
- `retrieval_evidence.yaml`: preflight summary, database query summaries, row
  counts, tier counts, parse coverage, successful/failed endpoints per gap,
  same/cross/ambiguous-package LKM chain summaries, SQLite/LKM conflicts,
  architecture translation warnings, and parse coverage warnings
- `context_missing_preflight.yaml`: written when strict-mode context is missing
  and card generation stops
- `lkm/*.json`: LKM retrieval artifacts when LKM retrieval is used and the
  outputs are audit artifacts, reasonably sized, and not secret-bearing

Every experiment card must include the role-separated evidence fields plus the
new classifier/archetype fields:

- `package_mode`
- `gap_classifier_output`
- `mechanism_axes`
- `primary_mechanism_axis`
- `secondary_mechanism_axes`
- `card_archetype`
- `classification_mode`
- `archetype_selection`
- `design_motif_evidence`
- `design_memory_role`
- `lkm_design_reasoning`
- `observable_to_mechanism_mapping`
- `non_closure_criteria`
- `belief_update_contract`
- `sqlite_precedent_quality`
- `sqlite_quality_warning`
- `ambiguous_lkm_chains`
- `p_i_n_adaptation_design`
- `planning_level`
- `execution_phase`
- `depends_on`
- `enables`
- `execution_rationale`
- `package_evidence_brief`
- `mechanism_decomposition_question`
- `factor_decomposition`
- `minimal_discriminating_matrix`
- `route_designs`
- `morphology_normalization_strategy`
- `same_sample_measurement_bundle`
- `passivation_transport_tradeoff_logic`
- `boundary_condition_tests`
- `gaia_evidence_node_mapping`
- `matrix_closure_rules`
- `matrix_non_closure_rules`
- `lab_reference_stack`
- optional `emergent_gap_family`

`retrieval_evidence.yaml` must include:

```yaml
preflight:
  strict_preflight_passed:
  package:
  package_mode:
  inputs_read:
  context_missing_preflight_generated:
  sqlite_available:
  lkm_credential_loaded:
  lab_preferred_device_architecture:
```

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

2. Normalize each gap into the handoff fields required by the experiment
   generator: target node, affected conclusions, current belief, original gap
   text, preliminary H/Alt, and source context. In real-package mode, do not
   infer placeholders for required package/device/intervention fields. If those
   fields remain missing, emit `context_missing_preflight` and stop before card
   generation. Extract package-local Gaia mechanism evidence first, including
   mechanism chains, missing causal links, conflicting mechanisms, and
   measurement logic.

3. Load the relevant references for this skill:
   - Database retrieval: [references/database-retrieval.md](references/database-retrieval.md)
   - LKM retrieval: [references/lkm-retrieval.md](references/lkm-retrieval.md)
   - Card schema and scoring: [references/experiment-card-schema.md](references/experiment-card-schema.md)
   - Gap taxonomy: [references/perovskite-gap-taxonomy.md](references/perovskite-gap-taxonomy.md)
   - Readout map: [references/perovskite-readout-map.md](references/perovskite-readout-map.md)

4. Run Stage A lightweight classification before retrieval. Use the result to
   shape SQLite, LKM, and design-memory queries, but do not finalize
   `card_archetype` yet.

5. Query the local SQLite database for every gap before drafting the card.
   Retrieve and tier precedents by package-specific architecture, absorber,
   intervention location, modulator family, paired with/without values, and
   parseable performance/stability metrics. Compute parse coverage and
   normalized deltas where possible. Record
   `tier1_strong_precedent`, `tier2_related_precedent`,
   `tier3_broad_context`, and `rejected_or_unusable` counts. Top precedent
   rows must include a component `similarity_score` breakdown for architecture,
   absorber, intervention location, modulator family, paired metric
   completeness, mechanism relevance, and total, plus `precedent_group`,
   `why_comparable`, `why_limited`, and parsed deltas. Record SQLite role as
   precedent/delta background only; never use it as mechanism proof.

6. Query LKM for every gap when access is available.
   Retrieve hybrid claim matches, reasoning-chain matches, claim reasoning
   chains, paper graphs, and hydrated variables when returned IDs make that
   useful. Summarize supported mechanisms, competing explanations, premises,
   discriminating observations, provenance papers, and agreement or conflict
   with database patterns. Separate same-package from cross-package reasoning
   and retain provenance fields in `lkm/*.json`, `retrieval_evidence.yaml`, and
   card summaries. Canonicalize LKM provenance as `same_package`,
   `cross_package`, or `ambiguous_package_scope`; ambiguous chains are audit
   evidence only and lower attribution weight. If LKM fails, emit
   `lkm_unavailable` diagnostics and lower confidence.

7. Run Stage B evidence-aware classification, then decide
   `classification_mode`:
   - `closed_set_archetype` for a single confident archetype,
   - `mixed_archetype` when multiple known archetypes contribute motifs, or
   - `open_world_design` when fixed families are insufficient.
   Draft one complete experiment card per experimental gap from the selected
   primitives or open-world motif synthesis.
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

8. If open-world design mode proposes an `emergent_gap_family`, keep
   `review_required: true`. New families become registry archetypes only after
   review of their motif sources, H/Alt logic, readout mapping, and safety
   boundary.

9. Rank cards with the 0-100 priority formula in
   `experiment-card-schema.md`. Sort `experiments.yaml` and the roadmap by
   descending priority. Preserve per-gap traceability even when multiple gaps
   can be bundled into one experimental campaign.

10. Write `EXPERIMENT_PLAN.md`, `experiments.yaml`,
   `retrieval_evidence.yaml`, and `lkm/*.json` artifacts when LKM retrieval is
   used. If strict-mode context is missing, write
   `context_missing_preflight.yaml` instead of cards. Include safety and
   feasibility boundaries in both human-readable and YAML outputs.

11. Use the automation entrypoint when a package has `ANALYSIS.md` and either
   recovered context or `experiment_context.yaml`:

   ```bash
   uv run python scripts/generate_experiment_plan.py . --output-dir .
   ```

   Trial runs that intentionally skip live LKM retrieval must use `--skip-lkm`
   and will emit `lkm_unavailable` diagnostics with lowered confidence. Strict
   real-package mode stops when SQLite is missing; `--allow-missing-sqlite` is
   for smoke tests or exploratory dry runs only.

12. Validate `experiments.yaml` before handoff:

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
- FF-loss budget must not be the default card. It is selected only by explicit
  FF/J-V-loss evidence or FF-loss-channel ambiguity.
- No cross-package LKM chain may be represented as same-package/source-paper
  proof.
- Ambiguous LKM provenance must stay in `ambiguous_lkm_chains`; do not coerce
  it to same-package or cross-package scope.
- No package locked context may be overwritten by the p-i-n lab translation.
- No single aggregate metric improvement may be treated as mechanism proof.
