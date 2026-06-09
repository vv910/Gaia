# Perovskite Gap Taxonomy

Classify each experimental gap into the most useful category or combination of
categories below. These labels are soft routing aids for design primitives, not
hard gates. If a gap spans categories, record multiple matches and use
`classification_mode: mixed_archetype`. If no family fits, use
`classification_mode: open_world_design`, synthesize a complete H-vs-Alt card
from causal uncertainty, LKM/design-memory motifs, and source context, and
optionally emit an `emergent_gap_family` with `review_required: true`.

To promote an emergent family into the registry, review:

- whether its mechanism axis is distinct from existing axes,
- whether motifs provide concrete readouts, controls, confounders, closure
  rules, and non-closure rules,
- whether motif sources are provenance-retained,
- whether p-i-n translation boundaries are explicit, and
- whether no wet-lab recipe details leak into outputs.

## 1. Passivation / Recombination Gap

Typical uncertainty:

A performance improvement is attributed to defect passivation, but
transport/contact/morphology alternatives remain plausible.

Default H:

The intervention reduces non-radiative recombination through defect
passivation at the relevant bulk or interface region.

Default Alt:

The observed performance change mainly arises from contact selectivity,
transport resistance, morphology/crystallization, or measurement artifacts
rather than passivation.

Candidate readouts:

- PLQY
- TRPL
- QFLS
- light-intensity Voc
- ideality factor
- TPV/TPC
- EIS
- dark JV
- Voc deficit analysis

Core discriminating logic:

Separate reduced non-radiative recombination from improved contact selectivity
or changed series resistance.

## 2. Aggregate Performance / Transport / Contact Gap

Typical uncertainty:

An aggregate performance metric improvement, such as FF, PCE, Voc, hysteresis,
or stability-retention gain, may arise from several competing branches:
reduced recombination, changed series or shunt behavior, improved charge
extraction, altered contact selectivity, measurement-history effects, or
covariate changes.

Default H:

The intervention improves the target transport/contact or performance-limiting
branch in a way that explains the affected Gaia claim.

Default Alt:

The aggregate metric change is secondary to another branch, such as
recombination suppression, shunt changes, morphology, or measurement-condition
differences.

Candidate readouts:

- Rs/Rsh extraction
- Suns-Voc
- intensity-dependent JV or target-metric response
- dark JV
- EIS
- mobility proxies
- contact-only comparison
- selective-contact controls

Core discriminating logic:

Distinguish bulk/interface recombination from transport/contact resistance.
Use the generic `gap_resolution_strategy` to decompose the aggregate
performance metric into competing branches, such as recombination/passivation,
series or shunt behavior, contact effects, transport barriers, or scan-history
artifacts where relevant. No single aggregate metric improvement closes a
mechanism gap. If the strategy cannot distinguish the branches, keep the
mechanism conclusion bounded and do not close the gap.

## 3. Ion Migration / Hysteresis Gap

Typical uncertainty:

Reduced hysteresis may reflect suppressed ion migration, altered capacitive
response, changed interfacial charge accumulation, or measurement artifacts.

Default H:

The intervention suppresses ion migration or ion-driven interfacial charge
accumulation.

Default Alt:

The apparent hysteresis reduction is caused by scan protocol, preconditioning,
capacitive response, or unrelated contact/recombination effects.

Candidate readouts:

- scan-rate dependent JV
- bias preconditioning comparison
- transient photocurrent/photovoltage
- impedance
- KPFM
- ToF-SIMS-style evidence
- pre/post stress comparison

Core discriminating logic:

Distinguish true ion-migration suppression from scan or conditioning artifacts.

## 4. Stability Gap

Typical uncertainty:

Stability improvement may be due to chemical passivation, hydrophobic barrier
effects, morphology, phase stabilization, or encapsulation differences.

Default H:

The intervention improves intrinsic device or material stability under a
defined stress category.

Default Alt:

The retention difference is due to barrier effects, initial efficiency
differences, encapsulation, morphology, inconsistent stress protocols, or
short-term measurement artifacts.

Candidate readouts:

- ISOS-style protocol mapping where available
- light/heat/humidity/bias stress categories
- T80-style analysis
- pre/post JV
- PL/XRD/GIWAXS/XPS-type degradation markers

Core discriminating logic:

Distinguish device-level stability from short-term performance retention or
inconsistent stress protocols.

## 5. Energy-Level Alignment Gap

Typical uncertainty:

A voltage, transport, or aggregate performance improvement is attributed to
better energy alignment, but defect passivation or morphology changes may be
the real cause.

Default H:

The intervention changes energy-level alignment or work function in a way that
improves carrier selectivity and reduces contact loss.

Default Alt:

The gain is mainly caused by passivation, morphology, or crystallization
effects rather than energetic alignment.

Candidate readouts:

- UPS
- Kelvin probe
- KPFM
- work-function shift
- QFLS vs Voc loss
- contact selectivity controls
- selective-layer comparison

Core discriminating logic:

Separate energetic alignment from recombination suppression.

## 6. Crystallization / Morphology Gap

Typical uncertainty:

Performance improvement may be due to changed grain/crystal quality rather than
chemical passivation.

Default H:

The intervention improves film formation, grain/crystal quality, orientation,
or phase purity in a way that explains the performance change.

Default Alt:

The apparent morphology association is secondary; the performance change is
driven mainly by interface passivation, contact effects, or energy alignment.

Candidate readouts:

- GIWAXS/XRD
- SEM/AFM
- PL mapping
- film uniformity
- crystal orientation
- phase purity

Core discriminating logic:

Separate bulk morphology/crystallization effects from interface-specific
chemical effects.

## 7. Causal Attribution / Multifunctional Passivator Gap

Typical uncertainty:

A multifunctional passivator or interfacial molecule is credited as the sole
mechanistic cause even though passivation, crystallinity, morphology,
hydrophobicity, contact energetics, and recombination/trap changes may all vary
together.

Default H:

The proposed functional mechanism, such as defect passivation, is the dominant
causal link for the affected Gaia claim.

Default Alt:

The apparent effect is caused by morphology, crystallinity, hydrophobicity,
contact energetics, recombination/trap changes, or a coupled combination rather
than the proposed sole mechanism.

Candidate readouts:

- Functional analog control class
- Morphology and crystallinity bounding readouts
- Hydrophobicity or barrier-effect screens
- Contact energetics comparison
- Recombination/trap-sensitive readouts

Core discriminating logic:

Use design-level functional analog controls to bound covariates. The analog
control is a class of comparator, not a synthesis recipe. If an analog also
changes multiple variables, it cannot close the causal gap; it only narrows the
follow-up hypothesis space.

## Classification Rules

- If the Gaia gap names Voc or non-radiative recombination, start with
  passivation/recombination unless aggregate performance/contact evidence
  dominates.
- If the gap names an aggregate performance metric, series resistance, shunt
  resistance, extraction, or contact selectivity, start with aggregate
  performance/transport/contact.
- If the gap names hysteresis, preconditioning, scan rate, or ion migration,
  use ion migration/hysteresis.
- If the gap names retention, degradation, stress, T80, or outdoor operation,
  use stability.
- If the gap names work function, band offset, energy alignment, or selective
  contact energetics, use energy-level alignment.
- If the gap names grain size, crystallinity, phase purity, orientation, or
  film coverage, use crystallization/morphology.
- If the gap names sole-cause attribution, passivation not isolated,
  morphology/contact alternative, hydrophobicity alternative, multifunctional
  passivator, or coupled mechanism, use causal attribution/multifunctional
  passivator.
