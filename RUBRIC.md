# Labeling rubric

Every row is one real company from the free YC OSS API dump
(`https://yc-oss.github.io/api/companies/all.json`, fetched 2026-08-14).
No row is invented. No field is invented.

The ICP encoded here is **"YC-backed, Series A to C, B2B SaaS"**, decomposed into three
binary axes. A company is ICP only if all three are 1.

---

## Axis 1 - `is_b2b` (hand-labeled)

`1` if the primary paying customer is a business or organization. SMBs, solo
professional practices, clinics, law firms, restaurants, schools, and HOAs all count as
businesses.
`0` if the primary payer is an individual consumer spending their own money.

Ad-supported and creator-facing products are `0` unless the invoice goes to a company.

## Axis 2 - `is_saas` (hand-labeled)

`1` if the primary revenue line is a recurring software subscription or usage-priced
software/API that the customer self-serves or is provisioned into.

`0` if the primary revenue line is:
- human labor sold as a service (agency, staffing, consulting, managed service,
  bookkeeping-with-accountants, medical billing services, data-labeling services)
- hardware, robots, materials, physical goods, manufacturing
- biotech, therapeutics, reagents
- marketplace or wholesale take-rate
- lending, balance-sheet, or payments interchange
- logistics, delivery, or food operations

`is_saas` is judged independently of who buys, so a consumer subscription app is
`is_saas=1, is_b2b=0`.

## Axis 3 - `stage_fit` (computed, and it is a PROXY - read this)

No free source gives a reliable Series letter for 120 companies. So this axis is
**computed deterministically** from two YC-supplied fields, and it is a proxy, not a
funding-round label:

```
stage_fit = 1  iff  status == "Active"  AND  yc_stage == "Growth"
```

Rationale: `yc_stage == "Growth"` excludes seed-stage companies YC still classifies as
Early; `status == "Active"` excludes Acquired, Public, and Inactive companies, which are
the Series D+/exited/dead tail. What survives is the independent, scaled-past-seed band
that "Series A to C" is trying to name.

**Where this proxy is wrong:** YC's `stage` field is coarse and is not re-derived per
funding round. Companies that raised a large round without YC updating the flag land in
the wrong bucket. This is disclosed rather than hidden, and the per-axis table in
`results/report.txt` reports the stage axis separately so its error can be read off directly.

## Composite

```
icp = is_b2b AND is_saas AND stage_fit
```

## `borderline`

`1` marks rows where a careful second labeler could reasonably disagree. 21 of 120 rows
are flagged. They are kept in the set and counted normally; they are also reported as a
separate slice in `results/report.txt`, because a benchmark that quietly drops its hard cases
reports a precision it did not earn.

---

## Information gap between labeler and classifier (this is the point)

The labeler reads `long_description`, `tags`, `subindustry`, `status`, and `yc_stage`.

The classifier is only given `one_liner`, top-level `industries`, `team_size`, `batch`,
and `website` - roughly what a real inbound pipeline has after a form fill plus
firmographic enrichment. It never sees the long description or the YC stage flag.

Without that gap the benchmark would be circular and the F1 would be meaningless.
