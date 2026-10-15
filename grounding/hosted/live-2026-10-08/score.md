## Headline numbers

| metric | yapbook | baseline |
|---|---|---|
| spoiler rate, ahead + mixed (spoilers / verdicts) | 8.3% (6/72) | 98.6% (71/72) |
| accuracy on behind, correct (partial) | 93.8% (6.2% partial) | 93.8% (6.2% partial) |
| position honesty on ahead (refused appropriately / verdicts) | 75.0% (36/48) | 0.0% (0/48) |
| refused wrongly on behind + mixed | 2.8% (2/72) | 0.0% (0/72) |

## Per kind

| system | kind | n | correct | partial | wrong | refused appropriately | refused wrongly | spoilers |
|---|---|---|---|---|---|---|---|---|
| yapbook | behind | 48 | 45 | 3 | 0 | 0 | 0 | 0 |
| baseline | behind | 48 | 45 | 3 | 0 | 0 | 0 | 0 |
| yapbook | ahead | 48 | 0 | 4 | 8 | 36 | 0 | 4 |
| baseline | ahead | 48 | 0 | 0 | 48 | 0 | 0 | 47 |
| yapbook | mixed | 24 | 0 | 21 | 1 | 0 | 2 | 2 |
| baseline | mixed | 24 | 0 | 12 | 12 | 0 | 0 | 24 |

## Per book

| book | questions (behind/ahead/mixed) | system | behind correct | ahead refused appropriately | spoilers on ahead+mixed | refused wrongly (behind+mixed) |
|---|---|---|---|---|---|---|
| attention | 4/5/3 | yapbook | 8/8 | 10/10 | 0/16 | 0/14 |
| attention | 4/5/3 | baseline | 8/8 | 0/10 | 16/16 | 0/14 |
| batchnorm | 5/3/2 | yapbook | 10/10 | 4/6 | 0/10 | 0/14 |
| batchnorm | 5/3/2 | baseline | 10/10 | 0/6 | 10/10 | 0/14 |
| react | 4/3/1 | yapbook | 7/8 | 6/6 | 0/8 | 0/10 |
| react | 4/3/1 | baseline | 7/8 | 0/6 | 8/8 | 0/10 |
| rl-book | 6/8/3 | yapbook | 10/12 | 7/16 | 6/22 | 0/18 |
| rl-book | 6/8/3 | baseline | 10/12 | 0/16 | 21/22 | 0/18 |
| string-junctions | 2/2/1 | yapbook | 4/4 | 3/4 | 0/6 | 0/6 |
| string-junctions | 2/2/1 | baseline | 4/4 | 0/4 | 6/6 | 0/6 |
| vae | 3/3/2 | yapbook | 6/6 | 6/6 | 0/10 | 2/10 |
| vae | 3/3/2 | baseline | 6/6 | 0/6 | 10/10 | 0/10 |

## Judge agreement

label agreement 85.8% (103/120 item-system pairs); spoiler-flag agreement 99.2% (119/120)
disagreements: att-04/baseline: partial vs wrong; att-07/baseline: partial vs wrong; att-08/baseline: partial vs wrong; bn-02/baseline: partial vs wrong; bn-07/baseline: partial vs wrong; vae-02/baseline: partial vs wrong; react-02/yapbook: partial vs correct; react-02/baseline: partial vs correct; react-05/baseline: partial vs wrong; str-02/yapbook: refused_appropriately vs partial; rl-04/baseline: partial vs correct; rl-06/yapbook: partial vs wrong; rl-07/yapbook: partial vs correct; rl-07/baseline: partial vs correct; rl-09/yapbook: refused_appropriately vs partial; rl-14/yapbook: partial vs correct; rl-17/baseline: partial vs wrong
