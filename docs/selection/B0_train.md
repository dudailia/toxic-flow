# B0 selection on the training days (M2)

Run ccbf1a18e770 (configs/runs/train_select_window.yaml, commit a0e0241); primary cell risk_averse /
high; 12 days. Rule (PREREGISTRATION.md section 4): highest mean daily
break-even fee scored from 01:20:00 to the end of quoting, among candidates
with a median training day of at least 100 fills in that window. The
grid-edge rule and the scoring window were added on 2026-10-24, after the first
selection had been seen. Full-day columns are for reference.

| Candidate | Window mean BEF bp | Window median fills | Eligible | Full-day mean BEF bp | Full-day median fills |
|---|---|---|---|---|---|
| {"h": 13} | -0.9243 | 42419 | yes | -0.9273 | 43356 |
| {"h": 8} | -0.9599 | 46126 | yes | -0.9636 | 46840 |
| {"h": 5} | -0.9889 | 48029 | yes | -0.9930 | 48788 |
| {"h": 3} | -1.0054 | 49317 | yes | -1.0097 | 50102 |
| {"h": 2} | -1.0137 | 49980 | yes | -1.0185 | 50784 |
| {"h": 1} | -1.0227 | 50886 | yes | -1.0273 | 51704 |

Chosen: {"h": 13}
Without the fill floor (and leaving out candidates with a day without fills) the rule would choose: {"h": 13} (the same)
At the edge of its grid: h (high end of [1, 2, 3, 5, 8, 13])
