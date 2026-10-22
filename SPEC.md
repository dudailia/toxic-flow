# SPEC: toxic-flow

Owner and author: Ilia Duda. Builder: Claude Code. Design review: Claude chat.

A milestone is done when all of these hold:
1. `uv run python scripts/check_milestone.py M<n>` exits 0.
2. /code-review and the leakage-auditor agent report nothing that changes a conclusion.
3. Ilia passes `/viva M<n>`.

Checks for M1 to M6 are written into scripts/check_milestone.py at the start of each
milestone, from the criteria below, and Ilia approves them before implementation starts.
The file is protected, so the test is fixed before the code that has to pass it.

## Calendar (targets, revised only by Ilia)

| M  | Name                                   | Target  | Status |
|----|----------------------------------------|---------|--------|
| M0 | Recon, guards, one-day benchmark       | Oct 26  | open   |
| M1 | Data pipeline for train and val        | Oct 31  | open   |
| M2 | Harness, B0 and B1 on train days       | Nov 7   | open   |
| M3 | Signals, Hawkes fit, canaries          | Nov 15  | open   |
| M4 | Tuning, MDE, pre-registration freeze   | Nov 22  | open   |
| M5 | Test run, once                         | Nov 30  | open   |
| M6 | Paper, PDF, repo polish                | Dec 11  | open   |

M4 is the interview milestone. From then on the honest claim is: hypotheses, selected
configs, canaries and the minimum detectable effect were committed and pushed before any
test-day data existed on disk. Everything before M4 is also a fair talking point if an
interview comes earlier.

## Repo layout

```
CLAUDE.md SPEC.md PREREGISTRATION.md DEVIATIONS.md README.md LICENSE
Makefile pyproject.toml uv.lock
configs/  splits.yaml venue.yaml engine.yaml runs/*.yaml selected.yaml
data/     raw/ (gitignored, immutable)  converted/ (gitignored)  manifest.json  recon.json
src/toxic_flow/
  data/        download.py convert.py split_lock.py validate.py
  events/      market_orders.py
  signals/     ofi.py ewma.py hawkes_fit.py hawkes_online.py normalise.py
  strategies/  b0_fixed.py b1_glft.py overlay.py   (numba loops for hftbacktest)
  engine/      grid.py run.py
  eval/        metrics.py markouts.py bootstrap.py
  report/      tables.py figures.py
tests/    unit/ leakage/ canary/ writing_rules.txt test_writing.py
scripts/  check_milestone.py recon.py
results/  <config_hash>/ (summaries committed, bulky fills gitignored)
docs/     DATA_RECON.md ENGINE.md data_quality/
paper/    interactive page + one-page PDF source
viva/     M0.md ... M6.md
```

## M0: Recon, guards, one-day benchmark

Goal: know exactly what the data and engine are before designing around them, and have
the test-day lock in place before any download code exists.

Build:
- uv project, Python 3.12. Dependencies: hftbacktest (pin a release at least two weeks
  old), polars, pyarrow, numpy, scipy, numba, pyyaml, pytest, ruff.
- Makefile targets: check, check-full, hooks (installs a pre-commit hook that runs make
  check), data, run (stub), paper (stub).
- src/toxic_flow/data/split_lock.py and tests/leakage/test_split_lock.py, written before
  download.py. The lock refuses any test date unless `git tag --list prereg-v1` returns it
  and `git ls-remote --tags origin prereg-v1` returns it.
- scripts/recon.py: GET https://api.tardis.dev/v1/exchanges/binance-futures and keep what it
  says about BTCUSDT. No request to any dataset URL. (Changed 2026-10-22, Ilia's decision:
  datasets.tardis.dev answers HEAD with 404 for every URL, so HEAD cannot show a file
  exists; see docs/DATA_RECON.md. File sizes move to M1.)
- configs/venue.yaml: for each date, tick size, lot size, minimum notional, standard-tier
  maker and taker fee in bp, each with a source URL. Tick size on downloaded days is
  also inferred from the data and must match. Unsourced values stay TBD and block M0.
- docs/ENGINE.md: for the pinned version, the exact names used for Tardis conversion,
  the four queue models, the latency models, the exchange model and the fee model.
- Download and convert 2024-01-01 only. Run a minimal fixed-spread loop on it.
- tests/test_writing.py: fails on any banned word or em dash in .md and paper files,
  excluding CLAUDE.md, .claude/ and tests/writing_rules.txt.

Acceptance (implemented in scripts/check_milestone.py M0):
- AC0.1 the Tardis exchange metadata in data/recon.json lists BTCUSDT with both data types,
  available from on or before 2024-01-01 through on or after 2026-10-01. No request of any
  kind is made to a test-day URL; the only exception is the HEAD requests (status 404, no
  body) that recon sent on 2026-10-22 under the original M0 instruction, as recorded in
  recon.json. (Changed 2026-10-22 from "each of the 68 files HTTP 200 with a positive
  content-length", which HEAD cannot show on this server.) Other recon runs that day sent
  HEADs of the same kind that recon.json does not hold; they are listed in
  data/recon_logs/2026-10-22_recon_runs.txt, and whether the exception covers them is
  question 17 in docs/DATA_RECON.md. Since the decision every request goes through
  TardisClient and is logged in data/tardis_requests.jsonl before it is sent.
- AC0.2 recon.json records the exchange metadata returned by the Tardis API.
- AC0.3 configs/venue.yaml has every field for every date and no TBD.
- AC0.4 hftbacktest pinned in uv.lock; docs/ENGINE.md has sections Version, Data
  conversion, Queue models, Latency models, Exchange model, Fee model.
- AC0.5 split-lock test exists; no test date appears in data/manifest.json or in any
  filename under data/.
- AC0.6 manifest has the benchmark day with well-formed SHA-256 hashes; docs/DATA_RECON.md
  has sections Benchmark (raw bytes, converted bytes, conversion time, loop wall time,
  fill count, machine spec) and Compute projection (run counts for M4 and M5 times
  measured time, divided by usable cores).
- AC0.7 Makefile check target runs tests/leakage and the writing lint; pre-commit hook
  installed; make check passes.

Compute rule: if the projection for M5 exceeds [TBD: Ilia's limit in wall-clock hours],
the reduction is chosen before the tag, in this order: canaries in the primary cell only,
then drop the queue model whose fill counts sit between two others. Test days are never cut.

Viva topics: what incremental_book_L2 rows contain and how a snapshot starts the day;
exchange vs local timestamp; why the lock checks the remote and not just the local tag.

## M1: Data pipeline for train and val

Goal: 18 days downloaded, hashed, converted and validated, plus a market-order event
table built the same way for every day.

Build:
- download.py: writes data/raw/<date>/<type>.csv.gz once, verifies SHA-256 on re-run,
  records url, bytes, sha256, downloaded_at (UTC) and split in data/manifest.json.
- convert.py: hftbacktest Tardis conversion to its native format in data/converted/.
- validate.py: per day, writes docs/data_quality/<date>.json with crossed-book count after
  conversion, largest gap per stream inside the quoting window, feed latency quantiles
  (p50, p90, p99, max), trade count, book update count.
- events/market_orders.py: trades with the same exchange timestamp and the same aggressor
  side collapse into one market-order event (size summed, VWAP, levels swept). Reports
  the collapse ratio per day.

Acceptance:
- AC1.1 manifest has 36 raw files for the 18 train and val days, none for test days.
- AC1.2 slow test re-hashes every raw file against the manifest.
- AC1.3 a data-quality file exists per day. Any day meeting a pre-registered exclusion rule
  is listed in docs/data_quality/EXCLUSIONS.md with the rule number. Nothing else excludes.
- AC1.4 unit test: three prints at one timestamp and side become one event with the right
  size and VWAP; prints at one timestamp with opposite sides stay two events.
- AC1.5 the event table for each day is Parquet with schema
  (exch_ts, local_ts, side, size, vwap, n_prints, levels).
- AC1.6 content-length or bytes on disk recorded for all 36 train and val files.

Viva topics: why collapse prints; what goes wrong in a Hawkes MLE with tied timestamps;
what feed latency quantiles say about which latency setting is realistic.

## M2: Harness, B0 and B1 on training days

Goal: the grid runner and the two baselines, with PnL accounting that reconciles.

Build:
- engine/grid.py: expands a run config over queue models {risk-averse, power n=3,
  power n=2, log} and latency {low, high}, plus zero latency when a canary asks for it.
- engine/run.py: one day, one cell. Writes results/<config_hash>/ with a copy of the
  config, git commit, per-day metrics Parquet and fills Parquet.
- strategies: B0 and B1 as numba loops following PREREGISTRATION.md section 4.
- eval/metrics.py: gross PnL, traded notional, break-even fee, net PnL at each fee
  level, inventory variance, fill rate, quote presence, inventory at funding times.
- eval/markouts.py: per-fill markouts at 1 s, 10 s, 60 s.

Acceptance:
- AC2.1 results exist for B0 and B1 on 12 train days in all 8 cells.
- AC2.2 PnL reconciles: cash change plus inventory times end mid equals gross PnL, per
  day, to 1e-6 USDT.
- AC2.3 fee equivalence: on one day, net PnL from hftbacktest run with its own maker fee
  equals the post-hoc computation to 1e-6 USDT.
- AC2.4 the risk-averse model has the fewest fills of the four on every train day for B1.
  If not, stop: the pessimistic reference is not pessimistic.
- AC2.5 B0 h and B1 gamma and estimation window chosen by the pre-registered rule and
  written to configs/selected.yaml with the training-day table behind the choice.
- AC2.6 layering test passes: no import path from strategies or signals into eval.

Viva topics: derive the GLFT half-spread and skew on a whiteboard; why markouts belong
in eval only; what the risk-averse model assumes about cancellations.

## M3: Signals, Hawkes fit, canaries

Goal: three overlay signals with causal online versions, a fitted bivariate Hawkes
model with honest diagnostics, and canaries that can fail.

Build:
- signals/ofi.py: best-level OFI (Cont, Kukanov and Stoikov 2014) over trailing W.
- signals/ewma.py: signed decay-weighted trade counts with time constant tau.
- signals/hawkes_fit.py: bivariate exponential kernel, shared beta, MLE pooled over
  training days with the O(n) recursive log-likelihood, L-BFGS-B on log-parameters,
  standard errors from a numerical Hessian, branching ratio as the spectral radius of
  alpha / beta.
- signals/hawkes_online.py: O(1) recursive intensity update inside the numba loop.
- signals/normalise.py: trailing 30-minute normalisers and the training-day constant K.
- canaries C1 to C4 as specified in PREREGISTRATION.md section 10.

Acceptance:
- AC3.1 future-perturbation test for each signal: replace every event after t with random
  events; the signal at every decision time up to t is unchanged.
- AC3.2 online Hawkes intensity equals the offline formula on the same event stream to
  1e-9 relative error.
- AC3.3 slow test: simulate a bivariate Hawkes process with known parameters by Ogata
  thinning (at least 50,000 events); the fit recovers each parameter within 3 standard
  errors.
- AC3.4 fitted branching ratio is below 1. If not, stop and revise before the tag.
- AC3.5 time-rescaling residuals and KS statistics on validation days written to
  docs/hawkes_fit.md, whatever they show.
- AC3.6 the oracle canary C2 lives under tests/canary/ and is the only code allowed to
  read forward-looking arrays from a strategy loop; a test checks no other strategy
  file references them.

Viva topics: write the Hawkes log-likelihood and the recursion; what a branching ratio
near 1 means for this market; why B3 versus B2b is the real test.

## M4: Tuning, MDE, pre-registration freeze

Goal: choose overlay settings on validation days, compute the minimum detectable effect,
complete PREREGISTRATION.md, and hand over to Ilia for the tag.

Build:
- Tuning grid in the primary cell on 6 validation days: c in {0, 0.5, 1}, d in
  {0, 0.5, 1}, B2 window W in {1 s, 5 s, 30 s}, B2b decay tau in {1 s, 5 s, 30 s},
  B3 with fitted beta. Selection rule from PREREGISTRATION.md section 4.
- Canaries on validation days.
- MDE from section 9, then fill every [TBD] in PREREGISTRATION.md.

Acceptance:
- AC4.1 configs/selected.yaml has B2, B2b and B3 settings with the validation table.
- AC4.2 canary C2 beats B1 by more than 3 times the MDE on validation days. If not, stop:
  the harness cannot turn information into PnL, so a null result would mean nothing.
- AC4.3 canary C1 confidence interval against B1 includes 0 on validation days.
- AC4.4 PREREGISTRATION.md contains no [TBD] and passes the writing lint.
- AC4.5 Ilia has passed /viva M4.

Then Ilia, by hand: `git tag -a prereg-v1 -m "pre-registration"`, `git push origin
prereg-v1`, and records the commit hash and push time as the first entry in DEVIATIONS.md.

## M5: Test run, once

Goal: download the 16 test days and run the pre-registered analysis one time.

Acceptance:
- AC5.1 every test-day manifest entry has downloaded_at later than the tag's creation time.
- AC5.2 exclusion rules applied by script before any strategy result on that day exists.
- AC5.3 one results directory for the confirmatory grid. Any rerun has a DEVIATIONS.md
  entry naming the bug and the fixing commit, and both results stay in the report.
- AC5.4 leakage-auditor report on the test results saved to docs/audit_M5.md.

Viva topics: read the primary result aloud with its CI and MDE; explain one day where
B3 lost to B2b using its fills and markouts.

## M6: Paper and deliverables

Acceptance:
- AC6.1 the paper page matches the format of the other iliaduda.com project papers.
  Every result number is a {{key}} placeholder filled from results/summary.json; a
  script fails if a placeholder is unresolved or a result section contains a literal
  decimal number.
- AC6.2 one-page PDF summary built from the same summary.json.
- AC6.3 section "What I would do with L3 data and real fills".
- AC6.4 README reproduces the study with make data, make run, make paper.
- AC6.5 writing lint passes on everything.

## Out of scope

- L3 or market-by-order data, and any claim that depends on true queue position.
- Other venues (Deribit and the rest), other symbols, cross-venue signals.
- Live trading, paper trading, exchange API connectivity, any claim of deployability.
- A custom matching engine or changes to hftbacktest's Rust core.
- Market impact: orders are minimum size and the simulator replays history.
- Funding payments (inventory at funding times is reported so the gap can be bounded).
- Intraday-varying Hawkes baselines and non-exponential kernels (listed as future work).
- Learned signals (gradient boosting, neural nets) on top of the overlays.
- Fee-tier optimisation and rebate programmes beyond the fee levels in section 6.
- Any tuning, selection or diagnosis that uses test days before the confirmatory run.
