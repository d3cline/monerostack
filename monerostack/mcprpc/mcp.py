"""
Monero MCP tools, structured like the django-mcp-server bird_counter example:
- Class-based MCPToolset for clean tool grouping
- Optional secondary endpoint via DjangoMCP
- No local daemons; all calls hit Cake Wallet public nodes by region
"""

from typing import Any, List, Optional

import requests
from django.conf import settings

# Match the example's import style and public API
from mcp_server import mcp_server as mcp
from mcp_server.djangomcp import DjangoMCP
from mcp_server import MCPToolset  # (we're not using DRF publishers in this minimal app)


# ── Low-level JSON-RPC helper ────────────────────────────────────────────────
def _daemon_url() -> str:
    nodes = getattr(settings, "MONERO_NODES", {})
    region = getattr(settings, "MONERO_REGION", "us")
    url = nodes.get(region) or nodes.get("default")
    if not url:
        raise RuntimeError("MONERO_NODES / MONERO_REGION misconfigured; no node URL available.")
    return url


def _monero_rpc(method: str, params: Optional[dict[str, Any] | List[Any]] = None, *, timeout: Optional[int] = None) -> dict:
    """
    POST a Monero JSON-RPC call to the current region's Cake node.
    Returns the 'result' dict on success, or {'error': {...}} if daemon returns a JSON-RPC error.
    Raises requests.* exceptions for HTTP/transport failures.
    """
    url = _daemon_url()
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": "0", "method": method}
    if params is not None:
        payload["params"] = params
    r = requests.post(url, json=payload, timeout=timeout or getattr(settings, "MONERO_RPC_TIMEOUT", 20))
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        return {"error": data["error"], "method": method}
    return data.get("result", data)


# ── Primary toolset (daemon reads) ───────────────────────────────────────────
class MoneroDaemon(MCPToolset):
    """
    Public daemon (read-only) methods. These do NOT require a wallet.
    """

    def get_info(self) -> dict:
        """Return high-level daemon status (height, target_height, difficulty, nettype, status, etc.)."""
        return _monero_rpc("get_info")

    def get_block_count(self) -> dict:
        """Return {'count': <height>} with the current chain height."""
        return _monero_rpc("get_block_count")

    def get_last_block_header(self) -> dict:
        """Return the latest block header as {'block_header': {...}}."""
        return _monero_rpc("get_last_block_header")

    def get_block(self, height: int | None = None, hash: str | None = None) -> dict:
        """
        Get a block by height or by hash (exactly one must be provided).
        """
        if (height is None) == (hash is None):
            return {"error": "Provide exactly one of: height OR hash"}
        params: dict[str, Any] = {}
        if height is not None:
            params["height"] = int(height)
        else:
            params["hash"] = str(hash)
        return _monero_rpc("get_block", params)

    def get_block_headers_range(self, start_height: int, end_height: int) -> dict:
        """Get block headers within an inclusive height range."""
        return _monero_rpc(
            "get_block_headers_range",
            {"start_height": int(start_height), "end_height": int(end_height)},
        )

    def on_get_block_hash(self, height: int) -> dict:
        """Return the block hash (hex) at 'height' using the legacy positional-array call."""
        return _monero_rpc("on_get_block_hash", [int(height)])

    def get_transactions(self, txs_hashes: List[str], decode_as_json: bool = True, prune: bool = False) -> dict:
        """
        Get transactions by their hashes.

        Args:
          - txs_hashes: list of TXIDs (hex)
          - decode_as_json: ask daemon to return parsed JSON
          - prune: request pruned (smaller) payloads if the node supports it
        """
        return _monero_rpc(
            "get_transactions",
            {
                "txs_hashes": list(txs_hashes or []),
                "decode_as_json": bool(decode_as_json),
                "prune": bool(prune),
            },
        )


# ── Config toolset (region selection at runtime) ─────────────────────────────
class MoneroConfig(MCPToolset):
    """Runtime helpers: read/change the region used for RPC (in-memory only)."""

    def get_region(self) -> dict:
        """Return the current region and URL."""
        region = getattr(settings, "MONERO_REGION", "us")
        return {"region": region, "url": _daemon_url()}

    def set_region(self, region: str) -> dict:
        """
        Change the region for this process (in-memory). Valid keys are those in settings.MONERO_NODES.
        For a persistent change, set MONERO_REGION env var or edit settings.py.
        """
        nodes = getattr(settings, "MONERO_NODES", {})
        if region not in nodes:
            return {"error": f"Unknown region '{region}'. Valid: {', '.join(nodes.keys())}"}
        settings.MONERO_REGION = region
        return {"status": "ok", "region": region, "url": nodes[region]}


# ── Optional secondary MCP endpoint (mirrors example pattern) ────────────────
alt_mcp = DjangoMCP(name="monero-alt")

@alt_mcp.tool()
async def ping() -> dict:
    """Quick health probe for the current node. Returns 'ok' plus height/target when available."""
    try:
        info = _monero_rpc("get_info")
        if "error" in info:
            return {"ok": False, "error": info["error"]}
        return {
            "ok": True,
            "height": info.get("height"),
            "target_height": info.get("target_height") or info.get("height"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
