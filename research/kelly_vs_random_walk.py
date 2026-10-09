"""Kabbaj's Kelly formula, with the win rate tied to the ratio as it really is.

The book gives K% = W - (1-W)/R and treats W and R as independent inputs:
raise the payoff ratio, the optimal bet grows. But on a random walk the two
are not independent - P(+R before -1) = 1/(1+R) - and substituting gives

    K = 1/(1+R) - (R/(1+R))/R = 1/(1+R) - 1/(1+R) = 0

identically zero at every ratio. R:R alone buys nothing. Everything comes
from the points of hit rate above the random walk, and those cost fees.
"""
print(f"{'R:R':>5} | {'W aleatoire':>11} | {'Kelly':>7} | "
      f"{'W livre':>8} | {'Kelly':>7} | {'W - frais 0.48R':>15} | {'Kelly':>7}")
print("-" * 82)
for R in (1, 2, 3, 4, 5, 10):
    w_rand = 1 / (1 + R)
    k_rand = w_rand - (1 - w_rand) / R
    # the book's claim: 3:1 and you may be wrong two times out of three
    w_book = 1 / 3 if R == 3 else w_rand + 0.08
    k_book = w_book - (1 - w_book) / R
    # same edge, but each trade pays 0.48 R of fees (measured, crypto M5 stop)
    r_net = R - 0.48
    k_fee = w_book - (1 - w_book) / r_net if r_net > 0 else -1
    print(f"{R:5d} | {w_rand*100:10.1f}% | {k_rand*100:+6.1f}% | "
          f"{w_book*100:7.1f}% | {k_book*100:+6.1f}% | {w_book*100:14.1f}% | {k_fee*100:+6.1f}%")
print("\nColonne 2-3 : le marche seul. Kelly = 0 a TOUS les ratios.")
print("Colonne 4-5 : +8 points d'edge reel. C'est la seule source de Kelly positif.")
print("Colonne 6-7 : meme edge, frais crypto de 0.48 R deduits du gain.")
