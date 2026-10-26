# Leakage audit of the run-length run (2026-10-26)

Target: results/7ac2bbe74a19 (configs/runs/v2_run_length_val.yaml, commit be76d43), 6
validation days, primary cell. Auditor: the leakage-auditor agent, read-only.

## Verdict

No leak, no layering breach, no data or provenance error. Every comparison in the
"Run-length controls" section of docs/M4_v2_draft.md was reproduced exactly. B3 - RL_B3
is positive on 6 of 6 days but is not a clean measure of what the Hawkes signal knows
(finding 1). B2b - RL_B2b is inconclusive.

Checked and cleared: RL reads no market data (engine.run.run_length_pulls takes only the
day, the window, the step, the rate, the number of runs and the seed); its expected share
and number of runs equal the targets, and realised values are 0.97 to 1.02 times them;
K and theta_u act as for the strategies (magnitude rule off, theta_u 0.5 on u of +1 or
-1); seeds are deterministic and differ; the config's rates and runs equal B3's and B2b's
in c274b2def28e, committed before the config; B1, B3 and B2b equal c274b2def28e in every
metric but wall time; all 54 rows are validation days.

## Findings, ranked by how much they could change a reading

The figures below come from the auditor's offline reconstruction of the strategies'
toxic series from data/events, with scripts in the session scratchpad that are not
committed. They are audit evidence, not results: no number from this file goes into the
paper. Steps and per-run order state are not saved by the engine, so they could not be
checked against the engine directly.

1. Medium. RL pays more per pulled run than B3. About 41% of B3's pulled runs start
   within 0.2 s of our own fill on that side (49% within 1 s), when no order rests there
   and the pull gives up no queue place; for RL_B3 it is about 4% (12%). The engine's
   cancel counts agree in direction: over B1, RL_B3 cancels about 857 more times an hour
   and B3 about 471. A rough linear estimate from the random controls puts 0.004 to
   0.010 bp of the 0.0230 bp B3 - RL_B3 on this cost difference. So B3 - RL_B3 does not
   separate "the Hawkes direction predicts toxic flow" from a simple rule such as "do not
   rejoin the side just hit for a step or two". For B2b the share is 23% against 4%, but
   B2b also cancels about 102 more times an hour than RL_B2b, so the bias runs both ways.
2. Low to medium. B3's and B2b's pulls gather in busy steps and hours; RL's do not
   (about 4.3 to 4.8 market orders per step while B3 is pulled against 0.5 to 0.9
   otherwise; equal for RL). Direction unclear; C1 against R1, which also differ in
   timing with a random side, is about 0, which suggests the timing effect is small.
3. Low, mainly B2b. Run lengths and sides differ in shape: B2b has more one-step runs and
   much longer long runs than RL_B2b, and its next run pulls the same side 0.86 to 0.89
   of the time against 0.50. Direction unknown; if same-side persistence costs through
   inventory, RL flatters itself and B2b - RL_B2b is biased against B2b.
4. Informational. The seed spread of RL_B2b is about the size of B2b - RL_B2b, so more
   seeds would tighten it; B2b is inconclusive either way.

## What was done with it

- The limitation printed under the run-length table (scripts/m4_v2.py runlength) and the
  paper's limitation sentence now state findings 1 and 2 in words and point here. The
  draft no longer says the timing was not measured.
- Not done: a control that withholds the filled side for a while after each own fill
  (finding 1), or one that copies the strategies' run-length distribution and side
  persistence (finding 3). Both would be further exploratory controls; the comparisons
  they would refine have no pass rule. Listed in docs/TAG_CHECKLIST.md for Ilia.
