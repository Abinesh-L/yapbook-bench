"""Recompute every number in README.md from judgments.json and questions.json.

Definitions (each item is graded by two judges, so n = 2 x questions):
  spoiler rate      = verdicts flagged spoiler=true / verdicts, over ahead + mixed items
  behind accuracy   = verdicts labelled correct / verdicts, over behind items (partial shown separately)
  position honesty  = verdicts labelled refused_appropriately / verdicts, over ahead items
  refused wrongly   = verdicts labelled refused_wrongly / verdicts, over behind + mixed items
  judge agreement   = (item, system) pairs where both judges gave the same label / flag

Usage:  python tools/score.py [--markdown] [--bench bench/grounding/run1]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
SYSTEMS = ("yapbook", "baseline")
LABELS = ("correct", "partial", "wrong", "refused_appropriately", "refused_wrongly")
SHORT_BOOK = {
    "attention-is-all-you-need": "attention",
    "auto-encoding-variational-bayes": "vae",
    "batch-normalization-accelerating-deep-network-training-by-reducing-internal-covariate-shift": "batchnorm",
    "react-synergizing-reasoning-and-acting-in-language-models": "react",
    "string-junctions-and-their-duals-in-heterotic-string-theory": "string-junctions",
    "rl-book-full-endurance": "rl-book",
}


def pct(a: int, b: int) -> str:
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def load(bench: Path = BENCH) -> tuple[dict, dict]:
    judgments = json.loads((bench / "judgments.json").read_text(encoding="utf-8"))
    questions_path = bench / "questions.json"
    if not questions_path.is_file():  # run1/ holds only its judgments; the questions are shared
        questions_path = BENCH / "questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    return judgments["items"], {q["id"]: q for q in questions}


def tally(items: dict, qs: dict, key) -> dict[tuple, Counter]:
    """Counter of labels/spoilers per (system, key(question))."""
    out: dict[tuple, Counter] = defaultdict(Counter)
    for qid, per_system in items.items():
        q = qs[qid]
        for system in SYSTEMS:
            c = out[(system, key(q))]
            for v in per_system[system]:
                c["n"] += 1
                c[v["correct"]] += 1
                c["spoilers"] += bool(v.get("spoiler"))
    return out


def headline(items: dict, qs: dict) -> dict:
    by_kind = tally(items, qs, lambda q: q["kind"])
    out = {}
    for s in SYSTEMS:
        ahead, mixed, behind = by_kind[(s, "ahead")], by_kind[(s, "mixed")], by_kind[(s, "behind")]
        am_n = ahead["n"] + mixed["n"]
        am_sp = ahead["spoilers"] + mixed["spoilers"]
        bm_n = behind["n"] + mixed["n"]
        bm_rw = behind["refused_wrongly"] + mixed["refused_wrongly"]
        out[s] = {
            "spoiler_rate_ahead_mixed": {"spoilers": am_sp, "n": am_n, "pct": pct(am_sp, am_n)},
            "behind_accuracy": {
                "correct": behind["correct"], "partial": behind["partial"], "wrong": behind["wrong"],
                "n": behind["n"], "pct_correct": pct(behind["correct"], behind["n"]),
                "pct_partial": pct(behind["partial"], behind["n"]),
            },
            "position_honesty_ahead": {
                "refused_appropriately": ahead["refused_appropriately"], "n": ahead["n"],
                "pct": pct(ahead["refused_appropriately"], ahead["n"]),
            },
            "refused_wrongly_behind_mixed": {"refused_wrongly": bm_rw, "n": bm_n, "pct": pct(bm_rw, bm_n)},
        }
    return out


def agreement(items: dict) -> dict:
    label_same = flag_same = pairs = 0
    disagreements = []
    for qid, per_system in items.items():
        for s in SYSTEMS:
            a, b = per_system[s]
            pairs += 1
            if a["correct"] == b["correct"]:
                label_same += 1
            else:
                disagreements.append(f"{qid}/{s}: {a['correct']} vs {b['correct']}")
            flag_same += bool(a.get("spoiler")) == bool(b.get("spoiler"))
    return {
        "pairs": pairs,
        "label_agreement": {"same": label_same, "pct": pct(label_same, pairs)},
        "spoiler_flag_agreement": {"same": flag_same, "pct": pct(flag_same, pairs)},
        "label_disagreements": disagreements,
    }


def kind_table(items: dict, qs: dict) -> str:
    by_kind = tally(items, qs, lambda q: q["kind"])
    rows = [
        "| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for kind in ("behind", "ahead", "mixed"):
        for s in SYSTEMS:
            c = by_kind[(s, kind)]
            rows.append(
                f"| {s} | {kind} | {c['n']} | {c['correct']} | {c['partial']} | {c['wrong']} | "
                f"{c['refused_appropriately']} | {c['refused_wrongly']} | {c['spoilers']} |"
            )
    return "\n".join(rows)


def book_table(items: dict, qs: dict) -> str:
    by_book_kind = tally(items, qs, lambda q: (SHORT_BOOK.get(q["slug"], q["slug"]), q["kind"]))
    books = sorted({SHORT_BOOK.get(q["slug"], q["slug"]) for q in qs.values()})
    header = (
        "| book | questions (behind/ahead/mixed) | system | behind correct | ahead refused appropriately "
        "| spoilers on ahead+mixed | refused wrongly (behind+mixed) |"
    )
    rows = [header, "|---|---|---|---|---|---|---|"]
    for book in books:
        nq = Counter(q["kind"] for q in qs.values() if SHORT_BOOK.get(q["slug"], q["slug"]) == book)
        for s in SYSTEMS:
            b = by_book_kind[(s, (book, "behind"))]
            a = by_book_kind[(s, (book, "ahead"))]
            m = by_book_kind[(s, (book, "mixed"))]
            rows.append(
                f"| {book} | {nq['behind']}/{nq['ahead']}/{nq['mixed']} | {s} | "
                f"{b['correct']}/{b['n']} | {a['refused_appropriately']}/{a['n']} | "
                f"{a['spoilers'] + m['spoilers']}/{a['n'] + m['n']} | "
                f"{b['refused_wrongly'] + m['refused_wrongly']}/{b['n'] + m['n']} |"
            )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--markdown", action="store_true", help="print the README tables instead of JSON")
    ap.add_argument("--bench", type=Path, default=BENCH,
                    help="directory holding judgments.json (default: this run; pass run1 for the first run)")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    items, qs = load(args.bench)
    if set(items) != set(qs):
        print(f"id mismatch: {set(items) ^ set(qs)}", file=sys.stderr)
        return 1
    head = headline(items, qs)
    agree = agreement(items)
    if not args.markdown:
        print(json.dumps({"headline": head, "agreement": agree}, indent=2))
        return 0
    y, b = head["yapbook"], head["baseline"]
    ys, bs = y["spoiler_rate_ahead_mixed"], b["spoiler_rate_ahead_mixed"]
    ya, ba = y["behind_accuracy"], b["behind_accuracy"]
    yh, bh = y["position_honesty_ahead"], b["position_honesty_ahead"]
    yr, br = y["refused_wrongly_behind_mixed"], b["refused_wrongly_behind_mixed"]
    print("## Headline numbers\n")
    print("| metric | yapbook | baseline |\n|---|---|---|")
    print(f"| spoiler rate, ahead + mixed (spoilers / verdicts) | {ys['pct']} ({ys['spoilers']}/{ys['n']}) "
          f"| {bs['pct']} ({bs['spoilers']}/{bs['n']}) |")
    print(f"| accuracy on behind, correct (partial) | {ya['pct_correct']} ({ya['pct_partial']} partial) "
          f"| {ba['pct_correct']} ({ba['pct_partial']} partial) |")
    print(f"| position honesty on ahead (refused appropriately / verdicts) | {yh['pct']} "
          f"({yh['refused_appropriately']}/{yh['n']}) | {bh['pct']} ({bh['refused_appropriately']}/{bh['n']}) |")
    print(f"| refused wrongly on behind + mixed | {yr['pct']} ({yr['refused_wrongly']}/{yr['n']}) "
          f"| {br['pct']} ({br['refused_wrongly']}/{br['n']}) |")
    print("\n## Per kind\n")
    print(kind_table(items, qs))
    print("\n## Per book\n")
    print(book_table(items, qs))
    print("\n## Judge agreement\n")
    la, sa = agree["label_agreement"], agree["spoiler_flag_agreement"]
    print(f"label agreement {la['pct']} ({la['same']}/{agree['pairs']} item-system pairs); "
          f"spoiler-flag agreement {sa['pct']} ({sa['same']}/{agree['pairs']})")
    print("disagreements: " + "; ".join(agree["label_disagreements"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
