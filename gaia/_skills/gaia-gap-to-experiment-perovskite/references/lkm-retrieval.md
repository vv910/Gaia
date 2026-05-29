# LKM Retrieval

Use LKM as a complementary reasoning-evidence source, not as a replacement for
the local SQLite database. The database remains the hard gate for experiment
cards.

SQLite and LKM have different roles:

- SQLite is for precedent discovery, device/composition/intervention matching,
  paired performance deltas, hysteresis evidence, and stability protocol
  comparison.
- LKM is for mechanism claims, reasoning chains, competing explanations,
  premises, variables/factors relevant to measurement logic, and why a readout
  would distinguish H from Alt.

Do not claim that SQLite performance deltas prove a mechanism by themselves.
Use LKM or package-local reasoning to justify mechanism interpretation. If
SQLite precedent patterns and LKM reasoning disagree, explicitly report the
conflict and design the card to resolve it.

The documented API base URL is:

`https://open.bohrium.com/openapi/v1/lkm`

API documentation source:

`https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84`

Read the access key from `LKM_ACCESS_KEY` when available. Do not copy secrets
into the repository. The API documentation shows an access-key header; use the
header name accepted by the service, with examples using `accessKey`.

```python
import os
import requests

BASE_URL = "https://open.bohrium.com/openapi/v1/lkm"
access_key = os.environ.get("LKM_ACCESS_KEY")
headers = {"accessKey": access_key} if access_key else {}
```

If LKM access is unavailable or a request fails, record this in
`lkm_evidence_summary`, reduce card confidence, and continue only when the
SQLite database retrieval has succeeded.

## Query Terms

For every gap, build search text from:

- perovskite composition or absorber family
- interface location
- modulator type or material
- mechanism terms: passivation, recombination, FF, hysteresis, ion migration,
  stability, energy alignment, crystallization, morphology, contact
  selectivity, charge extraction
- H, Alt, and the discriminating observation from `ANALYSIS.md`

Use domain terms from the Gaia package and SQLite hits. Do not introduce
mechanism certainty before retrieval; phrase broad queries as questions when
appropriate.

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
    "query": "FA/Cs perovskite interface passivation FF hysteresis recombination alternative contact resistance",
    "retrieval_mode": "hybrid",
    "scopes": ["claim"],
    "reasoning_only": True,
    "limit": 10,
}
resp = requests.post(f"{BASE_URL}/search", json=payload, headers=headers, timeout=60)
resp.raise_for_status()
matches = resp.json()
```

### 2. Reasoning-Chain Search

Call `POST /reasoning/search` with a natural-language description of the gap.
Use this to retrieve full reasoning chains rather than isolated claims.

Example query:

```text
For an interfacial modulator in a perovskite solar cell, FF and Voc improved.
Is the improvement better explained by defect passivation, reduced
non-radiative recombination, improved contact selectivity, or reduced series
resistance? What observations distinguish these explanations?
```

Summarize returned chains into premises, mechanism support, competing
explanations, and suggested discriminating observations.

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
