import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Literal, List, Optional

from mcp_server import MCPToolset

from .utils import (
    MCPTransport,
    MoneroRPCConfig,
    create_daemon_transport,
    create_wallet_transport,
)

logger = logging.getLogger("mcp.monero")


# Minimal local-only Monero RPC Client
class MoneroAPI:
    def __init__(self, rpc_url: Optional[str] = None, wallet_rpc_url: Optional[str] = None):
        if rpc_url:
            cfg = MoneroRPCConfig.from_url(rpc_url, rpc_type="daemon")
            self.daemon_transport = MCPTransport(cfg)
        else:
            self.daemon_transport = create_daemon_transport()

        self.wallet_transport: Optional[MCPTransport] = None
        if wallet_rpc_url:
            wcfg = MoneroRPCConfig.from_url(wallet_rpc_url, rpc_type="wallet")
            self.wallet_transport = MCPTransport(wcfg)

    def _rpc_call(self, method: str, params: Optional[Dict[str, Any]] = None, *, use_wallet: bool = False) -> Dict[str, Any]:
        if use_wallet:
            if not self.wallet_transport:
                self.wallet_transport = create_wallet_transport()
            return self.wallet_transport.call(method, params)
        return self.daemon_transport.call(method, params)

    # Daemon methods
    def get_info(self) -> dict:
        return self._rpc_call("get_info")

    def get_daemon_height(self) -> dict:
        return self.daemon_transport.get_plain("/get_height")

    def get_last_block_header(self) -> dict:
        return self._rpc_call("get_last_block_header")

    def get_block(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("get_block", data)

    # Wallet RPC Methods
    def create_wallet(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("create_wallet", data, use_wallet=True)

    def restore_deterministic_wallet(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("restore_deterministic_wallet", data, use_wallet=True)

    def open_wallet(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("open_wallet", data, use_wallet=True)

    def close_wallet(self) -> dict:
        return self._rpc_call("close_wallet", {}, use_wallet=True)

    def get_balance(self, data: Optional[Dict[str, Any]] = None) -> dict:
        return self._rpc_call("get_balance", data or {}, use_wallet=True)

    def get_address(self, data: Optional[Dict[str, Any]] = None) -> dict:
        return self._rpc_call("get_address", data or {}, use_wallet=True)

    def create_address(self, data: Optional[Dict[str, Any]] = None) -> dict:
        return self._rpc_call("create_address", data or {}, use_wallet=True)

    def transfer(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("transfer", data, use_wallet=True)

    def transfer_split(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("transfer_split", data, use_wallet=True)

    def sweep_all(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("sweep_all", data, use_wallet=True)

    def get_transfers(self, data: Optional[Dict[str, Any]] = None) -> dict:
        return self._rpc_call("get_transfers", data or {}, use_wallet=True)

    def get_transfer_by_txid(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("get_transfer_by_txid", data, use_wallet=True)

    def refresh(self, data: Optional[Dict[str, Any]] = None) -> dict:
        return self._rpc_call("refresh", data or {}, use_wallet=True)

    def rescan_blockchain(self) -> dict:
        return self._rpc_call("rescan_blockchain", {}, use_wallet=True)

    def get_wallet_height(self) -> dict:
        return self._rpc_call("get_height", {}, use_wallet=True)

    def query_key(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("query_key", data, use_wallet=True)

    def make_integrated_address(self, data: Optional[Dict[str, Any]] = None) -> dict:
        return self._rpc_call("make_integrated_address", data or {}, use_wallet=True)

    def split_integrated_address(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("split_integrated_address", data, use_wallet=True)


# Wallet Manager delegating to Django management commands
class WalletManager:
    def __init__(self, wallet_dir: Optional[str] = None):
        self.wallet_dir = wallet_dir or os.path.expanduser("~/.monero/wallets")

    def ensure_wallet_dir(self) -> None:
        os.makedirs(self.wallet_dir, mode=0o700, exist_ok=True)

    def get_wallet_path(self, wallet_name: str) -> str:
        return str(Path(self.wallet_dir) / wallet_name)

    def wallet_exists(self, wallet_name: str) -> bool:
        base = Path(self.get_wallet_path(wallet_name))
        return base.exists() or (base.with_suffix(".keys").exists())

    def _manage_py(self) -> Path:
        return Path(__file__).resolve().parents[1] / "manage.py"

    def start_wallet_rpc(self, wallet_name: Optional[str] = None, password: Optional[str] = None, port: Optional[int] = None) -> Dict[str, Any]:
        cmd = [sys.executable, str(self._manage_py()), "start_wallet_rpc"]
        if wallet_name:
            cmd += ["--wallet", wallet_name]
        if password:
            cmd += ["--password", password]
        if port:
            cmd += ["--port", str(port)]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=20)
        if proc.returncode != 0:
            raise RuntimeError(f"start_wallet_rpc failed: {err or out}")
        try:
            return json.loads(out.strip())
        except json.JSONDecodeError:
            return {"status": "started", "raw": out.strip()}

    def stop_wallet_rpc(self) -> Dict[str, Any]:
        cmd = [sys.executable, str(self._manage_py()), "stop_wallet_rpc"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=20)
        if proc.returncode != 0:
            raise RuntimeError(f"stop_wallet_rpc failed: {err or out}")
        try:
            return json.loads(out.strip())
        except json.JSONDecodeError:
            return {"status": "stopped", "raw": out.strip()}

    def list_wallets(self) -> List[str]:
        self.ensure_wallet_dir()
        names: List[str] = []
        for p in Path(self.wallet_dir).glob("*.keys"):
            names.append(p.stem)
        return sorted(list(set(names)))


# MCP Toolset
class MoneroTools(MCPToolset):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._api_client = MoneroAPI()
        self._wallet_mgr = WalletManager()

    # Daemon tool
    def monero(
        self,
        action: Literal["get_info", "get_height", "get_last_block_header", "get_block", "get_node_status"],
        payload: Any | None = None,
    ):
        api = self._api_client
        if action == "get_info":
            return api.get_info()
        if action == "get_height":
            return api.get_daemon_height()
        if action == "get_last_block_header":
            return api.get_last_block_header()
        if action == "get_block":
            if not isinstance(payload, dict):
                raise ValueError("payload must be a dict with 'height' or 'hash'")
            return api.get_block(payload)
        if action == "get_node_status":
            ok = True
            info = {}
            try:
                info = api.get_info()
            except Exception as e:
                ok = False
                info = {"error": str(e)}
            return {
                "local": True,
                "rpc": api.daemon_transport.config.rpc_url,
                "ok": ok,
                "info": info,
            }
        raise ValueError(f"Unsupported monero action: {action}")

    # Wallet tool
    def wallet(
        self,
        action: Literal[
            "create",
            "restore",
            "open",
            "close",
            "balance",
            "address",
            "create_address",
            "transfer",
            "transfer_split",
            "sweep_all",
            "transfers",
            "transfer_by_txid",
            "refresh",
            "rescan",
            "query_key",
            "integrated_address",
            "split_integrated",
            "list",
            "start_rpc",
            "stop_rpc",
        ],
        payload: Any | None = None,
    ):
        api = self._api_client
        if action == "create":
            return api.create_wallet(payload or {})
        if action == "restore":
            return api.restore_deterministic_wallet(payload or {})
        if action == "open":
            return api.open_wallet(payload or {})
        if action == "close":
            return api.close_wallet()
        if action == "balance":
            return api.get_balance(payload or {})
        if action == "address":
            return api.get_address(payload or {})
        if action == "create_address":
            return api.create_address(payload or {})
        if action == "transfer":
            return api.transfer(payload or {})
        if action == "transfer_split":
            return api.transfer_split(payload or {})
        if action == "sweep_all":
            return api.sweep_all(payload or {})
        if action == "transfers":
            return api.get_transfers(payload or {})
        if action == "transfer_by_txid":
            return api.get_transfer_by_txid(payload or {})
        if action == "refresh":
            return api.refresh(payload or {})
        if action == "rescan":
            return api.rescan_blockchain()
        if action == "query_key":
            return api.query_key(payload or {})
        if action == "integrated_address":
            return api.make_integrated_address(payload or {})
        if action == "split_integrated":
            return api.split_integrated_address(payload or {})
        if action == "list":
            return {"wallets": self._wallet_mgr.list_wallets()}
        if action == "start_rpc":
            payload = payload or {}
            return self._wallet_mgr.start_wallet_rpc(
                wallet_name=payload.get("wallet"),
                password=payload.get("password"),
                port=payload.get("port"),
            )
        if action == "stop_rpc":
            return self._wallet_mgr.stop_wallet_rpc()
        raise ValueError(f"Unsupported wallet action: {action}")

    # Convenience helpers
    def _get_block_by_height(self, height: int) -> dict:
        return self._api_client.get_block({"height": height})
