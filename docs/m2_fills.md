# Fills per queue model on the training days (AC2.4), run c7921fce3271

Config configs/runs/train_chosen.yaml; commit ae291c6; hftbacktest 2.4.4.
From metrics.parquet by scripts/m2_report.py. Fewest: the queue model(s) with the
smallest fill count. AC2.4 needs risk_averse to have no more fills than any other
queue model for B1 on every day and latency; a tie passes (Q42).

| Strategy | Day | Latency | risk_averse | power3 | power2 | log | Fewest | Risk-averse no more |
|---|---|---|---|---|---|---|---|---|
| B0 | 2024-01-01 | high | 26811 | 26823 | 26821 | 26825 | risk_averse | yes |
| B0 | 2024-01-01 | low | 28887 | 28895 | 28893 | 28901 | risk_averse | yes |
| B0 | 2024-02-01 | high | 40966 | 40972 | 40972 | 40982 | risk_averse | yes |
| B0 | 2024-02-01 | low | 44520 | 44526 | 44526 | 44534 | risk_averse | yes |
| B0 | 2024-03-01 | high | 52481 | 52491 | 52491 | 52487 | risk_averse | yes |
| B0 | 2024-03-01 | low | 58529 | 58537 | 58537 | 58535 | risk_averse | yes |
| B0 | 2024-04-01 | high | 51614 | 51618 | 51620 | 51626 | risk_averse | yes |
| B0 | 2024-04-01 | low | 59367 | 59373 | 59375 | 59373 | risk_averse | yes |
| B0 | 2024-05-01 | high | 107589 | 107597 | 107595 | 107595 | risk_averse | yes |
| B0 | 2024-05-01 | low | 129961 | 129971 | 129967 | 129977 | risk_averse | yes |
| B0 | 2024-06-01 | high | 6872 | 6874 | 6874 | 6874 | risk_averse | yes |
| B0 | 2024-06-01 | low | 7750 | 7754 | 7754 | 7754 | risk_averse | yes |
| B0 | 2024-07-01 | high | 34845 | 34849 | 34851 | 34849 | risk_averse | yes |
| B0 | 2024-07-01 | low | 37327 | 37333 | 37335 | 37335 | risk_averse | yes |
| B0 | 2024-08-01 | high | 68466 | 68470 | 68472 | 68478 | risk_averse | yes |
| B0 | 2024-08-01 | low | 75754 | 75758 | 75758 | 75762 | risk_averse | yes |
| B0 | 2024-09-01 | high | 45961 | 45961 | 45961 | 45965 | risk_averse = power3 = power2 | yes |
| B0 | 2024-09-01 | low | 49984 | 49986 | 49986 | 49986 | risk_averse | yes |
| B0 | 2024-10-01 | high | 66796 | 66798 | 66798 | 66802 | risk_averse | yes |
| B0 | 2024-10-01 | low | 73336 | 73344 | 73344 | 73350 | risk_averse | yes |
| B0 | 2024-11-01 | high | 57759 | 57759 | 57759 | 57761 | risk_averse = power3 = power2 | yes |
| B0 | 2024-11-01 | low | 63058 | 63060 | 63062 | 63066 | risk_averse | yes |
| B0 | 2024-12-01 | high | 21572 | 21574 | 21574 | 21574 | risk_averse | yes |
| B0 | 2024-12-01 | low | 23508 | 23510 | 23510 | 23512 | risk_averse | yes |
| B1 | 2024-01-01 | high | 1046 | 1048 | 1048 | 1050 | risk_averse | yes |
| B1 | 2024-01-01 | low | 1010 | 1010 | 1010 | 1014 | risk_averse = power3 = power2 | yes |
| B1 | 2024-02-01 | high | 1520 | 1526 | 1524 | 1528 | risk_averse | yes |
| B1 | 2024-02-01 | low | 1462 | 1468 | 1468 | 1472 | risk_averse | yes |
| B1 | 2024-03-01 | high | 988 | 988 | 988 | 990 | risk_averse = power3 = power2 | yes |
| B1 | 2024-03-01 | low | 958 | 958 | 958 | 958 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-04-01 | high | 566 | 568 | 568 | 568 | risk_averse | yes |
| B1 | 2024-04-01 | low | 556 | 556 | 556 | 556 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-05-01 | high | 1192 | 1192 | 1192 | 1192 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-05-01 | low | 1126 | 1126 | 1126 | 1126 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-06-01 | high | 312 | 316 | 316 | 320 | risk_averse | yes |
| B1 | 2024-06-01 | low | 300 | 310 | 310 | 316 | risk_averse | yes |
| B1 | 2024-07-01 | high | 352 | 352 | 352 | 352 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-07-01 | low | 342 | 342 | 342 | 342 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-08-01 | high | 482 | 482 | 482 | 482 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-08-01 | low | 468 | 468 | 468 | 468 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-09-01 | high | 612 | 612 | 612 | 612 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-09-01 | low | 586 | 586 | 586 | 586 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-10-01 | high | 782 | 782 | 782 | 786 | risk_averse = power3 = power2 | yes |
| B1 | 2024-10-01 | low | 728 | 728 | 728 | 734 | risk_averse = power3 = power2 | yes |
| B1 | 2024-11-01 | high | 358 | 358 | 358 | 358 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-11-01 | low | 330 | 330 | 330 | 330 | risk_averse = power3 = power2 = log | yes |
| B1 | 2024-12-01 | high | 208 | 208 | 208 | 210 | risk_averse = power3 = power2 | yes |
| B1 | 2024-12-01 | low | 210 | 210 | 210 | 210 | risk_averse = power3 = power2 = log | yes |

B0: risk-averse has no more fills than any other queue model in 24 of 24 day and latency rows, and is alone with the fewest in 22.
B1: risk-averse has no more fills than any other queue model in 24 of 24 day and latency rows, and is alone with the fewest in 6.
AC2.4 holds for B1.
