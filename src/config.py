"""Strategy parameters. Every number here is a decision, not a fitted optimum.

Defaults were chosen to be *robust* (plateau values, see walkforward.py), not to
maximise backtest Sharpe. Changing them changes risk, not just return.
"""
from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class StrategyConfig:
    # --- universe ---
    assets: tuple = ("BTC", "ETH", "SOL")

    # --- trend signal ---
    ema_fast: int = 20          # fast EMA for the crossover vote
    ema_slow: int = 60          # slow EMA for the crossover vote
    sma_long: int = 200         # regime filter vote
    mom_lookback: int = 90      # absolute momentum vote

    # --- risk sizing ---
    target_vol: float = 0.30    # annualised vol budget per *fully invested* asset
    vol_halflife: int = 20      # EWMA halflife (days) for realised vol
    vol_floor: float = 0.20     # never size as if an asset were calmer than this
    max_weight_per_asset: float = 0.60
    max_gross: float = 1.00     # 1.00 = spot, no leverage

    # --- trading ---
    rebalance_weekday: int = 0  # 0 = Monday; None = daily
    no_trade_band: float = 0.05 # skip rebalance legs smaller than 5pp of equity
    cost_per_side: float = 0.0015  # 15 bps = taker fee + slippage, per unit turnover
    cash_yield: float = 0.0     # annualised yield on uninvested cash

    # --- execution ---
    exec_lag_days: int = 1      # signal from close t is traded at close t+1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["assets"] = list(self.assets)
        return d


DEFAULT = StrategyConfig()
