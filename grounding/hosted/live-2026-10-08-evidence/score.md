## Headline numbers

| metric | yapbook | baseline |
|---|---|---|
| spoiler rate, ahead + mixed (spoilers / verdicts) | 0.0% (0/72) | 77.8% (56/72) |
| accuracy on behind, correct (partial) | 64.6% (31.2% partial) | 75.0% (14.6% partial) |
| position honesty on ahead (refused appropriately / verdicts) | 100.0% (48/48) | 8.3% (4/48) |
| refused wrongly on behind + mixed | 6.9% (5/72) | 6.9% (5/72) |

## Per kind

| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |
|---|---|---|---|---|---|---|---|---|
| yapbook | behind | 48 | 31 | 15 | 0 | 0 | 2 | 0 |
| baseline | behind | 48 | 36 | 7 | 0 | 0 | 5 | 0 |
| yapbook | ahead | 48 | 0 | 0 | 0 | 48 | 0 | 0 |
| baseline | ahead | 48 | 0 | 3 | 41 | 4 | 0 | 41 |
| yapbook | mixed | 24 | 1 | 20 | 0 | 0 | 3 | 0 |
| baseline | mixed | 24 | 0 | 13 | 11 | 0 | 0 | 15 |

## Per book

| book | questions (behind/ahead/mixed) | system | behind correct | ahead refused appropriately | spoilers on ahead+mixed | refused wrongly (behind+mixed) |
|---|---|---|---|---|---|---|
| attention | 4/5/3 | yapbook | 7/8 | 10/10 | 0/16 | 2/14 |
| attention | 4/5/3 | baseline | 7/8 | 0/10 | 14/16 | 0/14 |
| batchnorm | 5/3/2 | yapbook | 7/10 | 6/6 | 0/10 | 0/14 |
| batchnorm | 5/3/2 | baseline | 7/10 | 0/6 | 6/10 | 0/14 |
| react | 4/3/1 | yapbook | 6/8 | 6/6 | 0/8 | 0/10 |
| react | 4/3/1 | baseline | 8/8 | 2/6 | 6/8 | 0/10 |
| rl-book | 6/8/3 | yapbook | 6/12 | 16/16 | 0/22 | 0/18 |
| rl-book | 6/8/3 | baseline | 5/12 | 2/16 | 19/22 | 5/18 |
| string-junctions | 2/2/1 | yapbook | 1/4 | 4/4 | 0/6 | 0/6 |
| string-junctions | 2/2/1 | baseline | 3/4 | 0/4 | 2/6 | 0/6 |
| vae | 3/3/2 | yapbook | 4/6 | 6/6 | 0/10 | 3/10 |
| vae | 3/3/2 | baseline | 6/6 | 0/6 | 9/10 | 0/10 |

## Judge agreement

label agreement 78.3% (94/120 item-system pairs); spoiler-flag agreement 98.3% (118/120)
disagreements: att-05/yapbook: partial vs correct; att-07/baseline: partial vs wrong; att-09/baseline: partial vs correct; bn-01/yapbook: partial vs correct; bn-01/baseline: partial vs correct; bn-05/yapbook: partial vs correct; bn-05/baseline: partial vs correct; bn-10/yapbook: partial vs correct; bn-10/baseline: partial vs correct; vae-02/yapbook: partial vs refused_wrongly; react-02/yapbook: partial vs correct; react-06/yapbook: partial vs correct; react-08/baseline: partial vs wrong; str-01/yapbook: partial vs correct; str-03/baseline: partial vs correct; rl-01/yapbook: partial vs correct; rl-04/yapbook: partial vs correct; rl-04/baseline: refused_wrongly vs partial; rl-06/yapbook: partial vs correct; rl-07/yapbook: partial vs correct; rl-07/baseline: partial vs correct; rl-10/yapbook: partial vs correct; rl-12/baseline: partial vs wrong; rl-14/yapbook: partial vs correct; rl-16/yapbook: correct vs partial; rl-17/baseline: partial vs wrong
