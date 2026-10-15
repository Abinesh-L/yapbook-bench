# yapbook

An audiobook you can talk to. Try it in your browser: **https://yapbook.app** (no install, no account, no key; a current Chrome, Edge or Safari on a laptop or desktop).

Drop in an EPUB or a PDF, or press the sample, and it reads aloud. Ask out loud mid-listen ("wait, what did it just say?", "why does that term drop out?") and it answers from what you have heard so far, grounded at the sentence you stopped on, then keeps reading. It does not run ahead of you. It can also read in your own voice: three sentences recorded once, and the recording never leaves your device.

**Local by design.** Your books, the narration, the speech-to-text and your voice stay on your device. Only the question you ask reaches a hosted model, together with the part of the book you have heard, and nothing is stored. Keep documents with card numbers, passwords or other private details out of it.

## What this repository is

The code of yapbook is not published. This repository holds the **write-up and the grounding benchmark records**: the 60 questions, both systems' answers, the two judges' verdicts and the scripts that graded and scored them, so the claim below can be checked rather than believed.

## The claim, and how it was measured

Every "chat with your PDF" tool sees the whole document, so it happily explains chapter 9 while you are in chapter 3. yapbook's answer path sees only what you have heard. Measured on the browser version itself: 60 questions at fixed listening positions across 6 books (a textbook and five papers), the same hosted model with and without the position gate, graded blind by two other models, both named in the records.

| metric (two judges, so n = 2 x questions) | gate on (the live site) | gate off (same model, whole book) |
|---|---|---|
| spoiler-free answers to questions whose answer lies ahead of the listener | 100% (72 of 72) | 22.2% (16 of 72) |
| "the book has not covered that yet", when that was the honest answer | 100% (48 of 48) | 8.3% (4 of 48) |
| heard material: correct, partial, wrong | 65%, 31%, 0 | 75%, 15%, 0 |
| refused a question whose answer had already been heard | 6.9% (5 of 72) | 6.9% (5 of 72) |

Measured against the live site on 2026-10-08. The gate costs something: with it the model answers heard material more tersely, and in 5 of 72 verdicts it refused a question whose answer it had heard. Caveats: one run per cell; the judges are language models (two, named, the prompt in `grounding/tools/judge.py`, 98 to 99% agreement between them on the spoiler flag); n is 60; the questions were typed, not spoken; one of the six books is a textbook the models know by heart, which is exactly where the gate-off arm spoils.

The full account, with the first run of that night (66 of 72 and 36 of 48), what changed and why, the model comparison and every verdict: [`grounding/hosted/README.md`](grounding/hosted/README.md). The installed version's local model was measured on the same questions in September: [`grounding/README.md`](grounding/README.md), runs 1 to 3.

If you build a reader and want to run the same 60 questions through it: `grounding/questions.json` holds the questions, the listening positions, the gold answers and the facts a spoiler would reveal; `grounding/tools/judge.py` is the rubric. Tell me what it shows and I will publish it.

## Layout

```
grounding/
  README.md                runs 1 to 3: the installed version's local model, position-grounded against a no-position baseline
  questions.json           the 60 questions (id, book, kind, position, gold, unheard facts), unchanged since run 1
  questions_verify.txt     the check that every gold passage is heard at its position and no spoiler keyword is
  answers_*.json           run 3's answers; judgments.json its verdicts; proof/ its logs and metadata
  run1/, run2/             the earlier runs, kept unchanged, each with the README of its time
  hosted/                  the browser version's hosted brain: the live run, the fix and the model pick, the live re-run, a parity run
  tools/judge.py           the judge: two named models, blind, one answer per call; the prompt is in the file
  tools/score.py           the scoring, from judgments.json to the tables
```

The scripts that drove the two systems import yapbook's own code and are not here; the READMEs name them where they were used.

## License

The two scripts under `grounding/tools/` are under the Apache License 2.0, in [LICENSE](LICENSE). The records are under the Creative Commons Attribution 4.0 license ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)): the questions with their gold answers and unheard facts, both systems' answers, the verdicts, the logs and the READMEs. Reuse them with a credit to yapbook and a link to this repository. The six books the questions are about are not in this repository (five arXiv papers and Sutton and Barto, Reinforcement Learning, second edition), each under its own terms; the records carry no passages from them, only what an answer paraphrased or quoted in passing.

## The installed version

There is also a version that installs on a computer and runs fully local: narration, transcription, the question-answering brain, figure descriptions and whole-book memory all on your own machine. It adds the earbud tap, formulas read like a tutor, figures described, a question book and a quiz after each chapter. Windows first, macOS next. It is not published yet; if you would like it on your computer, say so in the feedback box.

## Feedback

Yap all you want: https://yapbook.app/app/feedback. Any honest review is welcome, criticism, suggestions and bugs included.

yapbook is a hobby project by [Abinesh](https://www.linkedin.com/in/abinesh-l/), built for listening to dense textbooks while his hands are busy. The models and voices the browser version runs on are open ones, credited at https://yapbook.app/app/voice/NOTICE.md.
