# GTA VI Trophy Rarity Forecaster

Entry for [make.fun](https://make.fun) bounty
`gta6-trophy-rarity-forecast-01` ($250): forecast, for every GTA VI PS5
trophy, five quantiles (5%, 25%, 50%, 75%, 95%) of its Exophase earn rate at
2026-11-26 00:00 UTC, from the house's recording of the trophy page up to the
deadline (2026-11-21 11:30 UTC). Scored by mean pinball loss on the logit
scale; the prize needs a loss strictly below the best house entry.

## Program

`main.py` — Python 3.13, standard library only, offline, deterministic, no
network, no model call. Reads every `<id>.in` in `$MAKEFUN_INPUT_DIR` (else
`/input`), writes `<id>.out` to `$MAKEFUN_OUTPUT_DIR` (else `/output`).

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Model

Exophase's page is a **stale snapshot**: it only changes when Exophase
refreshes a game's counts (hours apart), and at a refresh the tracked-player
count jumps while each trophy's rate is diluted by the new players. Two
regimes, told apart by whether the history has ever shown a refresh:

- **Refreshes observed (the final case).** Per trophy, fit `log(rate)` against
  `ln(1 + hours since release)` on the distinct snapshots of the recent
  36-hour window (consecutive identical reads are the same stale page
  re-read), recency-weighted least squares. The fitted change from the last
  read is damped by `1 / (1 + x_target - x_last)`: a launch-night trend in
  `ln(1+h)` space is concave in truth (rates saturate as players finish the
  early game), so a straight line extrapolated 4.5 days would overshoot.
- **No refresh ever observed (the practice cases: every read identical).** No
  trend can be fitted, but the page is stale and a refresh is overdue: the
  tracked-player count is forecast to keep growing at the launch pace the
  house itself published for the first refresh (638 → 3,868 players over
  launch night, about a doubling every 2 h), measured from the first read and
  capped at 12×, while earners are held flat. That dilutes every other rate,
  which is what the practice answers do.

The logit spread per trophy combines a random-walk term growing with the
horizon, the fit's prediction uncertainty, count noise for rare trophies, and
a refresh-risk term (large when no refresh has been seen yet). Quantiles are
`inv_logit(logit(median) + z_tau * sigma)`, rounded to 4 decimals half-up,
clamped to [0.01, 99.99]%.

## Local test results

The kit ships no practice answers, so they were reconstructed from the
aggregates `competition.yaml` publishes for the 04:30Z refresh read
(3,868 players, 4,276 trophies earned; launch-night earners are exact
integers since the rates are k/638 to 2 decimals). The starter baseline
scores 1.40–1.69 on the reconstruction, bracketing the 1.51 the rules
publish — so the reconstruction is credible. Two allocation variants for the
103 newly earned trophies (proportional / zero) were tested.

| Test | Baseline (persistence) | This entry |
|---|---|---|
| Practice p00+p01 (reconstructed) | 1.40–1.69 | **0.31–0.32** |
| Synthetic final, world A (N power-law, rates saturating) | 0.29 | **0.25** |
| Synthetic final, world B (N saturating, rates power-law) | 0.40 | **0.30** |
| Synthetic final, world C (N exp-then-flat, rates ramp-then-flat) | 0.38 | **0.29** |

Practice: typical miss 0.03pp (baseline 0.68pp), 90% coverage 0.98
(baseline 0.00). Deterministic (byte-identical repeat runs), ~0.09 s per
case, output valid (55 rows, non-decreasing quantiles, ≤ 65,536 bytes).
Edge cases (single-read history, null rates, all-zero rates) all run clean.

## License

MIT — see `LICENSE`.
