#!/usr/bin/env python3
"""Evaluate every classifier in classify.py against icp_eval.csv.

Prints precision / recall / F1, the full confusion matrix, per-axis accuracy,
the borderline slice, cost-per-resolved-lead, and every individual error.

    python3 evaluate.py > results/report.txt
"""
import csv
import sys

from classify import CLASSIFIERS

# Enrichment unit cost is an INPUT ASSUMPTION, not a measured number. It is the
# price of one enrichment/resolution call on whatever vendor is behind the
# pipeline. Sweep it rather than trusting one value.
UNIT_COSTS = [0.02, 0.05, 0.10, 0.25]
DEFAULT_UNIT_COST = 0.10


def confusion(rows, preds, key="icp"):
    tp = fp = fn = tn = 0
    for r, p in zip(rows, preds):
        y, yhat = int(r[key]), p[key if key == "icp" else key]
        if y and yhat:
            tp += 1
        elif not y and yhat:
            fp += 1
        elif y and not yhat:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def main():
    rows = list(csv.DictReader(open("icp_eval.csv")))
    n = len(rows)
    pos = sum(int(r["icp"]) for r in rows)

    print("=" * 74)
    print("ICP BENCHMARK - 120 real YC companies, hand-labeled")
    print("=" * 74)
    print(f"rows: {n}   ICP positives: {pos} ({pos/n:.1%})   "
          f"borderline: {sum(int(r['borderline']) for r in rows)}")
    print(f"source: free YC OSS API (yc-oss.github.io/api), fetched 2026-08-14")
    print()

    results = {}
    for name, fn_ in CLASSIFIERS.items():
        preds = [fn_(r) for r in rows]
        results[name] = preds

    # ---- headline table ----
    print("-" * 74)
    print("ICP CLASSIFICATION (composite: b2b AND saas AND stage)")
    print("-" * 74)
    print(f"{'classifier':<16}{'TP':>4}{'FP':>4}{'FN':>4}{'TN':>4}"
          f"{'prec':>8}{'recall':>8}{'F1':>8}{'acc':>8}")
    for name, preds in results.items():
        tp, fp, fn, tn = confusion(rows, preds)
        p, r, f = prf(tp, fp, fn)
        print(f"{name:<16}{tp:>4}{fp:>4}{fn:>4}{tn:>4}"
              f"{p:>8.3f}{r:>8.3f}{f:>8.3f}{(tp+tn)/n:>8.3f}")
    print()

    # ---- confusion matrices, printed in full ----
    for name, preds in results.items():
        tp, fp, fn, tn = confusion(rows, preds)
        print(f"confusion matrix - {name}")
        print(f"                 pred ICP   pred not")
        print(f"  actual ICP     {tp:>8}   {fn:>8}")
        print(f"  actual not     {fp:>8}   {tn:>8}")
        print()

    # ---- per-axis accuracy ----
    print("-" * 74)
    print("PER-AXIS ACCURACY (rules classifier)")
    print("-" * 74)
    preds = results["rules"]
    for axis, label in (("b2b", "is_b2b"), ("saas", "is_saas"), ("stage", "stage_fit")):
        correct = sum(int(int(r[label]) == p[axis]) for r, p in zip(rows, preds))
        tp = sum(1 for r, p in zip(rows, preds) if int(r[label]) and p[axis])
        fp = sum(1 for r, p in zip(rows, preds) if not int(r[label]) and p[axis])
        fn = sum(1 for r, p in zip(rows, preds) if int(r[label]) and not p[axis])
        pr, rc, f1 = prf(tp, fp, fn)
        print(f"  {label:<10} acc={correct/n:.3f}  prec={pr:.3f}  recall={rc:.3f}  F1={f1:.3f}"
              f"   (TP={tp} FP={fp} FN={fn})")
    print()
    print("  NOTE: stage_fit is a proxy axis (see RUBRIC.md), and going in it was the")
    print("  axis expected to dominate the loss. It does not. is_saas is the weakest")
    print("  axis by F1, and the error list below shows why.")
    print()

    # ---- borderline slice ----
    print("-" * 74)
    print("SLICE: borderline rows excluded (the easy half of the set)")
    print("-" * 74)
    easy = [r for r in rows if not int(r["borderline"])]
    print(f"{'classifier':<16}{'n':>5}{'pos':>5}{'prec':>8}{'recall':>8}{'F1':>8}")
    for name, fn_ in CLASSIFIERS.items():
        ep = [fn_(r) for r in easy]
        tp, fp, fn, tn = confusion(easy, ep)
        p, r, f = prf(tp, fp, fn)
        print(f"{name:<16}{len(easy):>5}{sum(int(x['icp']) for x in easy):>5}"
              f"{p:>8.3f}{r:>8.3f}{f:>8.3f}")
    print()

    # ---- cost per resolved lead ----
    print("-" * 74)
    print("COST PER RESOLVED LEAD")
    print("-" * 74)
    print("  cost_per_resolved_lead = unit_cost * (leads enriched) / (true ICP leads found)")
    print("  'leads enriched' = predicted positives. unit_cost is an INPUT ASSUMPTION,")
    print("  not a measured price, so it is swept rather than asserted.")
    print()
    hdr = "".join(f"{'$%.2f/call' % u:>12}" for u in UNIT_COSTS)
    print(f"{'classifier':<16}{'enriched':>10}{'found':>7}{hdr}")
    for name, preds in results.items():
        enriched = sum(p["icp"] for p in preds)
        found = sum(1 for r, p in zip(rows, preds) if int(r["icp"]) and p["icp"])
        cells = "".join(
            f"{('$%.3f' % (u * enriched / found)) if found else 'n/a':>12}"
            for u in UNIT_COSTS)
        print(f"{name:<16}{enriched:>10}{found:>7}{cells}")
    print()
    base = results["enrich_all"]
    b_enriched = sum(p["icp"] for p in base)
    b_found = sum(1 for r, p in zip(rows, base) if int(r["icp"]) and p["icp"])
    print(f"  at ${DEFAULT_UNIT_COST:.2f}/call, versus enriching every lead:")
    for name in ("rules", "rules_v2"):
        preds = results[name]
        enr = sum(p["icp"] for p in preds)
        fnd = sum(1 for r, p in zip(rows, preds) if int(r["icp"]) and p["icp"])
        print(f"    {name:<9} calls {enr:>3} vs {b_enriched} "
              f"({100*(1-enr/b_enriched):>5.1f}% fewer) | "
              f"ICP found {fnd:>2}/{b_found} ({100*fnd/b_found:>5.1f}%) | "
              f"${DEFAULT_UNIT_COST*enr/fnd:.3f} vs ${DEFAULT_UNIT_COST*b_enriched/b_found:.3f} "
              f"per resolved lead")
    print()

    # ---- every error, named ----
    for name in ("rules", "rules_v2"):
        print("-" * 74)
        print(f"ERRORS - {name}, every one of them")
        print("-" * 74)
        for r, p in zip(rows, results[name]):
            y = int(r["icp"])
            if y == p["icp"]:
                continue
            kind = "FN (missed real ICP)" if y else "FP (wasted enrichment)"
            axes = (f"b2b {int(r['is_b2b'])}/{p['b2b']} "
                    f"saas {int(r['is_saas'])}/{p['saas']} "
                    f"stage {int(r['stage_fit'])}/{p['stage']}")
            flag = " [borderline]" if int(r["borderline"]) else ""
            print(f"  {kind:<24}{r['name']:<26}team={r['team_size']:<5}{axes}{flag}")
            print(f"      one_liner: {r['one_liner'][:88]}")
        print()
    print("(true/pred shown per axis)")


if __name__ == "__main__":
    sys.exit(main())
