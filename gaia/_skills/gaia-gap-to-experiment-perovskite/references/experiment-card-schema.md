# Experiment Card Schema

## Output Files

Write:

- `experiments.yaml`
- `EXPERIMENT_PLAN.md`
- `retrieval_evidence.yaml` with database and LKM summaries, per-gap
  `successful_endpoints`, `failed_endpoints`, same/cross-package chain
  summaries, SQLite parse coverage warnings, SQLite/LKM conflicts, and
  architecture translation warnings
- `context_missing_preflight.yaml` when strict-mode context is missing
- `lkm/*.json` when LKM retrieval is used and the artifacts are not
  secret-bearing

Each experimental gap from `ANALYSIS.md` must receive one complete YAML card.
Cards may reference shared bundled experiments, but per-gap traceability must be
preserved.

Validate generated cards before handoff:

```bash
uv run python scripts/validate_experiment_cards.py experiments.yaml \
  --retrieval-evidence retrieval_evidence.yaml
```

When generating from a real package, prefer the automation entrypoint first:

```bash
uv run python scripts/generate_experiment_plan.py . --output-dir .
```

For explicit synthetic smoke fixtures only:

```bash
uv run python scripts/validate_experiment_cards.py --smoke-test experiments.yaml
```

For permissive/trial runs that explicitly used README Evidence Gaps because
`ANALYSIS.md` was absent:

```bash
uv run python scripts/validate_experiment_cards.py --allow-readme-fallback experiments.yaml
```

Do not use README fallback in strict real-package mode.

## YAML Schema

Every card in `experiments.yaml` must include these keys:

```yaml
- gap_id:
  package_mode:
  planning_level:
  execution_phase:
  depends_on:
  enables:
  execution_rationale:
  source_package:
  target_claims:
  affected_conclusions:
  gap_claim_belief:
  original_evidence_gap_text:
  package_evidence_brief:
  mechanism_decomposition_question:
  factor_decomposition:
  minimal_discriminating_matrix:
  route_designs:
  morphology_normalization_strategy:
  same_sample_measurement_bundle:
  passivation_transport_tradeoff_logic:
  boundary_condition_tests:
  gaia_evidence_node_mapping:
  matrix_closure_rules:
  matrix_non_closure_rules:
  lab_reference_stack:
  gap_type:
  gap_classifier_output:
  mechanism_axes:
  primary_mechanism_axis:
  secondary_mechanism_axes:
  card_archetype:
  classification_mode:
  archetype_selection:
  priority:
  priority_rationale:
  scientific_uncertainty:
  hypothesis_H:
  alternative_Alt:
  discriminating_observation:
  database_queries_run:
  database_precedents:
  sqlite_role:
  sqlite_precedent_quality:
  sqlite_quality_warning:
  lkm_queries_run:
  lkm_role:
  lkm_design_reasoning:
  lkm_evidence_summary:
  top_reasoning_chains:
  design_motif_evidence:
  design_memory_role:
  mechanism_source_breakdown:
  same_package_lkm_chains:
  cross_package_lkm_chains:
  ambiguous_lkm_chains:
  sqlite_lkm_conflicts:
  mechanism_attribution_limitations:
  gap_resolution_strategy:
  recommended_experiment_class:
  source_device_context:
  lab_translation_context:
  p_i_n_adaptation_design:
  portability_risks_for_p_i_n:
  architecture_sensitive_readouts:
  what_not_to_generalize:
  variables_to_vary:
  controls:
  primary_readouts:
  secondary_readouts:
  observable_to_mechanism_mapping:
  expected_result_if_H:
  expected_result_if_Alt:
  success_criterion_for_closing_gap:
  non_closure_criteria:
  minimum_replicate_logic:
  statistics_or_comparison_logic:
  failure_modes:
  interpretation_decision_tree:
  outcome_matrix:
  belief_update_target:
  belief_update_contract:
  feasibility_notes:
  safety_boundary_note:
  confidence:
  open_questions:
```

Use lists for multi-valued fields. Prefer concise strings over deeply nested
objects unless nesting improves traceability. `database_queries_run` and
`lkm_queries_run` may contain summarized query descriptors rather than full raw
payloads; raw or longer summaries can live in `retrieval_evidence.yaml` and
`lkm/*.json` audit artifacts.

## Required Semantics

`gap_id`
: Stable identifier derived from `ANALYSIS.md`, such as
  `experimental_gap_01_passivation_voc`.

`target_claims`
: Gaia weak claim or gap node labels, not just prose names.

`affected_conclusions`
: Exported conclusions whose belief would change if the gap closes.

`planning_level`
: `aggregate_roadmap` for aggregate/corpus packages and
  `implementation_candidate` for locked package/stack/absorber/intervention
  contexts. Aggregate roadmaps order design work and select candidates;
  implementation candidates must carry concrete source-device context.

`execution_phase`, `depends_on`, `enables`, and `execution_rationale`
: Experimental order fields. These are separate from scientific `priority`.
  Priority ranks importance; execution fields state which design block must run
  first and what it unlocks.

`gap_claim_belief`
: Belief from `.gaia/beliefs.json` when available. Use `unknown` only when the
  belief file cannot map the claim. `current_belief` is a legacy alias and
  should not be emitted by new plans.

`original_evidence_gap_text`
: Verbatim or tightly excerpted Evidence Gap text from `ANALYSIS.md` that
  motivated the card. Do not replace this with a new summary.

`gap_type`
: One of the perovskite taxonomy classes, with optional secondary tags.

`classification_mode`
: One of `closed_set_archetype`, `mixed_archetype`, or
  `open_world_design`. Family labels are soft routing aids. If a gap has no
  good known family, the card must still contain H, Alt, readouts, controls,
  confounders, and closure/non-closure rules.

`archetype_selection`
: Mapping with `selected`, `rejected`, `conflict_reason`, and
  `classifier_confidence`. Use this to audit why the generator used one
  archetype, combined several motif sources, or entered open-world design mode.

`design_motif_evidence`
: Role-separated motif evidence:

  ```yaml
  design_motif_evidence:
    retrieved_from_lkm:
    retrieved_from_design_memory:
    retrieved_from_sqlite_background:
    motif_synthesis_summary:
  ```

  Design motifs guide controls/readouts/decision logic. They are not direct
  proof of the source-package mechanism.

`emergent_gap_family`
: Optional mapping emitted when open-world design finds that existing
  families are insufficient. It must include a proposed name, closest existing
  families, reason for insufficiency, motif sources, confidence, and
  `review_required: true`.

`hypothesis_H` and `alternative_Alt`
: Competing explanations stated as testable propositions.

`discriminating_observation`
: Observation that would distinguish H from Alt. It must be more specific than
  "improved performance."

`database_precedents`
: SQLite precedent summary. Must include query summaries or row-count links,
  `tier1_strong_precedent`, `tier2_related_precedent`,
  `tier3_broad_context`, and `rejected_or_unusable` counts, parse coverage for
  PCE, FF, Voc, Jsc, and hysteresis, and top precedent rows with component
  `similarity_score` breakdowns, `precedent_group`, comparability rationale,
  limitation rationale, and parsed deltas.

`sqlite_role`
: Must explicitly say that SQLite is for precedent discovery, stack/intervention
  matching, and paired delta background only; it is not mechanism proof. This
  is the canonical `sqlite_weight_or_role` field for this skill.

`database_confidence`
: Structured confidence penalty with `overall`, `metric_coverage`, and
  `interpretation_limit`. Required when parse coverage is low, tier-1 evidence
  is absent, or many rows have unknown composition/stack. State the limitation
  that should lower card confidence. Do not upgrade mechanism confidence from
  SQLite performance deltas alone.

`minimal_discriminating_matrix`
: Semantic matrix of factor groups and readout bundles. It must use labels
  such as baseline, mechanism-family, alternative-family, morphology-normalized
  comparator, or boundary class. It must not emit exact solvent,
  concentration, annealing, or stepwise fabrication details.

`route_designs`
: Design-level route logic, including a standard source-context route, a
  morphology-normalized route, and p-i-n translation route when relevant.

`same_sample_measurement_bundle`
: Same-sample readout bundle covering phase/composition, recombination/trap,
  transport/contact, device metrics, and stability when supported by package
  evidence.

`gaia_evidence_node_mapping`
: Mapping from matrix outcomes to target claims, affected conclusions,
  belief-update targets, source DSL nodes, and synthesis evidence rows.

`top_reasoning_chains`
: LKM chain summaries ranked by reasoning relevance. Each item should state
  `relevance`, `supports`, `key_premise`, `key_limitation`, and provenance.

`lkm_role`
: How LKM was used for mechanism reasoning, H-vs-Alt logic, measurement-class
  design, causal-chain checks, or an explicit `lkm_unavailable` diagnostic.
  This is the canonical `lkm_weight_or_role` field for this skill.

`lkm_evidence_summary`
: Mechanism/reasoning evidence from LKM, or an explicit failure/unavailable
  reason. If SQLite and LKM disagree, state the conflict directly.

`mechanism_source_breakdown`
: Required mapping that separates:

  ```yaml
  mechanism_source_breakdown:
    package_local_gaia_evidence:
    lkm_mechanism_reasoning:
    sqlite_precedent_delta_background:
  ```

  SQLite must be described as precedent/delta background, not as mechanism
  proof.

`same_package_lkm_chains` and `cross_package_lkm_chains`
: Lists of LKM chain summaries. Preserve as much provenance as the API returns:
  `source_package`, `paper_id`, `claim_id`, `conclusion_id`, `chain_id`,
  `title`, `score`, and `rerank_score`. Cross-package chains must be marked as
  cross-package and must not be presented as source-paper mechanism proof.

`sqlite_lkm_conflicts`
: Explicit conflict notes when SQLite precedent patterns disagree with
  Gaia/LKM reasoning. Preserve H-vs-Alt interpretation instead of letting
  SQLite override the mechanism chain.

`mechanism_attribution_limitations`
: Boundary statement for what can and cannot be attributed after the planned
  readouts. If LKM is unavailable and package-local Gaia reasoning is not
  strong, mechanism attribution confidence must be `low`.

`gap_resolution_strategy`
: Required generic, extensible experiment-design strategy:

  ```yaml
  gap_resolution_strategy:
    strategy_type:
    uncertainty_to_resolve:
    decomposition_axes:
    confounders_to_bound:
    decision_rules:
    extension_hooks:
  ```

  Use decomposition axes that fit the gap rather than hard-coded metric
  special cases. Examples include mechanism-vs-contact, stability-vs-barrier,
  ion-migration-vs-scan-history, energetic-alignment-vs-passivation, or
  aggregate-metric-vs-causal-readout branches. `extension_hooks` should state
  how future domains or new perovskite subproblems can add modules without
  changing the base schema.

`recommended_experiment_class`
: Class of experiment or characterization campaign, not an operational
  protocol.

`source_device_context`
: Locked package context. Do not overwrite it with lab preferences. Required
  fields are `solar_cell_structure`, `cell_stack_sequence`,
  `perovskite_composition`, `intervention_location`, and
  `modulator_material_or_family`.

`lab_translation_context`
: Lab-preferred adaptation context. Default
  `lab_preferred_device_architecture` is `inverted p-i-n`. If the source
  package is n-i-p, this context must say the p-i-n plan is translation, not
  source-paper proof.

`portability_risks_for_p_i_n`, `architecture_sensitive_readouts`,
`what_not_to_generalize`
: Required when source architecture differs from the p-i-n lab preference.
  Use these fields to mark n-i-p contact-stack dependencies, readouts whose
  interpretation changes under p-i-n, and source claims that should not be
  generalized.

`variables_to_vary`
: High-level variables such as interface location, modulator family, absorber
  family, stress category, or contact layer comparison. Do not include exact
  chemical recipes, stepwise synthesis, or actionable concentrations.

`controls`
: Required controls. Include matched baseline/no-modulator controls when the
  gap concerns modulator effects, and contact/absorber controls when needed to
  separate mechanisms.

`primary_readouts`
: Readouts that directly answer the discriminating observation. Every primary
  readout must map to a specific uncertainty, H prediction, Alt prediction, or
  alternative explanation. No orphan readouts are allowed.

  Acceptable shape:

  ```yaml
  primary_readouts:
    - name:
      maps_to_uncertainty:
      supports_H_pattern:
      supports_Alt_pattern:
  ```

`success_criterion_for_closing_gap`
: Criterion for considering the Gaia gap closed, tied to H-vs-Alt
  discrimination and belief update.

`minimum_replicate_logic`
: Non-operational comparison logic, such as independent devices/batches and
  matched controls. Avoid precise wet-lab execution instructions.

`statistics_or_comparison_logic`
: How to compare H vs Alt: paired comparison, direction of effect, confidence
  interval, consistency across controls, or contradiction of a predicted trend.

`interpretation_decision_tree`
: Short if/then logic mapping readout patterns to H, Alt, mixed result, or
  inconclusive.

`outcome_matrix`
: Mandatory structured decision matrix that distinguishes H, Alt, and
  unresolved cases:

  ```yaml
  outcome_matrix:
    supports_H:
      observation_pattern:
      interpretation:
      remaining_caveat:
    supports_Alt:
      observation_pattern:
      interpretation:
      remaining_caveat:
    mixed_or_unresolved:
      observation_pattern:
      interpretation:
      next_step:
  ```

  The matrix must be specific to the card's device context, target claim, and
  primary readouts. It must not repeat generic phrases such as "further study is
  needed."

`causal_isolation_controls`
: Required when a gap concerns sole-cause attribution, passivation not
  isolated, morphology/contact alternatives, hydrophobicity alternatives, or
  multifunctional passivators. Use functional analog design classes, not
  synthesis recipes. Bound morphology, crystallinity, hydrophobicity, contact
  energetics, and recombination/trap-sensitive readouts. If the analog also
  changes multiple variables, it cannot close the causal gap; it only narrows
  follow-up.

`belief_update_target`
: Which Gaia claim(s), prior(s), or alternative likelihood ratio would change
  and in what direction.

`safety_boundary_note`
: Must state that implementation requires qualified lab supervision and
  institutional safety review, and that the card is not an operational
  synthesis/protocol.

## EXPERIMENT_PLAN.md Structure

Organize `EXPERIMENT_PLAN.md` as:

1. Executive summary
2. Ranked experiment roadmap
3. One section per gap
4. Database evidence summary
5. LKM reasoning evidence summary
6. Mechanism source breakdown
7. Device architecture translation notes
8. Cross-gap experiment bundling opportunities
9. What not to conclude without additional controls
10. Safety and feasibility boundary

Each gap section should include:

- target Gaia node and affected conclusions
- H and Alt
- highest-value discriminating observation
- recommended experiment class
- required controls
- primary readouts
- outcome matrix
- database precedent summary
- LKM mechanism summary
- SQLite role and mechanism attribution limitations
- source package locked context and p-i-n lab translation context
- how results would update Gaia interpretation

## Priority Formula

Assign an integer `priority` from 0 to 100. Use this formula and explain it in
`priority_rationale`:

```text
priority =
  20 * gaia_impact +
  15 * belief_weakness +
  15 * bottleneck_value +
  15 * discriminating_power +
  10 * database_precedent_strength +
  10 * lkm_reasoning_support +
  10 * feasibility +
   5 * bundling_value
```

Each component is scored from 0.0 to 1.0:

- `gaia_impact`: number and importance of affected exported conclusions.
- `belief_weakness`: low current belief or high Alt plausibility.
- `bottleneck_value`: whether the node is shared by multiple conclusions.
- `discriminating_power`: whether one experiment can separate H from Alt.
- `database_precedent_strength`: quality, match, and consistency of SQLite
  precedents.
- `lkm_reasoning_support`: strength of LKM chains and relevance of premises.
  Use <= 0.3 when LKM was unavailable.
- `feasibility`: availability of non-operational readout classes and controls.
- `bundling_value`: ability to close multiple gaps with one campaign.

Round to the nearest integer. Priority is not the same as confidence: a low
confidence but high-impact bottleneck may still be high priority.

## Confidence

Use `confidence` to rate the card's evidence grounding:

- `high`: strong SQLite precedents, parseable matched controls, and relevant
  package-local Gaia evidence plus relevant LKM reasoning chains agree. SQLite
  may support precedent strength but cannot by itself justify high mechanism
  confidence.
- `moderate`: useful SQLite precedents and either partial LKM support or mixed
  database evidence; also allowed when LKM is unavailable only if strong
  package-local Gaia mechanism reasoning is present.
- `low`: sparse SQLite matches, poor parse coverage, unavailable LKM, or
  unresolved source conflict.

Never use high confidence when SQLite retrieval failed; that case must stop
before card generation.

Never use high confidence when LKM is unavailable or failed. If LKM is
unavailable and package-local Gaia mechanism reasoning is weak or absent, use
`low`.

## Anti-Vague Requirements

Every card must specify:

- what uncertainty is being resolved
- what H and Alt are
- what observation would distinguish them
- what controls are required
- what readouts are primary
- which uncertainty each primary readout resolves
- which outcome patterns support H, support Alt, or remain unresolved
- how the result would change Gaia interpretation
- which source supplies package-local Gaia evidence, LKM mechanism reasoning,
  and SQLite precedent/delta background
- what changes under p-i-n translation and what must not be generalized

Reject or revise cards that only say "do more characterization," "study
stability further," or "optimize performance."
