"""Minimal MCP client for MoonX, for use outside this session.

MoonX publishes no REST API; its only documented surface is MCP over HTTP. Any
MCP client can speak it, including thirty lines of `requests`, which is what
this is. It exists so the strategy can run on a machine that stays up, rather
than in an ephemeral container that only runs when spoken to.

The transport here is NOT exercised by the test suite: this container's network
policy refuses api.moon-x.io, so the request/response shape is written from the
protocol and has to be confirmed on first run against a real endpoint. Every
decision the loop makes is tested separately against a fake client, so a
transport surprise shows up as a connection error rather than as a wrong trade.

The token is read from the environment. It is never a parameter with a default
and never logged: a credential pasted into a transcript is a credential to
revoke.
"""
from __future__ import annotations

import itertools
import json
import os

ENDPOINT = "https://api.moon-x.io/mcp"


class MoonXError(RuntimeError):
    pass


class MoonXClient:
    def __init__(self, token: str | None = None, endpoint: str = ENDPOINT,
                 timeout: float = 30.0):
        self.token = token or os.environ.get("MOONX_MCP_TOKEN")
        if not self.token:
            raise MoonXError(
                "set MOONX_MCP_TOKEN in the environment (do not pass it on the "
                "command line, where it lands in the shell history)")
        self.endpoint, self.timeout = endpoint, timeout
        self._ids = itertools.count(1)
        self._session = None

    def _post(self, payload: dict) -> dict:
        import requests

        if self._session is None:
            self._session = requests.Session()
        r = self._session.post(
            self.endpoint, params={"token": self.token}, json=payload,
            headers={"Accept": "application/json, text/event-stream",
                     "Content-Type": "application/json"},
            timeout=self.timeout)
        r.raise_for_status()
        body = r.text
        # Streamable HTTP may answer as SSE; take the last data: line.
        if body.lstrip().startswith("event:") or "\ndata:" in body:
            chunks = [l[5:].strip() for l in body.splitlines() if l.startswith("data:")]
            if not chunks:
                raise MoonXError("event stream carried no data frame")
            body = chunks[-1]
        return json.loads(body)

    def call(self, tool: str, **arguments):
        reply = self._post({"jsonrpc": "2.0", "id": next(self._ids),
                            "method": "tools/call",
                            "params": {"name": tool, "arguments": arguments}})
        if "error" in reply:
            raise MoonXError(f"{tool}: {reply['error']}")
        result = reply.get("result", {})
        if result.get("isError"):
            raise MoonXError(f"{tool}: {result.get('content')}")
        for block in result.get("content", []):
            if block.get("type") == "text":
                try:
                    return json.loads(block["text"])
                except json.JSONDecodeError:
                    return block["text"]
        return result

    # --- the handful of calls the loop needs -------------------------------

    def candles(self, symbol: str, interval: str, limit: int = 500) -> dict:
        return self.call("get_candles", symbol=symbol, interval=interval, limit=limit)

    def overview(self) -> dict:
        return self.call("get_account_overview")

    def positions(self) -> list:
        return self.call("list_forex_positions") or []

    def orders(self) -> list:
        return self.call("list_forex_orders") or []

    def open_market(self, pair, side, lots, stop_loss, take_profit) -> dict:
        return self.call("open_forex_position", pairId=pair, side=side, lots=lots,
                         stopLoss=stop_loss, takeProfit=take_profit)

    def open_limit(self, pair, side, lots, limit_price, stop_loss, take_profit) -> dict:
        return self.call("open_forex_limit_order", pairId=pair, side=side, lots=lots,
                         limitPrice=limit_price, stopLoss=stop_loss,
                         takeProfit=take_profit)

    def cancel_order(self, order_id: str) -> dict:
        return self.call("cancel_forex_order", orderId=order_id)
