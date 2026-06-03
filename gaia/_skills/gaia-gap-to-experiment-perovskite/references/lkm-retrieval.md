# LKM Retrieval

Use LKM as the main external mechanism-reasoning source alongside
package-local Gaia evidence. It is not a replacement for the local SQLite
database because the database remains the hard precedent-retrieval gate before
experiment cards are drafted.

SQLite and LKM have different roles:

- SQLite is for precedent discovery, device/composition/intervention matching,
  paired performance deltas, hysteresis evidence, and stability protocol
  comparison.
- LKM is for mechanism claims, reasoning chains, competing explanations,
  premises, missing causal links, variables/factors relevant to measurement
  logic, and why a readout would distinguish H from Alt.

Do not claim that SQLite performance deltas prove a mechanism by themselves.
Use LKM or package-local reasoning to justify mechanism interpretation. If
SQLite precedent patterns and LKM reasoning disagree, explicitly report the
conflict and design the card to resolve it.

The documented API base URL is:

`https://open.bohrium.com/openapi/v1/lkm`

API documentation source:

`https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84`

Read the access key from `GAIA_LKM_ACCESS_KEY` or `LKM_ACCESS_KEY` when
available. The generator also checks `.env` files in this order: package,
output directory, current working directory, then the Gaia repo root. In this
workspace, the shared key is expected in `/personal/Gaia-v0.5/.env`. Do not copy
secrets into the repository, generated YAML/Markdown, or `lkm/*.json`; recording
only the variable name and source path is acceptable. The API documentation
shows an access-key header; use the header name accepted by the service, with
examples using `accessKey`.

```python
import os
import requests

BASE_URL = "https://open.bohrium.com/openapi/v1/lkm"
access_key = os.environ.get("GAIA_LKM_ACCESS_KEY") or os.environ.get("LKM_ACCESS_KEY")
headers = {"accessKey": access_key} if access_key else {}
```

If LKM access is unavailable or a request fails, record this in
`lkm_evidence_summary`, reduce card confidence, and continue only when the
SQLite database retrieval has succeeded.

If LKM is unavailable or failed, emit `lkm_unavailable` in the card or
retrieval diagnostics. Do not summarize an LKM failure as successful evidence.
Mechanism attribution confidence must be `low` unless strong package-local Gaia
mechanism reasoning supports at most `moderate` overall confidence.

When LKM retrieval is used, write redacted audit artifacts under `lkm/*.json`.
Store request summaries, endpoint names, result identifiers, relevant snippets,
and failure metadata. Do not store `LKM_ACCESS_KEY`, request headers, `.env`
contents, or other secrets. Summarize the same retrieval status in
`retrieval_evidence.yaml`.

## Query Terms

For every gap, build search text from:

- perovskite composition or absorber family
- interface location
- modulator type or material
- mechanism terms: passivation, recombination, aggregate performance metrics,
  hysteresis, ion migration, stability, energy alignment, crystallization,
  morphology, contact selectivity, charge extraction
- H, Alt, and the discriminating observation from `ANALYSIS.md`

Use domain terms from the Gaia package and SQLite hits. Do not introduce
mechanism certainty before retrieval; phrase broad queries as questions when
appropriate.

Every gap uses two LKM query intents:

1. Mechanism reasoning query:
   - What mechanism chains support or undermine this claim?
   - What competing explanations exist?
2. Experiment-design reasoning query:
   - What measurement classes distinguish H from Alt?
   - What controls isolate mechanism A from mechanism B?
   - What observations support H, support Alt, or remain unresolved?
   - What evidence would be insufficient?
   - How should this be translated to inverted p-i-n architecture?

Summarize the second intent into `lkm_design_reasoning`:

```yaml
lkm_design_reasoning:
  endpoint:
  query:
  readout_classes:
  controls:
  confounders:
  closure_rules:
  non_closure_rules:
  portability_notes:
  provenance:
  same_package:
  cross_package:
  ambiguous:
```

## Endpoint Workflow

### 1. Claim Search

Call `POST /search` for claim/question retrieval.

Required settings for this skill:

- `retrieval_mode = "hybrid"`
- `scopes = ["claim"]`
- `reasoning_only = true`

Use this to find relevant mechanism claims and question-like claims. Store the
request summary in `lkm_queries_run`.

Example request shape:

```python
payload = {
    "query": "FA/Cs perovskite interface passivation hysteresis recombination alternative contact resistance",
    "retrieval_mode": "hybrid",
    "scopes": ["claim"],
    "reasoning_only": True,
    "limit": 10,
}
resp = requests.post(f"{BASE_URL}/search", json=payload, headers=headers, timeout=60)
resp.raise_for_status()
matches = resp.json()
```

If claim search times out but reasoning-chain search and paper graph retrieval
succeed, do not treat LKM as absent. Record the claim-search timeout in
`retrieval_evidence.yaml` and `lkm_evidence_summary`, preserve the successful
reasoning/paper-graph evidence, and add a confidence caveat.

### 2. Reasoning-Chain Search

Call `POST /reasoning/search` with a natural-language description of the gap.
Use this to retrieve full reasoning chains rather than isolated claims.

Example query:

```text
For an interfacial modulator in a perovskite solar cell, an aggregate device
metric and Voc improved. Is the improvement better explained by defect
passivation, reduced non-radiative recombination, improved contact selectivity,
or reduced transport/contact losses? What observations distinguish these
explanations?
```

Summarize returned chains into premises, mechanism support, competing
explanations, and suggested discriminating observations.

Classify every returned chain:

- `same_package_lkm_chains` when the chain belongs to the source paper/package.
- `cross_package_lkm_chains` when the chain belongs to another paper/package.

Cross-package chains may inspire H-vs-Alt design or readout classes, but they
must not be presented as source-paper-internal mechanism proof.

### 3. Claim Reasoning

If `/search` or `/reasoning/search` returns a relevant claim id, call:

`GET /claims/{id}/reasoning`

Use request parameters such as `max_chains` and chain sorting when supported by
the API. Prefer reasoning chains with explicit premises and paper provenance.

### 4. Paper Graph

If a relevant paper is identified by DOI, title, package id, or paper id, call:

`POST /papers/graph`

Use this to retrieve variables, factors, motivations, and paper-local reasoning
structure. Record whether variables or factors map to the Gaia gap's proposed
readouts or controls.

### 5. Variable Hydration

When other endpoints return variable IDs, call:

`POST /variables/batch`

Hydrate at most the service-supported batch size per request. The documented
limit is 100 IDs per batch. Use hydrated details to clarify variable names,
units, measurement types, and whether they are inputs, factors, or outcomes.

## LKM Evidence Summary

For every gap, summarize LKM output into:

- supported mechanism claims
- competing explanations
- relevant premises
- suggested discriminating observations
- provenance papers
- provenance identifiers when available: `source_package`, paper id, claim id,
  conclusion id, chain id, title, score, and rerank score
- same-package chain summary
- cross-package chain summary
- variables or factors relevant to controls/readouts
- whether LKM agrees with, conflicts with, or is orthogonal to the local
  database patterns
- retrieval failures or access limitations

Do not present LKM claims as operational instructions. If chain text contains
protocol details, compress them into non-operational planning categories such
as "interface-treatment precedent" or "stability-stress category."

## Conflict Handling

When LKM and the database disagree:

- Favor neither source automatically.
- State the conflict explicitly in `lkm_evidence_summary` and
  `database_precedents`, `priority_rationale`, and the human-readable roadmap.
- Design the card's discriminating observation to test the unresolved
  mechanism, not to confirm the preferred source.
- Lower confidence unless the conflict itself makes the experiment especially
  valuable.

## Output Diagnostics

When LKM retrieval succeeds, `retrieval_evidence.yaml` must list per gap:

- `successful_endpoints`
- `failed_endpoints`
- `same_package_lkm_chains`
- `cross_package_lkm_chains`
- retained provenance fields
- SQLite/LKM agreement, conflict, or orthogonality

When only some endpoints succeed, preserve the successful reasoning evidence
and list the failed endpoints separately. Do not collapse partial failure into
either "LKM absent" or "LKM fully succeeded."
