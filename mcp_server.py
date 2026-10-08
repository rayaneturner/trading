#!/usr/bin/env python3
"""MCP server: the surface an external agent (Claude or anything else) is given.

Run it from an MCP client config:

    {"mcpServers": {"trading": {"command": "python",
                                "args": ["/path/to/trading/mcp_server.py"],
                                "env": {"TRADING_EXCHANGE": "kraken"}}}}

The design decision that matters: **this server does not accept target weights.**
An agent can read state and propose *tilts* in [-1, +1] against the deterministic
rule; the server computes the weights itself and clamps them to the risk envelope.
So the worst a confused, jailbroken or hostile client can do through this interface
is move the portfolio to cash. It cannot lever up, cannot short, cannot buy an
asset the trend rule says is falling, and cannot withdraw anything.

`execute_rebalance` additionally requires TRADING_LIVE=1 in this process's
environment. Without it every call is a dry run that returns the orders it would
have sent. A tool call cannot flip that switch.
"""
from __future__ import annotations

import json
import os

from mcp.server.mcpserver import MCPServer

from src import datafeed
from src.agent import AgentDecision, RiskEnvelope, apply_envelope, build_snapshot
from src.config import StrategyConfig
from src.execution import CcxtExecutor, ExecutionLimits, append_log, plan_orders
from src.strategy import live_weights

EXCHANGE = os.environ.get("TRADING_EXCHANGE", "kraken")
QUOTE = os.environ.get("TRADING_QUOTE", "USD")
ASSETS = tuple(a.strip().upper() for a in os.environ.get("TRADING_ASSETS", "BTC,ETH,SOL").split(","))
MAX_TILT_UP = float(os.environ.get("TRADING_MAX_TILT_UP", "0.10"))
MAX_ORDER = float(os.environ.get("TRADING_MAX_ORDER", "5000"))
LOG = os.environ.get("TRADING_LOG", "out/mcp.jsonl")

server = MCPServer(
    name="crypto-trend-portfolio",
    instructions=(
        "A long/flat spot crypto portfolio driven by a deterministic trend rule. "
        "You may read state and propose tilts against the rule; you cannot set weights "
        "directly. Tilt -1 flattens a position, 0 follows the rule, +1 adds the maximum "
        "permitted increment. A positive tilt on an asset the rule holds at zero is "
        "discarded. Default to 0: deviating from a rule with a measured drawdown needs a "
        "reason visible in the numbers."
    ),
    version="0.1.0",
)


def _prices() -> tuple:
    frame = datafeed.fetch_ccxt(ASSETS, exchange=EXCHANGE, quote=QUOTE).iloc[:-1]
    cfg0 = StrategyConfig(assets=ASSETS)
    frame = datafeed.clean(frame, min_history=cfg0.sma_long + cfg0.mom_lookback)
    cfg = StrategyConfig(assets=tuple(frame.columns))
    return frame, cfg


def _envelope(cfg: StrategyConfig) -> RiskEnvelope:
    return RiskEnvelope(max_tilt_up=MAX_TILT_UP,
                        max_weight_per_asset=cfg.max_weight_per_asset,
                        max_gross=cfg.max_gross)


@server.tool(description="Point-in-time features and the deterministic rule's target weights.")
def get_signal() -> dict:
    prices, cfg = _prices()
    stale = {a: n for a, n in datafeed.stale_tail(prices).items() if n >= 2}
    return {
        "snapshot": build_snapshot(prices, cfg),
        "rule_weights": {k: round(float(v), 4) for k, v in live_weights(prices, cfg).items()},
        "stale_feeds": stale,
        "tradeable": not stale,
    }


@server.tool(description="Current balances, prices and equity on the configured exchange.")
def get_portfolio() -> dict:
    prices, cfg = _prices()
    ex = CcxtExecutor(EXCHANGE, QUOTE, ExecutionLimits(), live=False)
    holdings, spot, cash = ex.snapshot(prices.columns)
    equity = cash + sum(holdings.get(a, 0.0) * spot[a] for a in prices.columns)
    return {"holdings_units": holdings, "prices": spot, "cash": cash,
            "equity": round(equity, 2),
            "weights": {a: round(holdings.get(a, 0.0) * spot[a] / equity, 4)
                        for a in prices.columns} if equity > 0 else {}}


@server.tool(description=(
    "Propose tilts in [-1, 1] per asset against the rule and get the orders they imply. "
    "Returns the clamped weights and the order list; sends nothing."))
def plan_rebalance(tilts: dict[str, float], reason: str = "") -> dict:
    prices, cfg = _prices()
    env = _envelope(cfg)
    rule = live_weights(prices, cfg)
    decision = AgentDecision(tilts={k.upper(): float(v) for k, v in tilts.items()},
                             regime="unclear", confidence=0.0, note=reason, model="mcp-client")
    final = apply_envelope(rule, decision, env)

    limits = ExecutionLimits(max_order_notional=MAX_ORDER, no_trade_band=cfg.no_trade_band)
    ex = CcxtExecutor(EXCHANGE, QUOTE, limits, live=False)
    holdings, spot, cash = ex.snapshot(prices.columns)
    orders, diag = plan_orders(final, holdings, spot, cash, limits)
    record = {"tool": "plan_rebalance", "requested_tilts": tilts, "reason": reason,
              "rule_weights": {k: round(float(v), 4) for k, v in rule.items()},
              "final_weights": {k: round(float(v), 4) for k, v in final.items()},
              "orders": [o.to_dict() for o in orders], "diagnostics": diag}
    append_log(LOG, record)
    return record


@server.tool(description=(
    "Send the orders implied by these tilts. Requires TRADING_LIVE=1 in the server's "
    "environment; otherwise returns a dry run. Cannot exceed the risk envelope."))
def execute_rebalance(tilts: dict[str, float], reason: str = "") -> dict:
    prices, cfg = _prices()
    env = _envelope(cfg)
    stale = {a: n for a, n in datafeed.stale_tail(prices).items() if n >= 2}
    if stale:
        return {"status": "refused", "why": "stale price feed", "stale_feeds": stale}

    rule = live_weights(prices, cfg)
    decision = AgentDecision(tilts={k.upper(): float(v) for k, v in tilts.items()},
                             regime="unclear", confidence=0.0, note=reason, model="mcp-client")
    final = apply_envelope(rule, decision, env)

    limits = ExecutionLimits(max_order_notional=MAX_ORDER, no_trade_band=cfg.no_trade_band)
    ex = CcxtExecutor(EXCHANGE, QUOTE, limits, live=True)
    holdings, spot, cash = ex.snapshot(prices.columns)
    orders, diag = plan_orders(final, holdings, spot, cash, limits)
    receipts = ex.execute(orders)
    record = {"tool": "execute_rebalance", "mode": "live" if ex.live else "dry_run",
              "requested_tilts": tilts, "reason": reason,
              "final_weights": {k: round(float(v), 4) for k, v in final.items()},
              "orders": [o.to_dict() for o in orders], "diagnostics": diag,
              "receipts": receipts}
    append_log(LOG, record)
    return record


@server.tool(description="The risk envelope and execution limits this server enforces.")
def get_limits() -> dict:
    cfg = StrategyConfig(assets=ASSETS)
    env = _envelope(cfg)
    return {"envelope": {"max_tilt_up": env.max_tilt_up, "allow_new_longs": env.allow_new_longs,
                         "max_weight_per_asset": env.max_weight_per_asset,
                         "max_gross": env.max_gross},
            "execution": {"max_order_notional": MAX_ORDER,
                          "no_trade_band": cfg.no_trade_band,
                          "shorting": False, "leverage": False},
            "live_trading_enabled": os.environ.get("TRADING_LIVE") == "1",
            "exchange": EXCHANGE, "assets": list(ASSETS)}


if __name__ == "__main__":
    server.run(transport="stdio")
