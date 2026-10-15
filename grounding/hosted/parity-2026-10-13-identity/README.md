# Parity run, 2026-10-13: the header lines as evidence

The 60 bench bodies (gate on, `hosted_bodies.mjs`) through the function on a local port
(`hosted_local_server.mjs`, default model), after the change that lets a question about the book
itself (author, title, position) quote the header lines as its evidence. Compared with
`live-2026-10-08-evidence/answers_yapbook.json`, the deployed function's run, by question id:

| kind | saved: covered / quoted / none | this run: covered / quoted / none |
|---|---|---|
| behind (24) | 22 / 22 / 2 | 23 / 23 / 1 |
| mixed (12) | 5 / 5 / 7 | 5 / 5 / 7 |
| ahead (24) | 1 / 1 / 23 | 1 / 1 / 23 |

Rejected evidence: 0 in both. Errors: 0 (two upstream 502s retried). The one ahead question
covered in both runs is rl-09, the known case (answered from heard text, passed by both judges).
The one tag that moved is rl-16 (behind): a wrong refusal in the saved run, answered with a
quotation here; it is not a question about the book itself, so this is the model's run-to-run
variance, not the change. Median 2.24 s on the local port with a second set of requests running
beside it; the deployed function's median stands at 1.17 s.

Not judged: the change touches only questions the bench does not contain. Files: the compact
answers and the meta, as the other runs; no book text.
