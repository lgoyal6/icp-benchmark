#!/usr/bin/env python3
"""ICP classifiers.

Every classifier sees ONLY the fields a real inbound pipeline has after a form
fill plus firmographic enrichment: one_liner, industries, team_size, batch,
website. None of them sees the long description or the YC stage flag that the
labeler used. See RUBRIC.md.
"""
import re

CURRENT_YEAR = 2026

# --- vocabulary for the rules classifier -------------------------------------
# Words that show up in the tagline of something you can sell as a subscription.
SAAS_WORDS = {
    "software", "saas", "platform", "api", "app", "dashboard", "tool", "tools",
    "suite", "os", "crm", "erp", "cms", "ehr", "analytics", "automation",
    "automate", "automated", "automating", "workflow", "observability",
    "monitoring", "infrastructure", "agents", "agent", "copilot", "engine",
}
# Words that mean the revenue line is not a software subscription.
NON_SAAS_WORDS = {
    "marketplace", "wholesale", "network", "services", "service", "agency",
    "managed", "consulting", "staffing", "robot", "robots", "robotic",
    "hardware", "device", "devices", "wearable", "coating", "coatings",
    "materials", "manufacturing", "manufacture", "supply", "supplies",
    "logistics", "delivery", "fleet", "catering", "food", "lending", "loans",
    "capital", "bank", "banking", "neobank", "fund", "reagents", "therapeutics",
    "biotech", "satellites", "data centers", "components", "purchasing",
    "billing services", "labeling",
}
CONSUMER_WORDS = {
    "consumer", "consumers", "shoppers", "job seekers", "people", "friends",
    "personal", "your favorite", "everyone",
}
BIZ_WORDS = {
    "b2b", "business", "businesses", "company", "companies", "teams", "team",
    "enterprise", "developers", "organizations", "firms", "operators",
    "merchants", "brands", "sales", "recruiters", "marketing",
}


def _words(text):
    return set(re.findall(r"[a-z]+", text.lower()))


def _batch_year(batch):
    m = re.search(r"(\d{4})", batch or "")
    return int(m.group(1)) if m else CURRENT_YEAR


# --- classifier 1: enrich everything (status quo baseline) -------------------
def baseline_enrich_all(row):
    return {"b2b": 1, "saas": 1, "stage": 1, "icp": 1}


# --- classifier 2: trust the industry tag alone ------------------------------
def baseline_industry_tag(row):
    b2b = int("B2B" in row["industries"].split("|"))
    return {"b2b": b2b, "saas": b2b, "stage": 1, "icp": b2b}


# --- classifier 3: transparent 3-axis rules ----------------------------------
def rules(row):
    inds = set(row["industries"].split("|"))
    one = row["one_liner"]
    w = _words(one)
    low = one.lower()
    team = int(row["team_size"])

    # axis 1: b2b
    if "B2B" in inds:
        b2b = 1
    elif "Consumer" in inds:
        b2b = 0
    else:
        b2b = int(bool(w & BIZ_WORDS) and not (w & CONSUMER_WORDS))

    # axis 2: saas
    hits = len(w & SAAS_WORDS)
    misses = len(w & NON_SAAS_WORDS) + sum(p in low for p in NON_SAAS_WORDS if " " in p)
    saas = int(hits > misses)

    # axis 3: stage. headcount band plus enough time since the batch that a
    # seed round would have been raised and deployed.
    age = CURRENT_YEAR - _batch_year(row["batch"])
    stage = int(20 <= team <= 500 and age >= 2)

    return {"b2b": b2b, "saas": saas, "stage": stage,
            "icp": int(b2b and saas and stage)}


# --- classifier 4: rules with the saas axis inverted -------------------------
# Written AFTER reading the error list from `rules`, so its numbers are in-sample
# and should be read as an upper bound (see RESULTS.md). The change is one
# principled edit, not per-row tuning: absence of software vocabulary in a
# tagline is not evidence of absence of software, so the saas axis defaults to
# yes and is vetoed only by an explicit non-software signal.
def rules_v2(row):
    base = rules(row)
    one = row["one_liner"]
    w = _words(one)
    low = one.lower()
    veto = bool(w & NON_SAAS_WORDS) or any(
        p in low for p in NON_SAAS_WORDS if " " in p)
    saas = int(not veto)
    return {"b2b": base["b2b"], "saas": saas, "stage": base["stage"],
            "icp": int(base["b2b"] and saas and base["stage"])}


CLASSIFIERS = {
    "enrich_all": baseline_enrich_all,
    "industry_tag": baseline_industry_tag,
    "rules": rules,
    "rules_v2": rules_v2,
}
