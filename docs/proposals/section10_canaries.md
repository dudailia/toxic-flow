# Proposal: canary decisions before the tag (Q24 to Q26, Q28 to Q30)

PREREGISTRATION.md is not frozen yet, so these can still change it. Nothing here has been
applied. Each item gives the issue, the options, the option I recommend, and the exact
text it would put into PREREGISTRATION.md. The evidence comes from the SMOKE canary run
on 2024-01-01 and its audit (docs/smoke/audit_canaries_2024-01-01.md); one day decides
nothing, so the evidence only shows that each issue is real.

## Q28. What C1 is compared with

Issue. C1 shuffles the event signs, so its direction u carries no information, but its
magnitude m is unchanged: m depends on total activity, not on signs. On 2024-01-01 the K
recomputed on shuffled sides is 3.464, the same as B3's, and mean m is 0.068 in both.
Section 10 compares C1 with B1. With a selected d > 0, C1 widens its quotes when activity
is high and B1 does not, so C1 minus B1 can exclude 0 with no sign information at all.
Section 11 would then say the gain is not order-flow information, which is a different
claim from the one the data supports.

Options.
- A. Compare C1 with B3 at the selected d and c = 0 (magnitude only, same K). Both have
  the same magnitude channel, so the difference isolates what shuffled signs add. Costs
  one extra strategy in the canary and confirmatory configs.
- B. Run C1 with d = 0 and compare it with B1. No extra strategy, but C1 then tests a
  different overlay from the selected B3.
- C. Keep section 10 as written and add the caveat to the conclusion.

Recommended: A. Proposed text for section 10:

> - C1, shuffled signs: B3 with the selected settings, but the side of each market-order
>   event is randomly permuted within the day (one permutation, seed 1729) before it
>   enters the intensity. Its comparator is B3 with the selected d and c = 0, which has
>   the same magnitude and no direction. Pass: the interval for C1 minus that comparator
>   includes 0.

A related point for the same decision: the pass rule is two-sided, so C1 also fails when
random skews make it significantly worse than the comparator. Section 11's sentence about
C1 fits only the case where C1 is better. If you want the rule one-sided, the sentence
becomes "Pass: the interval for C1 minus that comparator does not lie entirely above 0."

## Q24. How many permutations for C1

Issue. Section 10 says the sides are "randomly permuted" without saying how many times.
The code uses one permutation per day, seed 1729, and B3's fitted parameters with no refit.

Recommended: one permutation, no refit, stated in the text above. Averaging over several
permutations would cut the canary's own noise but multiplies its run time.

## Q25. K for the C4 variants

Issue. Section 5 defines K "for that signal and parameter". C4 changes beta, so by that
wording each variant has its own K. The code keeps B3's K. On 2024-01-01:

| Variant | Own K | Mean m with B3's K | Mean m with own K |
|---|---|---|---|
| B3 | 3.464 | 0.068 | 0.068 |
| C4, x10 | 7.665 | 0.087 | 0.053 |
| C4, x0.1 | 2.006 | 0.043 | 0.070 |

With B3's K, C4 changes the decay and the amount of widening together. With its own K,
the widening stays on the same scale and only the decay changes, which is what C4 is
meant to test.

Recommended: own K, computed on training days by scripts/fit_signals.py (it already
writes C4_x10 and C4_x0.1). Proposed text for section 10:

> - C4, wrong decay: B3 with beta multiplied by 10 and divided by 10, alpha rescaled so
>   the branching ratio stays at its fitted value, and K recomputed on training days for
>   each variant.

Code change if accepted: in src/toxic_flow/engine/configs.py, C4 entries take
constants["K"][f"C4_x{f:g}"] instead of B3's K.

## Q26. What zero latency means for C3

Issue. C3 sets order latency to zero. Feed latency stays, because it is in the data as
local minus exchange time. True zero latency would also need local time set to exchange
time, which means a second converted copy of each day.

Recommended: zero order latency only, stated. Proposed text for section 3:

> Zero latency runs only as canary C3, and sets order entry and response latency to
> zero. Feed latency stays as recorded, so C3 is not a zero-latency participant.

## Q29. How the C3 flag is judged

Issue. Section 10 flags C3 if "any non-zero-latency run of B3 beats it on the mean". On
2024-01-01 the paired hourly bootstrap of B3 high minus zero was +0.0125 bp with
interval [-0.014, +0.040]: the latency effect is the size of the noise, so a rule on
means fires about half the time by chance. The same holds for the CLAUDE.md trigger
"any run beating its zero-latency twin", which started the audit.

Recommended: judge C3 like everything else, with the paired day-level interval. Proposed
text for section 10:

> - C3, zero latency: B3 selected settings at zero order latency. Reported as an upper
>   bound. Flag if the paired day-level bootstrap interval for B3 at either non-zero
>   latency minus C3 lies entirely above 0.

The CLAUDE.md trigger is yours to word. One option: keep it for any single smoke day,
where an audit is cheap, and use the interval rule once there are several days.

## Q30. Order latency looks up to 1 s ahead

Issue. generate_order_latency keeps one feed-latency row per second, and
intp_order_latency interpolates between the rows on either side of t, so the order
latency applied at t depends on feed latency up to 1 s later. The strategy never reads
latency, so it cannot inform a quote, and shifting the file in time moved B3's BEF both
ways with no systematic gain.

Options. A: state it as a limitation. B: shift the latency file one row later so the
value at t uses only rows at or before t. That changes every result a little and needs a
new latency file per day.

Recommended: A. Proposed text for section 3, after the latency bullet:

> Order latency at time t is interpolated between one-second samples of feed latency on
> either side of t, so it uses feed latency up to one second ahead. The strategy never
> reads latency, so this cannot inform a decision.
