> Copied unchanged from the yapbook repository (bench/grounding) on 2026-10-14. The code it names (src/, the run scripts under tools/ other than judge.py and score.py, covtag/, author/) lives in the private repository; the records and the two grading scripts are here.

# Grounding benchmark: position-grounded answering vs a no-position baseline

Three runs of the same 60 questions, same books, same model, same grading protocol, same
definitions. **Run 3** (this directory) is the current result. **Run 2** (`run2/`) and **run 1**
(`run1/`) are kept unchanged for comparison, each with the README that described it at the time.

Code under test for run 3: the repo at `HEAD 5415fca` ("bench: position-grounded answering vs
no-position baseline") **plus the coverage-tag calibration that was staged in the working tree
and not yet committed when the run was made**, because the run fell inside the weekday commit
window. The staged change is `src/yapbook/qa/context.py` (the system prompt: tag definition and
worked examples), `src/yapbook/qa/answer.py` (the tag regex accepts a comma), a test,
`CHANGELOG.md`, `ARCHITECTURE.md` and the calibration record in `covtag/`. The harness imports
the repo `src/` directly, so the working tree is what ran. The exact system prompt is identified
by its SHA-256 in `proof/answers_yapbook.meta.json` (`436490b6...`, 2947 chars) rather than by a
commit id, and the six wording markers of the calibration were checked in-process before the
run and recorded there. Once the calibration is committed, the SHA to cite is that commit; until
then "5415fca plus the staged calibration" is the honest description.

## Purpose

yapbook reads a textbook aloud and lets the listener interrupt with a question. Its answer path
is tied to the playhead: the model sees only what has already been read, so it can say "the book
has not covered that yet" instead of revealing what the book is about to explain. This benchmark
asks whether that design actually changes answer quality compared with the obvious alternative, a
"chat with your PDF" retriever that searches the whole book with no idea where the listener is.
Sixty questions were written at known listening positions in six books, both systems answered
every question with the same local 4B model, and two independent LLM judges graded the answers
blind. In run 3 the no-position baseline leaked not-yet-read material in 85% of judged verdicts
on questions about upcoming content and yapbook in 3%; yapbook gave the position-honest answer on
88% of upcoming-content verdicts, the baseline on none. On already-read content yapbook was graded
correct on 67% of verdicts against 52% for the baseline, but it also refused 3 questions it could
have answered (6 of 72 verdicts), down from 4 questions (8 of 72) in run 2. The calibration fixed
the two misfires it targeted (vae-07 and rl-04) and introduced one new one (vae-03); the run 2
wrong refusals on att-08 and att-12 did not move.

## What changed in the code between the runs

All three changes are in the commits named in the table below (the calibration, staged when run
3 was made, was committed as 36f9ff5). Nothing else in the answer path changed
between runs, and the baseline code did not change at all (its retrieved hits and prompt hashes
are byte-identical across all three runs for all 60 questions).

| from | to | change | commit |
|---|---|---|---|
| run 1 | run 2 | **Retrieval trigger.** Whole-book retrieval used to join the prompt only on cross-chapter wording ("chapter 2", "earlier in the book"), which no benchmark question uses, so in run 1 it never fired. Now every question is embedded and the block joins when the best gated cosine score reaches 0.60 (`RETRIEVAL_MIN_SCORE`); the spoiler rule is enforced inside `retrieval.retrieve`, so no row at or past the playhead can surface. | aecd630 |
| run 1 | run 2 | **Coverage tag.** The system prompt forbids outside knowledge and asks the model to open every reply with `COVERED` or `NOT_COVERED`. The streaming layer strips the tag; on `NOT_COVERED` yapbook speaks a fixed line, "The book has not covered that yet.", followed by the model's partial, which that wording required to begin "So far it". | 17eba38 |
| run 2 | run 3 | **Coverage-tag calibration.** Same protocol, reworded: the tag is defined over everything heard (anywhere in the chapter transcript, not only the just-heard quote, plus the retrieved earlier-chapter passages, which count as covered even when this chapter has not said it); the prompt forbids writing `NOT_COVERED` and then stating the answer; the "So far it" opener is gone; four invented worked examples sit in the stable prefix; a comma after the tag is accepted as a terminator. Sixteen wordings were measured on the 48 behind and ahead benchmark questions, the 12 mixed ones and a held-out set of 24 questions on chapters the benchmark never used (`covtag/`). The run 2 README had named vae-07 and att-08 as the misfires to fix. | staged, uncommitted |

The run 2 to run 3 change is prompt-only. Retrieval behaved identically in the two runs: the
block was present in 53 of 60 prompts with the same 7 below the gate (att-02, att-10, vae-07,
react-01, react-08, str-01, str-02), the force path fired on 0 of 60, and 0 of the 212 retrieved
rows lay at or past the playhead. The median yapbook prompt grew from 5841 to 7068 characters
(the longer system prefix). No prompt hash is shared between run 2 and run 3, as expected.

## Method

### Books

Six books, all ingested into a scratch data directory (the real yapbook library was never
touched; every command ran with `YAPBOOK_DATA_DIR` pointing at the scratch copy, and a before and
after snapshot of the real library, 808 files by path, size and mtime, was diffed: identical, and
identical to the run 2 snapshots):

| slug | source | chapters | segments |
|---|---|---|---|
| attention-is-all-you-need | arXiv 1706.03762 | 28 | 217 |
| auto-encoding-variational-bayes | arXiv 1312.6114 | 23 | 251 |
| batch-normalization-accelerating-deep-network-training-by-reducing-internal-covariate-shift | arXiv 1502.03167 | 19 | 255 |
| react-synergizing-reasoning-and-acting-in-language-models | arXiv 2210.03629 | 47 | 550 |
| string-junctions-and-their-duals-in-heterotic-string-theory | arXiv hep-th/9901001 | 8 | 164 |
| rl-book-full-endurance | Sutton and Barto, Reinforcement Learning (2nd ed.), copied from the owner's library | 286 | 9015 |

The five papers were `yapbook add <arxiv-id> --figures defer` ingests (docling, no VLM); figure
descriptions are caption placeholders. "Chapters" are yapbook's heading-level units, which is why
the RL book has 286 of them. Chapter indices below are 0-based `book.json` indices; yapbook's own
prompt header prints them 1-based. All three runs used the same ingested copies and the same
`nomic-embed-text` index (complete for all six books).

### Position semantics

A question is asked at `(chapter, seq)`. The listener is taken to have heard every segment of
every earlier chapter plus segments `0..seq-1` of `chapter`; segment `seq` itself has not been
heard. This is exactly what `yapbook.mcp_server.ask_book_text` reconstructs from
`positions.json`, verified before run 3 by a byte-identical prompt check on the calibrated code
(`run_yapbook3.py --check att-01`: the explicit-position path and the `positions.json` path give
the same prompt, sha256 `d73fac57...`, 5287 chars, retrieval block present). That check appended
one extra att-01 entry to the scratch book's `qa_log.json`; the run's own entry was matched
afterwards (60 of 60 matched).

### Questions (questions.json, 60 records, unchanged since run 1)

Each record has `id, slug, chapter, seq, kind, question, gold, gold_location` and, for
ahead/mixed items, `unheard_facts`. Three kinds:

- **behind** (24): the answer is fully contained in already-heard text. `gold_location` cites
  the segment ids.
- **ahead** (24): the answer lives at or after the position. The gold is the position-honest
  answer ("not covered yet", plus whatever partial hint has been heard), and `unheard_facts`
  lists the specific facts a spoiler would reveal.
- **mixed** (12): part of the answer has been heard, part has not. The gold states the heard
  part and notes the rest is still to come.

Questions were drafted by an LLM after reading the full text of the five papers and three
chapters of the RL book (bandits, TD learning, policy gradient), in the voice of a listener who
does not know what comes next. `tools/build_questions.py` then verified every record mechanically
against the ingested text: each cited gold segment must exist and be heard at the position; each
cited unheard segment must exist and be unheard; and every spoiler keyword (numbers, names,
phrases distinctive to the unheard facts) was grepped over all heard text (spoken and source
text, every earlier chapter in full plus the heard prefix). `questions_verify.txt` is the
386-line log of that check (60 records, 0 problems). Three keyword hits were investigated and
explained there (a substring false positive in str-02; headings that name "double learning" and
"policy gradient theorem" before defining them in rl-13 and rl-15, which the golds acknowledge).
Two positions were moved during verification because a table's source text had already leaked
the answer (react-08, bn-02).

Seven behind/mixed golds live wholly or partly in an earlier chapter than the position (att-07,
att-08, vae-02 fully; bn-01, bn-02, react-05, rl-17 partly). These are the items that test
cross-chapter memory.

### The two systems

Both use the same brain model (`qwen3:4b-instruct` via local Ollama, `num_ctx` 16384,
temperature 0.3, `num_predict` 256), the same `qa.answer()` streaming code with its 4-sentence
cap and sanitizer, the same per-book index (`nomic-embed-text`), and the same 60 questions. They
differ only in what the prompt contains:

| | yapbook (shipped path, run 3) | baseline (`tools/baseline_ask.py`, unchanged since run 1) |
|---|---|---|
| entry point | `mcp_server.ask_book_text` after writing `positions.json` | `ask_baseline` |
| context | header naming the current chapter; the heard-so-far transcript of that chapter; a "just heard" quote of the last 3 segments; a 4-passage "Relevant passages from earlier in the book" block when the similarity gate passes (53 of 60), drawn only from rows before the playhead | the 12 segments most cosine-similar to the question over the whole index, no spoiler gate, no chapter labels |
| system prompt | yapbook's calibrated prompt: position and spoiler rules, no outside knowledge, reply opens with a COVERED / NOT_COVERED tag defined over the whole transcript plus the retrieved passages, four worked examples | yapbook's run 1 prompt with the position and spoiler rules removed; grounding rule, "say so instead of guessing", length and plain-text rules kept verbatim. No tag protocol, no no-outside-knowledge rule, no examples |
| what it knows about position | chapter and playhead | nothing |

The baseline was deliberately left as it was in run 1 so that its three runs differ only by
sampling at temperature 0.3 and by judging; whether it should also get the new grounding wording
is a design choice, not an oversight, and is listed under caveats. The staged calibration does
not touch the baseline: it changes yapbook's `SYSTEM_PROMPT`, which the baseline never uses, and
the tag regex, which leaves untagged replies exactly as before. The post-check confirmed 0 of 60
baseline answers contained a tag, the fixed line, or a "So far it" opener.

The only deviation from shipped yapbook code is a pass-through client wrapper that records the
prompt and tees the stream, a wrapper on `retrieval.retrieve` that records the hits it returns,
and a log handler that captures the gate decision; none changes what the shipped code does.
Exactly one model call and one retrieve call per question. All three runs completed 60 of 60 on
both sides with no errors, no exclusions, no retries and no empty answers. `answers_yapbook.json`
and `answers_baseline.json` hold every answer with prompt size and SHA-256; the yapbook records
also carry the coverage tag, the gate decision and best score, the top-4 retrieved `(chapter,
seq, score)` hits and the `qa_log` cross-check; the baseline records list the 12 retrieved hits.
The prompts themselves are not committed because they contain book text.

The two run 3 answer runs were executed concurrently on one machine (baseline 10:52 to 10:57,
yapbook 10:53 to 10:58 local time on 2026-09-11) sharing the Ollama server with each other and
with an unrelated benchmark. The yapbook side writes only `qa_log.json` and `positions.json` in
the scratch books, which the baseline never reads; index and chapter files were not modified
(checked by mtime). Wall-clock seconds in the answer files are therefore informational only.

### Grading

Two independent LLM judge passes graded every (question, system) answer. Each judge saw the
question, the position, the gold, the `unheard_facts` (ahead/mixed) and both answers with the
system labels hidden; labels were restored only after all verdicts were fixed. Each verdict is
one label from `correct | partial | wrong | refused_appropriately | refused_wrongly`, scored
against the gold (so for ahead items the position-honest answer is the target), plus a `spoiler`
flag (true if the answer states something from `unheard_facts`) with the leaked text quoted as
`evidence`, and a written reason. `judgments.json` holds all 240 run 3 verdicts;
`run2/judgments.json` and `run1/judgments.json` hold the earlier runs, same schema. Judge
agreement in run 3: 96.7% on the label (116 of 120 item-system pairs; the four disagreements are
all on baseline answers, att-05, bn-02, rl-01 and rl-10, each partial vs correct) and 99.2% on
the spoiler flag (119 of 120). Run 2: 97.5% and 99.2%. Run 1: 81.7% and 97.5%.

## Headline numbers, runs 1, 2 and 3 side by side

Each item has two judges, so n is 2 x questions. All numbers are recomputed from the judgment
files by `python tools/score.py --markdown` (run 3), `--bench bench/grounding/run2` (run 2) and
`--bench bench/grounding/run1` (run 1).

| metric | definition | yapbook run 1 | yapbook run 2 | yapbook run 3 | baseline run 1 | baseline run 2 | baseline run 3 |
|---|---|---|---|---|---|---|---|
| spoiler rate | verdicts with `spoiler=true` / verdicts, over ahead + mixed items (36 questions, n=72) | 15.3% (11/72) | 2.8% (2/72) | **2.8% (2/72)** | 84.7% (61/72) | 81.9% (59/72) | 84.7% (61/72) |
| accuracy on behind | verdicts labelled `correct` / verdicts, over behind items (24 questions, n=48); `partial` and `wrong` shown separately | 85.4% correct, 14.6% partial, 0 wrong | 68.8% correct, 18.8% partial, 0 wrong | **66.7% correct, 25.0% partial, 0 wrong** | 52.1% correct, 33.3% partial, 14.6% wrong | 47.9% correct, 39.6% partial, 12.5% wrong | 52.1% correct, 35.4% partial, 12.5% wrong |
| position honesty on ahead | verdicts labelled `refused_appropriately` / verdicts, over ahead items (24 questions, n=48) | 45.8% (22/48) | 83.3% (40/48) | **87.5% (42/48)** | 0.0% (0/48) | 0.0% (0/48) | 0.0% (0/48) |
| refused wrongly | verdicts labelled `refused_wrongly` / verdicts, over behind + mixed items (n=72) | 5.6% (4/72) | 11.1% (8/72) | **8.3% (6/72)** | 0.0% (0/72) | 0.0% (0/72) | 0.0% (0/72) |

Reading the yapbook column across the runs: the two run 2 fixes removed 9 of the 11 run 1
spoiler verdicts and raised position-honest verdicts from 22 to 40; the run 3 calibration kept
the spoiler count at 2 (both bn-06, in both runs), raised position-honest verdicts to 42 (vae-04
and react-01 moved from `partial`; bn-04 moved the other way) and reduced wrong refusals from 8
to 6 verdicts. The behind accuracy is 41, 33 and 32 correct verdicts across the three runs: the
calibration recovered vae-07 (refused wrongly to correct) and rl-04 (refused wrongly to partial),
lost vae-03 (correct to refused wrongly), and traded bn-09 (partial to correct) against bn-10 and
rl-14 (correct to partial). The cost of the tag protocol relative to run 1 is still visible: 6
wrong-refusal verdicts against 4, and 12 partial verdicts against 7.

The baseline columns differ only by sampling and judging: its prompts were byte-identical across
the three runs and 8 of its 60 run 3 answers were byte-identical to run 2 (9 to run 1). Its
numbers moved by a net 2 spoiler verdicts and a net 2 behind-correct verdicts between runs, which
is the size of change that should be read as noise on the yapbook side as well.

### Per kind

Run 3:

| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |
|---|---|---|---|---|---|---|---|---|
| yapbook | behind | 48 | 32 | 12 | 0 | 0 | 4 | 0 |
| baseline | behind | 48 | 25 | 17 | 6 | 0 | 0 | 4 |
| yapbook | ahead | 48 | 0 | 4 | 2 | 42 | 0 | 2 |
| baseline | ahead | 48 | 0 | 0 | 48 | 0 | 0 | 44 |
| yapbook | mixed | 24 | 12 | 6 | 0 | 4 | 2 | 0 |
| baseline | mixed | 24 | 7 | 11 | 6 | 0 | 0 | 17 |

Run 2, same definitions:

| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |
|---|---|---|---|---|---|---|---|---|
| yapbook | behind | 48 | 33 | 9 | 0 | 0 | 6 | 0 |
| baseline | behind | 48 | 23 | 19 | 6 | 0 | 0 | 4 |
| yapbook | ahead | 48 | 0 | 6 | 2 | 40 | 0 | 2 |
| baseline | ahead | 48 | 0 | 1 | 47 | 0 | 0 | 41 |
| yapbook | mixed | 24 | 10 | 8 | 0 | 4 | 2 | 0 |
| baseline | mixed | 24 | 4 | 12 | 8 | 0 | 0 | 18 |

Run 1, same definitions:

| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |
|---|---|---|---|---|---|---|---|---|
| yapbook | behind | 48 | 41 | 7 | 0 | 0 | 0 | 0 |
| baseline | behind | 48 | 25 | 16 | 7 | 0 | 0 | 5 |
| yapbook | ahead | 48 | 3 | 8 | 15 | 22 | 0 | 10 |
| baseline | ahead | 48 | 1 | 10 | 37 | 0 | 0 | 45 |
| yapbook | mixed | 24 | 10 | 8 | 0 | 2 | 4 | 1 |
| baseline | mixed | 24 | 8 | 13 | 3 | 0 | 0 | 16 |

How to read the run 3 ahead rows: the baseline never said "not yet"; it answered from the whole
book and every one of its 48 verdicts is `wrong`, 44 of them flagged as spoilers (the 4 unflagged
verdicts are rl-05 and rl-15, where the answer was wrong but its content came from before the
position or from nowhere). yapbook gave the position-honest answer in 42 of 48 verdicts. The
remaining 6 are bn-06 (`wrong`, spoiler, both judges), where the model stated the running-average
inference rule from memory despite the no-outside-knowledge rule, the only spoiler yapbook
produced in runs 2 and 3; and bn-04 and rl-09 (`partial`, both judges), where the model tagged
COVERED and answered from heard text without telling the listener that the actual answer is still
ahead.

The `refused_wrongly` verdicts (6 of 72 on behind + mixed) are three questions: att-12 and att-08
(both also refused in run 2) and vae-03 (new). vae-03 is the clearest misfire of run 3: the
reply is the bare fixed line, "The book has not covered that yet.", with no partial, on a
question whose answer sits in the heard part of the current chapter (ch6 seq17-19, 20 of 29
segments heard). att-08 is the case the calibration was meant to fix and did not: the retrieval
block again contained the introduction sentence "...trained for as little as twelve hours on
eight P100 GPUs." (chapter 3 seq 8, fourth passage, score 0.548) and the reply was "The book has
not covered that yet. The book does not say how long it took to train this model. Earlier it
mentions training for as little as twelve hours, but that was in a different context about the
Transformer model, not this specific training data setup." The model read the passage, quoted
it, and refused anyway; the changelog notes this item did not move under any of the sixteen
wordings tried. On the other side, vae-07 (run 2: "not covered yet" followed by the correct
answer) is now a clean COVERED answer, which is exactly what the "never write NOT_COVERED and
then state the answer" rule was for.

Two run 3 replies show the tag and the spoken text disagreeing. rl-15 (ahead) was tagged COVERED
but its text is an abstention ("The book does not say how they get around needing the derivative
of the state distribution..."); both judges graded it `refused_appropriately` on the text, so the
score counts it as position-honest while the tag does not. rl-04 (behind) was tagged COVERED and
gives the reason (weight recent rewards more) but then says "It does not say why" about the
rationale the book does give; graded `partial`. Graders scoring on the tag instead of the spoken
text would move both.

### Per-item transitions, run 2 to run 3 (yapbook)

| transition | items |
|---|---|
| ahead: partial in run 2, position-honest in run 3 | vae-04, react-01 |
| ahead: position-honest in run 2, partial in run 3 | bn-04 (tag COVERED in both runs; the run 3 gloss "not by forcing them to zero mean and unit variance" was judged misleading) |
| ahead: spoiler in both runs | bn-06 |
| ahead: partial in both runs | rl-09 |
| ahead: tag flipped NOT_COVERED to COVERED, verdict unchanged (`refused_appropriately`) | rl-15 |
| behind: refused wrongly in run 2, correct in run 3 | vae-07 |
| behind: refused wrongly in run 2, partial in run 3 | rl-04 |
| behind: correct in run 2, refused wrongly in run 3 | vae-03 |
| behind: refused wrongly in both runs | att-12 |
| behind: partial in run 2, correct in run 3 | bn-09, bn-03 (one judge) |
| behind: correct in run 2, partial in run 3 | bn-10, rl-14 |
| mixed: partial in run 2, correct in run 3 | bn-02 |
| mixed: refused wrongly in both runs | att-08 |
| everything else | unchanged label |

The coverage tag itself flipped on 4 of 60 items between the runs (vae-03 and rl-15 in the wrong
direction, vae-04 and vae-07 in the right one), leaving the per-kind tag counts identical (behind
22 COVERED / 2 NOT_COVERED, ahead 19 / 5, mixed 9 / 3). Only 2 of 60 yapbook answer texts are
byte-identical to run 2, so at temperature 0.3 each run is one sample; the four flips are within
what sampling alone produces.

### Per book (run 3; run 2 in `run2/README.md`, run 1 in `run1/README.md`)

| book | questions (behind/ahead/mixed) | system | behind correct | ahead refused appropriately | spoilers on ahead+mixed | refused wrongly (behind+mixed) |
|---|---|---|---|---|---|---|
| attention | 4/5/3 | yapbook | 4/8 | 10/10 | 0/16 | 4/14 |
| attention | 4/5/3 | baseline | 7/8 | 0/10 | 16/16 | 0/14 |
| batchnorm | 5/3/2 | yapbook | 6/10 | 2/6 | 2/10 | 0/14 |
| batchnorm | 5/3/2 | baseline | 4/10 | 0/6 | 8/10 | 0/14 |
| react | 4/3/1 | yapbook | 8/8 | 6/6 | 0/8 | 0/10 |
| react | 4/3/1 | baseline | 6/8 | 0/6 | 7/8 | 0/10 |
| rl-book | 6/8/3 | yapbook | 8/12 | 14/16 | 0/22 | 0/18 |
| rl-book | 6/8/3 | baseline | 2/12 | 0/16 | 18/22 | 0/18 |
| string-junctions | 2/2/1 | yapbook | 2/4 | 4/4 | 0/6 | 0/6 |
| string-junctions | 2/2/1 | baseline | 2/4 | 0/4 | 4/6 | 0/6 |
| vae | 3/3/2 | yapbook | 4/6 | 6/6 | 0/10 | 2/10 |
| vae | 3/3/2 | baseline | 4/6 | 0/6 | 8/10 | 0/10 |

The attention paper is still where the tag protocol costs yapbook most: att-12 and att-08 hold 4
of the 6 wrong-refusal verdicts, and att-05 and att-07 are `partial` on both sides. The batchnorm
paper is where yapbook is least position-honest (2 of 6 ahead verdicts): bn-04 answered from
heard text without a "not yet" and bn-06 answered from memory. The RL book is where the
baseline's flat retrieval hurts most on behind questions (2 of 12 correct; 1 of 12 in the earlier
runs): with 9015 sentence-sized segments, the 12 nearest hits to a question about the current
section are often the same concept as discussed in a later chapter. On the short papers the two
systems are close on behind questions; the gap there is almost entirely spoilers.

## Five side-by-side examples (run 3)

Answers are verbatim. The "0. 9"-style spacing inside numbers and the Unicode math symbols are
artifacts of the shared sentence splitter and sanitizer in `qa.answer()` and of the ingested
text, present in all runs and affecting both systems equally.

### 1. att-02 (ahead): baseline spoils the explanation the listener is about to hear

Position: Attention paper, chapter 9 ("3.2.1 Scaled Dot-Product Attention"), 3 of 9 segments
heard. The transcript has said the dot products are divided by root d k; the reason comes at
seq 7-8. yapbook's gate skipped retrieval (best score 0.501). The baseline's 12 hits included
chapter 9 seq 8 and the chapter 10 seq 8 footnote, both unheard.

> **Q:** Why do they divide by the square root of d k?
>
> **yapbook:** The book has not covered that yet. The book does not say why they divide by the square root of d k.
>
> **baseline:** They divide by the square root of d k to scale the dot products, preventing them from becoming too large. This scaling ensures the softmax function operates in regions where it has reasonable gradients. Without this, large dot products would push the softmax into areas with very small gradients, reducing the effectiveness of the attention mechanism. The division by √ d k is a key part of the scaled dot-product attention mechanism.

Judges: yapbook `refused_appropriately` x2. Baseline `wrong` x2, spoiler x2 (the small-gradients
rationale is the unheard seq 7-8). In run 1 yapbook answered this from memory and was graded
`wrong` with a spoiler; it has refused cleanly in runs 2 and 3.

### 2. rl-11 (ahead): baseline compares two algorithms before the second one is defined

Position: RL book, chapter 89 ("6.4 Sarsa: On-policy TD Control"), all 16 segments heard;
Q-learning is defined in chapter 91 and the cliff-walking comparison is in chapter 92. yapbook's
block was present (best 0.667) but of little use: one passage is the chapter 1 history sentence
that names Watkins's Q-learning, the other three are single-character formula fragments ("q")
that the index treats as segments; all four are before the playhead. All 12 baseline hits came
from chapters 92 to 98.

> **Q:** How is Q-learning different from Sarsa?
>
> **yapbook:** The book has not covered that yet. The book does not say how Q-learning is different from Sarsa. It mentions Q-learning briefly in an earlier passage, noting it made action-value functions important, but does not compare it to Sarsa in the current section.
>
> **baseline:** Q-learning is an off-policy method, while Sarsa is an on-policy method. Q-learning learns the values of the optimal policy, whereas Sarsa learns the value of the current policy. Q-learning has better long-term performance in theory but performs worse in online practice than Sarsa on some tasks.

Judges: yapbook `refused_appropriately` x2. Baseline `wrong` x2, spoiler x2 (the off-policy
definition and the cliff-walking online-performance result are both after the position).

### 3. str-03 (behind): both systems had the passage; only yapbook used it

Position: String junctions paper, chapter 3 ("2. Spectrum of a Heterotic String"), 29 of 44
segments heard; the condition is at seq 25-28, in the heard part of the chapter transcript. The
baseline's top hit (score 0.977) was that very segment (chapter 3 seq 25), so the relevant
passage was in both prompts.

> **Q:** What's the BPS condition for the heterotic string here?
>
> **yapbook:** The BPS condition for the heterotic string here is Nsubosc plus a equals 0. This corresponds to the condition that the norm of K is less than or equal to 2, which is given as K squared equals minus 2 times the quantity Ntildesubosc plus atilde, and this is equivalent to the BPS condition for junctions J times J less than or equal to 2.
>
> **baseline:** The BPS condition for a heterotic string is given in the passage as part of the spectrum of the heterotic string. It relates the string charges (P µ , Q µ) through equation (1. 2), which connects the quantum numbers of heterotic strings to the invariant charges of string junctions in type IIB theory. The BPS condition ensures that the string states satisfy a relation between their charges and masses, maintaining supersymmetry.

Judges: yapbook `correct` x2. Baseline `wrong` x2, no spoiler (it never states the condition).
Same outcome in run 2.

### 4. vae-03 (behind): yapbook refused a question whose answer was in its own transcript

Position: VAE paper, chapter 6 ("2.3 The SGVB estimator and AEVB algorithm"), 20 of 29 segments
heard; the explanation (the KL term can be integrated analytically, so only the reconstruction
term needs sampling) is at seq 17-19, in the heard chapter transcript. yapbook's block was
present (best 0.642, four earlier passages) but the answer is in the transcript, not the block.
The baseline's top hit (0.718) was chapter 6 seq 19; its second hit was Appendix F (chapter 22).

> **Q:** Why does the second version of the estimator have lower variance?
>
> **yapbook:** The book has not covered that yet.
>
> **baseline:** The second version of the estimator has lower variance because the model involves Gaussian distributions for p α ( θ ), p θ ( z ), q φ ( θ ), and q φ ( z | x ), allowing four terms of f φ to be solved analytically. This analytical solution reduces the variance of the gradient estimator. The resulting estimator is specifically designed to have less variance than the generic Monte Carlo gradient estimator. This reduction in variance makes the estimator more stable and practical for optimization.

Judges: yapbook `refused_wrongly` x2. Baseline `partial` x2, spoiler x2 (the Gaussian
hyperprior explanation is Appendix F's full-VB estimator, not the section 2.3 one, and the
appendices are far past the position). In run 2 yapbook was `correct` x2 on this item; the raw
run 3 stream was `NOT_COVERED` and nothing else, so the listener hears only the fixed line.

### 5. bn-06 (ahead): both systems answer from memory; yapbook's only spoiler

Position: BatchNorm paper, chapter 4 ("3 Normalization via Mini-Batch Statistics"), all 28
segments heard; inference-time normalization is chapter 5. yapbook's prompt held the whole of
chapter 4 plus four passages from chapters 0 to 2 (best 0.657), none of which describe
inference. The model tagged COVERED.

> **Q:** What happens at test time when there's no mini-batch to normalize over?
>
> **yapbook:** At test time, when there's no mini-batch to normalize over, the normalized activations are computed using the running averages of the mean and variance, which are updated during training. This ensures consistent behavior between training and test time.
>
> **baseline:** At test time, when there is no mini-batch to normalize over, the network uses running averages of the mean and variance computed during training, rather than mini-batch statistics. This ensures the output depends only on the input, deterministically. The batch normalization transform then applies these precomputed values to produce consistent, stable outputs.

Judges: both systems `wrong` x2, spoiler x2. The content is roughly what the paper says in the
next chapter, and neither prompt contained it: the 4B model knows this paper. This item has been
a yapbook spoiler in all three runs and is the clearest limit of a prompt-level
no-outside-knowledge rule.

## Caveats

1. **LLM judges, not people.** Both judge passes are language models. Run 3 label agreement was
   96.7% and spoiler-flag agreement 99.2% (run 2: 97.5% and 99.2%; run 1: 81.7% and 97.5%). The
   judge prompts and model identities were run by the orchestrating session and are not
   recorded in this directory; the verdicts and rationales are. Each run was judged in a
   separate pass, so part of every run-to-run delta is judging noise as well as sampling noise;
   the baseline columns, whose prompts did not change, bound that at about 2 verdicts per
   metric.
2. **The calibration was tuned on these questions.** The run 3 system prompt was chosen among
   sixteen wordings measured on this benchmark's own 48 behind and ahead questions and its 12
   mixed ones, plus a 24-question held-out set on chapters the benchmark never used (`covtag/`).
   The yapbook run 3 numbers are therefore in-sample for the prompt wording; the held-out set is
   the out-of-sample check (0 of 24 wrong refusals, 18 of 24 NOT_COVERED on ahead questions,
   per the changelog). The same applies to `RETRIEVAL_MIN_SCORE = 0.60`, which was set by looking
   at this benchmark's score distribution in run 1.
3. **Same local 4B model for both systems, and it knows these papers.** `qwen3:4b-instruct` has
   almost certainly seen Attention, VAE, BatchNorm and ReAct in training. The
   no-outside-knowledge rule removed 9 of yapbook's 11 run 1 spoiler verdicts; bn-06 shows it is
   a rule the model can still break. A bigger or smaller model could behave differently in
   either direction. Nothing here measures the model's quality, only what the two prompts let it
   do.
4. **The code under test is not a commit.** Run 3 ran on 5415fca plus staged, uncommitted
   changes. The working tree equalled the index (no unstaged diff, no untracked files) and the
   system prompt's SHA-256 and six wording markers are in `proof/answers_yapbook.meta.json`, so
   the run is reproducible from the staged diff, but a reader checking out 5415fca alone will
   get the run 2 wording.
5. **The baseline did not get the new prompt.** Its system prompt is still the run 1 wording,
   with no tag protocol, no no-outside-knowledge rule and no examples, so it stays comparable
   with its own earlier runs. A baseline given the new wording could plausibly refuse more and
   spoil somewhat less on questions whose answer is not in its 12 hits; it could not become
   position-honest without a position, which is the thing under test. Because the baseline
   retrieves from the whole book, every one of its 60 prompts contained at least one segment at
   or after the listening position; that is the intended contrast, and it favors the baseline on
   raw correctness of ahead questions while ruling out position honesty by construction.
6. **Questions were written by an LLM.** They were verified against the ingested text
   mechanically and the five papers plus three RL chapters were read in full, but for the other
   RL chapters the absence of unheard facts rests on the keyword grep, not on reading. The gold
   answers and `unheard_facts` are also LLM-written from those readings.
7. **Small n.** 60 questions, 6 books, 24/24/12 by kind, 5 to 17 per book. Per-book numbers in
   particular are a handful of items each. No confidence intervals are given because the two
   judges are not independent samples of the same distribution. Between run 2 and run 3 the
   yapbook tag flipped on 4 items and the label on 11; at temperature 0.3 with only 2 of 60
   answers byte-identical between runs, that is one sample's worth of movement.
8. **Baseline was not tuned.** k=12 single segments with no neighbours and no chapter labels was
   a first choice, not a search; yapbook's context is the entire heard chapter plus a 4-passage
   block, and its header names the chapter. Neither k was tuned.
9. **Non-deterministic.** Temperature 0.3 is yapbook's shipped default and was used on both
   sides; a re-run will produce different wording and some different verdicts. Wall-clock
   seconds in the answer files are informational only; the two answer runs and an unrelated
   benchmark shared the machine, and latency was not measured. One yapbook answer hit the
   4-sentence cap (bn-09; shipped behaviour).
10. **Fresh ingests.** The five papers were re-ingested for run 1; chapter and segment numbers
    refer to these copies only, and the six figure descriptions per paper are deferred
    placeholders. Runs 2 and 3 reused the same copies.
11. **Shipped side effects were confined to the scratch directory.** Each yapbook ask appended a
    `source="ask"` entry to the scratch book's `qa_log.json` and rewrote the scratch
    `positions.json`; the real library was verified unchanged by a file snapshot before and after
    the run.

## Files

| file | contents |
|---|---|
| `questions.json` | the 60 questions with gold answers and locations (shared by all runs) |
| `questions_verify.txt` | mechanical verification log for every question (gold segments quoted, unheard segments quoted, keyword absence) |
| `answers_yapbook.json` | run 3: yapbook's 60 answers with position, chapter title, heard segment count, coverage tag, retrieval gate decision and hits, `qa_log` cross-check, prompt size and SHA-256 |
| `answers_baseline.json` | run 3: the baseline's 60 answers with the 12 retrieved hits, prompt size and SHA-256 |
| `judgments.json` | run 3: 240 verdicts (60 questions x 2 systems x 2 judges) plus the aggregate |
| `run2/` | run 2: `answers_yapbook.json`, `answers_baseline.json`, `judgments.json`, the run 2 `README.md` with its numbers and its run 1 comparison, and `proof/` logs |
| `run1/` | run 1: same layout, the run 1 `README.md` with its numbers, and `proof/` logs |
| `covtag/` | the coverage-tag calibration record: the sixteen wordings, the held-out question set and its verification log, replies, verdicts and the summary table (staged with the calibration) |
| `tools/build_questions.py` | source of the questions and the verifier; regenerates `questions.json` and `questions_verify.txt` |
| `tools/yapbook_ask.py` | yapbook's shipped answer path at an explicit position (used for the probe and the equivalence check) |
| `tools/run_yapbook3.py` | run 3 runner: all questions through `mcp_server.ask_book_text` via `positions.json`, recording prompt, tag, gate, hits, `qa_log` and the calibration markers |
| `tools/run_yapbook2.py`, `tools/run_yapbook.py` | the run 2 and run 1 runners (kept) |
| `tools/baseline_ask.py` | the no-position baseline |
| `tools/run_baseline.py` | runs all questions through the baseline |
| `tools/summarize_yapbook3.py`, `tools/postcheck_baseline_run3.py` | run 3 sanity checks: tag counts, gate decisions, spoiler-gate check on hits, tag flips and prompt growth vs run 2, baseline determinism vs runs 1 and 2 (not grades) |
| `tools/summarize_yapbook2.py`, `tools/postcheck_baseline_run2.py`, `tools/summarize_yapbook.py`, `tools/summarize_baseline.py` | the run 2 and run 1 sanity checks |
| `tools/score.py` | recomputes every number above from a judgments file (`--bench run2` or `run1` for the earlier runs) |
| `proof/` | run 3 logs and run metadata (`run_yapbook3.log`, `answers_yapbook.meta.json` with the system-prompt SHA-256 and calibration markers, `answers_baseline.log`, `answers_baseline.meta.json`, `summarize_yapbook3.txt`) and the RL book chapter map |

## How to re-run

Prerequisites: the repo checkout with its venv (`pip install -e .[all,dev]`), Ollama running
locally with `qwen3:4b-instruct` and `nomic-embed-text` pulled, and roughly half an hour
including ingest (each answer run took about 5 minutes here).

```
# 1. scratch data dir; never point this at your real library
set YAPBOOK_DATA_DIR=C:\path\to\scratch\data
mkdir %YAPBOOK_DATA_DIR%
```

Put a `config.toml` there with the shipped brain settings plus `retrieval_enabled = true`,
`embed_model = "nomic-embed-text"`, `ingest_figures = "defer"`, `quiz_enabled = false`.

```
# 2. books (the RL book must be copied from a library that already has it, slug rl-book-full-endurance)
yapbook add 1706.03762 --figures defer
yapbook add 1312.6114 --figures defer
yapbook add 1502.03167 --figures defer
yapbook add 2210.03629 --figures defer
yapbook add arxiv.org/abs/hep-th/9901001 --figures defer
for each slug: yapbook index <slug>

# 3. verify the questions against your ingest (positions can shift if ingestion changes)
python bench/grounding/tools/build_questions.py
python bench/grounding/tools/run_yapbook3.py --dry-run
python bench/grounding/tools/run_yapbook3.py --check att-01   # explicit position vs positions.json must give the same prompt

# 4. answer
python bench/grounding/tools/run_yapbook3.py
python bench/grounding/tools/run_baseline.py
python bench/grounding/tools/summarize_yapbook3.py
python bench/grounding/tools/postcheck_baseline_run3.py

# 5. judge (not automated here): produce judgments.json in the schema described in its "schema" field,
#    with the system labels hidden from the judge, then
python bench/grounding/tools/score.py --markdown
python bench/grounding/tools/score.py --markdown --bench bench/grounding/run2
python bench/grounding/tools/score.py --markdown --bench bench/grounding/run1
```

The runners refuse to start without `YAPBOOK_DATA_DIR`, write results after every question, and
are resumable. `run_yapbook3.py` writes `answers_yapbook_full.json` next to the compact file
(full prompts, raw stream, log lines); it is not committed because it contains book text. It also
records the loaded system prompt's SHA-256 and checks the calibration markers, so a run on the
wrong wording is visible in the meta file. Pass `--temperature 0` to both `yapbook_ask.py` and
`baseline_ask.py` for repeatable answers.
