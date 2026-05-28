# Experiment Card Schema

## Output Files

Write:

- `experiments.yaml`
- `EXPERIMENT_PLAN.md`
- optional `retrieval_evidence/` with database and LKM summaries

Each experimental gap from `ANALYSIS.md` must receive one complete YAML card.
Cards may reference shared bundled experiments, but per-gap traceability must be
preserved.

## YAML Schema

Every card in `experiments.yaml` must include these keys:

```yaml
- gap_id:
  source_package:
  target_claims:
  affected_conclusions:
  current_belief:
  gap_type:
  priority:
  priority_rationale:
  scientific_uncertainty:
  hypothesis_H:
  alternative_Alt:
  discriminating_observation:
  database_queries_run:
  database_precedents:
  lkm_queries_run:
  lkm_evidence_summary:
  recommended_experiment_class:
  device_context:
  variables_to_vary:
  controls:
  primary_readouts:
  secondary_readouts:
  expected_result_if_H:
  expected_result_if_Alt:
  success_criterion_for_closing_gap:
  minimum_replicate_logic:
  statistics_or_comparison_logic:
  failure_modes:
  interpretation_decision_tree:
  belief_update_target:
  feasibility_notes:
  safety_boundary_note:
  confidence:
  open_questions:
```

Use lists for multi-valued fields. Prefer concise strings over deeply nested
objects unless nesting improves traceability. `database_queries_run` and
`lkm_queries_run` may contain summarized query descriptors rather than full raw
payloads; raw or longer summaries can live under `retrieval_evidence/`.

## Required Semantics

`gap_id`
: Stable identifier derived from `ANALYSIS.md`, such as
  `experimental_gap_01_passivation_voc`.

`target_claims`
: Gaia weak claim or gap node labels, not just prose names.

`affected_conclusions`
: Exported conclusions whose belief would change if the gap closes.

`current_belief`
: Belief from `.gaia/beliefs.json` when available. Use `unknown` only when the
  belief file cannot map the claim.

`gap_type`
: One of the perovskite taxonomy classes, with optional secondary tags.

`hypothesis_H` and `alternative_Alt`
: Competing explanations stated as testable propositions.

`discriminating_observation`
: Observation that would distinguish H from Alt. It must be more specific than
  "improved performance."

`recommended_experiment_class`
: Class of experiment or characterization campaign, not an operational
  protocol.

`variables_to_vary`
: High-level variables such as interface location, modulator family, absorber
  family, stress category, or contact layer comparison. Do not include exact
  chemical recipes, stepwise synthesis, or actionable concentrations.

`controls`
: Required controls. Include matched baseline/no-modulator controls when the
  gap concerns modulator effects, and contact/absorber controls when needed to
  separate mechanisms.

`primary_readouts`
: Readouts that directly answer the discriminating observation.

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
6. Cross-gap experiment bundling opportunities
7. What not to conclude without additional controls
8. Safety and feasibility boundary

Each gap section should include:

- target Gaia node and affected conclusions
- H and Alt
- highest-value discriminating observation
- recommended experiment class
- required controls
- primary readouts
- database precedent summary
- LKM mechanism summary
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
  LKM reasoning chains agree.
- `moderate`: useful SQLite precedents and either partial LKM support or mixed
  database evidence.
- `low`: sparse SQLite matches, poor parse coverage, unavailable LKM, or
  unresolved source conflict.

Never use high confidence when SQLite retrieval failed; that case must stop
before card generation.

## Anti-Vague Requirements

Every card must specify:

- what uncertainty is being resolved
- what H and Alt are
- what observation would distinguish them
- what controls are required
- what readouts are primary
- how the result would change Gaia interpretation

Reject or revise cards that only say "do more characterization," "study
stability further," or "optimize performance."
