#!/usr/bin/env python3
"""Join the sampled companies with the hand labels and emit icp_eval.csv.

stage_fit is computed here, not hand-entered, so it cannot drift from the rule
written down in RUBRIC.md.
"""
import csv
import json

SAMPLE = "sample_unlabeled.jsonl"
LABELS = "labels.csv"
OUT = "icp_eval.csv"

FEATURE_COLS = ["one_liner", "industries", "team_size", "batch", "website"]


def main():
    rows = {json.loads(l)["id"]: json.loads(l) for l in open(SAMPLE)}

    with open(LABELS) as fh:
        reader = csv.DictReader(fh)
        labels = list(reader)
    for i, rec in enumerate(labels, 2):
        if len(rec) != 6 or any(v is None for v in rec.values()):
            raise SystemExit(f"{LABELS} line {i}: wrong field count (stray comma in a note?)")

    if len(labels) != len(rows):
        raise SystemExit(f"{len(labels)} labels vs {len(rows)} sampled rows")

    out = []
    for rec in labels:
        cid = int(rec["id"])
        c = rows[cid]
        if c["name"] != rec["name"]:
            raise SystemExit(f"id {cid}: label name {rec['name']!r} != sample {c['name']!r}")
        is_b2b = int(rec["is_b2b"])
        is_saas = int(rec["is_saas"])
        # computed axis, see RUBRIC.md
        stage_fit = int(c["status"] == "Active" and c["yc_stage"] == "Growth")
        out.append({
            "id": cid,
            "name": c["name"],
            "stratum": c["stratum"],
            # --- features the classifier is allowed to see ---
            "one_liner": c["one_liner"],
            "industries": "|".join(c["industries"]),
            "team_size": c["team_size"],
            "batch": c["batch"],
            "website": c["website"],
            # --- labeler-only evidence, kept for auditability ---
            "yc_status": c["status"],
            "yc_stage": c["yc_stage"],
            # --- labels ---
            "is_b2b": is_b2b,
            "is_saas": is_saas,
            "stage_fit": stage_fit,
            "icp": int(is_b2b and is_saas and stage_fit),
            "borderline": int(rec["borderline"]),
            "label_note": rec["note"],
            "label_source": "YC OSS API long_description + tags + subindustry, read by hand",
        })

    out.sort(key=lambda r: r["id"])
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    pos = sum(r["icp"] for r in out)
    print(f"wrote {OUT}: {len(out)} rows, {pos} ICP positives ({pos/len(out):.1%}), "
          f"{sum(r['borderline'] for r in out)} borderline")
    for axis in ("is_b2b", "is_saas", "stage_fit"):
        print(f"  {axis:10s} positives: {sum(r[axis] for r in out)}")


if __name__ == "__main__":
    main()
