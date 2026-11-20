"""GTA VI trophy rarity forecaster (gta6-trophy-rarity-forecast-01).

Forecasts, for every trophy, five quantiles of its Exophase earn rate at the
case's target, as a pinball loss on the logit scale scores them.

Model (standard library only, offline, deterministic, no model call)
--------------------------------------------------------------------
Exophase's page is a *stale snapshot*: it only changes when Exophase
refreshes a game's counts (hours apart), and at a refresh the tracked-player
count jumps while each trophy's rate is diluted by the new players. Two
regimes, told apart by whether the history has ever shown a refresh:

*Refreshes observed (the final case).* Per trophy, fit log(rate) against
x = ln(1 + hours since release) on the distinct snapshots of the recent
window (consecutive identical reads are the same stale page re-read, so only
the first of each run is kept), recency-weighted least squares. The fitted
change from the last read is *damped* by 1 / (1 + x_target - x_last): a
launch-night trend in ln(1+h) space is concave in truth (rates saturate as
players finish the early game), so a straight line extrapolated 4.5 days
would overshoot; the damping is the prior that the trend flattens. Earners
never fall and a trophy held by ~everyone stays ~100%.

*No refresh ever observed (the practice cases: every read identical).* No
trend can be fitted, but the page is stale and a refresh is overdue: the
tracked-player count is forecast to keep growing at the launch pace the
house itself published for the first refresh (638 -> 3,868 players over
launch night, about a doubling every 2 h), measured from the first read,
capped at 12x, while earners are held flat (new players earn ~1 trophy each
early on, the ~100% one, which tracks the player count instead). That
dilutes every other rate, which is what the practice answers do; the spread
below is widened to match, since the refresh's size is a guess.

Spread (logit sigma per trophy) combines a random-walk term growing with the
horizon, the log-rate fit's prediction uncertainty, count noise for rare
trophies, and a refresh-risk term (large when no refresh has been seen yet).
Quantiles are inv_logit(logit(median) + z_tau * sigma), rounded to 4 decimals
half-up, clamped to [0.01, 99.99] percent.

I/O: reads every <id>.in in $MAKEFUN_INPUT_DIR (else /input), writes
<id>.out to $MAKEFUN_OUTPUT_DIR (else /output), one row per trophy.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Random-walk diffusion of a rate on the logit scale, per sqrt(day).
SIGMA_RW = 0.5
# Spread when no trend can be fitted at all.
SIGMA_NOFIT = 0.4
# Extra logit spread while the page has never been seen to refresh: the next
# refresh's size is a guess, so the band must be honest about it.
SIGMA_REFRESH_UNSEEN = 1.0
# Extra logit spread once refreshes are a known, recurring event.
SIGMA_REFRESH_SEEN = 0.35
# Launch-pace prior for the tracked-player count while no refresh has been
# observed: doubling time in hours, measured from the first read.
PRIOR_DOUBLING_HOURS = 2.0
PRIOR_MAX_MULTIPLIER = 12.0
# Recent window for the log-rate fit, in hours; fall back to all snapshots
# when the window holds too few.
FIT_WINDOW_HOURS = 36.0
FIT_WINDOW_MIN_SNAPS = 4


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def clamp_pct(x: float) -> float:
    return min(99.99, max(0.01, x))


def logit(pct: float) -> float:
    p = clamp_pct(pct)
    return math.log(p / (100.0 - p))


def inv_logit(lg: float) -> float:
    if lg >= 0:
        return 100.0 / (1.0 + math.exp(-lg))
    e = math.exp(lg)
    return 100.0 * e / (1.0 + e)


def round4(x: float):
    """Round to 4 decimals, half up, as JavaScript's Math.round does it."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if value.is_integer() else value


def wlsq(xs, ys, ws):
    """Weighted least squares of y on x. Returns (a, b, resid_sd, n, xbar, sxx)
    or None when the fit is degenerate (fewer than 3 points or no x spread)."""
    n = len(xs)
    if n < 3:
        return None
    sw = sum(ws)
    xbar = sum(w * x for w, x in zip(ws, xs)) / sw
    ybar = sum(w * y for w, y in zip(ws, ys)) / sw
    sxx = sum(w * (x - xbar) ** 2 for w, x in zip(ws, xs))
    if sxx <= 1e-12:
        return None
    sxy = sum(w * (x - xbar) * (y - ybar) for w, x, y in zip(ws, xs, ys))
    b = sxy / sxx
    a = ybar - b * xbar
    resid = [y - (a + b * x) for x, y in zip(xs, ys)]
    dof = max(n - 2, 1)
    var = sum(w * r * r for w, r in zip(ws, resid)) / sw
    resid_sd = math.sqrt(var * n / dof)
    return (a, b, resid_sd, n, xbar, sxx)


def forecast_case(case: dict, name: str) -> dict:
    if case["levels"] != LEVELS:
        raise ValueError(f"{name} asks for levels {case['levels']}, not {LEVELS}")
    history = case.get("history") or []
    if not history:
        raise ValueError(f"{name} has no history")

    release = parse_time(case["game"]["release_date"] + "T00:00:00Z")
    target = parse_time(case["target"])
    horizon_days = case["horizon_minutes"] / 1440.0

    def hours_since_release(t: datetime) -> float:
        return (t - release).total_seconds() / 3600.0

    def x_of(t: datetime) -> float:
        return math.log1p(max(hours_since_release(t), 0.0))

    x_target = x_of(target)

    # Distinct snapshots: consecutive reads with identical (players, rates) are
    # the same stale page re-read, so keep only the first of each run.
    snaps = []
    prev_key = None
    for read in history:
        key = (read["players_tracked"], tuple(read["rates"]))
        if key != prev_key:
            snaps.append(read)
            prev_key = key
    first_time = parse_time(history[0]["at"])
    last = history[-1]
    last_time = parse_time(last["at"])
    n_last = last["players_tracked"]
    refreshed = len({s["players_tracked"] for s in snaps}) > 1

    # --- Flat-history prior: no refresh ever observed. The page is stale and
    # a refresh is overdue; the tracked count grows at the launch pace while
    # earners are held flat, so every rate is diluted by n_last / n_star. ---
    n_star_prior = None
    if not refreshed:
        stale_hours = (target - first_time).total_seconds() / 3600.0
        mult = min(2.0 ** (stale_hours / PRIOR_DOUBLING_HOURS), PRIOR_MAX_MULTIPLIER)
        n_star_prior = n_last * mult

    # Recent window for the log-rate fits.
    window_start = last_time.timestamp() - FIT_WINDOW_HOURS * 3600.0
    fit_snaps = [s for s in snaps if parse_time(s["at"]).timestamp() >= window_start]
    if len(fit_snaps) < FIT_WINDOW_MIN_SNAPS:
        fit_snaps = snaps

    rows = []
    for i, trophy in enumerate(case["trophies"]):
        # Last non-null rate.
        rate_last = None
        for read in reversed(history):
            r = read["rates"][i]
            if r is not None:
                rate_last = r
                break
        if rate_last is None:
            rate_last = 0.5
        e_last = rate_last * n_last / 100.0

        if rate_last >= 99.99:
            # Held by (nearly) everyone tracked: it tracks the player count.
            rate_star = 99.99
            se = SIGMA_NOFIT if refreshed else SIGMA_REFRESH_UNSEEN
            sigma_extra = 0.0
        elif not refreshed:
            # Dilution by the overdue refresh; earners held flat.
            rate_star = clamp_pct(100.0 * e_last / n_star_prior)
            se = SIGMA_REFRESH_UNSEEN
            sigma_extra = 0.5 / math.sqrt(e_last + 1.0)
        else:
            # Fit log(rate) on ln(1 + hours since release), recent window.
            xs, ys, ws = [], [], []
            for s in fit_snaps:
                r = s["rates"][i]
                if r is None:
                    continue
                xs.append(x_of(parse_time(s["at"])))
                # 0.00% printed means fewer than 0.005%: use that as the floor.
                ys.append(math.log(max(r, 0.005)))
                ws.append(0.5 ** ((last_time - parse_time(s["at"])).total_seconds() / 86400.0))
            fit = wlsq(xs, ys, ws)
            log_last = math.log(max(rate_last, 0.005))
            if fit is None:
                rate_star = rate_last
                se = SIGMA_NOFIT
            else:
                a, b, sd, n, xbar, sxx = fit
                raw = a + b * x_target
                # Damp the fitted change from the last read: the trend in
                # ln(1+h) space flattens as rates saturate, so a straight
                # line extrapolated days out overshoots.
                x_last = xs[-1]
                lam = 1.0 / (1.0 + max(x_target - x_last, 0.0))
                log_star = log_last + lam * (raw - log_last)
                rate_star = clamp_pct(math.exp(log_star))
                se = lam * sd * math.sqrt(1.0 + 1.0 / n + (x_target - xbar) ** 2 / sxx)
            sigma_extra = 0.5 / math.sqrt(e_last + 1.0)

        # ---- Spread on the logit scale. ----
        s_refresh = SIGMA_REFRESH_UNSEEN if not refreshed else SIGMA_REFRESH_SEEN
        sigma = math.sqrt(
            (SIGMA_RW ** 2) * horizon_days
            + se ** 2
            + s_refresh ** 2
            + sigma_extra ** 2
        )
        sigma = min(max(sigma, 0.30), 2.5)

        lg = logit(rate_star)
        rows.append({
            "id": trophy["id"],
            "q": [round4(clamp_pct(inv_logit(lg + z * sigma))) for z in Z],
        })

    return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
