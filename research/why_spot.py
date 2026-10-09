"""Why the spot leg is the whole trade, measured rather than argued.

Funding is paid by perp longs to perp shorts. Collecting it means being
short the perp. But a short perp is also a short on the price, and the
price moves far more than the funding does. The spot leg exists to cancel
that, leaving only the cash flow.
"""
import numpy as np, pandas as pd

FEE = 0.0007

f = pd.read_csv("data/crypto/funding/BTCUSDT.csv.gz")
f["timestamp"] = pd.to_datetime(f["timestamp"], utc=True)
f = f.set_index("timestamp")["fundingRate"].sort_index()

p = pd.read_csv("data/crypto/btc_15m.csv.gz", index_col=0, parse_dates=True)["close"]
p = p.resample("8h").last().dropna()

idx = f.index.floor("8h").intersection(p.index)
fr = f.copy(); fr.index = fr.index.floor("8h")
fr = fr[~fr.index.duplicated()].reindex(idx)
px = p.reindex(idx)
ret = px.pct_change().fillna(0.0)          # price move over each 8h period
fr = fr.fillna(0.0)

print(f"BTC, {len(idx)} periodes de 8h, {idx[0].date()} -> {idx[-1].date()}\n")
print("=" * 86)
print("LES DEUX FACONS D'ENCAISSER LE FUNDING")
print("=" * 86)

strategies = {
    "short perp SEUL (sans spot)":      -ret + fr,
    "short perp + long spot (neutre)":   fr,
    "long spot seul (reference)":        ret,
}
print(f"{'':34s} {'rendement/an':>13s} {'volatilite':>11s} {'Sharpe':>8s} "
      f"{'pire mois':>10s} {'pire jour':>10s}")
print("-" * 86)
yrs = (idx[-1] - idx[0]).days / 365.25
for lab, s in strategies.items():
    cum = (1 + s).prod() - 1
    ann = (1 + cum) ** (1 / yrs) - 1
    vol = s.std() * np.sqrt(3 * 365)
    sh = s.mean() / s.std() * np.sqrt(3 * 365) if s.std() > 0 else np.nan
    m = s.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    print(f"{lab:34s} {ann*100:+12.1f}% {vol*100:10.1f}% {sh:+7.2f} "
          f"{m.min()*100:+9.1f}% {s.min()*100:+9.1f}%")

print()
print("=" * 86)
print("SUR TES 100 USD, LA MEME CHOSE EN DOLLARS")
print("=" * 86)
print(f"{'':34s} {'apres 1 an':>12s} {'pire mois':>11s} {'pire periode 8h':>17s}")
print("-" * 86)
for lab, s in strategies.items():
    ann = (1 + ((1 + s).prod() - 1)) ** (1 / yrs) - 1
    m = s.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    print(f"{lab:34s} {100*(1+ann):11.2f}$ {100*m.min():+10.2f}$ {100*s.min():+16.2f}$")

print()
print("=" * 86)
print("CE QUE LE FUNDING PESE FACE AU PRIX, PAR PERIODE DE 8H")
print("=" * 86)
print(f"  funding median        {fr.abs().median()*100:7.4f}%")
print(f"  mouvement de prix median {ret.abs().median()*100:7.4f}%")
print(f"  rapport : le prix bouge {ret.abs().median()/fr.abs().median():.0f}x plus que le funding")
print()
print("  Donc sans la jambe spot, 1 periode sur 2 voit le prix effacer")
print(f"  {ret.abs().median()/fr.abs().median():.0f} fois le funding encaisse. Le carry n'existe pas.")
