# Proposal: text for the five M0 [TBD]s in PREREGISTRATION.md

AC4.4 needs PREREGISTRATION.md free of [TBD] before the tag. Five of the twelve left are
M0 items whose facts are already in docs/ENGINE.md and docs/DATA_RECON.md; three of them
wait on a decision (Q2, Q3, Q6). Nothing has been applied. Each item quotes the current
line, then the proposed replacement.

## 1. Engine version (section 3), a fact

Now: "Engine: hftbacktest [TBD M0: exact version]."

Proposed:

> - Engine: hftbacktest 2.4.4, pinned in uv.lock. Replay-based, so our orders do not move
>   the market. Order size is the minimum the venue allows, which keeps that assumption
>   close to true.

## 2. Exchange model (section 3), waits on Q3

Now: "Exchange model: [TBD M0: partial-fill or no-partial-fill, with reason]."

Proposed, if Q3 keeps the current choice:

> - Exchange model: no partial fills (`no_partial_fill_exchange()`, the hftbacktest
>   default). The partial-fill model stops with an internal error on 2024-01-01 in 2.4.4
>   (docs/ENGINE.md). Limitation: an order at the front of the queue fills in full on any
>   trade at its price, whatever the trade size. On 2024-01-01 in the primary cell, fills
>   made only by prints at the order's price, the most this can affect, were 17.4% of
>   B1's fills and 8.5% of B3's; fills where those prints totalled less than the order were
>   1 of 4,502 and 0 of 2,556 (docs/smoke/partial_fill_bound_2024-01-01.json).

The two shares bound the effect from both sides: the queue ahead of the order is not
visible from outside the engine, so the true count lies between them. The same script can
report them for all 12 training days once they are on disk.

## 3. Queue model names (section 3), waits on Q2

Now: "Exact API names: [TBD M0]."

Proposed:

> Exact API names: `risk_adverse_queue_model()`, `power_prob_queue_model(3.0)`,
> `power_prob_queue_model(2.0)` and `log_prob_queue_model()`, the first variant of each
> family in hftbacktest 2.4.4.

## 4. Latency API (section 3), a fact plus the Q11 wording

Now: "(local timestamp minus exchange timestamp) [TBD M0: API]."

Proposed:

> (local timestamp minus exchange timestamp), sampled once per second of local time by
> hftbacktest's `generate_order_latency` with multiplier 1 for entry and response, and
> loaded with `intp_order_latency`. Order latency at time t is interpolated between the
> samples on either side of t, so it uses feed latency up to one second ahead; the
> strategy never reads latency, so this cannot inform a decision.

High is the same with multiplier 3, which the next sentence of section 3 already says.

## 5. Third fee level (section 6), waits on Q6

Now: "0, [TBD M0: a published rebate tier with source, or a labelled hypothetical]}."

Proposed:

> 0, -0.1 bp}. -0.1 bp is the Tier 1 maker fee of Binance's USD-M Futures Liquidity
> Provider Program on USDT pairs, published for 2025-03-03 onward and open to accounts
> with at least 100M USD of 30-day futures volume (source:
> https://www.binance.com/en/support/announcement/detail/cde392fe431a4045a951d40d7498abbc).
> It applies to the test days; for training and validation days before 2025-03-03 it is a
> hypothetical rate.

Every run config already uses this level as `lp_tier1: -0.1`.
