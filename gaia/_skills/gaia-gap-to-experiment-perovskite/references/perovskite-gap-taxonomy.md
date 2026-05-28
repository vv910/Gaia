# Perovskite Gap Taxonomy

Classify each experimental gap into the most specific category below. The
category determines the default H-vs-Alt framing, readout priorities, and
required controls. If a gap spans categories, choose one primary category and
record secondary categories in the card.

## 1. Passivation / Recombination Gap

Typical uncertainty:

FF or Voc improvement is attributed to defect passivation, but
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

## 2. FF / Transport / Contact Gap

Typical uncertainty:

FF improvement may arise from reduced recombination, reduced series resistance,
improved shunt resistance, improved charge extraction, or changed contact
selectivity.

Default H:

The intervention improves charge transport or contact selectivity in a way that
directly increases FF.

Default Alt:

The FF change is secondary to recombination suppression, shunt changes,
morphology, or measurement-condition differences.

Candidate readouts:

- Rs/Rsh extraction
- Suns-Voc
- intensity-dependent JV/FF
- dark JV
- EIS
- mobility proxies
- contact-only comparison
- selective-contact controls

Core discriminating logic:

Distinguish bulk/interface recombination from transport/contact resistance.

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

Voc/FF improvement is attributed to better energy alignment, but defect
passivation or morphology changes may be the real cause.

Default H:

The intervention changes energy-level alignment or work function in a way that
improves carrier selectivity and reduces contact loss.

Default Alt:

The Voc/FF gain is mainly caused by passivation, morphology, or crystallization
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

## Classification Rules

- If the Gaia gap names Voc or non-radiative recombination, start with
  passivation/recombination unless FF/contact evidence dominates.
- If the gap names FF, series resistance, shunt resistance, extraction, or
  contact selectivity, start with FF/transport/contact.
- If the gap names hysteresis, preconditioning, scan rate, or ion migration,
  use ion migration/hysteresis.
- If the gap names retention, degradation, stress, T80, or outdoor operation,
  use stability.
- If the gap names work function, band offset, energy alignment, or selective
  contact energetics, use energy-level alignment.
- If the gap names grain size, crystallinity, phase purity, orientation, or
  film coverage, use crystallization/morphology.
