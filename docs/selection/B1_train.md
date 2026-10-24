# B1 selection on the training days (M2)

Run ccbf1a18e770 (configs/runs/train_select_window.yaml, commit a0e0241); primary cell risk_averse /
high; 12 days. Rule (PREREGISTRATION.md section 4): highest mean daily
break-even fee scored from 01:20:00 to the end of quoting, among candidates
with a median training day of at least 100 fills in that window. The
grid-edge rule and the scoring window were added on 2026-10-24, after the first
selection had been seen. Full-day columns are for reference.

| Candidate | Window mean BEF bp | Window median fills | Eligible | Full-day mean BEF bp | Full-day median fills |
|---|---|---|---|---|---|
| {"gamma": 0.8, "update_every": 50, "window_s": 4800} | 0.4104 | 32 | no | 0.4104 | 32 |
| {"gamma": 0.4, "update_every": 50, "window_s": 600} | -0.5494 | 126 | yes | -0.5653 | 128 |
| {"gamma": 0.4, "update_every": 50, "window_s": 4800} | -0.5506 | 122 | yes | -0.5506 | 122 |
| {"gamma": 0.4, "update_every": 50, "window_s": 1200} | -0.5708 | 107 | yes | -0.5849 | 109 |
| {"gamma": 0.4, "update_every": 50, "window_s": 2400} | -0.5868 | 118 | yes | -0.5883 | 118 |
| {"gamma": 0.4, "update_every": 50, "window_s": 300} | -0.6665 | 144 | yes | -0.6630 | 146 |
| {"gamma": 0.2, "update_every": 50, "window_s": 2400} | -0.6708 | 605 | yes | -0.6847 | 608 |
| {"gamma": 0.2, "update_every": 50, "window_s": 1200} | -0.6760 | 585 | yes | -0.6867 | 589 |
| {"gamma": 0.2, "update_every": 50, "window_s": 4800} | -0.6806 | 637 | yes | -0.6806 | 637 |
| {"gamma": 0.2, "update_every": 50, "window_s": 600} | -0.6834 | 597 | yes | -0.6936 | 602 |
| {"gamma": 0.2, "update_every": 50, "window_s": 300} | -0.6987 | 622 | yes | -0.7050 | 629 |
| {"gamma": 0.1, "update_every": 50, "window_s": 1200} | -0.7669 | 2223 | yes | -0.7724 | 2263 |
| {"gamma": 0.1, "update_every": 50, "window_s": 4800} | -0.7740 | 2353 | yes | -0.7740 | 2353 |
| {"gamma": 0.1, "update_every": 50, "window_s": 2400} | -0.7746 | 2247 | yes | -0.7805 | 2280 |
| {"gamma": 0.1, "update_every": 50, "window_s": 600} | -0.7878 | 2222 | yes | -0.7911 | 2263 |
| {"gamma": 0.1, "update_every": 50, "window_s": 300} | -0.7940 | 2301 | yes | -0.7975 | 2347 |
| {"gamma": 0.05, "update_every": 50, "window_s": 600} | -0.8099 | 5133 | yes | -0.8121 | 5257 |
| {"gamma": 0.05, "update_every": 50, "window_s": 1200} | -0.8150 | 5014 | yes | -0.8181 | 5127 |
| {"gamma": 0.05, "update_every": 50, "window_s": 4800} | -0.8169 | 4895 | yes | -0.8169 | 4895 |
| {"gamma": 0.05, "update_every": 50, "window_s": 300} | -0.8173 | 5267 | yes | -0.8176 | 5400 |
| {"gamma": 0.05, "update_every": 50, "window_s": 2400} | -0.8174 | 4903 | yes | -0.8190 | 4990 |
| {"gamma": 0.025, "update_every": 50, "window_s": 4800} | -0.8521 | 7826 | yes | -0.8521 | 7826 |
| {"gamma": 0.025, "update_every": 50, "window_s": 1200} | -0.8615 | 7808 | yes | -0.8633 | 8034 |
| {"gamma": 0.025, "update_every": 50, "window_s": 2400} | -0.8625 | 7754 | yes | -0.8640 | 7902 |
| {"gamma": 0.025, "update_every": 50, "window_s": 600} | -0.8637 | 7862 | yes | -0.8660 | 8092 |
| {"gamma": 0.025, "update_every": 50, "window_s": 300} | -0.8649 | 7940 | yes | -0.8663 | 8122 |
| {"gamma": 0.8, "update_every": 50, "window_s": 1200} | none | 28 | no | none | 28 |
| {"gamma": 0.8, "update_every": 50, "window_s": 2400} | none | 34 | no | none | 34 |
| {"gamma": 0.8, "update_every": 50, "window_s": 300} | none | 28 | no | none | 28 |
| {"gamma": 0.8, "update_every": 50, "window_s": 600} | none | 24 | no | none | 24 |

Chosen: {"gamma": 0.4, "update_every": 50, "window_s": 600}
Without the fill floor (and leaving out candidates with a day without fills) the rule would choose: {"gamma": 0.8, "update_every": 50, "window_s": 4800} (the floor decided the choice)
At the edge of its grid: no
