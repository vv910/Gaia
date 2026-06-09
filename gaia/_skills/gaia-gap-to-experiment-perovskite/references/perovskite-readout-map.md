# Perovskite Readout Map

Use this map to choose primary and secondary readouts. Primary readouts must
directly discriminate H from Alt. Secondary readouts can support interpretation
or flag failure modes.

## Passivation / Recombination

Primary readouts:

- PLQY or absolute luminescence proxy for non-radiative recombination.
- TRPL lifetime trend interpreted with caution and controls.
- QFLS or Voc deficit analysis to connect film recombination to device Voc.
- Light-intensity Voc and ideality factor to separate recombination regimes.

Secondary readouts:

- EIS or TPV/TPC for recombination/transport context.
- Dark JV for leakage and diode behavior.
- PL mapping for spatial uniformity.

Required controls:

- Matched no-modulator baseline.
- Same stack and absorber composition where possible.
- Contact/selective-layer comparison when contact effects are plausible.
- Morphology check when film formation may change.

Decision logic:

- H gains support when recombination-linked readouts improve in the expected
  direction while contact-resistance and morphology alternatives are controlled.
- Alt gains support when JV gains occur without recombination-readout changes,
  or when contact/morphology controls explain the effect.

## Aggregate Performance / Transport / Contact

Primary readouts:

- Rs/Rsh extraction from matched JV analysis.
- Suns-Voc or pseudo-JV comparison to separate recombination from transport
  losses.
- Intensity-dependent JV or target-metric response.
- EIS features tied to transport/contact limitations.
- Contact-only or selective-contact comparison when feasible.

Secondary readouts:

- Dark JV.
- Mobility or extraction proxies.
- TPV/TPC.
- Voc and Jsc consistency checks.

Required controls:

- Matched baseline with and without intervention.
- Same absorber and device area class.
- Selective-contact controls or contact-layer-only comparison.
- Scan-condition controls if hysteresis may affect the target metric.
- Generic aggregate-metric decomposition through `gap_resolution_strategy`,
  covering the branches relevant to the specific claim rather than requiring a
  fixed metric-specific module.

Decision logic:

- H gains support when the target metric improvement tracks the declared
  contact/transport branch while recombination-only indicators do not fully
  explain the gain.
- Alt gains support when the target metric improvement disappears under the
  discriminating comparison or is explained by recombination, shunt, morphology,
  or scan artifacts.
- Aggregate metric improvement alone is not mechanism proof. If branch
  decomposition cannot separate the losses, keep the result
  `mixed_or_unresolved`.

## Ion Migration / Hysteresis

Primary readouts:

- Scan-rate dependent JV.
- Bias preconditioning comparison.
- Transient photocurrent/photovoltage.
- EIS under relevant bias/light states.
- Pre/post stress comparison of hysteresis behavior.

Secondary readouts:

- KPFM for interfacial potential changes.
- ToF-SIMS-style ion distribution evidence.
- Dark JV and capacitive response checks.

Required controls:

- Same scan protocol for baseline and intervention.
- Forward/reverse scan comparison.
- Preconditioning state control.
- Time-dependent measurement control.
- Matched no-modulator baseline.

Decision logic:

- H gains support when hysteresis reduction persists across scan-rate and
  preconditioning controls and aligns with ion/charge-accumulation indicators.
- Alt gains support when hysteresis reduction depends on scan settings,
  conditioning history, or capacitive artifacts.

## Stability

Primary readouts:

- Stress-category mapping to light, heat, humidity, bias, or outdoor exposure.
- T80-style retention analysis when data support it.
- Pre/post JV with consistent measurement conditions.
- Degradation markers such as PL, XRD/GIWAXS, or XPS-style evidence.

Secondary readouts:

- Encapsulation and barrier metadata.
- Initial PCE normalization.
- Hysteresis change after stress.
- Absorber or interface composition changes.

Required controls:

- Matched baseline under the same stress category.
- Same encapsulation or explicit encapsulation comparison.
- Same measurement intervals and reporting basis.
- Initial-performance normalization.

Decision logic:

- H gains support when retention improvement persists under matched stress
  conditions and degradation markers support the proposed mechanism.
- Alt gains support when retention differences follow encapsulation, initial
  efficiency, stress mismatch, or barrier-only effects.

## Energy-Level Alignment

Primary readouts:

- UPS, Kelvin probe, or KPFM work-function/energy-level evidence.
- QFLS vs device Voc loss.
- Contact selectivity comparison.
- Selective-layer comparison.

Secondary readouts:

- PLQY/TRPL to check passivation confounding.
- Dark JV.
- EIS contact features.
- Morphology checks.

Required controls:

- Matched interface without intervention.
- Contact-layer comparison that isolates energetic effects.
- Passivation readouts to rule out recombination-only explanations.
- Same absorber and stack where possible.

Decision logic:

- H gains support when energy-level/work-function changes align with reduced
  contact loss and recombination/morphology controls do not explain the gain.
- Alt gains support when passivation or morphology readouts explain the target
  metric improvements without a decisive energetic shift.

## Crystallization / Morphology

Primary readouts:

- GIWAXS/XRD for phase purity, orientation, and crystallinity.
- SEM/AFM for morphology and coverage.
- PL mapping for spatial uniformity.
- Film uniformity and phase-purity comparison.

Secondary readouts:

- TRPL/PLQY to connect morphology to recombination.
- JV metric consistency.
- Interface-specific readouts if passivation remains plausible.

Required controls:

- Same absorber composition and stack.
- Matched no-modulator baseline.
- Interface-only control when the proposed mechanism is chemical passivation.
- Device and film-level comparisons to avoid overinterpreting morphology alone.

Decision logic:

- H gains support when morphology/crystallization changes track the performance
  shift and interface/passivation controls are insufficient to explain it.
- Alt gains support when performance changes occur without morphology change or
  are better explained by passivation/contact readouts.

## Causal Isolation / Functional Analog Controls

Use this when a gap involves sole-cause attribution, passivation not isolated
from morphology/contact alternatives, hydrophobicity alternatives, or
multifunctional passivators.

Primary readouts:

- Functional analog control class that preserves the intended comparison while
  changing one functional feature at a time where possible.
- Morphology and crystallinity bounding readouts.
- Hydrophobicity or barrier-effect comparison when stability or moisture
  tolerance is part of the claim.
- Contact energetics comparison when interface energetics could explain the
  effect.
- Recombination/trap-sensitive readouts to separate passivation from
  non-passivation alternatives.

Required controls:

- Matched no-modulator baseline.
- Functional analog class, described at design level only.
- Covariate bounds for morphology, crystallinity, hydrophobicity, contact
  energetics, and recombination/trap-sensitive readouts.

Decision logic:

- H gains support only when the proposed mechanism moves while bounded
  covariates do not explain the effect.
- Alt gains support when bounded covariates move in a way that explains the
  performance or stability change.
- If analog controls also change several variables, the result supports
  follow-up narrowing only and does not close the causal gap.

## Cross-Gap Bundling

Prefer bundled experiment classes when they preserve per-gap traceability:

- Passivation plus energy alignment: combine recombination readouts with
  work-function/contact-selectivity evidence.
- Aggregate performance/contact plus hysteresis: combine intensity-dependent
  JV, scan-rate JV, and EIS under controlled scan/preconditioning states.
- Stability plus morphology: combine matched stress retention with pre/post
  structural and optical degradation markers.

Bundling must not erase controls. If one control is required by any included
gap, keep it in the bundled plan.
