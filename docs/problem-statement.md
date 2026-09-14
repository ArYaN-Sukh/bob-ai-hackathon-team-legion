# Problem Statement — Clinical Trial Risk Monitor

## The Challenge

Clinical trials are one of the most regulated and high-stakes activities in medicine. Before any new drug reaches patients, it must pass through Phase I, II, and III trials governed by **ICH E6(R2) Good Clinical Practice (GCP)** guidelines and scrutinised by regulatory bodies including the FDA and EMA.

### Protocol Deviations: A Pervasive and Costly Problem

A **protocol deviation** occurs when the conduct of a clinical trial diverges from the approved protocol — a patient is enrolled despite failing an inclusion criterion, a scheduled visit window is missed, a Serious Adverse Event (SAE) is not reported within 24 hours. Every deviation creates a risk to patient safety, data integrity, and regulatory acceptability.

**The scale is significant:**
- FDA inspection findings consistently cite protocol deviations as a leading cause of clinical trial failure
- Studies indicate 30–60% of trials experience at least one major deviation per site
- A single undetected eligibility breach can invalidate an entire patient's data contribution
- SAE reporting delays above 24 hours violate GCP §5.17 and trigger mandatory FDA submission amendments

### The Manual Monitoring Problem

Today, Clinical Research Associates (CRAs) monitor trial sites through:
1. **Source Data Verification (SDV):** Manually comparing patient records to source documents
2. **Site monitoring visits:** On-site audits every 4–12 weeks per site
3. **Data Clarification Forms (DCFs):** Back-and-forth paper queries for every discrepancy

This process is:
- **Reactive** — deviations are discovered weeks after they occur
- **Labour-intensive** — a CRA spends ~60% of monitoring time on manual checks
- **Non-prioritised** — all sites receive the same cadence regardless of actual risk
- **Poorly tooled** — most sponsors use Excel spreadsheets or basic CTMS systems

### Consequence of Inadequate Monitoring

- **Patient Safety Risk:** Ineligible patients may receive experimental treatment
- **Data Integrity Failure:** Protocol deviations can render primary endpoint data unusable
- **Regulatory Action:** FDA 483 observations, warning letters, and Complete Response Letters (CRLs) citing inadequate monitoring
- **Financial Impact:** A Phase III trial costs $50M–$500M; a single CRL can delay approval by 12–24 months

## The Opportunity

The shift to **Risk-Based Monitoring (RBM)** under ICH E6(R2) requires sponsors to:
1. Identify critical process and data variables
2. Score sites by risk tier
3. Focus monitoring effort on high-risk sites

This is exactly the problem TrialGuard addresses: **automating the detection, classification, and risk-scoring of protocol deviations** so CRAs can act proactively rather than reactively.

## Target Users

| User | Need |
|------|------|
| Clinical Research Associate (CRA) | Know which sites need immediate attention before a monitoring visit |
| Data Manager | Quickly identify patients with open lab threshold violations |
| Medical Monitor | View SAE reporting compliance across all sites in real time |
| Sponsor QA | Generate CAPA documentation for inspection readiness |

## References

- ICH E6(R2) Good Clinical Practice Guideline (2016)
- FDA Guidance on Risk-Based Approach to Monitoring (2013)
- FDA Inspection Observations — BIMO Metrics (2022)
- TransCelerate BioPharma — Risk-Based Quality Management Framework (2021)
