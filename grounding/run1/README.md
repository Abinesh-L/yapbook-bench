> **Archived: run 1.** These are the first run's answers and verdicts, produced on the phrase-trigger build
> (commit 1904431, before aecd630 and 17eba38). They are kept unchanged so the two runs can be compared;
> the current results and the side-by-side comparison are in `../README.md`. Re-score this run with
> `python tools/score.py --markdown --bench bench/grounding/run1`. The two "Addressed after this run" notes
> in the caveats below were appended while the fixes were being built and describe the change this run
> motivated; run 2 measures it.

# Grounding benchmark: position-grounded answering vs a no-position baseline

## Purpose

yapbook reads a textbook aloud and lets the listener interrupt with a question. Its answer
path is tied to the playhead: the model only sees the part of the current chapter that has
already been read, so it can say "that has not come up yet" instead of revealing what the
book is about to explain. This benchmark asks whether that design actually changes answer
quality compared with the obvious alternative, a "chat with your PDF" retriever that
searches the whole book with no idea where the listener is. Sixty questions were written at
known listening positions in six books, both systems answered every question with the same
local 4B model, and two independent LLM judges graded the answers blind. The result: the
no-position baseline leaked not-yet-read material in 85% of judged verdicts on questions
about upcoming content, yapbook in 15%; on questions about already-read content yapbook was
graded correct 85% of the time versus 52% for the baseline. yapbook also has a real
weakness that the benchmark exposes: it forgot facts from earlier chapters in 4 of 72
verdicts, because its cross-chapter retrieval never fired on any of these questions.

## Method

### Books

Six books were used, all ingested into a scratch data directory (the real yapbook library
was never touched; every command ran with `YAPBOOK_DATA_DIR` pointing at the scratch copy):

| slug | source | chapters | segments |
|---|---|---|---|
| attention-is-all-you-need | arXiv 1706.03762 | 28 | 217 |
| auto-encoding-variational-bayes | arXiv 1312.6114 | 23 | 251 |
| batch-normalization-accelerating-deep-network-training-by-reducing-internal-covariate-shift | arXiv 1502.03167 | 19 | 255 |
| react-synergizing-reasoning-and-acting-in-language-models | arXiv 2210.03629 | 47 | 550 |
| string-junctions-and-their-duals-in-heterotic-string-theory | arXiv hep-th/9901001 | 8 | 164 |
| rl-book-full-endurance | Sutton and Barto, Reinforcement Learning (2nd ed.), copied from the owner's library | 286 | 9015 |

The five papers were fresh `yapbook add <arxiv-id> --figures defer` ingests (docling, no
VLM); figure descriptions are caption placeholders. "Chapters" are yapbook's heading-level
units, which is why the RL book has 286 of them. Chapter indices below are 0-based
`book.json` indices; yapbook's own prompt header prints them 1-based.

### Position semantics

A question is asked at `(chapter, seq)`. The listener is taken to have heard every segment
of every earlier chapter plus segments `0..seq-1` of `chapter`; segment `seq` itself has not
been heard. This is exactly what `yapbook.mcp_server.ask_book_text` reconstructs from
`positions.json`, verified by a byte-identical prompt check (`run_yapbook.py --check`).

### Questions (questions.json, 60 records)

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
chapters of the RL book (bandits, TD learning, policy gradient), and written in the voice of
a listener who does not know what comes next. `tools/build_questions.py` then verified every
record mechanically against the ingested text: each cited gold segment must exist and be
heard at the position; each cited unheard segment must exist and be unheard; and every
spoiler keyword (numbers, names, phrases distinctive to the unheard facts) was grepped over
all heard text (spoken and source text, every earlier chapter in full plus the heard prefix).
`questions_verify.txt` is the 386-line log of that check (60 records, 0 problems). Three
keyword hits were investigated and explained there (a substring false positive in str-02;
headings that name "double learning" and "policy gradient theorem" before defining them in
rl-13 and rl-15, which the golds acknowledge). Two positions were moved during verification
because a table's source text had already leaked the answer (react-08, bn-02).

No question uses cross-chapter phrasing ("chapter N", "earlier in the book"), which is what
triggers yapbook's whole-book retrieval; see caveat 3 below.

### The two systems

Both use the same brain model (`qwen3:4b-instruct` via local Ollama, `num_ctx` 16384,
temperature 0.3, `num_predict` 256), the same `qa.answer()` streaming code with its
4-sentence cap and sanitizer, the same per-book index (`nomic-embed-text`, complete for all
six books), and the same 60 questions. They differ only in what the prompt contains:

| | yapbook (shipped path) | baseline (`tools/baseline_ask.py`) |
|---|---|---|
| entry point | `mcp_server.ask_book_text` after writing `positions.json` | `ask_baseline` |
| context | header naming the current chapter, the heard-so-far transcript of that chapter, a "just heard" quote of the last 3 segments; whole-book passages only if the question's wording triggers `ChapterContext.needs_retrieval()` (never fired here) | the 12 segments most cosine-similar to the question over the whole index, no spoiler gate, no chapter labels |
| system prompt | yapbook's, with the position and spoiler rules | yapbook's with rules 1 and 3 (position, spoiler) removed; grounding rule, "say so instead of guessing", length and plain-text rules kept verbatim |
| what it knows about position | chapter and playhead | nothing |

The only deviation from shipped yapbook code is a pass-through client wrapper that records
the prompt (the shipped code never exposes it). Exactly one model call per question. Both
runs completed 60/60 with no errors and no empty answers. `answers_yapbook.json` and
`answers_baseline.json` hold every answer with prompt size and SHA-256; the baseline records
also list the 12 retrieved `(chapter, seq, score)` hits. The prompts themselves are not
committed because they contain book text.

### Grading

Two independent LLM judge passes graded every (question, system) answer. Each judge saw the
question, the position, the gold, the `unheard_facts` (ahead/mixed) and both answers with the
system labels hidden; labels were restored only after all verdicts were fixed. Each verdict
is one label from `correct | partial | wrong | refused_appropriately | refused_wrongly`,
scored against the gold (so for ahead items "correct" means the position-honest answer), plus
a `spoiler` flag (true if the answer states something from `unheard_facts`) with the leaked
text quoted as `evidence`, and a written reason. `judgments.json` holds all 240 verdicts.
Judge agreement: 81.7% on the label (98/120 item-system pairs), 97.5% on the spoiler flag
(117/120). Every disagreement is listed by `tools/score.py --markdown`.

## Headline numbers

Each item has two judges, so n is 2 x questions. All numbers are recomputed from
`judgments.json` by `python tools/score.py --markdown`.

| metric | definition | yapbook | baseline |
|---|---|---|---|
| spoiler rate | verdicts with `spoiler=true` / verdicts, over ahead + mixed items (36 questions, n=72) | 15.3% (11/72) | 84.7% (61/72) |
| accuracy on behind | verdicts labelled `correct` / verdicts, over behind items (24 questions, n=48); `partial` shown separately | 85.4% correct, 14.6% partial, 0 wrong | 52.1% correct, 33.3% partial, 14.6% wrong |
| position honesty on ahead | verdicts labelled `refused_appropriately` / verdicts, over ahead items (24 questions, n=48) | 45.8% (22/48) | 0.0% (0/48) |
| refused wrongly | verdicts labelled `refused_wrongly` / verdicts, over behind + mixed items (n=72) | 5.6% (4/72) | 0.0% (0/72) |

### Per kind

| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |
|---|---|---|---|---|---|---|---|---|
| yapbook | behind | 48 | 41 | 7 | 0 | 0 | 0 | 0 |
| baseline | behind | 48 | 25 | 16 | 7 | 0 | 0 | 5 |
| yapbook | ahead | 48 | 3 | 8 | 15 | 22 | 0 | 10 |
| baseline | ahead | 48 | 1 | 10 | 37 | 0 | 0 | 45 |
| yapbook | mixed | 24 | 10 | 8 | 0 | 2 | 4 | 1 |
| baseline | mixed | 24 | 8 | 13 | 3 | 0 | 0 | 16 |

How to read the ahead rows: the baseline never once said "not yet"; it answered from the
whole book and was flagged as a spoiler in 45 of 48 verdicts. yapbook gave the position-honest
answer in 22 of 48 verdicts, but in the other 26 it did not: 10 verdicts are spoilers where
the 4B model supplied the upcoming explanation from its own knowledge of these well-known
papers (att-02, att-03, bn-06, rl-13, rl-15), and most of the remaining `wrong` verdicts are
confident answers that were simply incorrect and not in the book (att-06, bn-04, rl-05,
react-08). The "correct"/"partial" labels on ahead items are not clean: the two judges did
not always agree on whether a book-accurate but premature answer counts as correct (bn-06 is
the clearest case), which is why the spoiler rate and position honesty are the headline
metrics for ahead items and the label counts are shown for completeness.

The 4 `refused_wrongly` verdicts (att-08, vae-02, both judges) are the cross-chapter cases:
the heard facts sat in the abstract or introduction, yapbook's prompt contained only the
current chapter's transcript, and its whole-book retrieval was not triggered by the question
wording. The baseline, having no notion of position, retrieved them from the index. The same
gap explains yapbook's two `partial` verdicts on att-07 (the Table 1 complexities live two
chapters earlier).

### Per book

| book | questions (behind/ahead/mixed) | system | behind correct | ahead refused appropriately | spoilers on ahead+mixed | refused wrongly (behind+mixed) |
|---|---|---|---|---|---|---|
| attention | 4/5/3 | yapbook | 8/8 | 4/10 | 4/16 | 2/14 |
| attention | 4/5/3 | baseline | 7/8 | 0/10 | 16/16 | 0/14 |
| batchnorm | 5/3/2 | yapbook | 6/10 | 2/6 | 2/10 | 0/14 |
| batchnorm | 5/3/2 | baseline | 6/10 | 0/6 | 8/10 | 0/14 |
| react | 4/3/1 | yapbook | 8/8 | 2/6 | 0/8 | 0/10 |
| react | 4/3/1 | baseline | 6/8 | 0/6 | 6/8 | 0/10 |
| rl-book | 6/8/3 | yapbook | 12/12 | 6/16 | 5/22 | 0/18 |
| rl-book | 6/8/3 | baseline | 1/12 | 0/16 | 19/22 | 0/18 |
| string-junctions | 2/2/1 | yapbook | 1/4 | 2/4 | 0/6 | 0/6 |
| string-junctions | 2/2/1 | baseline | 1/4 | 0/4 | 4/6 | 0/6 |
| vae | 3/3/2 | yapbook | 6/6 | 6/6 | 0/10 | 2/10 |
| vae | 3/3/2 | baseline | 4/6 | 0/6 | 8/10 | 0/10 |

The RL book is where the baseline's flat retrieval hurts most on behind questions (1/12
correct): with 9015 sentence-sized segments, the 12 nearest hits to a question about the
current section can be the same concept as discussed in a later chapter. The judges'
evidence shows this directly in rl-07 (a chapter 6 TD-error question answered with
actor-critic and eligibility-trace material) and rl-17. On the short papers the two systems
are close on behind questions; the gap there is almost entirely spoilers.

## Five side-by-side examples

Answers are verbatim. The "0. 9"-style spacing inside numbers is an artifact of the shared
sentence splitter in `qa.answer()` (a streamed chunk ending in a decimal point is treated as
a sentence end) and affects both systems equally.

### 1. att-10 (ahead): baseline spoils, yapbook is position-honest

Position: Attention paper, chapter 20 ("5.4 Regularization"), 3 of 6 segments heard. The
text so far says only that three types of regularization are used.

> **Q:** What are the three kinds of regularization they use?
>
> **yapbook:** The transcript just said they employ three types of regularization during training, but it didn't specify what those three kinds are.
>
> **baseline:** The three kinds of regularization they use are label smoothing with ϵ ls = 0. 1, dropout with P drop = 0. 1, and positional embedding instead of sinusoids. These are explicitly mentioned in the section on regularization.

Judges: yapbook `refused_appropriately` x2. Baseline `wrong` x2, spoiler x2 (the label
smoothing and dropout values are from the unheard segments; "positional embedding instead of
sinusoids" is not a regularization technique in the paper).

### 2. rl-02 (ahead): baseline states the result before the book does

Position: RL book, chapter 27 ("2.3 The 10-armed Testbed"), 9 of 28 segments heard. The
testbed and the comparison have been set up; the outcome is in the next segments.

> **Q:** So which one wins in the long run, greedy or epsilon-greedy?
>
> **yapbook:** The transcript doesn't say which one wins in the long run. It only describes that Figure 2. 2 compares the methods and shows the increase in expected reward with experience. Without seeing the graph or knowing the results from it, we can't tell which method performs better over time.
>
> **baseline:** In the long run, epsilon-greedy wins because it continues to explore, which increases the chances of finding the optimal action, especially when rewards are uncertain or noisy. The greedy method might find the optimal action quickly but risks missing better alternatives due to lack of exploration. With noisier rewards, exploration is more critical, and epsilon-greedy performs better relative to the greedy method. The passage states that epsilon-greedy methods eventually perform better because they continue to explore and improve their chances of recognizing the optimal action.

Judges: yapbook `refused_appropriately` x2. Baseline `wrong` x2, spoiler x2 ("the passage
states" refers to text the listener has not reached).

### 3. bn-03 (behind): both systems had the answer available; only yapbook used it

Position: BatchNorm paper, chapter 3 ("2 Towards Reducing Internal Covariate Shift"), 13 of
23 segments heard; the argument is in segments 7 to 12.

> **Q:** Why can't you just normalize the activations outside the gradient step?
>
> **yapbook:** Because if you normalize outside the gradient step, the parameters like bias b get updated during training, but the normalization uses the old values of b, leading to a mismatch. This causes the output to stay unchanged, so the loss doesn't improve. As training continues, the bias grows without bound while the loss remains fixed. The problem gets worse if normalization also scales the activations.
>
> **baseline:** You can't normalize the activations outside the gradient step because doing so would require the normalization to be updated after each parameter update, which means the gradient step might be based on outdated or inconsistent statistics. This breaks the connection between the gradient descent update and the normalization, reducing the effectiveness of the gradient propagation. Additionally, the normalization must be based on the entire training data distribution to preserve the network's representation ability, which is not possible if it's applied outside the optimization loop.

Judges: yapbook `partial` x2 (right symptoms, garbled mechanism: the paper's point is that the
gradient step ignores the dependence of the mean on b, so the b update is cancelled by
re-normalization). Baseline `wrong` x2 (never states the argument). No spoilers either side.

### 4. att-06 (ahead): yapbook wrong without spoiling; baseline wrong and spoiling

Position: Attention paper, chapter 13 ("3.4 Embeddings and Softmax"), 3 of 5 segments heard;
positional encoding is the next section.

> **Q:** With no recurrence, how does the model know what order the words are in?
>
> **yapbook:** The model doesn't use recurrence to determine word order. Instead, it uses attention mechanisms to weigh the importance of different input tokens at each step, allowing it to focus on relevant parts of the sequence without relying on recurrence.
>
> **baseline:** With no recurrence, the model knows what order the words are in by injecting information about the relative or absolute position of the tokens in the sequence. This positional information allows each position in the decoder to attend over all positions in the input sequence. The model uses self-attention to capture the order of tokens without relying on recurrence.

Judges: yapbook `wrong` x2, no spoiler (attention alone is permutation-invariant; the answer
is incorrect and not position-honest). Baseline `wrong` x2, spoiler x2 (the "injecting
information about the relative or absolute position" sentence opens the unheard section).
This is the failure mode the position gate cannot fix: the 4B model answered from its own
belief instead of saying the transcript has not covered it.

### 5. att-08 (mixed): yapbook refused wrongly; the answer was in an earlier chapter

Position: Attention paper, chapter 17 ("5.1 Training Data and Batching"), 2 of 4 segments
heard. The abstract (chapter 2) and introduction (chapter 3) already gave 3.5 days on eight
GPUs and twelve hours on eight P100 GPUs; the step counts are in the unheard chapter 18.

> **Q:** How long did it take to train this thing?
>
> **yapbook:** The transcript doesn't mention how long it took to train the model.
>
> **baseline:** It took 3.5 days to train the big models. The training lasted 300,000 steps, with each step taking 1. 0 seconds. This total time was achieved using 8 NVIDIA P100 GPUs. The base models took 12 hours of training, or 100,000 steps.

Judges: yapbook `refused_wrongly` x2. Baseline `correct` x2 but spoiler x2 (the step counts and
per-step time are from the unheard training-schedule segments). yapbook's prompt held only
chapter 17's two heard segments; its whole-book retrieval, which would have found the
abstract, only joins the prompt when the question mentions another chapter or "earlier in the
book".

## Caveats

1. **LLM judges, not people.** Both judge passes are language models. Label agreement was
   81.7% and every disagreement is one step apart (`correct`/`partial` or `partial`/`wrong`)
   except bn-06, where for both systems the judges split `wrong` vs `correct` on whether a
   book-accurate but premature answer counts as correct. Spoiler-flag
   agreement was 97.5%. The judge prompts and model identities were run by the orchestrating
   session and are not recorded in this directory; the verdicts and rationales are.
2. **Same local 4B model for both systems, and it knows these papers.** `qwen3:4b-instruct`
   has almost certainly seen Attention, VAE, BatchNorm and ReAct in training. That is what
   makes yapbook's 10 ahead spoilers possible (the model filled in the upcoming explanation
   from memory) and it also means a bigger model could behave differently in either
   direction. Nothing here measures the model's quality, only what the two prompts let it do.
   *Addressed after this run:* the system prompt now forbids outside knowledge outright and
   asks the model to open every reply with a `COVERED` / `NOT_COVERED` line that the
   streaming layer strips (qa/answer.py; NOT_COVERED speaks a fixed "The book has not
   covered that yet." plus the model's partial). Re-run through the shipped path on the 24
   ahead and 24 behind questions (same model, temperature 0.3, three passes): the tag was
   well formed on 48/48 every time; ahead questions tagged NOT_COVERED 18/24 (the old prompt
   gave 9/24 position-honest answers), behind questions tagged COVERED 23/24 (att-12 is a
   false refusal). Of the 6 ahead items still tagged COVERED, bn-06 still states the
   running-average inference rule from memory; att-03, vae-04, react-01 and rl-09 answer from
   heard text and bn-04 says the book does not say. att-02, rl-13 and rl-15, spoilers in the
   recorded run, are now NOT_COVERED. The answers and verdicts above were not re-judged.
3. **yapbook's whole-book retrieval was never exercised.** `needs_retrieval` was false for all
   60 questions because none used cross-chapter wording, so yapbook's prompt was the current
   chapter's heard prefix only. This benchmark therefore compares yapbook's heard-chapter
   context against the baseline's index, not index against index. It cost yapbook 4
   `refused_wrongly` verdicts and 2 `partial` verdicts on the three fully cross-chapter items
   (att-07, att-08, vae-02). A follow-up with retrieval-triggering paraphrases of the same
   questions would isolate that.
   *Addressed after this run:* the phrase trigger was replaced by a similarity gate (every
   question is embedded; the block joins when the best gated cosine score reaches 0.60,
   `RETRIEVAL_MIN_SCORE` in `qa/context.py`; cross-chapter wording still forces it). With
   the same index, 53 of the 60 questions now carry the block, including all three
   cross-chapter items; the answers and verdicts above are from the phrase-trigger build and
   were not re-judged. Note that att-07's Table 1 segment ranks 17th among the gated rows for
   that question, past the top-4 cut, so the gate alone does not reach it.
4. **Questions were written by an LLM.** They were verified against the ingested text
   mechanically and the five papers plus three RL chapters were read in full, but for the
   other RL chapters the absence of unheard facts rests on the keyword grep, not on reading.
   The gold answers and `unheard_facts` are also LLM-written from those readings.
5. **Small n.** 60 questions, 6 books, 24/24/12 by kind, 5 to 17 per book. Per-book numbers
   in particular are a handful of items each. No confidence intervals are given because the
   two judges are not independent samples of the same distribution.
6. **Baseline was not tuned.** k=12 single segments with no neighbours and no chapter labels
   was a first choice, not a search; yapbook's context is the entire heard chapter (up to
   thousands of characters). A baseline with neighbour expansion or chapter labels might
   score better on behind questions; it could not score better on spoilers without adding a
   position, which is the thing under test.
7. **Non-deterministic.** Temperature 0.3 is yapbook's shipped default and was used on both
   sides; a re-run will produce different wording and some different verdicts. Wall-clock
   seconds in the answer files are informational only; the machine was shared with another
   benchmark and latency was not measured.
8. **Fresh ingests.** The five papers were re-ingested for this run; chapter and segment
   numbers refer to these copies only, and the six figure descriptions per paper are
   deferred placeholders.

## Files

| file | contents |
|---|---|
| `questions.json` | the 60 questions with gold answers and locations |
| `questions_verify.txt` | mechanical verification log for every question (gold segments quoted, unheard segments quoted, keyword absence) |
| `answers_yapbook.json` | yapbook's 60 answers with position, chapter title, heard segment count, retrieval flags, prompt size and SHA-256 |
| `answers_baseline.json` | the baseline's 60 answers with the 12 retrieved hits, prompt size and SHA-256 |
| `judgments.json` | 240 verdicts (60 questions x 2 systems x 2 judges) plus the aggregate |
| `tools/build_questions.py` | source of the questions and the verifier; regenerates `questions.json` and `questions_verify.txt` |
| `tools/yapbook_ask.py` | yapbook's shipped answer path at an explicit position (used for the probe and the equivalence check) |
| `tools/run_yapbook.py` | runs all questions through `mcp_server.ask_book_text` via `positions.json` |
| `tools/baseline_ask.py` | the no-position baseline |
| `tools/run_baseline.py` | runs all questions through the baseline |
| `tools/summarize_yapbook.py`, `tools/summarize_baseline.py` | run sanity checks and a keyword-based abstain heuristic (not a grade) |
| `tools/score.py` | recomputes every number above from `judgments.json` |
| `proof/` | run logs, baseline run metadata, and the RL book chapter map (index, segment count, title) |

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
python bench/grounding/tools/run_yapbook.py --dry-run

# 4. answer
python bench/grounding/tools/run_yapbook.py
python bench/grounding/tools/run_baseline.py
python bench/grounding/tools/summarize_yapbook.py
python bench/grounding/tools/summarize_baseline.py

# 5. judge (not automated here): produce judgments.json in the schema described in its "schema" field,
#    with the system labels hidden from the judge, then
python bench/grounding/tools/score.py --markdown
```

The runners refuse to start without `YAPBOOK_DATA_DIR`, write results after every question,
and are resumable. Pass `--temperature 0` to both `yapbook_ask.py` and `baseline_ask.py` for
repeatable answers.
