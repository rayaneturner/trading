"""Funding rate carry, the one crypto edge that is documented rather than charted.

A perpetual has no expiry, so the exchange ties it to spot by making longs
pay shorts when the perp trades rich. That payment is not a forecast: it is
a cash flow, collected every eight hours by whoever is short the perp and
long the spot. Nothing here predicts direction.

Two things are measured:
  1. the carry itself, delta neutral, net of fees
  2. funding as a directional signal, which is the part that would be an
     edge rather than a yield
"""
import sys; sys.path.insert(0, "src")
import numpy as np, pandas as pd

FEE = 0.0007
ASSETS = {"BTCUSDT": "btc", "ETHUSDT": "eth", "BNBUSDT": "bnb"}


def funding(sym):
    d = pd.read_csv(f"data/crypto/funding/{sym}.csv.gz")
    d["timestamp"] = pd.to_datetime(d["timestamp"], utc=True)
    return d.set_index("timestamp")["fundingRate"].sort_index()


def price(sym):
    if sym == "btc":
        d = pd.read_csv("data/crypto/btc_15m.csv.gz", index_col=0, parse_dates=True)
        return d["close"].resample("1h").last().dropna()
    return pd.read_csv(f"data/crypto/{sym}_1h.csv.gz", index_col=0, parse_dates=True)["close"]


print("=" * 92)
print("1. LE CARRY DELTA-NEUTRE : short perp + long spot, on encaisse le funding")
print("=" * 92)
print(f"{'actif':6s} {'periode':24s} {'funding/an':>11s} {'frais':>8s} "
      f"{'net/an':>9s} {'8h negatifs':>12s} {'pire mois':>10s}")
print("-" * 92)
for sym, short in ASSETS.items():
    f = funding(sym)
    yrs = (f.index[-1] - f.index[0]).days / 365.25
    gross = f.sum()
    # One entry and one exit on each leg; the position is simply held.
    fees = 4 * FEE
    net_yr = (gross - fees) / yrs
    monthly = f.resample("ME").sum()
    print(f"{short:6s} {str(f.index[0].date())+' -> '+str(f.index[-1].date()):24s} "
          f"{gross/yrs*100:10.2f}% {fees*100:7.2f}% {net_yr*100:8.2f}% "
          f"{100*(f<0).mean():11.1f}% {monthly.min()*100:9.2f}%")

print()
print("=" * 92)
print("2. LE FUNDING COMME SIGNAL DIRECTIONNEL (la partie qui serait un edge)")
print("=" * 92)
print("   funding extreme = positionnement sature. Le prix corrige-t-il ensuite ?")
print()
for sym, short in ASSETS.items():
    f, p = funding(sym), price(short)
    idx = f.index.intersection(p.index)
    if len(idx) < 500:
        p = p.reindex(f.index, method="nearest", tolerance=pd.Timedelta("2h")).dropna()
        idx = f.index.intersection(p.index)
    fr, px = f.loc[idx], p.loc[idx]
    fwd = px.shift(-3) / px - 1          # rendement sur les 24h suivantes
    z = (fr - fr.rolling(90).mean()) / fr.rolling(90).std()
    d = pd.DataFrame({"z": z, "fwd": fwd}).dropna()
    print(f"  {short}  n={len(d)}")
    for lo, hi, lab in ((2.0, 99, "funding tres eleve (z>+2)"),
                        (1.0, 2.0, "funding eleve (+1<z<+2)"),
                        (-99, -1.0, "funding negatif (z<-1)")):
        s = d[(d.z > lo) & (d.z <= hi)]
        if len(s) < 25:
            print(f"     {lab:28s} n={len(s):4d}  trop peu"); continue
        t = s.fwd.mean() / (s.fwd.std() / np.sqrt(len(s)))
        print(f"     {lab:28s} n={len(s):4d}  rendement 24h {s.fwd.mean()*100:+6.3f}%  t={t:+5.2f}")
    print(f"     {'toutes periodes':28s} n={len(d):4d}  rendement 24h {d.fwd.mean()*100:+6.3f}%")
