"""Build the JSON the results page reads.

Imports the repository's own classifiers and its confusion/prf helpers and
re-runs them over icp_eval.csv, rather than parsing results/report.txt. The
page therefore shows what the code does, and adding a classifier to
classify.py puts it on the page without touching this file.

    python3 scripts/make_page_data.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from classify import CLASSIFIERS          # noqa: E402
from evaluate import confusion, prf       # noqa: E402

OUT = ROOT / "docs" / "data"

# Unit cost per enrichment call is an input assumption, not a measured price,
# so the page sweeps it the same way the report does.
UNIT_COSTS = [0.02, 0.05, 0.10, 0.25]


# The classifiers return a dict of the three axis calls plus the composite
# `icp`, so the axes are already there and nothing needs to be re-derived.
AXIS_PRED = {"is_b2b": "b2b", "is_saas": "saas", "stage_fit": "stage"}


def axis_scores(rows: list[dict], preds: list[dict]) -> dict:
    out = {}
    for gold_key, pred_key in AXIS_PRED.items():
        tp = fp = fn = 0
        for r, pred in zip(rows, preds):
            got, want = bool(pred[pred_key]), bool(int(r[gold_key]))
            tp += got and want
            fp += got and not want
            fn += want and not got
        p, rec, f1 = prf(tp, fp, fn)
        out[gold_key] = {"precision": p, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}
    return out


def main() -> None:
    rows = list(csv.DictReader((ROOT / "icp_eval.csv").open()))
    n = len(rows)
    positives = sum(int(r["icp"]) for r in rows)

    classifiers = []
    for name, fn in CLASSIFIERS.items():
        preds = [fn(r) for r in rows]
        tp, fp, fn_, tn = confusion(rows, preds)
        p, rec, f1 = prf(tp, fp, fn_)
        enriched = tp + fp
        classifiers.append({
            "name": name,
            "tp": tp, "fp": fp, "fn": fn_, "tn": tn,
            "precision": p, "recall": rec, "f1": f1,
            "accuracy": (tp + tn) / n,
            # What a team would actually pay: every predicted positive gets
            # enriched, and only the true positives were worth enriching.
            "enriched": enriched,
            "found": tp,
            "cost_per_resolved": {
                str(c): (c * enriched / tp) if tp else None for c in UNIT_COSTS
            },
            # Every error, named, because a benchmark that reports a score
            # without its mistakes cannot be argued with.
            "axes": axis_scores(rows, preds),
            # Every error, named, because a benchmark that reports a score
            # without its mistakes cannot be argued with.
            "errors": [
                {
                    "name": r["name"],
                    "kind": "missed" if int(r["icp"]) else "wasted",
                    "team_size": r["team_size"],
                    "one_liner": r["one_liner"],
                    "borderline": bool(int(r["borderline"])),
                    "axes": {
                        gold: {"gold": int(r[gold]), "pred": int(pred[pk])}
                        for gold, pk in AXIS_PRED.items()
                    },
                }
                for r, pred in zip(rows, preds)
                if bool(pred["icp"]) != bool(int(r["icp"]))
            ],
        })

    payload = {
        # Every labelled row, so the page can re-run the whole set through the
        # in-browser classifier at load and show that it reproduces the score.
        "rows": [
            {k: r[k] for k in
             ("name", "industries", "one_liner", "team_size", "batch", "icp", "borderline")}
            for r in rows
        ],
        "n": n,
        "positives": positives,
        "borderline": sum(int(r["borderline"]) for r in rows),
        "unit_costs": UNIT_COSTS,
        "classifiers": classifiers,
        "source": "free YC OSS API (yc-oss.github.io/api), fetched 2026-08-14",
    }
    # The page runs classify.py itself, in Pyodide, so a reader can score a
    # company the repository never saw. Copying the module verbatim rather than
    # porting it is what keeps the thing in the browser and the thing that was
    # measured from drifting apart.
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "classify.py").write_text((ROOT / "classify.py").read_text())

    path = OUT / "eval.json"
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} kB")
    for c in classifiers:
        print(f"  {c['name']:<16} prec {c['precision']:.3f}  recall {c['recall']:.3f}  "
              f"F1 {c['f1']:.3f}  errors {len(c['errors'])}")


if __name__ == "__main__":
    main()
