"""
Minimal local-only Monero RPC transport utilities.

This module provides a small, focused HTTP transport for talking to a locally
reachable Monero daemon (monerod) and wallet RPC (monero-wallet-rpc). No
remote node discovery or multi-node logic is included.
"""
from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests


logger = logging.getLogger("mcp.transport")


@dataclass
class MoneroRPCConfig:
    """Configuration for a single Monero RPC endpoint."""

    host: str = os.getenv("MONERO_RPC_HOST", "127.0.0.1")
    port: int = int(os.getenv("MONERO_RPC_PORT", "18081"))  # monerod default
    path: str = "/json_rpc"
    scheme: str = os.getenv("MONERO_RPC_SCHEME", "http")
    username: Optional[str] = os.getenv("MONERO_RPC_USER")
    password: Optional[str] = os.getenv("MONERO_RPC_PASS")
    timeout: int = int(os.getenv("MONERO_RPC_TIMEOUT", "10"))
    rpc_type: str = "daemon"  # "daemon" or "wallet"

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def rpc_url(self) -> str:
        return f"{self.base_url}{self.path}"

    @classmethod
    def from_url(cls, url: str, *, rpc_type: str = "daemon", timeout: int | None = None) -> "MoneroRPCConfig":
        parsed = urlparse(url)
        path = parsed.path or "/json_rpc"
        port = parsed.port or (18082 if rpc_type == "wallet" else 18081)
        return cls(
            host=parsed.hostname or "127.0.0.1",
            port=port,
            path=path,
            scheme=parsed.scheme or "http",
            timeout=timeout or int(os.getenv("MONERO_RPC_TIMEOUT", "10")),
            rpc_type=rpc_type,
        )


class MCPTransportError(Exception):
    """Base exception for MCP transport errors."""


class MoneroRPCError(MCPTransportError):
    """Exception raised for Monero RPC specific errors."""

    def __init__(self, message: str, *, error_code: Optional[int] = None, error_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_data = error_data or {}


class MCPTransport:
    """Simple HTTP JSON-RPC transport for a single endpoint."""

    def __init__(self, config: MoneroRPCConfig):
        self.config = config
        self._session = requests.Session()

    def call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": "0", "method": method}
        if params:
            payload["params"] = params
        auth = (self.config.username, self.config.password) if (self.config.username and self.config.password) else None
        try:
            resp = self._session.post(
                self.config.rpc_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=self.config.timeout,
                auth=auth,
            )
        except requests.RequestException as e:
            raise MCPTransportError(f"RPC connection error to {self.config.rpc_url}: {e}") from e

        try:
            data = resp.json()
        except ValueError:
            raise MCPTransportError(f"Non-JSON response from RPC: HTTP {resp.status_code}")

        if "error" in data:
            err = data["error"]
            raise MoneroRPCError(
                err.get("message", "RPC error"),
                error_code=err.get("code"),
                error_data=err.get("data"),
            )
        return data.get("result", data)

    def get_plain(self, path: str) -> Dict[str, Any]:
        """Call non-JSON endpoints like /get_height that return JSON without JSON-RPC envelope."""
        url = f"{self.config.base_url}{path}"
        try:
            resp = self._session.get(url, timeout=self.config.timeout, headers={"Content-Type": "application/json"})
            return resp.json()
        except requests.RequestException as e:
            raise MCPTransportError(f"HTTP error calling {url}: {e}") from e
        except ValueError:
            raise MCPTransportError(f"Non-JSON response from {url}")

    def test_connection(self) -> bool:
        try:
            if self.config.rpc_type == "wallet":
                self.call("get_version")
            else:
                self.call("get_info")
            return True
        except MCPTransportError:
            return False

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self) -> "MCPTransport":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# Convenience factories (local-only)

def create_daemon_transport(host: str | None = None, port: int | None = None) -> MCPTransport:
    host = host or os.getenv("MONERO_DAEMON_RPC_HOST", os.getenv("MONERO_RPC_HOST", "127.0.0.1"))
    port = port or int(os.getenv("MONERO_DAEMON_RPC_PORT", os.getenv("MONERO_RPC_PORT", "18081")))
    cfg = MoneroRPCConfig(host=host, port=port, path="/json_rpc", rpc_type="daemon")
    return MCPTransport(cfg)


def create_wallet_transport(host: str | None = None, port: int | None = None) -> MCPTransport:
    # Wallet RPC runs on 18082 by default to avoid clashing with monerod (18081)
    host = host or os.getenv("MONERO_WALLET_RPC_HOST", os.getenv("MONERO_RPC_HOST", "127.0.0.1"))
    port = port or int(os.getenv("MONERO_WALLET_RPC_PORT", "18082"))
    cfg = MoneroRPCConfig(host=host, port=port, path="/json_rpc", rpc_type="wallet")
    return MCPTransport(cfg)
