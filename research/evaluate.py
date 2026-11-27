"""Score fixed, independent, manually reviewed 30-second windows by deployment and noise."""
import argparse
import csv
import json
from collections import Counter, defaultdict


def evaluate(rows):
    counts = defaultdict(Counter)
    splits, seen = {}, set()
    for row in rows:
        deployment, split = row["deployment"], row["split"]
        key = (deployment, row["window_start_utc"], row["target"])
        if key in seen or splits.setdefault(deployment, split) != split:
            raise ValueError("Duplicate window or deployment shared between splits")
        seen.add(key)
        if split not in ("development", "held-out") or row["noise"] not in ("quiet", "moderate", "loud", "unknown"):
            raise ValueError("Unknown split or noise stratum")
        truth, predicted = row["review"], row["prediction"]
        if truth not in ("present", "absent", "unknown") or predicted not in ("present", "absent"):
            raise ValueError("Unexpected prediction or review")
        label = "excluded" if truth == "unknown" else {
            ("present", "present"): "TP", ("absent", "present"): "FP",
            ("present", "absent"): "FN", ("absent", "absent"): "TN"
        }[truth, predicted]
        for noise in ("all", row["noise"]):
            counts[(split, row["target"], noise)][label] += 1
    results = []
    for (split, target, noise), c in sorted(counts.items()):
        tp, fp, fn, tn = (c[k] for k in ("TP", "FP", "FN", "TN"))
        results.append(dict(split=split, target=target, noise=noise, TP=tp, FP=fp, FN=fn, TN=tn,
                            excluded=c["excluded"], precision=tp/(tp+fp) if tp+fp else None,
                            recall=tp/(tp+fn) if tp+fn else None,
                            false_positive_rate=fp/(fp+tn) if fp+tn else None))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    with open(parser.parse_args().csv, newline="") as src:
        print(json.dumps(evaluate(csv.DictReader(src)), indent=2))
