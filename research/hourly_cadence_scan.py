"""What survives an HOURLY decision cadence and crypto perp fees.

The agent wakes once an hour. It cannot react intrabar. So the only things
testable are positions that stay valid for an hour or more. Fees are charged
on every change of position, which makes turnover the thing that kills you,
not win rate.
"""
import pandas as pd, numpy as np, glob

FEE = 0.0007          # per side, MoonX crypto futures
BARS_YEAR = 24 * 365

def load(sym):
    d = pd.read_csv(f"data/crypto/{sym}_1h.csv.gz", index_col=0, parse_dates=True)
    return d["close"]

def stats(ret, pos, label):
    """ret = bar-to-bar asset return, pos = position held OVER that bar."""
    turn = pos.diff().abs().fillna(pos.abs())
    net = pos * ret - turn * FEE
    gross = pos * ret
    n = len(net)
    if n == 0 or net.std() == 0:
        print(f"{label:34s} n/a"); return
    sh = net.mean() / net.std() * np.sqrt(BARS_YEAR)
    shg = gross.mean() / gross.std() * np.sqrt(BARS_YEAR)
    t = net.mean() / (net.std() / np.sqrt(n))
    eq = (1 + net).cumprod()
    dd = (1 - eq / eq.cummax()).max()
    trades_yr = turn.sum() / (n / BARS_YEAR) / 2
    cagr = eq.iloc[-1] ** (BARS_YEAR / n) - 1
    print(f"{label:34s} Sharpe {sh:+5.2f} (brut {shg:+5.2f})  CAGR {cagr*100:+7.1f}%  "
          f"DD {dd*100:5.1f}%  t {t:+5.2f}  {trades_yr:6.0f} trades/an")
    return sh

close = {s: load(s) for s in ("btc", "eth", "sol", "bnb")}
btc = close["btc"]
ret = btc.pct_change().shift(-1)        # return realised AFTER the decision bar
cut = int(0.64 * len(btc))

print("=" * 100)
print("A. SUIVI DE TENDANCE time-series sur BTC, decision horaire, long seul")
print("=" * 100)
for n in (24, 72, 168, 336, 720, 1440, 2160):
    pos = (btc > btc.rolling(n).mean()).astype(float)
    d = pd.DataFrame({"r": ret, "p": pos}).dropna()
    stats(d.r.iloc[:cut], d.p.iloc[:cut], f"  MA{n:4d}h  IN-SAMPLE")
    stats(d.r.iloc[cut:], d.p.iloc[cut:], f"  MA{n:4d}h  OUT-OF-SAMPLE")
bh = pd.DataFrame({"r": ret, "p": 1.0}).dropna()
stats(bh.r.iloc[:cut], bh.p.iloc[:cut], "  buy&hold IN-SAMPLE")
stats(bh.r.iloc[cut:], bh.p.iloc[cut:], "  buy&hold OUT-OF-SAMPLE")

print()
print("=" * 100)
print("B. MEME CHOSE EN LONG/SHORT (+1 / -1)")
print("=" * 100)
for n in (168, 336, 720, 1440):
    pos = np.where(btc > btc.rolling(n).mean(), 1.0, -1.0)
    d = pd.DataFrame({"r": ret, "p": pos}, index=btc.index).dropna()
    stats(d.r.iloc[:cut], d.p.iloc[:cut], f"  MA{n:4d}h L/S  IN-SAMPLE")
    stats(d.r.iloc[cut:], d.p.iloc[cut:], f"  MA{n:4d}h L/S  OUT-OF-SAMPLE")

print()
print("=" * 100)
print("C. CROSS-SECTIONAL : classer 4 actifs par rendement passe, long top / short bottom")
print("=" * 100)
px = pd.DataFrame(close).dropna()
rets = px.pct_change().shift(-1)
c2 = int(0.64 * len(px))
for look in (24, 72, 168, 336, 720):
    for hold in (4, 24, 168):
        mom = px.pct_change(look)
        rank = mom.rank(axis=1)
        top, bot = rank.max(axis=1), rank.min(axis=1)
        w = (rank.eq(top, axis=0).astype(float) - rank.eq(bot, axis=0).astype(float))
        w = w.where(px.index.to_series().groupby(
                np.arange(len(px)) // hold).transform("first").eq(px.index.to_series()))
        w = w.ffill().fillna(0.0) / 2
        pnl = (w * rets).sum(axis=1)
        turn = w.diff().abs().sum(axis=1).fillna(0)
        net = (pnl - turn * FEE).dropna()
        if net.std() == 0: continue
        for lo, hi, lab in ((0, c2, "IS "), (c2, len(net), "OOS")):
            s = net.iloc[lo:hi]
            sh = s.mean()/s.std()*np.sqrt(BARS_YEAR)
            t = s.mean()/(s.std()/np.sqrt(len(s)))
            eq=(1+s).cumprod()
            print(f"  look{look:4d}h hold{hold:4d}h {lab}  Sharpe {sh:+5.2f}  "
                  f"t {t:+5.2f}  final x{eq.iloc[-1]:6.2f}")
