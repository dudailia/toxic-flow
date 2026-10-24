# B1 selection on the training days (M2)

Run c5012b395d5a (commit cd0245f), primary cell risk_averse / high,
12 days. Rule: highest mean daily break-even fee (PREREGISTRATION.md section 4).

| Candidate | Mean daily BEF bp |
|---|---|
| {"gamma": 0.2, "update_every": 50, "window_s": 1200} | -0.6867 |
| {"gamma": 0.2, "update_every": 50, "window_s": 600} | -0.6936 |
| {"gamma": 0.2, "update_every": 50, "window_s": 300} | -0.7050 |
| {"gamma": 0.1, "update_every": 50, "window_s": 1200} | -0.7724 |
| {"gamma": 0.1, "update_every": 50, "window_s": 600} | -0.7911 |
| {"gamma": 0.1, "update_every": 50, "window_s": 300} | -0.7975 |
| {"gamma": 0.05, "update_every": 50, "window_s": 600} | -0.8121 |
| {"gamma": 0.05, "update_every": 50, "window_s": 300} | -0.8176 |
| {"gamma": 0.05, "update_every": 50, "window_s": 1200} | -0.8181 |
| {"gamma": 0.025, "update_every": 50, "window_s": 1200} | -0.8633 |
| {"gamma": 0.025, "update_every": 50, "window_s": 600} | -0.8660 |
| {"gamma": 0.025, "update_every": 50, "window_s": 300} | -0.8663 |

Chosen: {"gamma": 0.2, "update_every": 50, "window_s": 1200}
