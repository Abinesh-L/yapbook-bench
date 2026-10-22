# groundbench, hosted run: the browser edition's brain, gate on against gate off

Run of Thursday 2026-10-08, early morning ET. The same 60 questions as runs 1 to 3
(`../questions.json`, unchanged since run 1), the same six books, asked of the browser
edition's hosted brain instead of the installed tool's local model. Everything here was
produced by scripts in `../tools/` (`hosted_*.{mjs,py}`, `judge.py`); nothing ran on a local
language model.

## What is measured

The browser edition answers through one server function (`site/api/ask.js`). The page sends the
transcript the listener has heard so far (capped at 60,000 characters), the lines just heard,
a position line, the title and author, and the question; the function builds the prompt, calls
the model and parses the reply. That path is the **gate**: the model never sees text past the
playhead and is told where the listener is.

Two arms, **same model**, same sampling (temperature 0.3), same spoken-answer format:

- **gate on** (`answers_yapbook.json`): the function itself, called over HTTP with the body the
  page would send (`hosted_bodies.mjs` imports the page's own `heardText`, `justHeard` and
  `positionLine` from `site/app/ask.js`, so nothing is ported). The benchmark's position
  (chapter, seq S) means seqs 0..S-1 are heard; the page's position is the seq last played, so it
  gets S-1. All 60 bodies were checked to end at the heard boundary and to contain no unheard
  segment. 17 of 60 (the RL-book questions) hit the 60,000-character cap, which drops the oldest
  heard text, never adds unheard text.
- **gate off** (`answers_baseline.json`): the same model handed the whole book in the page's own
  rendering (`hosted_bodies.mjs --whole`; the RL book is 1.72 million characters, about 380,000
  tokens), with no position, no "so far", no spoiler rule and no tag, asked the same question
  (`hosted_run_wholebook.py`, OpenRouter directly). An assistant that has read the book.

So the difference between the arms is the gate alone, and the numbers that follow are the
gate's, not a claim about any model's knowledge. The same questions run against the installed
tool's 4B local model are in `../README.md` (run 3, 2026-09-11); that path is not part of the
first release and gets its own multi-model run later.

Books: the ingested copies the earlier runs used (`yapbook-verify/fix-answers/data`), verified
again against `questions.json` with `build_questions.py` before this run: 60 records, 0
problems (every gold segment heard at its position, every spoiler keyword absent from heard
text).

## Grading

Two **named** judge models, blind, one answer per call (`../tools/judge.py`, prompt in the file,
SHA-256 in each `judgments.json`): judge 1 `anthropic/claude-sonnet-5.5`, judge 2
`google/gemini-3.8-flash`, temperature 0, neither of them a model under test. Each judge saw
the question, its kind, the position line, the gold, the unheard facts (ahead and mixed items)
and one answer with no system label, never the other arm's answer. Labels and the spoiler flag
are the benchmark's (`../tools/score.py` reads them unchanged): behind items `correct | partial
| wrong | refused_wrongly`; ahead items `refused_appropriately` (the target) `| partial |
wrong`; mixed items `correct | partial | wrong | refused_wrongly`; `spoiler` true when the
answer states a fact from `unheard_facts`. 14 of the first 240 verdicts came back cut off
inside the JSON (judge 2 with `max_tokens` 400); they were re-collected at 4000 and the limit
stays there.

Run 3's judges were two unnamed passes of the orchestrating session. This is the first run
whose judging anyone can repeat.

## 1. The live function as deployed (`live-2026-10-08/`)

Model `openai/gpt-4.1-mini` (the deployment's default on that date), the prompt as deployed
(commit f1a0cb5 for `site/api/ask.js`), 60 questions through `https://yapbook.app/api/ask`,
paced to the function's 30-per-five-minutes limit, 60 of 60 answered with HTTP 200 on the
first try, median 1.5 s, p90 2.2 s. Gate off: the same model, whole book, 7.0 million prompt
tokens, about $2.81.

| metric (two judges, so n = 2 x questions) | gate on | gate off |
|---|---|---|
| spoiler-free on ahead + mixed (verdicts without a spoiler / verdicts) | 91.7% (66/72) | 1.4% (1/72) |
| position honesty on ahead (said "not yet" / verdicts) | 75.0% (36/48) | 0.0% (0/48) |
| heard material: correct, partial, wrong | 94%, 6%, 0 | 94%, 6%, 0 |
| refused wrongly on behind + mixed | 2.8% (2/72) | 0.0% (0/72) |

Judge agreement: label 85.8% (103/120 pairs; all but two disagreements are partial against
wrong or partial against correct), spoiler flag 99.2% (119/120). Per judge, gate on: judge 1
spoilers 3/36 and honest 19/24, judge 2 spoilers 3/36 and honest 17/24.

The six spoiler verdicts are three RL-book items, both judges each (rl-02: which of greedy and
epsilon-greedy wins; rl-03: tracking a nonstationary bandit; rl-06: what the baseline in the
gradient bandit update is for). In each the transcript had only set the question up and the
model completed it from memory of the book, tagged COVERED and opened with "the book says". The
eight "wrong" verdicts on ahead items are those three plus bn-04 (a muddled answer treated as
covered) and rl-08 (an abstract contrast given where an everyday example was asked, with no
"not yet"). The two wrong refusals are vae-02 (mixed: the heard part, that reparameterizing the
bound gives the SGVB estimator, was in an earlier chapter and left out). Nine of 24 ahead
questions came back tagged COVERED.

The pattern is the mirror image of run 3's: the 4B local model over-refused (8.3% wrong
refusals, 2.8% spoilers); a hosted model that knows the textbook over-answers.

## 2. The fix, and the model pick (`pick/`)

Two changes to `site/api/ask.js`, measured before anything was deployed:

1. **An EVIDENCE line.** After the COVERED tag and the HEARD_AS line the model writes
   `EVIDENCE: "<the transcript's own words that contain the answer>"` or `EVIDENCE: none`. The
   function checks the quotation against the passages it sent (letters and digits only; whole,
   or any eight words in a row): a COVERED answer whose quotation is not in the transcript is
   an answer from memory and the listener gets the fixed "not covered" line alone; a COVERED
   answer with `EVIDENCE: none` is treated as not covered, keeping the model's partial. The
   reply to the page carries `evidence: quoted | none | rejected | absent`.
2. **Two rules sharpened.** Memory of this very book is outside knowledge too ("the book says"
   may introduce only what the transcript says); a question that asks for something the
   transcript has set up, named or promised but not yet stated is not answered by restating
   the set-up; when the purpose, reason or result of something the transcript has only named
   is known to the model, it stays out. One worked example added (a comparison set up, its
   result not stated: NOT_COVERED).

`site/api/ask.test.mjs` covers the parsing and the check (21 tests). The runs below went
through the same function behind a local port (`hosted_local_server.mjs`), so the handler and
the prompt are the deployment's; only the transport differs, and the per-address limit was
not paced (a distinct forwarded address per request). Same bodies, same judges, same prompt.

Gate on, four hosted models, the new prompt; all kinds judged for the first three:

| model (gate on, new prompt) | spoiler-free, ahead + mixed | position honesty, ahead | heard material: correct, partial, wrong | refused wrongly, behind + mixed | latency median, p90 | list price in/out per M tokens |
|---|---|---|---|---|---|---|
| gpt-4.1-mini, old prompt (section 1, live) | 91.7% (66/72) | 75.0% (36/48) | 94%, 6%, 0 | 2.8% (2/72) | 1.5 s, 2.2 s | $0.40 / $1.60 |
| gpt-4.1-mini | 97.2% (70/72) | 91.7% (44/48) | 71%, 29%, 0 | 6.9% (5/72) | 1.4 s, 2.4 s | $0.40 / $1.60 |
| claude-haiku-4.5 | 100% (72/72) | 93.8% (45/48) | 75%, 21%, 0 | 4.2% (3/72) | 2.0 s, 2.9 s | $1.00 / $5.00 |
| **gemini-2.5-flash** | **100% (72/72)** | **100% (48/48)** | 58%, 35%, 0 | 5.6% (4/72) | 1.2 s, 1.6 s | $0.30 / $2.50 |
| gpt-4.1-nano | not judged | not judged | 20 of 24 behind questions tagged NOT_COVERED | | | $0.10 / $0.40 |
| claude-haiku-5.5 (released the day before) | not judged | not judged | 8 of 60 unanswered (74 upstream timeouts), 10 replies without the EVIDENCE line | | 2.7 s, 3.2 s | $0.10 / $0.50 |

The check itself never fired on a fabricated quotation in the three judged runs (`rejected`
0 of 180; the models wrote `none` 19, 18 and 33 times). What moved the numbers is the
discipline the line imposes and the rules; the check is the guard for the day a model does
fabricate one (it fired once, on claude-haiku-5.5).

No model gave a wrong answer on heard material in any arm. The trade is visible in the table:
the models that never spoil and always say "not yet" answer heard material more tersely
(gemini-2.5-flash: 58% of behind verdicts fully correct, 35% partial, judge 1 the stricter of
the two on completeness) and refuse a heard question a little more often (4 of 72 verdicts:
vae-03 both judges, rl-16 one judge, vae-02 one judge).

**gemini-2.5-flash, gate on against gate off, same model** (`pick/gemini-2.5-flash/`, gate off
7.17 million prompt tokens, about $2.16):

| metric | gate on | gate off |
|---|---|---|
| spoiler-free on ahead + mixed | 100% (72/72) | 22.2% (16/72) |
| position honesty on ahead | 100% (48/48) | 8.3% (4/48) |
| heard material: correct, partial, wrong | 58%, 35%, 0 | 75%, 15%, 0 |
| refused wrongly on behind + mixed | 5.6% (4/72) | 6.9% (5/72) |

Per judge, gate on: judge 1 spoilers 0/36 and honest 24/24, judge 2 the same; gate off: judge
1 spoilers 29/36, judge 2 27/36. The headline rests on both judges separately, not on the
Google judge grading a Google model. Judge agreement on this pair: spoiler flag 98.3%
(118/120), label 80.0% (96/120; 17 of the 24 disagreements are partial against correct).

Handed the whole book with no position, gemini-2.5-flash still said "the book does not say"
on 4 of 48 ahead verdicts and spoiled less than gpt-4.1-mini did (56 against 71 of 72), which
is why the gate-off column differs between the two pairs. The gate-on column does not.

## 3. The live function after the deploy (`live-2026-10-08-evidence/`)

The fix of section 2 deployed (default model `google/gemini-2.5-flash`, the EVIDENCE line and
check, the sharpened rules), the same 60 bodies through `https://yapbook.app/api/ask` at 08:24
to 08:35 UTC, 60 of 60 answered with HTTP 200 on the first try, median 1.5 s, p90 2.0 s;
`evidence` came back `quoted` 28 times and `none` 32, never `rejected` or `absent`. The gate-off
arm and its verdicts are the gemini-2.5-flash whole-book run of section 2, copied unchanged
(same model, same questions). Gate on judged fresh: 120 verdicts, same two judges, blind.

| metric | gate on (live) | gate off (same model, whole book) |
|---|---|---|
| spoiler-free on ahead + mixed | 100% (72/72) | 22.2% (16/72) |
| position honesty on ahead | 100% (48/48) | 8.3% (4/48) |
| heard material: correct, partial, wrong | 65%, 31%, 0 | 75%, 15%, 0 |
| refused wrongly on behind + mixed | 6.9% (5/72) | 6.9% (5/72) |

Per judge, gate on: judge 1 spoilers 0/36 and honest 24/24, judge 2 the same. The five wrong
refusals are att-08 (both judges), vae-03 (both) and vae-02 (one judge). Judge agreement:
spoiler flag 98.3% (118/120), label 78.3% (94/120; the disagreements are almost all partial
against correct, judge 1 the stricter on completeness). These were the numbers the README, the
landing page and the release notes carried until 2026-10-22 (section 4 has the brain deployed since); the `pick/` run of the same code behind a local port
had scored 72/72, 48/48, 58% correct, 4 of 72 refused.

## 4. The brain deployed since 2026-10-22 (`brain-partial-first-2026-10-22/`)

Two changes to the function since section 3, measured together on 2026-10-22 with the
deployment's code behind a local port (`hosted_local_server.mjs`) and the deployment's default
model, the same 60 bodies, the same two judges grading the gate-on arm blind. The gate-off arm
did not change, so its answers and verdicts are the copies of `live-2026-10-08-evidence/`
(noted in `judgments.json`).

- Whole-book memory (2026-10-21): in a long book the page sends, beside the transcript cut to
  its newest 60,000 characters, up to four heard passages the cap dropped that fit the
  question's words, as an `earlier` field the function quotes under a label and counts as
  evidence. Only the textbook's 17 questions hit the cap; the other 43 bodies are the same.
- The answer a listener hears (2026-10-22): a request to summarize or recap what has been
  heard is answered from the whole transcript and tagged covered; the identity note names a
  document, paper, article, text or file as well as a book; and after a not-covered tag the
  page gets the model's partial first and "The rest has not come yet." after it, instead of
  the fixed line first.

| metric (two judges, n = 2 x questions) | gate on | gate off (same model, whole book) |
|---|---|---|
| spoiler-free on ahead + mixed | 100% (72/72) | 22.2% (16/72) |
| position honesty on ahead | 95.8% (46/48) | 8.3% (4/48) |
| heard material: correct, partial, wrong | 62.5%, 33.3%, 0 | 75.0%, 14.6%, 0 |
| refused wrongly on behind + mixed | 8.3% (6/72) | 6.9% (5/72) |

Per judge, gate on: judge 1 spoilers 0/36 and honest 23/24, judge 2 the same. The two ahead
verdicts that are not refusals are one question (rl-09, both judges) answered with the part
the book had said and the note that the example itself has not been read yet, judged partial,
no spoiler. Judge agreement: spoiler flag 98.3% (118/120), label 80.8% (97/120). `score.md`
has the per-book table: 0 spoiler verdicts on every one of the six books. These are the
numbers the README and the landing page carry since 2026-10-22.

## What this run does not show

1. **One run per cell.** No repeat for stability, except that the shipped configuration was
   run twice, once behind a local port (section 2) and once against the live site (section 3),
   with the same headline both times.
2. **Typed questions.** Recognition never entered the benchmark; the HEARD_AS repair fired 0
   times in 60 (the questions were written, not misheard).
3. **Six books, 60 questions, one famous textbook.** The spoilers of section 1 came from the
   one book the model knows by heart; a benchmark of only arXiv papers would have hidden the
   failure. Books with a table of contents in the heard text were not in the set (a model may
   quote the contents page; the 22-question check of 2026-10-02 saw gemini-2.5-flash do so
   twice under the old prompt).
4. **The judges are models.** Two, named, with a committed prompt and 98 to 99% agreement on
   the spoiler flag, but models; a 20-verdict human read (random, blind, seed 20261008) was
   handed to the maintainer with the run.
5. **The local harness is not the deployment.** Section 2's runs used the deployment's code
   behind a local port; the deployed function is Vercel's Node runtime with a 15-second
   upstream timeout. Section 3 is the deployment itself.
6. **Cost.** Gate off over the whole RL book is the expensive arm (about $2 to $3 per pass);
   the gate-on arm cost cents. Judging: about $1.50 per 240 verdicts.

## Files

- `live-2026-10-08/`: section 1. `answers_yapbook.json` (gate on, live function: id, answer,
  covered, heardAs, status, seconds, attempts, passagesChars, capped, position),
  `answers_baseline.json` (gate off: id, answer, seconds, tokens, prompt SHA-256), both
  `.meta.json`, `judgments.json` (240 verdicts, schema inside, raw judge texts kept),
  `score.md` and `score.json` (from `../tools/score.py --bench bench/grounding/hosted/live-2026-10-08`).
- `live-2026-10-08-evidence/`: section 3, the same files as `live-2026-10-08/` for the deployed
  fix; its `answers_baseline*.json` and the baseline verdicts in `judgments.json` are copies of
  `pick/gemini-2.5-flash/`'s (noted in the schema).
- `pick/<model>/`: section 2, one folder per model; `gemini-2.5-flash/` also holds its gate-off
  arm and `score.md`; `gpt-4.1-nano/` and `claude-haiku-5.5/` hold answers only.
- `brain-partial-first-2026-10-22/`: section 4, the same files as `live-2026-10-08-evidence/` (no
  `score.json`); its gate-off answers and the baseline verdicts in `judgments.json` are copies of that run's.
- `parity-2026-10-13-identity/`: a parity run, not judged: the 60 bodies through the function on
  a local port after the header lines (title, author, position) were let count as evidence for a
  question about the book itself, compared by id with `live-2026-10-08-evidence/` (its README has
  the table: ahead and mixed unchanged, one wrong refusal on a behind question answered).
- Not committed (book text): the request bodies and the whole-book transcripts
  (`hosted_bodies.mjs` rebuilds them from the ingested books in under a second), the full
  reply files.

## How to re-run

```
set YAPBOOK_DATA_DIR=<data dir holding books/<slug> for the six books>
node bench/grounding/tools/hosted_bodies.mjs <scratch>/bodies.json
node bench/grounding/tools/hosted_bodies.mjs --whole <scratch>/whole.json
# gate on, live:
python bench/grounding/tools/hosted_run_live.py <scratch>/bodies.json --out-dir bench/grounding/hosted/<run>
# gate on, a change to the function before it is deployed (OPENROUTER_API_KEY, OPENROUTER_MODEL in the environment):
node bench/grounding/tools/hosted_local_server.mjs 8799
python bench/grounding/tools/hosted_run_live.py <scratch>/bodies.json --endpoint http://127.0.0.1:8799/api/ask --xff --gap 0.5 --out-dir bench/grounding/hosted/<run>
# gate off, same model:
python bench/grounding/tools/hosted_run_wholebook.py <scratch>/whole.json --model <id> --out-dir bench/grounding/hosted/<run>
# judge and score:
python bench/grounding/tools/judge.py --bench bench/grounding/hosted/<run> --judges anthropic/claude-sonnet-5.5,google/gemini-3.8-flash
python bench/grounding/tools/score.py --markdown --bench bench/grounding/hosted/<run>
```
