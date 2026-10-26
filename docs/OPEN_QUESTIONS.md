# Open questions Q32 to Q51

Triage of 2026-10-26. Each question is quoted in short from docs/SESSION_REPORT.md, where
the full text and its context are. "Frozen" means the answer changes something the tag
prereg-v1 freezes: PREREGISTRATION.md, or code that the test-day runs use. Recommended
answers are Claude's; Ilia decides each open one.

## Still open, for Ilia, ordered by what they affect

1. Q36, section 11 (frozen, a pre-committed sentence). Section 8 says a result is
   inconclusive when the bootstrap and t intervals disagree about 0, but section 11 has
   no row for that case when |mean| is below the MDE, and its "inconclusive" row says
   "the point estimate is large", which is then false. The code prints: "Inconclusive:
   the bootstrap and t intervals disagree on whether 0 is inside, and the point estimate
   is below the minimum detectable effect." Recommended: add that row to the section 11
   table before the tag, word for word as the code prints it, so the paper never states a
   sentence the plan did not commit to.
2. Q34, section 10 (frozen, pass rules). C1's pass ("the interval for C1 minus R1
   includes 0") and C4's match use the bootstrap interval only; section 10 does not say
   which interval. Recommended: keep the bootstrap interval and say so in section 10. It
   is the narrower one at 16 days (section 8), so it is the harder test for both: C1
   passes only if even the narrow interval includes 0, and C4 claims "the fitted decay is
   not what drives any gain" only if even the narrow interval includes B3. Requiring both
   intervals would make both canaries easier to pass.
3. Q35, section 8 (frozen, the selectivity flag). "Ratio of B3 to B2b traded notional on
   the median test day" can be read as the median of daily ratios (what the code does,
   eval/bootstrap.selectivity) or a ratio of medians. Recommended: the median over test
   days of each day's ratio, written into section 8 in those words. It keeps the day as
   the unit, as every other statistic does.
4. Q50, section 3 (frozen, the exchange model, as a stated limitation). In v1, 5 to 14% of
   fills had no opposite trade at their exchange time: hftbacktest fills a resting quote
   when the book moves through its price. Not look-ahead and not biased across days, but
   a real venue would treat some of these differently. Not measured for v2, whose quotes
   sit at the touch. Recommended: add one sentence to section 3 that fills include those
   where the book moves through the quote without a print, and measure the share on the
   v2 validation runs for the paper's limitation text. No change to the fill model, which
   is hftbacktest's (CLAUDE.md: no custom matching engine).
5. Q40, conversion code the test days use (frozen code). The Q13 converter fix keeps a
   larger later snapshot whole instead of cutting it as hftbacktest's one-shot output
   would. Every training and validation day was converted with it and its events hashes
   are in data/manifest.json. Recommended: confirm. Undoing it now would change every
   result so far.
6. Q38, section 6 markouts (frozen, secondary metric). The horizon is added to the fill's
   exchange time, but the mid is read on the local-time step grid, a feed latency (a few
   ms) behind. Already stated in eval/markouts.py. Recommended: state it in section 6 in
   one sentence and keep the code; at horizons of 1 s and more the offset is small, and
   moving the lookup to exchange time would change every markout reported so far.
7. Q37, paper only (not frozen). The paper prints the tag's creation time; the push time
   on GitHub is Ilia's first DEVIATIONS.md entry. Recommended: keep the creation time,
   which scripts/analyse.py reads from git, and leave the push time in DEVIATIONS.md,
   where a reader checks it against GitHub. It can be decided after the tag.

## Closed

Closed because they record a fact, were decided, or concern the v1 design that v2
replaced (Design history). None needs an answer before the tag.

| Q | Question, short | Why closed |
|---|---|---|
| Q32 | configs/selected.yaml format | In use: configs/selected.yaml holds the v2 settings Ilia approved on 2026-10-26. |
| Q33 | confirmatory grid as one config with per-strategy cells; B2b in the validation canary run | Built that way (engine/configs.v2_confirmatory, v2_canaries); the two planned test-day runs confirmed by Ilia (SPEC AC5.3, 2026-10-26). |
| Q39 | disk and memory options | Superseded: Ilia set the 3 GB floor and chose an external SSD for data/raw (docs/ssd_move.md). |
| Q41 | v1 selections at the edge of their grids | Decided and applied 2026-10-24; v1 only, and v2 B0 and B1 have no parameters. |
| Q42 | AC2.4 and ties | Decided by Ilia 2026-10-24: a tie passes (SPEC AC2.4). |
| Q43 | v1 grid-edge steps and late-starting windows | v1 only. |
| Q44 | C1 against B1 with centre noise at c above 0 | v1 only; v2 has no centre shift, and C1 is judged against R1 (section 10, 2026-10-26). |
| Q45 | v1 scoring window from 01:20 | v1 only. |
| Q46 | the 12 GB floor and swap | Superseded by Ilia's 3 GB floor. |
| Q47 | H1 zero by construction under the v1 choice | v1 only; under v2, B3 and B2b differ every day (s = 0.0329 bp, section 9). |
| Q48 | thin validation days for GLFT B1 | v1 only; v2 B1 joins the touch and fills about 39,000 times a validation day (docs/M4_v2_draft.md). |
| Q49 | v1 overlay choices decided by one 4-fill day | v1 only. |
| Q51 | C2 failed under v1 | Resolved by v2: C2 beats B1 by 2.102 bp against 3 x MDE 0.069 bp (AC4.2). |
