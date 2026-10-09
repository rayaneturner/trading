"""The ICT sweep on four crypto assets, with the stop that survives the fees.

Crypto is fixed, so 0.070%/side is fixed, so the only lever left is the
stop. A round trip costs 0.14% of notional; to keep fees under 0.10 R the
stop has to be at least 1.4% wide. That rules out every minute chart and
puts the structure on 12h with the entry on 1h.

BTC gave 142 trades on its own, +0.125 R gross, t = +1.13 - promising and
unprovable at that size. Four assets is the test that settles it.
"""
import sys; sys.path.insert(0, "src")
import numpy as np, pandas as pd
from ict_sweep import IctConfig, backtest

ASSETS = ("btc", "eth", "sol", "bnb")
HTF_RULE, FEE = "12h", 0.0007


def load(sym):
    if sym == "btc":
        d = pd.read_csv("data/crypto/btc_15m.csv.gz", index_col=0, parse_dates=True)
        d = d.resample("1h", label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    else:
        d = pd.read_csv(f"data/crypto/{sym}_1h.csv.gz", index_col=0, parse_dates=True)
    return d[["open", "high", "low", "close"]]


def stats(rows, label):
    if not rows:
        print(f"{label:46s} aucun trade"); return None
    R = np.array([t.r_net for t in rows])
    wins = sum(1 for t in rows if t.outcome == "win")
    res = sum(1 for t in rows if t.outcome in ("win", "loss"))
    rr = float(np.mean([t.rr for t in rows]))
    t = R.mean() / (R.std(ddof=1) / np.sqrt(len(R))) if R.std(ddof=1) > 0 else np.nan
    print(f"{label:46s} n={len(R):5d}  wr={wins/res*100 if res else 0:5.2f}% "
          f"(seuil {100/(1+rr):5.2f}%)  E={R.mean():+.4f}R  t={t:+5.2f}")
    return t


frames = {s: load(s) for s in ASSETS}
for s, d in frames.items():
    print(f"{s:4s} {len(d):6d} bougies 1h  {d.index[0].date()} -> {d.index[-1].date()}")
cut = pd.Timestamp("2024-02-25", tz="UTC")
print(f"\nstructure {HTF_RULE} | entree 1h | split {cut.date()} | frais {FEE*100:.3f}%/cote\n")

results = []
for tgt in ("rr", "structure"):
    for val in (True, False):
        for fee, flab in ((0.0, "brut"), (FEE, "net ")):
            cfg = IctConfig(stop_mode="sweep", target=tgt, require_validity=val,
                            fee_per_side=fee, max_wait_choch=48, max_hold=120)
            allt = []
            for s in ASSETS:
                d = frames[s]
                H = d.resample(HTF_RULE, label="left", closed="left").agg(
                    {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
                allt += backtest(H, d, cfg)
            lab = f"tp={tgt:9s} filtre={str(val):5s} {flab}"
            stats(allt, lab + "  TOTAL")
            stats([t for t in allt if t.entered < cut], lab + "  in-sample")
            t_oos = stats([t for t in allt if t.entered >= cut], lab + "  OUT-OF-SAMPLE")
            if fee == FEE and t_oos is not None:
                results.append((t_oos, tgt, val))
                oos = [t for t in allt if t.entered >= cut]
                if oos:
                    print(f"{'':46s} stop median {100*np.median([t.stop_pct for t in oos]):.2f}%"
                          f"  frais {np.median([t.fees_in_r for t in oos]):.3f} R")
            print()

print("=" * 104)
print(f"{len(results)} configurations nettes testees -> barre de Bonferroni t = 2.8")
if results:
    b = max(results)
    print(f"meilleure out-of-sample nette : t = {b[0]:+.2f}  (tp={b[1]}, filtre={b[2]})")
