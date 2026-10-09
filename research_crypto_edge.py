"""Where, if anywhere, is there an exploitable edge in crypto?

This is the record of a search, including what it ruled out, because the
negative results cost the same to produce as a positive one would have and are
worth more than another untested idea.

The data: 227,521 BTC M15 bars and four assets hourly, 2020-2026, from
data/crypto. Everything below splits 65/35 into in-sample and out-of-sample and
charges the venue's real fee.

What was tested, and what it gave:

  1. 25 entry triggers against fixed barriers (pin, engulfing, liquidity sweep,
     breakout, RSI extremes, momentum runs, EMA pullbacks, compression, and
     combinations), long and short, at 3:1 and 4:1.
     -> Not one beat break-even out of sample. Best was 21.0% against 25.8%
        needed. Net expectancy -0.24R to -0.58R.
     -> The all-bars baseline matched the random-walk rate to within 0.4pt over
        6.5 years, so these entries carry no directional information at all.

  2. Mean reversion, 40 combinations of lookback, z-threshold and holding time.
     -> The effect is real and overwhelming statistically: 30-minute returns
        autocorrelate at -0.0384 with t = -12.97 on 227k observations.
     -> And it is worthless. The implied edge is 0.04-0.08% per trade against a
        0.10% round trip. Every out-of-sample t landed between -1.15 and +0.59.
        A thing can be certain and still not pay.

  3. Time-series momentum, lookbacks from 1 hour to 2 months.
     -> In sample it works and works consistently: Sharpe 1.07 to 1.25 across
        BTC, ETH, SOL and BNB at a two-week lookback, which is the same horizon
        the literature reports and the same one src/strategy.py uses.
     -> Out of sample, 2024-04 onward, the average Sharpe across the four assets
        is 0.00. BTC alone holds up at +0.38; ETH, SOL and BNB are negative.
        No lookback from one to six weeks is robust.

So no strategy here is demonstrably profitable on recent data. What momentum
does still provide out of sample is protection: on three assets of four it beat
buy-and-hold on both return and drawdown, halving the worst decline. That is a
risk-management property, not an edge, and it should not be sold as one.

The one measurement that points somewhere: cost expressed in standard
deviations of the move being traded. At 15 minutes it is 0.29, at one hour
0.15, at one day 0.03, at one week 0.01. Scalping does not fail because the
patterns are absent. It fails because the toll is charged on a move too small
to pay it.
"""
