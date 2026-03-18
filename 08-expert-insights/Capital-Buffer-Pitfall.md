---
type: expert_insight
topic: Capital conservation buffer miscalculation
risk_category: Compliance
applies_to_roles: [CRO, CFO]
severity: high
tags: [capital, rwa, cet1, basel_iii, off_balance_sheet]
---

## The pitfall

Off-balance sheet items — including unfunded loan commitments, letters of credit, and derivatives — are excluded from the Risk-Weighted Asset (RWA) calculation. This causes CET1 ratios to appear higher than they actually are under stress, leading management to believe capital buffers are adequate when they are not.

## Why it matters

The [[Basel-III-Capital-Rules]] require all material off-balance sheet exposures to be converted to credit equivalent amounts using Credit Conversion Factors (CCFs) and included in RWA. Institutions that omit or underweight these exposures will:

- Overstate CET1 capital ratios in regulatory filings
- Understate capital requirements under adverse stress scenarios in [[DFAST-Stress-Testing]]
- Risk an MRA or MRiA from the OCC or Federal Reserve upon examination
- Potentially trigger prompt corrective action if the error is material

See [[OCC-Capital-Guidance]] for the OCC's specific expectations on off-balance sheet treatment.

## How to avoid it

1. Quarterly review of all contingent liabilities and off-balance sheet exposures by the CFO and CRO jointly
2. Reconcile off-balance sheet schedule (Call Report Schedule RC-L) to the RWA model inputs every reporting period
3. Independent model validation of the RWA calculation — at minimum annually. See [[SR-11-7-Model-Risk]]
4. Board Risk Committee should receive a quarterly capital adequacy report that explicitly shows OBS contribution to RWA

## Examiner focus

OCC and Federal Reserve examiners specifically target the RWA model during capital adequacy reviews. They will request:
- Model documentation for the CCF assignment methodology
- Evidence of independent validation
- Prior period reconciliations between Call Report and internal capital models

This is a high-frequency finding at institutions between $1Bn and $50Bn in assets.

## Related regulations

[[Basel-III-Capital-Rules]] | [[OCC-Capital-Guidance]] | [[DFAST-Stress-Testing]] | [[SR-11-7-Model-Risk]]
