# Engine notes: hftbacktest 2.4.4

Every name below was read from the installed package (`.venv/lib/python3.12/site-packages/hftbacktest`)
and from the source at the release tag. Source links point at tag `py-v2.4.4`, commit
`a244a14250b42d97fc305569c93c4117cd5e1dff`, which is also tag `rust-v0.9.4` of the Rust core.

## Version

- Pinned: `hftbacktest==2.4.4` in pyproject.toml and uv.lock. PyPI upload 2025-12-10
  (https://pypi.org/project/hftbacktest/2.4.4/). It is the newest release on PyPI as of
  2026-10-22, so it is also the newest one that is at least two weeks old.
- Source: https://github.com/nkaz001/hftbacktest/tree/py-v2.4.4
- Requires numpy >=2.0,<2.3 and numba ~=0.61. The lock resolves numpy 2.2.6 and numba 0.68.0.
- The Python builder `BacktestAsset` is a Rust class; its methods and defaults are in
  [py-hftbacktest/src/lib.rs](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/src/lib.rs).
  Defaults when a method is not called: constant latency 0, `LogProbQueueModel2`,
  `NoPartialFillExchange`, `TradingValueFeeModel` with zero fees, linear asset with contract
  size 1, `parallel_load` on (lib.rs lines 130 to 155).
- Depth: `HashMapMarketDepthBacktest([asset])`. No price range has to be fixed in advance,
  unlike `ROIVectorMarketDepthBacktest`.

## Data conversion

- hftbacktest function: `hftbacktest.data.utils.tardis.convert(input_files, output_filename=None,
  buffer_size=100_000_000, ss_buffer_size=1_000_000, base_latency=0, snapshot_mode='process')`
  ([tardis.py](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/hftbacktest/data/utils/tardis.py)).
  Input order is trades first, then `incremental_book_L2`, so that a trade lowers queue
  position before the book update it caused.
- Steps inside it: Tardis microsecond timestamps times 1000 to nanoseconds; depth rows through
  the numba function `_convert_depth`, which turns each snapshot block into
  `DEPTH_CLEAR_EVENT` plus `DEPTH_SNAPSHOT_EVENT` rows; then
  `hftbacktest.data.validation.correct_local_timestamp`, `correct_event_order` and
  `validate_event_order`
  ([validation.py](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/hftbacktest/data/validation.py)).
- `snapshot_mode='process'` keeps every snapshot, including the start-of-day one Tardis adds,
  so the book is complete from the first snapshot (2024-01-01: exchange time 00:00:00.049).
- `correct_local_timestamp`: if any row has local_ts < exch_ts, every local_ts of the day is
  shifted up by the most negative feed latency. Feed latency after conversion is therefore
  never negative. The shift for each day is recorded in data/converted/DATE/convert.json.
- `correct_event_order`: rows sorted by exchange time and by local time are merged; a row
  whose two orders disagree is split into an `EXCH_EVENT` row and a `LOCAL_EVENT` row. The
  exchange side of the simulator reads one sequence, the strategy side the other.
- Exchange timestamp: Tardis uses Binance's `E` (event time, when the message was sent),
  not `T` (match time). The converter docstring says so, and adds that measured feed
  latency is slightly less than the true one.
- Memory, and what this repo does about it: a BTCUSDT day is about 98M events, 6.3 GB as
  64-byte hftbacktest events. The one-shot `convert` holds the whole CSV as a DataFrame,
  the event buffer, two sort indices and a 2N-row output in `correct_event_order`; my
  estimate of its peak is about 14 GB (event buffer 6.3 GB, touched output at least 6.3 GB,
  indices 1.6 GB, plus the DataFrame). Not measured, because it would not fit: this
  machine has 16 GiB with about 6 to 9 GiB free. `src/toxic_flow/data/convert.py` calls the same hftbacktest functions
  but streams the CSV and writes the day as several parts, cut at instants where no message
  is in flight. The parts, concatenated, are byte-identical to `tardis.convert` output:
  `tests/unit/test_convert.py` checks this on synthetic data and, as a slow test, on the
  first 3M book rows of 2024-01-01. It also refuses two cases where parts could differ:
  a cut inside a snapshot block, and a later snapshot with more levels than an earlier
  one. In that second case `_convert_depth` itself would silently truncate the snapshot,
  because it reslices its buffer to each block's size (checked empirically).
- Loading: `BacktestAsset().data([part_00, part_01, ...])` reads the parts in order.

## Queue models

PREREGISTRATION.md section 3 names four. Builder methods on `BacktestAsset`
([lib.rs 325 to 392](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/src/lib.rs#L325-L392);
models in [queue.rs](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/hftbacktest/src/backtest/models/queue.rs);
docs [order_fill.rst](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/docs/order_fill.rst)):

| Study name | Builder call | Rust type |
|---|---|---|
| risk-averse | `risk_adverse_queue_model()` | `RiskAdverseQueueModel` |
| power n = 3 | `power_prob_queue_model(3.0)` | `ProbQueueModel<PowerProbQueueFunc>` |
| power n = 2 | `power_prob_queue_model(2.0)` | `ProbQueueModel<PowerProbQueueFunc>` |
| log | `log_prob_queue_model()` | `ProbQueueModel<LogProbQueueFunc>` |

Note the spelling `adverse` in the method name.

- Risk-averse (queue.rs lines 42 to 96): on entry, the quantity ahead is the whole level.
  It falls by each trade at that price. A book update sets it to min(ahead, new level qty),
  so cancellations move the order forward only when the level shrinks below the quantity
  ahead. Filled once the quantity ahead goes below zero by at least half a lot.
- Probabilistic (queue.rs lines 130 to 217): trades reduce the quantity ahead as above. When
  the level shrinks by `chg` (net of trades already counted), the part of the decrease
  assigned to the front is `(1 - p) * chg` with p = prob(front, back), so
  `front' = front - (1 - p) * chg + min(back - p * chg, 0)`, capped at the new level qty.
- `PowerProbQueueFunc`: p = f(back) / (f(back) + f(front)), f(x) = x^n (queue.rs 219 to 240).
- `LogProbQueueFunc`: same form with f(x) = log(1 + x) (queue.rs 242 to 262).
- Other variants exist and are not used: `power_prob_queue_model2` (p = f(back) / f(back + front)),
  `power_prob_queue_model3` (p = 1 - f(front / (front + back))), `log_prob_queue_model2`,
  and `l3_fifo_queue_model` (needs L3 data).
- [TBD: PREREGISTRATION.md says "power function n = 3, power n = 2, and log function" without
  naming the variant. The table above uses the first variant of each, which share one
  formula and differ only in f. Ilia to confirm.]

## Latency models

- Feed latency is in the data: local_ts minus exch_ts on every event. Nothing to configure.
- Order latency, builder methods
  ([lib.rs 271 to 323](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/src/lib.rs#L271-L323);
  [latency.rs](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/hftbacktest/src/backtest/models/latency.rs);
  docs [latency_models.rst](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/docs/latency_models.rst)):
  - `constant_order_latency(entry_latency, resp_latency)` gives `ConstantLatency`.
    `constant_latency` is the deprecated alias. Zero latency for canary C3 is
    `constant_order_latency(0, 0)`.
  - `intp_order_latency(data, latency_offset=0)` gives `IntpOrderLatency`, which
    interpolates entry and response latency between rows of (req_ts, exch_ts, resp_ts,
    _padding) arrays in nanoseconds.
- Order latency from feed latency:
  `hftbacktest.data.utils.feed_order_latency.generate_order_latency(feed_file, output_file=None,
  mul_entry=1, offset_entry=0, mul_resp=1, offset_resp=0, resampling_ns=1_000_000_000)`
  ([feed_order_latency.py](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/hftbacktest/data/utils/feed_order_latency.py)).
  It keeps rows flagged both `EXCH_EVENT` and `LOCAL_EVENT`, takes the last row in each 1 s
  bucket of local time, and sets req_ts = local_ts, exch_ts = req_ts + mul_entry *
  feed_latency + offset_entry, resp_ts = exch_ts + mul_resp * feed_latency + offset_resp.
  - Low latency in this study: mul_entry = mul_resp = 1, offsets 0.
  - High latency: mul_entry = mul_resp = 3, offsets 0.
  - With a day in parts, the function runs on each part and the outputs are concatenated
    in order. Compared with one call on the whole day, that adds at most one extra 1 s
    sample per cut, at most n_parts - 1 rows in about 86,400.
- Look-ahead inside the engine: `IntpOrderLatency::entry` at time t interpolates between the
  last row with req_ts <= t and the next row, so the latency applied to an order uses
  feed latency observed up to one resampling step (1 s) later. This is the simulated
  environment, not information the strategy can read, but it means order latency is not
  strictly causal. Stated here so the auditor does not have to find it.
- Outside the data range the first or last row's latency is used (latency.rs lines 171 to 186).

## Exchange model

- Builder methods: `no_partial_fill_exchange()` (`NoPartialFillExchange`, the default) and
  `partial_fill_exchange()` (`PartialFillExchange`)
  ([lib.rs 436 to 450](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/src/lib.rs#L436-L450);
  [nopartialfillexchange.rs](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/hftbacktest/src/backtest/proc/nopartialfillexchange.rs);
  [partialfillexchange.rs](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/hftbacktest/src/backtest/proc/partialfillexchange.rs)).
- Both fill a resting buy in full when its price is at or above the best ask, or above a
  sell trade price. They differ when the order is at the front of the queue and a trade
  prints at its price: `NoPartialFillExchange` fills the whole order whatever the trade
  size; `PartialFillExchange` fills at most the remaining traded quantity.
- Both accept `GTX` (post-only), which the study uses. `PartialFillExchange` also accepts
  `FOK` and `IOC`.
- Proposal for PREREGISTRATION.md section 3 [TBD: Ilia to decide]: `partial_fill_exchange()`.
  Reason: it never fills more than the no-partial-fill model, and with minimum-size orders a
  print smaller than the order (one lot, 0.001 BTC) is possible, where the no-partial-fill
  model would fill the whole order. The M0 benchmark loop uses it.
- Replay caveat from the docs: market data cannot react to our orders, so a fill does not
  remove liquidity from the replayed book.

## Fee model

- Builder methods: `trading_value_fee_model(maker_fee, taker_fee)`, `trading_qty_fee_model`,
  `flat_per_trade_fee_model` ([lib.rs 452 onward](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/src/lib.rs#L452);
  [fee.rs](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/hftbacktest/src/backtest/models/fee.rs)).
- `TradingValueFeeModel` charges rate times traded value (price times quantity times contract
  size), maker or taker rate depending on the fill (fee.rs lines 52 to 73). Rates are
  fractions: 2 bp is `0.0002`. A negative rate is a rebate.
- The study runs with `trading_value_fee_model(0.0, 0.0)` and applies fees in evaluation as
  rate times traded notional (PREREGISTRATION.md section 3). M2 has a test that a run with
  hftbacktest's own maker fee gives the same net PnL.
- Accumulated fee, traded value, traded volume, fill count, position and cash per asset:
  `hbt.state_values(asset_no)` with fields `fee`, `trading_value`, `trading_volume`,
  `num_trades`, `position`, `balance`
  ([state.py](https://github.com/nkaz001/hftbacktest/blob/py-v2.4.4/py-hftbacktest/hftbacktest/state.py)).
