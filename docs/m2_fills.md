# Fills per queue model on the training days (AC2.4), run 633a29217f4b

Config configs/runs/train_chosen_window.yaml; commit 2e174b6; hftbacktest 2.4.4.
From metrics.parquet by scripts/m2_report.py. Fewest: the queue model(s) with the
smallest fill count. AC2.4 needs risk_averse to have no more fills than any other
queue model for B1 on every day and latency; a tie passes (Q42).

| Strategy | Day | Latency | risk_averse | power3 | power2 | log | Fewest | Risk-averse no more |
|---|---|---|---|---|---|---|---|---|
| B0 | 2024-01-01 | high | 20531 | 20557 | 20559 | 20567 | risk_averse | yes |
| B0 | 2024-01-01 | low | 21681 | 21709 | 21711 | 21729 | risk_averse | yes |
| B0 | 2024-02-01 | high | 32108 | 32122 | 32122 | 32124 | risk_averse | yes |
| B0 | 2024-02-01 | low | 34322 | 34340 | 34340 | 34340 | risk_averse | yes |
| B0 | 2024-03-01 | high | 46725 | 46733 | 46733 | 46739 | risk_averse | yes |
| B0 | 2024-03-01 | low | 51051 | 51063 | 51065 | 51069 | risk_averse | yes |
| B0 | 2024-04-01 | high | 46740 | 46748 | 46750 | 46748 | risk_averse | yes |
| B0 | 2024-04-01 | low | 52685 | 52695 | 52697 | 52701 | risk_averse | yes |
| B0 | 2024-05-01 | high | 101662 | 101668 | 101670 | 101686 | risk_averse | yes |
| B0 | 2024-05-01 | low | 120293 | 120307 | 120309 | 120313 | risk_averse | yes |
| B0 | 2024-06-01 | high | 5619 | 5621 | 5621 | 5625 | risk_averse | yes |
| B0 | 2024-06-01 | low | 6228 | 6228 | 6228 | 6232 | risk_averse = power3 = power2 | yes |
| B0 | 2024-07-01 | high | 31051 | 31057 | 31057 | 31069 | risk_averse | yes |
| B0 | 2024-07-01 | low | 33101 | 33107 | 33109 | 33121 | risk_averse | yes |
| B0 | 2024-08-01 | high | 61822 | 61828 | 61828 | 61830 | risk_averse | yes |
| B0 | 2024-08-01 | low | 67482 | 67500 | 67500 | 67508 | risk_averse | yes |
| B0 | 2024-09-01 | high | 39988 | 39992 | 39992 | 40004 | risk_averse | yes |
| B0 | 2024-09-01 | low | 43147 | 43159 | 43159 | 43179 | risk_averse | yes |
| B0 | 2024-10-01 | high | 60000 | 60006 | 60006 | 60012 | risk_averse | yes |
| B0 | 2024-10-01 | low | 65032 | 65054 | 65056 | 65054 | risk_averse | yes |
| B0 | 2024-11-01 | high | 52118 | 52124 | 52126 | 52132 | risk_averse | yes |
| B0 | 2024-11-01 | low | 56363 | 56369 | 56371 | 56381 | risk_averse | yes |
| B0 | 2024-12-01 | high | 20022 | 20024 | 20024 | 20026 | risk_averse | yes |
| B0 | 2024-12-01 | low | 21516 | 21520 | 21520 | 21522 | risk_averse | yes |
| B1 | 2024-01-01 | high | 252 | 252 | 252 | 252 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-01-01 | low | 246 | 246 | 246 | 246 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-02-01 | high | 300 | 302 | 302 | 302 | risk_averse | yes |
| B1 | 2024-02-01 | low | 278 | 280 | 280 | 280 | risk_averse | yes |
| B1 | 2024-03-01 | high | 132 | 132 | 132 | 132 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-03-01 | low | 130 | 130 | 130 | 130 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-04-01 | high | 88 | 88 | 88 | 88 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-04-01 | low | 86 | 86 | 86 | 86 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-05-01 | high | 210 | 210 | 210 | 210 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-05-01 | low | 194 | 194 | 194 | 194 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-06-01 | high | 124 | 124 | 124 | 126 | risk_averse = power3 = power2 | yes |
| B1 | 2024-06-01 | low | 122 | 124 | 124 | 126 | risk_averse | yes |
| B1 | 2024-07-01 | high | 88 | 88 | 88 | 88 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-07-01 | low | 80 | 80 | 80 | 80 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-08-01 | high | 104 | 104 | 104 | 104 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-08-01 | low | 96 | 96 | 96 | 96 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-09-01 | high | 134 | 134 | 134 | 134 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-09-01 | low | 128 | 128 | 128 | 128 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-10-01 | high | 180 | 180 | 180 | 182 | risk_averse = power3 = power2 | yes |
| B1 | 2024-10-01 | low | 174 | 174 | 174 | 176 | risk_averse = power3 = power2 | yes |
| B1 | 2024-11-01 | high | 102 | 102 | 102 | 102 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-11-01 | low | 94 | 94 | 94 | 94 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-12-01 | high | 32 | 32 | 32 | 32 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-12-01 | low | 30 | 30 | 30 | 30 | risk_averse = power3 = power2 = log | yes |

B0: risk-averse has no more fills than any other queue model in 24 of 24 day and latency rows, and is alone with the fewest in 23.
B1: risk-averse has no more fills than any other queue model in 24 of 24 day and latency rows, and is alone with the fewest in 3.
AC2.4 holds for B1.
