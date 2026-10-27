# Open questions Q32 to Q51

Triage of 2026-10-26. Each question is quoted in short from docs/SESSION_REPORT.md, where
the full text and its context are. "Frozen" means the answer changes something the tag
prereg-v1 freezes: PREREGISTRATION.md, or code that the test-day runs use. Recommended
answers are Claude's; Ilia decides each open one. Updated the same day with Ilia's
decisions on Q34, Q35, Q36 and Q50, and with Q37 and Q40 applied as recommended because
they change no frozen text.

## Still open, for Ilia

None.

## Closed

Closed because Ilia decided them, they were applied as recommended, they record a fact,
or they concern the v1 design that v2 replaced (Design history). None needs an answer
before the tag.

| Q | Question, short | Why closed |
|---|---|---|
| Q34 | which interval the section 10 pass rules use | Decided by Ilia 2026-10-26: the 95% percentile bootstrap, 10,000 resamples, seed 1729; written into section 10. The code already did this. |
| Q35 | selectivity: median of daily ratios or ratio of medians | Decided by Ilia 2026-10-26: the median over test days of the daily ratio of B3 to B2b traded notional; written into section 8. The code already did this (eval/bootstrap.selectivity). |
| Q36 | section 11 had no row for intervals that disagree about 0 | Decided by Ilia 2026-10-26: the row "The bootstrap and t intervals disagree on whether 0 is inside", statement "Inconclusive: the two intervals disagree on whether 0 is inside." Written into section 11; eval/bootstrap.conclusion prints it whatever the size of the mean, and a test checks that every statement is a section 11 row word for word. |
| Q37 | the paper prints the tag's creation time, not its push time | Applied as recommended (no frozen text): scripts/analyse.py keeps reading the creation time from git, and the push time stays Ilia's first DEVIATIONS.md entry. |
| Q38 | the markout clock: horizon on exchange time, mid on the local-time step grid | Decided by Ilia 2026-10-26: the sentence added to section 6, code kept as is (eval/markouts.py); Design history entry. |
| Q40 | the Q13 converter fix keeps a larger later snapshot whole | Applied as recommended (no frozen text): confirmed as is. Every training and validation day was converted with it, and its events hashes are in data/manifest.json; undoing it would change every result so far. |
| Q50 | fills where the book moves through the quote with no print | Decided by Ilia 2026-10-26: section 3 states it, and each day's share is reported. Measured per cell as no_print_fill_share (eval/metrics.no_print_share: no opposite print at or through our price at the fill's exchange time, prices compared in ticks); the test-day summary has the share for every strategy and day in the primary cell, and the paper a table for B0 to B3. No change to the fill model, which is hftbacktest's. |
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
