import sys; sys.path.insert(0, "src")
import numpy as np, pandas as pd
from ict_sweep import IctConfig, backtest, summarise

d = pd.read_csv("data/crypto/btc_15m.csv.gz", index_col=0, parse_dates=True)[
        ["open", "high", "low", "close"]]
H = d.resample("4h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
cut = d.index[int(0.64 * len(d))]
print(f"HTF 4h {len(H)} bougies | LTF 15m {len(d)} bougies | split {cut.date()}\n")

def run(cfg, label):
    tr = backtest(H, d, cfg)
    a = summarise(tr, label + "  TOTAL")
    summarise([t for t in tr if t.entered < cut],  label + "  in-sample")
    o = summarise([t for t in tr if t.entered >= cut], label + "  OUT-OF-SAMPLE")
    return a, o

print("=" * 96)
print("LE FILTRE DU PDF : la bougie suivant le sweep ne doit ni depasser ni cloturer sous lui")
print("=" * 96)
run(IctConfig(require_validity=True),  "avec filtre   ")
print()
run(IctConfig(require_validity=False), "sans filtre   ")

print()
print("=" * 96)
print("VARIANTES (out-of-sample, zero frais)")
print("=" * 96)
res = []
for zone in ("mid", "ob", "fvg"):
    for tgt in ("structure", "rr"):
        for val in (True, False):
            cfg = IctConfig(entry_zone=zone, target=tgt, require_validity=val)
            tr = [t for t in backtest(H, d, cfg) if t.entered >= cut]
            s = summarise(tr, f"zone={zone:4s} tp={tgt:9s} filtre={str(val):5s}")
            if s: res.append((s["t"], s["n"], zone, tgt, val))
print(f"\n{len(res)} variantes testees -> barre de Bonferroni ~ t = 3.0")
if res:
    best = max(res, key=lambda r: r[0])
    print(f"meilleure : t = {best[0]:+.2f} sur {best[1]} trades "
          f"(zone={best[2]}, tp={best[3]}, filtre={best[4]})")

print()
print("=" * 96)
print("AVEC LES FRAIS REELS MOONX CRYPTO (0.070%/cote), out-of-sample")
print("=" * 96)
tr = [t for t in backtest(H, d, IctConfig(fee_per_side=0.0007)) if t.entered >= cut]
summarise(tr, "ICT sweep + frais")
if tr:
    print(f"  stop median {100*np.median([t.stop_pct for t in tr]):.3f}%  "
          f"-> frais medians {np.median([t.fees_in_r for t in tr]):.3f} R")
