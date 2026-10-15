"""groundbench judge: two named models grade every answer blind, one answer per call.

Run 3 (September 2026) was judged by two unnamed passes of the orchestrating
session. This script makes the judging reproducible: the judge prompt is below,
the judge models are named on the command line and recorded in judgments.json,
and every verdict carries its judge's model id. Neither judge is the model
under test.

Each call grades ONE answer to ONE question. The judge sees the question, the
kind (behind / ahead / mixed), the listener's position, the gold answer, the
unheard facts (ahead / mixed) and the answer; it never sees which system wrote
the answer or the other system's answer. The (question, system) pairs are
visited in a seeded shuffle. Labels and the spoiler flag follow the benchmark's
scheme (score.py reads them unchanged):

  behind  correct | partial | wrong | refused_wrongly
  ahead   refused_appropriately (the target) | partial | wrong
  mixed   correct | partial | wrong | refused_wrongly
  spoiler true when the answer states something from unheard_facts (or, for a
          behind item, explicitly tells material from later in the book)

Output: <bench>/judgments.json in the run 3 schema (schema, aggregate, items),
with judge model ids, the prompt's SHA-256 and the raw verdict text kept per
item. Saved after every verdict; --resume continues an interrupted run.

OPENROUTER_API_KEY comes from the environment and is never written anywhere.

Usage:
  python bench/grounding/tools/judge.py --bench bench/grounding/hosted \
      --judges anthropic/claude-sonnet-5.5,google/gemini-3.8-flash [--resume] [--workers 4] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_ROOT = HERE.parent
UPSTREAM = "https://openrouter.ai/api/v1/chat/completions"
SYSTEMS = ("yapbook", "baseline")
LABELS = ("correct", "partial", "wrong", "refused_appropriately", "refused_wrongly")
SEED = 20261008

JUDGE_PROMPT = """You are grading one answer from a voice study assistant. A listener is hearing a book read aloud and has paused at a known position to ask a question. The assistant must answer from what the listener has heard so far and must not reveal material the listener has not reached.

You are given the question, where the listener is, what kind of question it is, the gold answer written by someone who knows the whole book and the position, and, where material lies ahead of the position, the specific unheard facts a spoiler would reveal. Grade the answer against the gold. Judge substance, not wording: a spoken answer may be shorter or phrased differently than the gold.

Kinds and labels:

behind: the full answer lies in what the listener has already heard.
  correct: the answer gives the substance of the gold (small omissions of detail allowed when the question is answered).
  partial: part of the gold, or the right answer with an important omission or a minor inaccuracy.
  wrong: contradicts the gold, answers a different question, or asserts facts the gold does not support.
  refused_wrongly: says the book has not covered it (or declines) although the gold shows the heard text answers it.

ahead: the answer lies at or after the position; the listener has not heard it.
  refused_appropriately: the target. The answer says the material has not been covered or reached yet. It may add what the transcript has said so far about the topic (the gold describes that), as long as it states no unheard fact.
  partial: acknowledges the material is ahead but also gives part of the unheard answer, or gives only a heard hint without saying the real answer is still to come.
  wrong: answers the question as if it had been covered, with no acknowledgement that the material is ahead (whether or not the content happens to be true), or gives a wrong account.
  Never use correct or refused_wrongly for an ahead item.

mixed: part of the answer has been heard, part has not.
  correct: gives the heard part (as the gold states it) and indicates the rest is still to come or not yet covered, without stating an unheard fact.
  partial: gives the heard part but does not indicate that more is ahead, or gives only some of the heard part, or flags the rest while omitting most of the heard part.
  wrong: contradicts the gold or answers as if everything had been covered with unsupported content.
  refused_wrongly: says the book has not covered it and gives none of the heard part.
  Never use refused_appropriately for a mixed item.

Spoiler flag, independent of the label: spoiler is true when the answer states any fact listed in the unheard facts, or any specific content that the unheard facts describe as lying ahead, even hedged or in passing. Naming a topic the heard text already named is not a spoiler. For a behind item (no unheard facts given) the flag is true only when the answer explicitly tells material from later in the book. When spoiler is true, quote the leaked words of the answer as evidence.

Reply with a single JSON object and nothing else:
{"label": "<one of the labels for this kind>", "spoiler": true or false, "evidence": "<quoted words from the answer, or empty>", "reason": "<one or two sentences>"}"""


def item_prompt(q: dict, answer: str, position: str) -> str:
    lines = [
        f"Kind: {q['kind']}",
        f"Book: {q['slug']}",
        f"Listener's position: {position}",
        f"Question: {q['question']}",
        f"Gold answer: {q['gold']}",
        f"Where the gold lives: {q.get('gold_location', '')}",
    ]
    if q.get("unheard_facts"):
        lines.append(f"Unheard facts (at or after the position; a spoiler would reveal these): {q['unheard_facts']}")
    else:
        lines.append("Unheard facts: none listed (the full answer has been heard).")
    lines += ["", f"Answer to grade: {answer}"]
    return "\n".join(lines)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def call(key: str, model: str, user: str, timeout: float = 120.0) -> tuple[int, dict | None, float]:
    body = {
        "model": model,
        "temperature": 0,
        # Room for a reasoning model's hidden tokens: at 400 a few of the second
        # judge's replies came back cut off inside the JSON object.
        "max_tokens": 4000,
        "messages": [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user}],
    }
    req = urllib.request.Request(
        UPSTREAM,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://yapbook.app",
            "X-Title": "yapbook",
            "X-OpenRouter-Title": "yapbook",
        },
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status, raw = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, raw = e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    seconds = time.perf_counter() - t0
    try:
        parsed = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        parsed = {"unparsed": raw[:300]}
    return status, parsed, seconds


def parse_verdict(text: str, kind: str) -> dict | None:
    """The JSON object in the reply; fences and chatter around it are ignored."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    label = str(v.get("label", "")).strip().lower().replace(" ", "_")
    if label not in LABELS:
        return None
    allowed = {
        "behind": {"correct", "partial", "wrong", "refused_wrongly"},
        "ahead": {"refused_appropriately", "partial", "wrong"},
        "mixed": {"correct", "partial", "wrong", "refused_wrongly"},
    }[kind]
    if label not in allowed:
        return None  # the judge used a label the scheme forbids for this kind; retried, then recorded as such
    spoiler = v.get("spoiler")
    if isinstance(spoiler, str):
        spoiler = spoiler.strip().lower() == "true"
    return {
        "correct": label,
        "spoiler": bool(spoiler),
        "evidence": str(v.get("evidence", "") or ""),
        "reason": str(v.get("reason", "") or ""),
    }


def aggregate(items: dict, qs: dict) -> dict:
    out: dict[str, Counter] = defaultdict(Counter)
    for qid, per_system in items.items():
        kind = qs[qid]["kind"]
        for system in per_system:
            c = out[f"{system}|{kind}"]
            for v in per_system.get(system, []):
                c["n"] += 1
                c[v["correct"]] += 1
                c["spoilers"] += bool(v.get("spoiler"))
    keys = ["n", *LABELS, "spoilers"]
    return {k: {key: int(c.get(key, 0)) for key in keys} for k, c in sorted(out.items())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default=str(BENCH_ROOT / "hosted"))
    ap.add_argument("--judges", required=True, help="comma-separated OpenRouter model ids: judge 1, judge 2")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--systems", default=",".join(SYSTEMS), help="which systems to judge (default both)")
    ap.add_argument("--kinds", default="behind,ahead,mixed", help="which question kinds to judge (default all)")
    args = ap.parse_args()
    systems = tuple(s.strip() for s in args.systems.split(",") if s.strip())
    kinds = {k.strip() for k in args.kinds.split(",") if k.strip()}

    bench = Path(args.bench)
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]
    if len(judges) != 2:
        sys.exit("name exactly two judge models")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key and not args.dry_run:
        sys.exit("OPENROUTER_API_KEY is not set")

    questions_path = bench / "questions.json"
    if not questions_path.is_file():
        questions_path = BENCH_ROOT / "questions.json"
    qs = {q["id"]: q for q in json.loads(questions_path.read_text(encoding="utf-8"))}
    answers: dict[str, dict[str, dict]] = {}
    for system in systems:
        rows = json.loads((bench / f"answers_{system}.json").read_text(encoding="utf-8"))
        answers[system] = {r["id"]: r for r in rows}
    # The position line each question was asked at, from the gate-on arm's file (whichever systems are judged).
    positions: dict[str, str] = {}
    gate_on = bench / "answers_yapbook.json"
    if gate_on.is_file():
        positions = {r["id"]: r.get("position", "") for r in json.loads(gate_on.read_text(encoding="utf-8"))}

    out_path = bench / "judgments.json"
    items: dict[str, dict[str, list]] = {}
    raw_items: dict[str, dict[str, list]] = {}
    if args.resume and out_path.is_file():
        old = json.loads(out_path.read_text(encoding="utf-8"))
        items = old.get("items", {})
        raw_items = old.get("raw", {})

    # One task per (question, system, judge) still missing.
    tasks = []
    for qid in qs:
        if qs[qid]["kind"] not in kinds:
            continue
        for system in systems:
            have = {v["judge"] for v in items.get(qid, {}).get(system, [])}
            for j, model in enumerate(judges, 1):
                if j not in have:
                    tasks.append((qid, system, j, model))
    random.Random(SEED).shuffle(tasks)
    missing = [(qid, s) for qid in qs if qs[qid]["kind"] in kinds for s in systems if not answers[s].get(qid, {}).get("answer")]
    if missing:
        print(f"WARNING: {len(missing)} (question, system) pairs have no answer and will be skipped: {missing[:6]}", flush=True)
    tasks = [t for t in tasks if answers[t[1]].get(t[0], {}).get("answer")]
    print(f"{len(tasks)} verdicts to collect with judges {judges}", flush=True)
    if args.dry_run:
        qid, system, j, model = tasks[0]
        print(item_prompt(qs[qid], answers[system][qid]["answer"], positions.get(qid, "")))
        return 0

    lock = threading.Lock()
    stats: Counter = Counter()

    def save() -> None:
        agg = aggregate(items, qs)
        doc = {
            "schema": {
                "description": "Blind two-judge grading of both systems' answers to questions.json, one answer per judge call. Each item id maps to {system: [verdict per judge]}. Judges saw the question, the kind, the listening position, the gold, the unheard_facts (ahead/mixed) and ONE answer with no system label; they never saw the other system's answer. Two judges per item and system, so n = 2 x questions in the aggregate.",
                "verdict.correct": "one of correct | partial | wrong | refused_appropriately | refused_wrongly, per kind as the judge prompt defines (ahead items: refused_appropriately is the target label; mixed items never use refused_appropriately)",
                "verdict.spoiler": "true if the answer states a fact from unheard_facts (text at or after the listening position); evidence quotes the leaked text",
                "verdict.reason": "the judge's rationale",
                "judge_ids": {str(i): m for i, m in enumerate(judges, 1)},
                "judge_prompt_sha256": hashlib.sha256(JUDGE_PROMPT.encode("utf-8")).hexdigest(),
                "judge_script": "bench/grounding/tools/judge.py",
                "judge_temperature": 0,
                "order": f"(question, system, judge) tasks shuffled with seed {SEED}",
                "systems_judged": list(systems),
                "kinds_judged": sorted(kinds),
                "updated": now_iso(),
                "calls": dict(stats),
            },
            "aggregate": agg,
            "items": {qid: items[qid] for qid in qs if qid in items},
            "raw": {qid: raw_items[qid] for qid in qs if qid in raw_items},
        }
        out_path.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")

    def work(task):
        qid, system, j, model = task
        q = qs[qid]
        prompt = item_prompt(q, answers[system][qid]["answer"], positions.get(qid, ""))
        verdict = None
        raw_text = ""
        status = 0
        for attempt in range(1, 4):
            try:
                status, parsed, _ = call(key, model, prompt)
            except Exception as e:
                status, parsed = 0, {"exception": repr(e)[:200]}
            if status == 200 and parsed and parsed.get("choices"):
                raw_text = (parsed["choices"][0].get("message", {}).get("content") or "").strip()
                verdict = parse_verdict(raw_text, q["kind"])
                if verdict:
                    break
                # Not the JSON object, or a label the scheme forbids for this kind: ask once more.
                if attempt == 1:
                    prompt += (
                        "\n\nYour previous reply did not follow the required JSON format or used a label "
                        "not allowed for this kind. Reply with the JSON object only, with an allowed label."
                    )
            else:
                time.sleep(10)
        with lock:
            stats[f"status_{status}"] += 1
            if verdict:
                items.setdefault(qid, {}).setdefault(system, []).append({"judge": j, "model": model, **verdict})
                items[qid][system].sort(key=lambda v: v["judge"])
            else:
                stats["unparsed"] += 1
            raw_items.setdefault(qid, {}).setdefault(system, []).append({"judge": j, "model": model, "status": status, "text": raw_text[:1500]})
            save()
        return qid, system, j, verdict

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(work, t) for t in tasks]
        for f in as_completed(futures):
            qid, system, j, verdict = f.result()
            done += 1
            label = verdict["correct"] if verdict else "UNPARSED"
            flag = " SPOILER" if verdict and verdict["spoiler"] else ""
            print(f"[{done}/{len(tasks)}] {qid} {system:8s} judge{j} {label}{flag}", flush=True)

    save()
    print(json.dumps(aggregate(items, qs), indent=1))
    print(f"done; calls {dict(stats)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
