> **Archived: run 2.** These are the second run's answers and verdicts, produced on the code under test at
> `main` 05ac302 (similarity-gated retrieval aecd630 plus the first coverage-tag wording 17eba38). They are
> kept unchanged so the runs can be compared; the current results (run 3, after the coverage-tag calibration)
> and the three-way side-by-side are in `../README.md`. Re-score this run with
> `python tools/score.py --markdown --bench bench/grounding/run2`. Paths in the text below that say `run1/`
> still resolve (`../run1/`); references to "this directory" mean this `run2/` directory, and the tools it
> names (`run_yapbook2.py`, `summarize_yapbook2.py`, `postcheck_baseline_run2.py`) are still in `../tools/`.

# Grounding benchmark: position-grounded answering vs a no-position baseline

Two runs. **Run 2** (this directory) is the current result, produced on the code under test at
`main` 05ac302 after two fixes that run 1 motivated. **Run 1** (`run1/`) is the first run on the
phrase-trigger build (commit 1904431), kept unchanged for comparison. Same 60 questions, same
books, same model, same grading protocol, same definitions in both.

## Purpose

yapbook reads a textbook aloud and lets the listener interrupt with a question. Its answer
path is tied to the playhead: the model sees only what has already been read, so it can say
"the book has not covered that yet" instead of revealing what the book is about to explain.
This benchmark asks whether that design actually changes answer quality compared with the
obvious alternative, a "chat with your PDF" retriever that searches the whole book with no
idea where the listener is. Sixty questions were written at known listening positions in six
books, both systems answered every question with the same local 4B model, and two independent
LLM judges graded the answers blind. In run 2 the no-position baseline leaked not-yet-read
material in 82% of judged verdicts on questions about upcoming content and yapbook in 3%;
yapbook gave the position-honest answer on 83% of upcoming-content verdicts, the baseline on
none. The cost shows up on already-read content: yapbook was graded correct on 69% of those
verdicts against 48% for the baseline, but it also refused 4 questions it could have answered
(8 of 72 verdicts), a failure mode run 1 did not have at that rate.

## What changed between run 1 and run 2

Both changes are in `CHANGELOG.md` under 0.2.0 ("Whole-book memory" and "Answers default to
'not covered yet'"). Nothing else in the answer path changed; the baseline code did not change
at all.

1. **Retrieval trigger (aecd630).** In run 1 yapbook's whole-book retrieval block joined the
   prompt only when the question's wording named another chapter or said "earlier in the
   book". No benchmark question does, so it never fired: yapbook's prompt was the current
   chapter's heard prefix and nothing else, and facts from a paper's abstract were unreachable
   from a later chapter. Now every question is embedded and the block joins when the best
   gated cosine score reaches 0.60 (`RETRIEVAL_MIN_SCORE` in `qa/context.py`; cross-chapter
   wording still forces it). The spoiler rule is enforced inside the retrieval function: no
   row at or past the playhead can surface. In run 2 the block was present in 53 of 60 prompts
   (4 passages each, all including at least one passage from another chapter); 7 questions
   fell below the gate (att-02, att-10, vae-07, react-01, react-08, str-01, str-02). The force
   path fired on 0 of 60, so every block came from the similarity gate. 0 of the 212 retrieved
   rows lay at or past the playhead.
2. **Coverage tag (17eba38).** The system prompt now forbids outside knowledge outright (run 1
   showed the 4B model completing famous papers from memory) and asks the model to open every
   reply with `COVERED` or `NOT_COVERED`. The streaming layer strips the tag; on `NOT_COVERED`
   yapbook speaks a fixed line, "The book has not covered that yet.", followed by the model's
   "So far it ..." partial. In run 2 the tag was well formed on 60 of 60 replies (cross-checked
   against the `covered` field the shipped path wrote to each scratch book's `qa_log.json`, 0
   mismatches). Tags by kind: behind 22 COVERED / 2 NOT_COVERED, ahead 19 NOT_COVERED / 5
   COVERED, mixed 9 COVERED / 3 NOT_COVERED.

Because both fixes went in together, the run 1 to run 2 delta cannot be attributed to one of
them. The per-item transitions below make the attribution partly visible anyway.

## Method

### Books

Six books, all ingested into a scratch data directory (the real yapbook library was never
touched; every command ran with `YAPBOOK_DATA_DIR` pointing at the scratch copy, and a before
and after snapshot of the real library was diffed: identical):

| slug | source | chapters | segments |
|---|---|---|---|
| attention-is-all-you-need | arXiv 1706.03762 | 28 | 217 |
| auto-encoding-variational-bayes | arXiv 1312.6114 | 23 | 251 |
| batch-normalization-accelerating-deep-network-training-by-reducing-internal-covariate-shift | arXiv 1502.03167 | 19 | 255 |
| react-synergizing-reasoning-and-acting-in-language-models | arXiv 2210.03629 | 47 | 550 |
| string-junctions-and-their-duals-in-heterotic-string-theory | arXiv hep-th/9901001 | 8 | 164 |
| rl-book-full-endurance | Sutton and Barto, Reinforcement Learning (2nd ed.), copied from the owner's library | 286 | 9015 |

The five papers were `yapbook add <arxiv-id> --figures defer` ingests (docling, no VLM);
figure descriptions are caption placeholders. "Chapters" are yapbook's heading-level units,
which is why the RL book has 286 of them. Chapter indices below are 0-based `book.json`
indices; yapbook's own prompt header prints them 1-based. Run 2 used the same ingested copies
and the same `nomic-embed-text` index as run 1 (the baseline's retrieved hits and prompt
hashes are identical across the two runs for all 60 questions, which is the check that the
index did not change).

### Position semantics

A question is asked at `(chapter, seq)`. The listener is taken to have heard every segment
of every earlier chapter plus segments `0..seq-1` of `chapter`; segment `seq` itself has not
been heard. This is exactly what `yapbook.mcp_server.ask_book_text` reconstructs from
`positions.json`, verified by a byte-identical prompt check on the run 2 code
(`run_yapbook2.py --check att-01`: explicit-position path and `positions.json` path give the
same prompt, sha256 52858b7b..., 4060 chars).

### Questions (questions.json, 60 records, unchanged from run 1)

Each record has `id, slug, chapter, seq, kind, question, gold, gold_location` and, for
ahead/mixed items, `unheard_facts`. Three kinds:

- **behind** (24): the answer is fully contained in already-heard text. `gold_location`
  cites the segment ids.
- **ahead** (24): the answer lives at or after the position. The gold is the
  position-honest answer ("not covered yet", plus whatever partial hint has been heard), and
  `unheard_facts` lists the specific facts a spoiler would reveal.
- **mixed** (12): part of the answer has been heard, part has not. The gold states the
  heard part and notes the rest is still to come.

Questions were drafted by an LLM after reading the full text of the five papers and three
chapters of the RL book (bandits, TD learning, policy gradient), in the voice of a listener
who does not know what comes next. `tools/build_questions.py` then verified every record
mechanically against the ingested text: each cited gold segment must exist and be heard at
the position; each cited unheard segment must exist and be unheard; and every spoiler keyword
(numbers, names, phrases distinctive to the unheard facts) was grepped over all heard text
(spoken and source text, every earlier chapter in full plus the heard prefix).
`questions_verify.txt` is the 386-line log of that check (60 records, 0 problems). Three
keyword hits were investigated and explained there (a substring false positive in str-02;
headings that name "double learning" and "policy gradient theorem" before defining them in
rl-13 and rl-15, which the golds acknowledge). Two positions were moved during verification
because a table's source text had already leaked the answer (react-08, bn-02).

Seven behind/mixed golds live wholly or partly in an earlier chapter than the position
(att-07, att-08, vae-02 fully; bn-01, bn-02, react-05, rl-17 partly). These are the items
that test cross-chapter memory, which is what the retrieval fix targets.

### The two systems

Both use the same brain model (`qwen3:4b-instruct` via local Ollama, `num_ctx` 16384,
temperature 0.3, `num_predict` 256), the same `qa.answer()` streaming code with its
4-sentence cap and sanitizer, the same per-book index (`nomic-embed-text`, complete for all
six books), and the same 60 questions. They differ only in what the prompt contains:

| | yapbook (shipped path, run 2) | baseline (`tools/baseline_ask.py`, unchanged since run 1) |
|---|---|---|
| entry point | `mcp_server.ask_book_text` after writing `positions.json` | `ask_baseline` |
| context | header naming the current chapter; the heard-so-far transcript of that chapter; a "just heard" quote of the last 3 segments; a 4-passage "Relevant passages from earlier in the book" block when the similarity gate passes (53 of 60), drawn only from rows before the playhead | the 12 segments most cosine-similar to the question over the whole index, no spoiler gate, no chapter labels |
| system prompt | yapbook's: position and spoiler rules, no outside knowledge, reply opens with a COVERED / NOT_COVERED tag | yapbook's run 1 prompt with the position and spoiler rules removed; grounding rule, "say so instead of guessing", length and plain-text rules kept verbatim. Not updated for run 2: no tag protocol, no no-outside-knowledge rule |
| what it knows about position | chapter and playhead | nothing |

The baseline was deliberately left as it was in run 1 so that its two runs differ only by
sampling at temperature 0.3; whether it should also get the new grounding wording is a
design choice, not an oversight, and is listed under caveats. The only deviation from shipped
yapbook code is a pass-through client wrapper that records the prompt and tees the stream, a
wrapper on `retrieval.retrieve` that records the hits it returns, and a log handler that
captures the gate decision; none changes what the shipped code does. Exactly one model call
and one retrieve call per question. Both runs completed 60/60 with no errors, no exclusions
and no empty answers. `answers_yapbook.json` and `answers_baseline.json` hold every answer
with prompt size and SHA-256; the yapbook records also carry the coverage tag, the gate
decision and best score, the top-4 retrieved `(chapter, seq, score)` hits and the `qa_log`
cross-check; the baseline records list the 12 retrieved hits. The prompts themselves are not
committed because they contain book text.

### Grading

Two independent LLM judge passes graded every (question, system) answer. Each judge saw the
question, the position, the gold, the `unheard_facts` (ahead/mixed) and both answers with the
system labels hidden; labels were restored only after all verdicts were fixed. Each verdict
is one label from `correct | partial | wrong | refused_appropriately | refused_wrongly`,
scored against the gold (so for ahead items the position-honest answer is the target), plus
a `spoiler` flag (true if the answer states something from `unheard_facts`) with the leaked
text quoted as `evidence`, and a written reason. `judgments.json` holds all 240 run 2
verdicts; `run1/judgments.json` the 240 run 1 verdicts, same schema. Judge agreement in run 2:
97.5% on the label (117/120 item-system pairs; disagreements bn-03/yapbook partial vs
correct, rl-03/baseline wrong vs partial, rl-14/baseline correct vs partial), 99.2% on the
spoiler flag (119/120). Run 1: 81.7% and 97.5%. The run 2 verdicts are easier to agree on
because most yapbook answers are now an unambiguous refusal or an unambiguous answer.

## Headline numbers, run 1 and run 2 side by side

Each item has two judges, so n is 2 x questions. All numbers are recomputed from the
judgment files by `python tools/score.py --markdown` (run 2) and
`python tools/score.py --markdown --bench bench/grounding/run1` (run 1).

| metric | definition | yapbook run 1 | yapbook run 2 | baseline run 1 | baseline run 2 |
|---|---|---|---|---|---|
| spoiler rate | verdicts with `spoiler=true` / verdicts, over ahead + mixed items (36 questions, n=72) | 15.3% (11/72) | **2.8% (2/72)** | 84.7% (61/72) | 81.9% (59/72) |
| accuracy on behind | verdicts labelled `correct` / verdicts, over behind items (24 questions, n=48); `partial` and `wrong` shown separately | 85.4% correct, 14.6% partial, 0 wrong | **68.8% correct, 18.8% partial, 0 wrong** | 52.1% correct, 33.3% partial, 14.6% wrong | 47.9% correct, 39.6% partial, 12.5% wrong |
| position honesty on ahead | verdicts labelled `refused_appropriately` / verdicts, over ahead items (24 questions, n=48) | 45.8% (22/48) | **83.3% (40/48)** | 0.0% (0/48) | 0.0% (0/48) |
| refused wrongly | verdicts labelled `refused_wrongly` / verdicts, over behind + mixed items (n=72) | 5.6% (4/72) | **11.1% (8/72)** | 0.0% (0/72) | 0.0% (0/72) |

Reading the yapbook column: the two fixes removed 9 of the 11 run 1 spoiler verdicts (the
two left are bn-06) and raised position-honest verdicts on ahead items from 22 to 40. On the
other side, wrong refusals went from 4 verdicts (att-08, vae-02) to 8: vae-02 was fixed by
retrieval, att-08 stayed, and att-12, vae-07 and rl-04 are new. The behind accuracy drop (41
to 33 correct verdicts) is those 6 new wrong-refusal verdicts plus att-05 and bn-09 (correct
to partial, both judges) partly offset by str-03 and bn-03 (one judge each, partial to
correct). The baseline's two columns
differ only by sampling and judging: its prompts were byte-identical across runs and 9 of its
60 answers were byte-identical too.

### Per kind

Run 2:

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

How to read the run 2 ahead rows: the baseline again never said "not yet"; it answered from
the whole book and was flagged as a spoiler in 41 of 48 verdicts (the 7 unflagged verdicts
are wrong answers whose content came from before the position or from nowhere: bn-04, rl-09,
rl-15 and one rl-05 verdict). yapbook gave the position-honest answer in 40 of 48 verdicts. The remaining 8 are:
bn-06 (`wrong`, spoiler, both judges), where the model still stated the running-average
inference rule from memory despite the no-outside-knowledge rule, the only spoiler yapbook
produced in run 2; and vae-04, react-01 and rl-09 (`partial`, both judges), where the model
tagged COVERED and answered from heard text without telling the listener that the actual
answer is still ahead. bn-04 also tagged COVERED but said in words that the book had not
addressed the question, and was graded `refused_appropriately`.

The `refused_wrongly` verdicts (8 of 72 on behind + mixed) are the price of the new default:
att-12, vae-07 and att-08 opened with the fixed "The book has not covered that yet." line on
material the transcript or the retrieval block already contained, and rl-04 tagged COVERED
but denied that the book gives the rationale it does give. vae-07 is the clearest misfire:
the reply says "not covered yet" and then, in the same breath, gives the complete correct
answer. att-08 is the more instructive one: the retrieval fix did what it was meant to do
(the block contained the introduction's "twelve hours on eight P100 GPUs" sentence) and the
model refused anyway. The same fix did work on vae-02, which went from `refused_wrongly` in
run 1 to `correct` in run 2 once the abstract's SGVB sentence was in the block. att-07 stayed
`partial` in both runs: the Table 1 segment ranks 17th among the gated rows for that
question, past the top-4 cut.

### Per-item transitions, run 1 to run 2 (yapbook)

| transition | items |
|---|---|
| ahead: spoiler or wrong in run 1, position-honest in run 2 | att-02, att-03, att-06, bn-04, react-08, rl-05, rl-13, rl-15 |
| ahead: partial in run 1, position-honest in run 2 | str-02, rl-08 |
| ahead: position-honest in run 1, partial in run 2 | vae-04 |
| ahead: spoiler in both runs | bn-06 |
| ahead: partial in both runs (one judge said correct in run 1) | react-01, rl-09 |
| mixed: refused wrongly in run 1, correct in run 2 (retrieval reached the abstract) | vae-02 |
| mixed: partial in run 1, refused appropriately in run 2 | react-05 |
| mixed: correct in run 1, partial in run 2 | bn-02, vae-06 |
| mixed: partial in run 1, correct in run 2 | bn-07 |
| behind: correct in run 1, refused wrongly in run 2 | att-12, vae-07, rl-04 |
| behind: correct in run 1, partial in run 2 | att-05, bn-09 |
| behind or mixed: unchanged label | everything else (including att-08 refused wrongly and att-07 partial in both) |

### Per book (run 2; run 1 in `run1/README.md`)

| book | questions (behind/ahead/mixed) | system | behind correct | ahead refused appropriately | spoilers on ahead+mixed | refused wrongly (behind+mixed) |
|---|---|---|---|---|---|---|
| attention | 4/5/3 | yapbook | 4/8 | 10/10 | 0/16 | 4/14 |
| attention | 4/5/3 | baseline | 8/8 | 0/10 | 16/16 | 0/14 |
| batchnorm | 5/3/2 | yapbook | 5/10 | 4/6 | 2/10 | 0/14 |
| batchnorm | 5/3/2 | baseline | 4/10 | 0/6 | 6/10 | 0/14 |
| react | 4/3/1 | yapbook | 8/8 | 4/6 | 0/8 | 0/10 |
| react | 4/3/1 | baseline | 6/8 | 0/6 | 8/8 | 0/10 |
| rl-book | 6/8/3 | yapbook | 10/12 | 14/16 | 0/22 | 2/18 |
| rl-book | 6/8/3 | baseline | 1/12 | 0/16 | 17/22 | 0/18 |
| string-junctions | 2/2/1 | yapbook | 2/4 | 4/4 | 0/6 | 0/6 |
| string-junctions | 2/2/1 | baseline | 0/4 | 0/4 | 4/6 | 0/6 |
| vae | 3/3/2 | yapbook | 4/6 | 4/6 | 0/10 | 2/10 |
| vae | 3/3/2 | baseline | 4/6 | 0/6 | 8/10 | 0/10 |

The attention paper is where the new default hurts yapbook most: two of its four behind
questions (att-12, att-05) lost verdicts, and it holds 4 of the 8 wrong-refusal verdicts. The
RL book is where the baseline's flat retrieval hurts most on behind questions (1 of 12
correct in both runs): with 9015 sentence-sized segments, the 12 nearest hits to a question
about the current section can be the same concept as discussed in a later chapter (rl-07,
rl-17). On the short papers the two systems are close on behind questions; the gap there is
almost entirely spoilers.

## Five side-by-side examples (run 2)

Answers are verbatim. The "0. 9"-style spacing inside numbers is an artifact of the shared
sentence splitter in `qa.answer()` (a streamed chunk ending in a decimal point is treated as
a sentence end) and affects both systems equally; it is present in run 1 too.

### 1. att-10 (ahead): baseline spoils, yapbook is position-honest

Position: Attention paper, chapter 20 ("5.4 Regularization"), 3 of 6 segments heard. The
text so far says only that three types of regularization are used. yapbook's gate skipped
retrieval here (best score 0.586).

> **Q:** What are the three kinds of regularization they use?
>
> **yapbook:** The book has not covered that yet. So far it does not say what the three kinds of regularization are.
>
> **baseline:** The three kinds of regularization they use are label smoothing with ϵ ls = 0. 1, dropout with P drop = 0. 1, and positional embedding instead of sinusoids. These are explicitly mentioned in the section on regularization.

Judges: yapbook `refused_appropriately` x2. Baseline `wrong` x2, spoiler x2 (the label
smoothing and dropout values are from the unheard segments; "positional embedding instead of
sinusoids" is a Table 3 model variation, not a regularization technique).

### 2. rl-08 (ahead): baseline tells the book's own example before the book does

Position: RL book, chapter 85 (the TD(0) prediction section), 22 of 49 segments heard. The
update rule and backup diagram have been heard; the driving-home example starts at the next
segment. yapbook's retrieval block was present (best score 0.799; all four passages came from the
TD chapter's own opening, chapters 83 and 84, before the playhead).

> **Q:** Is there an everyday example of how TD differs from Monte Carlo?
>
> **yapbook:** The book has not covered that yet. So far it does not say anything about an everyday example of how TD differs from Monte Carlo.
>
> **baseline:** Yes, consider driving home after work. In Monte Carlo, you only update your estimate of how well a route works after you've completed the entire trip and know the final outcome. In TD, you update your estimate after every single step—like when you reach a traffic light or a corner—based on what you see next, making it faster and more responsive to new experiences. This makes TD more efficient in real-time situations.

Judges: yapbook `refused_appropriately` x2. Baseline `wrong` x2, spoiler x2 (the driving-home
example is the unheard ch85 seq22-42, and the details are garbled relative to the book's
legs). In run 1 yapbook was graded `partial` on this item; it now refuses cleanly.

### 3. str-03 (behind): both systems had the passage; only yapbook used it

Position: String junctions paper, chapter 3 ("2. Spectrum of a Heterotic String"), 29 of 44
segments heard; the condition is in the heard part of that chapter. yapbook's block held four
earlier passages (best 0.742); the baseline's top hit (score 0.977) was a chapter 3 segment from
the heard region (seq 25), so the relevant passage was in both prompts.

> **Q:** What's the BPS condition for the heterotic string here?
>
> **yapbook:** For BPS states, the condition is Nosc + a = 0. This corresponds to the BPS condition for junctions J · J ≤ 2 given in reference 8.
>
> **baseline:** The BPS condition for a heterotic string is given in the passage as part of the spectrum of the heterotic string. It relates the string charges (P µ , Q µ) to the quantum numbers of the string states through equation (1. 2). The condition ensures that the string states are BPS states, meaning they satisfy a balance between mass and charge. The BPS condition is tied to the invariant charges of string junctions in dual theories, which must be integers.

Judges: yapbook `correct` x2. Baseline `wrong` x2, no spoiler (never states the condition).

### 4. att-08 (mixed): yapbook refused wrongly with the fact in its own prompt

Position: Attention paper, chapter 17 ("5.1 Training Data and Batching"), 2 of 4 segments
heard. The abstract (chapter 2) and introduction (chapter 3) already gave 3.5 days on eight
GPUs and twelve hours on eight P100 GPUs; the step counts are in the unheard chapter 18. In
run 2 yapbook's similarity gate passed (best 0.612) and the 4-passage block included the
introduction sentence "...trained for as little as twelve hours on eight P100 GPUs."
(chapter 3, seq 8). The model tagged NOT_COVERED anyway.

> **Q:** How long did it take to train this thing?
>
> **yapbook:** The book has not covered that yet. So far it does not say how long it took to train this thing.
>
> **baseline:** It took 3.5 days to train the big models. The training lasted 300,000 steps, with each step taking 1. 0 seconds. This total time was achieved using 8 NVIDIA P100 GPUs.

Judges: yapbook `refused_wrongly` x2 (both runs). Baseline `partial` x2, spoiler x2 (the step
counts and per-step time are from the unheard training-schedule segments). This is the
clearest evidence that the retrieval fix is necessary but not sufficient: the passage reached
the prompt and the 4B model did not use it. The same fix did work on vae-02 (see transitions).

### 5. vae-07 (behind): the coverage tag misfires and contradicts itself

Position: VAE paper, chapter 10 ("5 Experiments"), 13 of 20 segments heard; the sentence
about superfluous latent variables not overfitting is in the heard part and in the prompt.
yapbook's gate skipped retrieval (best 0.583); that does not matter here because the fact is
in the chapter transcript.

> **Q:** Did adding more latent variables make it overfit?
>
> **yapbook:** The book has not covered that yet. So far it says that adding more latent variables did not result in overfitting, and this is explained by the regularizing effect of the variational bound.
>
> **baseline:** No, adding more latent variables did not make it overfit. The passages state that superfluous latent variables did not result in overfitting, which is explained by the regularizing nature of the variational bound. This regularizing effect prevents overfitting even as the number of latent variables increases.

Judges: yapbook `refused_wrongly` x2. Baseline `correct` x2. The raw model stream was
`NOT_COVERED` followed by the correct content; the fixed spoken line is what the tag protocol
does with that tag, so the listener hears a denial and then the answer. In run 1 (no tag
protocol) yapbook was `correct` x2 on this item.

The single yapbook spoiler in run 2, bn-06, is not shown as a full example because both
systems produced near-identical answers: both stated the running-average inference procedure
from the unheard chapter 5. yapbook's prompt held only chapter 4's transcript and four earlier
passages, none of which describe inference; the answer came from the model's knowledge of the
paper, against the system prompt's rule.

## Caveats

1. **LLM judges, not people.** Both judge passes are language models. Run 2 label agreement
   was 97.5% and spoiler-flag agreement 99.2% (run 1: 81.7% and 97.5%). The judge prompts and
   model identities were run by the orchestrating session and are not recorded in this
   directory; the verdicts and rationales are. Run 1 and run 2 were judged in separate
   passes, so a small part of the run-to-run delta is judging noise as well as sampling
   noise; the baseline columns, whose prompts did not change, bound that: a net 2 spoiler
   verdicts and a net 2 behind-correct verdicts moved between runs on identical prompts.
2. **Same local 4B model for both systems, and it knows these papers.** `qwen3:4b-instruct`
   has almost certainly seen Attention, VAE, BatchNorm and ReAct in training. The
   no-outside-knowledge rule removed 9 of yapbook's 11 run 1 spoiler verdicts; bn-06 shows it
   is a rule the model can still break. A bigger or smaller model could behave differently
   in either direction. Nothing here measures the model's quality, only what the two prompts
   let it do.
3. **The retrieval gate was tuned on these questions.** `RETRIEVAL_MIN_SCORE = 0.60` was set
   by looking at the score distribution of this benchmark's 60 questions (the comment in
   `qa/context.py` cites it). The 53 of 60 inclusion rate is therefore an in-sample number,
   not a prediction for other books or question styles.
4. **Two fixes went in together.** Run 2 differs from run 1 by the gated retrieval and by the
   rewritten system prompt with the tag protocol. The transitions table separates them only
   where the mechanism is visible in the record (vae-02 needed the block; the ahead flips
   needed the prompt); the aggregate delta cannot be split between them.
5. **The baseline did not get the new prompt.** Its system prompt is still the run 1 wording
   (grounding rule, "say so instead of guessing"), with no tag protocol and no
   no-outside-knowledge rule, so it stays comparable with its own run 1. A baseline given the
   new wording could plausibly refuse more and spoil somewhat less on questions whose answer
   is not in its 12 hits; it could not become position-honest without a position, which is
   the thing under test. 0 of 60 baseline answers contained a tag or the fixed line.
6. **Questions were written by an LLM.** They were verified against the ingested text
   mechanically and the five papers plus three RL chapters were read in full, but for the
   other RL chapters the absence of unheard facts rests on the keyword grep, not on reading.
   The gold answers and `unheard_facts` are also LLM-written from those readings.
7. **Small n.** 60 questions, 6 books, 24/24/12 by kind, 5 to 17 per book. Per-book numbers
   in particular are a handful of items each. No confidence intervals are given because the
   two judges are not independent samples of the same distribution.
8. **Baseline was not tuned.** k=12 single segments with no neighbours and no chapter labels
   was a first choice, not a search; yapbook's context is the entire heard chapter plus a
   4-passage block, and its header names the chapter. Neither k was tuned.
9. **Non-deterministic.** Temperature 0.3 is yapbook's shipped default and was used on both
   sides; a re-run will produce different wording and some different verdicts. Wall-clock
   seconds in the answer files are informational only; the machine was shared with another
   benchmark and latency was not measured. Two yapbook answers hit the 4-sentence cap (bn-10,
   react-05; shipped behaviour).
10. **Fresh ingests.** The five papers were re-ingested for run 1; chapter and segment
    numbers refer to these copies only, and the six figure descriptions per paper are
    deferred placeholders. Run 2 reused the same copies.
11. **Shipped side effects were confined to the scratch directory.** Each yapbook ask
    appended a `source="ask"` entry to the scratch book's `qa_log.json` and rewrote the
    scratch `positions.json`; the real library was verified unchanged by a file snapshot
    before and after the run.

## Files

| file | contents |
|---|---|
| `questions.json` | the 60 questions with gold answers and locations (shared by both runs) |
| `questions_verify.txt` | mechanical verification log for every question (gold segments quoted, unheard segments quoted, keyword absence) |
| `answers_yapbook.json` | run 2: yapbook's 60 answers with position, chapter title, heard segment count, coverage tag, retrieval gate decision and hits, `qa_log` cross-check, prompt size and SHA-256 |
| `answers_baseline.json` | run 2: the baseline's 60 answers with the 12 retrieved hits, prompt size and SHA-256 |
| `judgments.json` | run 2: 240 verdicts (60 questions x 2 systems x 2 judges) plus the aggregate |
| `run1/` | run 1: `answers_yapbook.json`, `answers_baseline.json`, `judgments.json`, the run 1 `README.md` with its numbers, and `proof/` logs |
| `tools/build_questions.py` | source of the questions and the verifier; regenerates `questions.json` and `questions_verify.txt` |
| `tools/yapbook_ask.py` | yapbook's shipped answer path at an explicit position (used for the probe and the equivalence check) |
| `tools/run_yapbook2.py` | run 2 runner: all questions through `mcp_server.ask_book_text` via `positions.json`, recording prompt, tag, gate, hits and `qa_log` |
| `tools/run_yapbook.py` | run 1 runner (kept; it predates the tag and gate fields) |
| `tools/baseline_ask.py` | the no-position baseline |
| `tools/run_baseline.py` | runs all questions through the baseline |
| `tools/summarize_yapbook2.py`, `tools/postcheck_baseline_run2.py` | run 2 sanity checks: tag counts, gate decisions, spoiler-gate check on hits, determinism vs run 1 (not grades) |
| `tools/summarize_yapbook.py`, `tools/summarize_baseline.py` | run 1 sanity checks and a keyword-based abstain heuristic (not a grade) |
| `tools/score.py` | recomputes every number above from a judgments file (`--bench run1` for run 1) |
| `proof/` | run 2 logs and run metadata (`run_yapbook2.log`, `answers_yapbook.meta.json`, `answers_baseline.log`, `answers_baseline.meta.json`, `summarize_yapbook2.txt`) and the RL book chapter map |

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
python bench/grounding/tools/run_yapbook2.py --dry-run
python bench/grounding/tools/run_yapbook2.py --check att-01   # explicit position vs positions.json must give the same prompt

# 4. answer
python bench/grounding/tools/run_yapbook2.py
python bench/grounding/tools/run_baseline.py
python bench/grounding/tools/summarize_yapbook2.py
python bench/grounding/tools/postcheck_baseline_run2.py

# 5. judge (not automated here): produce judgments.json in the schema described in its "schema" field,
#    with the system labels hidden from the judge, then
python bench/grounding/tools/score.py --markdown
python bench/grounding/tools/score.py --markdown --bench bench/grounding/run1
```

The runners refuse to start without `YAPBOOK_DATA_DIR`, write results after every question,
and are resumable. `run_yapbook2.py` writes `answers_yapbook_full.json` next to the compact
file (full prompts, raw stream, log lines); it is not committed because it contains book
text. Pass `--temperature 0` to both `yapbook_ask.py` and `baseline_ask.py` for repeatable
answers.
