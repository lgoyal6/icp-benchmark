#!/usr/bin/env python3
"""Draw a deterministic, stratified sample of real companies from the free
YC OSS API (https://yc-oss.github.io/api/companies/all.json).

The strata are chosen so the evaluation set contains hard negatives, not just
easy ones: seed-stage B2B, late-stage/public B2B, consumer, and non-SaaS
(services, hardware, biotech). A classifier that only ever sees easy negatives
reports a precision number that means nothing.

Usage:
    python3 build_sample.py --raw yc_all.json --out sample_unlabeled.jsonl
"""
import argparse
import json
import random

# Fixed seed: the sample must be reproducible by anyone re-running this.
SEED = 20260814
TARGET = 120

NON_SAAS_TAGS = {
    "Hard Tech", "Hardware", "Robotics", "Manufacturing", "Biotech",
    "Therapeutics", "Drug Discovery", "Semiconductors", "Space", "Energy",
    "Climate", "Consulting", "Agency", "Marketplace", "Construction",
}


def stratum(c):
    """Assign each company to exactly one sampling stratum."""
    inds = set(c.get("industries") or [])
    tags = set(c.get("tags") or [])
    team = c.get("team_size") if isinstance(c.get("team_size"), int) else 0
    status = c.get("status")
    stage = c.get("stage")

    if "Consumer" in inds:
        return "consumer"
    if tags & NON_SAAS_TAGS:
        return "non_saas"
    if status in ("Public", "Acquired") or team > 500:
        return "late_stage"
    if "B2B" in inds and stage == "Growth" and status == "Active" and 20 <= team <= 500:
        return "b2b_growth"
    if "B2B" in inds and team and team < 15:
        return "b2b_seed"
    if inds & {"Fintech", "Healthcare"}:
        return "ambiguous"
    return None  # not sampled


QUOTA = {
    "b2b_growth": 34,
    "b2b_seed": 22,
    "late_stage": 16,
    "consumer": 20,
    "non_saas": 18,
    "ambiguous": 10,
}
assert sum(QUOTA.values()) == TARGET


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="yc_all.json")
    ap.add_argument("--out", default="sample_unlabeled.jsonl")
    args = ap.parse_args()

    companies = json.load(open(args.raw))
    buckets = {k: [] for k in QUOTA}
    for c in companies:
        # require the fields both the labeler and the classifier need
        if not c.get("one_liner") or not c.get("long_description"):
            continue
        if not isinstance(c.get("team_size"), int) or c["team_size"] <= 0:
            continue
        s = stratum(c)
        if s in buckets:
            buckets[s].append(c)

    rng = random.Random(SEED)
    picked = []
    for name, quota in sorted(QUOTA.items()):
        pool = sorted(buckets[name], key=lambda c: c["id"])  # stable order first
        if len(pool) < quota:
            raise SystemExit(f"stratum {name} has only {len(pool)} rows, need {quota}")
        picked += [(name, c) for c in rng.sample(pool, quota)]

    picked.sort(key=lambda t: t[1]["id"])
    with open(args.out, "w") as fh:
        for name, c in picked:
            fh.write(json.dumps({
                "id": c["id"],
                "stratum": name,
                "name": c["name"],
                "website": c.get("website", ""),
                "batch": c.get("batch", ""),
                "team_size": c["team_size"],
                "status": c.get("status", ""),
                "yc_stage": c.get("stage", ""),
                "industries": c.get("industries") or [],
                "subindustry": c.get("subindustry", ""),
                "tags": c.get("tags") or [],
                "one_liner": c["one_liner"],
                "long_description": " ".join(c["long_description"].split()),
            }) + "\n")

    print(f"wrote {len(picked)} rows to {args.out}")
    for name in sorted(QUOTA):
        print(f"  {name:12s} quota={QUOTA[name]:3d}  pool={len(buckets[name])}")


if __name__ == "__main__":
    main()
