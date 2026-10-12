"""Score the Balanced Price Range on everything in data/crypto.

Four questions, in order:
  1. Does the plain retest rule make money anywhere?
  2. Does the direction of the bias matter, or is the zone just a magnet?
  3. Does any variant survive out-of-sample once the search is paid for?
  4. Does it survive fees?
"""
import sys; sys.path.insert(0, "src")

import itertools

import pandas as pd

from bpr import BprConfig, backtest, find_zones, summarise

SETS = [("BTC 1h", "data/crypto/btc_1h.csv.gz", None),
        ("ETH 1h", "data/crypto/eth_1h.csv.gz", None),
        ("SOL 1h", "data/crypto/sol_1h.csv.gz", None),
        ("BNB 1h", "data/crypto/bnb_1h.csv.gz", None),
        ("BTC 15m", "data/crypto/btc_15m.csv.gz", None),
        ("BTC 4h", "data/crypto/btc_1h.csv.gz", "4h")]
COLS = ["open", "high", "low", "close"]


def load(path, resample=None):
    d = pd.read_csv(path, index_col=0, parse_dates=True)[COLS]
    if resample:
        d = d.resample(resample, label="left", closed="left").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    return d


DATA = {name: load(p, r) for name, p, r in SETS}
SPLIT = {name: d.index[int(0.64 * len(d))] for name, d in DATA.items()}

print("=" * 104)
print("DONNEES")
print("=" * 104)
for name, d in DATA.items():
    z = find_zones(d, BprConfig())
    print(f"{name:8s} {len(d):7d} bougies  {d.index[0].date()} -> {d.index[-1].date()}  "
          f"{len(z):5d} BPR  ({len(d)/max(len(z),1):6.1f} bougies par BPR)  "
          f"split {SPLIT[name].date()}")

print()
print("=" * 104)
print("1. LA REGLE DE BASE : retest au CE, stop au bord de zone, 2R  (zero frais)")
print("=" * 104)
for name, d in DATA.items():
    summarise(backtest(d, BprConfig()), name)

print()
print("=" * 104)
print("2. LE BIAIS A-T-IL UN SENS ?  meme zones, direction inversee  (zero frais)")
print("=" * 104)
for name, d in DATA.items():
    summarise(backtest(d, BprConfig(invert=True)), name + "  inverse")

print()
print("=" * 104)
print("3. DECLENCHEUR x OBJECTIF x STOP, hors echantillon  (zero frais)")
print("=" * 104)
grid = list(itertools.product(("touch", "ce", "through", "reject"),
                              ("rr", "structure"),
                              (1.0, 2.0, 3.0)))
res = []
for name in ("BTC 1h", "ETH 1h", "BTC 15m"):
    d = DATA[name]
    cut = SPLIT[name]
    print(f"--- {name} ---")
    for trig, tgt, rr in grid:
        cfg = BprConfig(trigger=trig, target=tgt, rr=rr)
        tr = [t for t in backtest(d, cfg) if t.entered >= cut]
        s = summarise(tr, f"trig={trig:8s} tp={tgt:9s} rr={rr:.0f}")
        if s:
            res.append((s["t"], s["n"], name, trig, tgt, rr))
    print()
print(f"{len(res)} variantes testees -> barre de Bonferroni ~ t = 3.3 pour conclure a un edge")
if res:
    best = max(res, key=lambda r: r[0])
    print(f"meilleure : {best[2]} trig={best[3]} tp={best[4]} rr={best[5]:.0f}  "
          f"t={best[0]:+.2f} sur n={best[1]}")

print()
print("=" * 104)
print("4. TAILLE DE ZONE : les BPR etroits valent-ils mieux que les larges ?  (zero frais)")
print("=" * 104)
for name in ("BTC 1h", "ETH 1h", "BTC 15m"):
    print(f"--- {name} ---")
    for ovl in (0.05, 0.25, 0.50):
        cfg = BprConfig(trigger="reject", min_ovl_atr=ovl)
        summarise(backtest(DATA[name], cfg), f"chevauchement > {ovl:.2f} ATR")
    print()

print("=" * 104)
print("5. AVEC FRAIS REELS (4 bps par cote, taker crypto)")
print("=" * 104)
for name, d in DATA.items():
    summarise(backtest(d, BprConfig(fee_per_side=0.0004)), name + "  CE")
    summarise(backtest(d, BprConfig(trigger="reject", fee_per_side=0.0004)), name + "  rejet confirme")
    summarise(backtest(d, BprConfig(fee_per_side=0.0004, invert=True)), name + "  inverse")

print()
print("=" * 104)
print("6. LE MEILLEUR CANDIDAT, DEDANS / DEHORS  (rejet confirme, zone > 0.25 ATR, 2R)")
print("=" * 104)
for name, d in DATA.items():
    cut = SPLIT[name]
    tr = backtest(d, BprConfig(trigger="reject", min_ovl_atr=0.25))
    summarise(tr, name + "  total brut")
    summarise([t for t in tr if t.entered < cut], name + "  in-sample")
    summarise([t for t in tr if t.entered >= cut], name + "  OUT-OF-SAMPLE")
    trn = backtest(d, BprConfig(trigger="reject", min_ovl_atr=0.25, fee_per_side=0.0004))
    summarise([t for t in trn if t.entered >= cut], name + "  OUT-OF-SAMPLE net")
    print()
