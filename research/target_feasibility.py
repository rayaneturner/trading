"""What a 5-10%/month target actually requires. Pure arithmetic, no backtest."""
import numpy as np

print("=" * 86)
print("1. TAUX DE REUSSITE REQUIS a 2:1, 3 trades/jour (90/mois), pour +5%/mois net")
print("=" * 86)
print(f"{'stop':>7s} {'risque':>7s} | " + " | ".join(f"{t:>14s}" for t in
      ("MoonX crypto", "MoonX indices", "broker 0.002%")))
print(f"{'':>7s} {'/trade':>7s} | " + " | ".join(f"{'0.070%/cote':>14s}" for _ in range(1)) +
      f" | {'0.010%/cote':>14s} | {'0.002%/cote':>14s}")
print("-" * 86)
need_per_trade = 0.05 / 90          # fraction du capital, par trade
for stop in (0.0029, 0.01, 0.03, 0.06):
    for f in (0.01, 0.02):
        row = []
        for fee in (0.0007, 0.0001, 0.00002):
            fee_R = 2 * fee / stop                 # aller-retour, en unites de stop
            need_R = fee_R + need_per_trade / f    # esperance brute requise
            p = (need_R + 1) / 3                   # E = 3p-1 a 2:1
            row.append("impossible" if p > 1 else f"{p*100:5.1f}%  ({fee_R:.2f}R)")
        print(f"{stop*100:6.2f}% {f*100:6.1f}% | " + " | ".join(f"{c:>14s}" for c in row))
print("\naleatoire a 2:1 = 33.3%   |   mesure sur 11 129 trades H4-break = 32.1%")

print()
print("=" * 86)
print("2. CROISSANCE MAXIMALE ATTEIGNABLE POUR UN SHARPE DONNE (critere de Kelly)")
print("=" * 86)
print("   croissance log/an = S^2/2 a Kelly plein, 3/8*S^2 a demi-Kelly")
print(f"{'Sharpe':>8s} | {'Kelly plein':>22s} | {'demi-Kelly':>22s} | {'DD typique':>12s}")
print("-" * 86)
for S in (0.36, 0.5, 0.75, 1.0, 1.08, 1.25, 1.5, 1.75, 2.5):
    g_full, g_half = S**2 / 2, 3/8 * S**2
    m_full = np.exp(g_full / 12) - 1
    m_half = np.exp(g_half / 12) - 1
    print(f"{S:8.2f} | {g_full*100:7.1f}%/an = {m_full*100:5.2f}%/mois | "
          f"{g_half*100:7.1f}%/an = {m_half*100:5.2f}%/mois | {'~50%' :>12s}")

print()
print("=" * 86)
print("3. SHARPE REQUIS PAR LA CIBLE")
print("=" * 86)
for m in (0.05, 0.10):
    g = 12 * np.log(1 + m)
    print(f"  {m*100:4.0f}%/mois = {(1+m)**12-1:6.1%}/an  ->  "
          f"Sharpe {np.sqrt(2*g):.2f} a Kelly plein, {np.sqrt(g/(3/8)):.2f} a demi-Kelly")
print(f"\n  meilleur resultat out-of-sample mesure cette session : Sharpe 0.36")
print(f"  buy & hold BTC out-of-sample                          : Sharpe 0.27")
print(f"  Renaissance Medallion, 30 ans, net de frais           : Sharpe ~2.5")

print()
print("=" * 86)
print("4. COUT DES FRAIS SEULS, en % du capital par an, a 3 trades/jour")
print("=" * 86)
for fee, lab in ((0.0007, "MoonX crypto 0.070%"), (0.0001, "MoonX indices 0.010%")):
    for lev in (1, 3, 10):
        print(f"  {lab}  levier {lev:2d}x  ->  {1095 * 2 * fee * lev * 100:7.1f}% du capital/an")
