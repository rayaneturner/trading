"""What 100 USD can and cannot do, given everything measured in this repo.

Percentage fees are scale invariant, so none of the arithmetic degrades at
100 USD - the same strategy returns the same percentage it would on
100,000. What changes is the absolute figure, and the pull toward leverage
that follows from it. Leverage multiplies the fee burden one for one.
"""
import numpy as np

CAP, FEE = 100.0, 0.0007
rng = np.random.default_rng(7)

print("=" * 90)
print("1. CE QUE CHAQUE PISTE DONNE SUR 100 USD EN UN AN")
print("=" * 90)
print(f"{'piste':38s} {'rendement':>10s} {'apres 1 an':>11s} {'gain':>8s} {'/mois':>8s}")
print("-" * 90)
for lab, r in (("carry funding, regime 2021", 0.306),
               ("carry funding, moyenne 2019-2023", 0.160),
               ("carry funding, regime 2022 (baissier)", 0.042),
               ("filtre de tendance MA720h (mesure OOS)", 0.066),
               ("buy & hold BTC (mesure OOS)", 0.013),
               ("ICT sweep, out-of-sample", -0.098 * 40)):
    print(f"{lab:38s} {r*100:+9.1f}% {CAP*(1+r):10.2f}$ "
          f"{CAP*r:+7.2f}$ {CAP*r/12:+7.2f}$")

print()
print("=" * 90)
print("2. LE LEVIER MULTIPLIE LES FRAIS UN POUR UN")
print("=" * 90)
print(f"{'levier':>7s} {'notionnel':>11s} {'cout/aller-retour':>18s} "
      f"{'71 trades/an':>14s} {'en % du capital':>16s}")
print("-" * 90)
for lev in (1, 2, 5, 10, 25, 100):
    notion = CAP * lev
    rt = notion * 2 * FEE
    print(f"{lev:6d}x {notion:10.0f}$ {rt:17.3f}$ {rt*71:13.2f}$ "
          f"{rt*71/CAP*100:15.1f}%")

print()
print("=" * 90)
print("3. 100 -> 1000 USD : COMBIEN DE TEMPS, ET AVEC QUELLE PROBABILITE")
print("=" * 90)
print("   10 000 simulations par ligne, 3 ans de trading, pas mensuel")
print(f"{'approche':34s} {'mediane':>10s} {'P(x10)':>8s} {'P(ruine)':>9s} {'P(perte)':>9s}")
print("-" * 90)
MONTHS = 36
for lab, mu_y, vol_y in (("carry delta-neutre  ~10%/an", 0.10, 0.05),
                         ("filtre tendance  ~6.6%/an",   0.066, 0.36),
                         ("edge nul, levier 1x",          0.00, 0.60),
                         ("edge nul, levier 5x",          0.00, 3.00),
                         ("edge nul, levier 20x",         0.00, 12.0)):
    mu_m, vol_m = mu_y / 12, vol_y / np.sqrt(12)
    paths = np.full(10000, CAP)
    ruined = np.zeros(10000, bool)
    for _ in range(MONTHS):
        step = 1 + rng.normal(mu_m, vol_m, 10000)
        step = np.maximum(step, 0.0)          # a month cannot lose over 100%
        paths = np.where(ruined, 0.0, paths * step)
        ruined |= paths < CAP * 0.10          # under 10 USD you cannot trade
    print(f"{lab:34s} {np.median(paths):9.0f}$ "
          f"{100*(paths >= 10*CAP).mean():7.1f}% {100*ruined.mean():8.1f}% "
          f"{100*(paths < CAP).mean():8.1f}%")

print()
print("=" * 90)
print("4. LE BUDGET DE FRAIS A 100 USD")
print("=" * 90)
for lev in (1, 3, 10):
    budget = CAP * 0.10
    n = budget / (CAP * lev * 2 * FEE)
    print(f"  levier {lev:2d}x -> 10% du capital = {budget:.0f}$/an "
          f"= {n:5.0f} trades/an = {n/52:4.1f}/semaine")
