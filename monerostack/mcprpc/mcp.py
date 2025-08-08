import logging
from typing import Any, Dict, Literal, Optional

from mcp_server import MCPToolset

from .utils import MCPTransport, MoneroRPCConfig, create_daemon_transport, create_wallet_transport

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

    def _rpc_call(self, method: str, params: Any = None, *, use_wallet: bool = False) -> Dict[str, Any]:
        if use_wallet:
            if not self.wallet_transport:
                self.wallet_transport = create_wallet_transport()
            return self.wallet_transport.call(method, params)
        return self.daemon_transport.call(method, params)

    # --- Daemon methods (node) ---
    def get_info(self) -> dict:
        return self._rpc_call("get_info")

    def get_version(self) -> dict:
        return self._rpc_call("get_version")

    def get_block_count(self) -> dict:
        return self._rpc_call("get_block_count")

    def get_daemon_height(self) -> dict:
        return self.daemon_transport.get_plain("/get_height")

    def get_last_block_header(self) -> dict:
        return self._rpc_call("get_last_block_header")

    def get_block(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("get_block", data)

    def get_block_header_by_height(self, height: int) -> dict:
        return self._rpc_call("get_block_header_by_height", {"height": height})

    def get_block_header_by_hash(self, block_hash: str) -> dict:
        return self._rpc_call("get_block_header_by_hash", {"hash": block_hash})

    def get_block_headers_range(self, start_height: int, end_height: int) -> dict:
        return self._rpc_call("get_block_headers_range", {"start_height": start_height, "end_height": end_height})

    def on_get_block_hash(self, height: int) -> dict:
        # This method expects positional params (array)
        return self._rpc_call("on_get_block_hash", [height])

    def get_transactions(self, tx_hashes: list[str], decode_as_json: bool = True, prune: bool = False) -> dict:
        # Non-JSON-RPC endpoint
        payload = {"txs_hashes": tx_hashes, "decode_as_json": decode_as_json, "prune": prune}
        return self.daemon_transport.post_plain("/get_transactions", payload)

    def get_transaction_pool(self) -> dict:
        return self.daemon_transport.get_plain("/get_transaction_pool")

    def get_connections(self) -> dict:
        return self.daemon_transport.get_plain("/get_connections")

    def get_peer_list(self) -> dict:
        return self.daemon_transport.get_plain("/get_peer_list")

    def sync_info(self) -> dict:
        return self._rpc_call("sync_info")

    def hard_fork_info(self) -> dict:
        return self._rpc_call("hard_fork_info")

    def get_fee_estimate(self, grace_blocks: Optional[int] = None) -> dict:
        params = {"grace_blocks": grace_blocks} if grace_blocks is not None else None
        return self._rpc_call("get_fee_estimate", params)

    # --- Wallet RPC Methods (no creation/open/close here) ---

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

# MCP Toolset
class MoneroTools(MCPToolset):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._api_client = MoneroAPI()

    # Node/daemon tool
    def monero(
        self,
        action: Literal[
            "status",
            "get_node_status",  # alias for status
            "get_info",
            "height",
            "get_height",  # alias for height
            "block_count",
            "last_block_header",
            "block_by_height",
            "block_by_hash",
            "block_hash",
            "headers_range",
            "get_block",  # legacy alias
            "tx",
            "tx_pool",
            "sync_info",
            "fee_estimate",
            "hard_fork_info",
            "version",
            "connections",
            "peers",
        ],
        payload: Any | None = None,
    ):
        """Monero node/daemon tool (read-only diagnostics and lookups).

    Actions (payload -> result):
    - status|get_node_status: null -> { rpc, ok, height?, info }
    - get_info: null -> get_info
    - height|get_height: null -> { height }
    - block_count: null -> { count }
    - last_block_header: null -> get_last_block_header
    - block_by_height: { height:int } -> get_block
    - block_by_hash: { hash:str } -> get_block
    - block_hash: { height:int } -> { hash }
    - headers_range: { start_height:int, end_height:int } -> get_block_headers_range
    - get_block (legacy): { height:int } | { hash:str } -> get_block
    - tx: { hash|txid:str } or { hashes:[str] } -> /get_transactions
    - tx_pool: null -> /get_transaction_pool
    - sync_info: null -> sync_info
    - fee_estimate: { grace_blocks?:int } -> get_fee_estimate
    - hard_fork_info: null -> hard_fork_info
    - version: null -> get_version
    - connections: null -> /get_connections
    - peers: null -> /get_peer_list

    Raises ValueError for invalid payloads. Transport/RPC failures bubble up.
    """
        api = self._api_client
        if action == "status" or action == "get_node_status":
            ok = True
            info: dict[str, Any] = {}
            try:
                info = api.get_info()
            except Exception as e:
                ok = False
                info = {"error": str(e)}
            height = None
            if ok:
                try:
                    h = api.get_daemon_height()
                    height = h.get("height")
                except Exception:
                    height = None
            return {
                "rpc": api.daemon_transport.config.rpc_url,
                "ok": ok,
                "height": height,
                "info": info,
            }
        if action == "get_info":
            return api.get_info()
        if action == "height" or action == "get_height":
            return api.get_daemon_height()
        if action == "block_count":
            return api.get_block_count()
        if action == "last_block_header":
            return api.get_last_block_header()
        if action == "block_by_height":
            if not isinstance(payload, dict) or "height" not in payload:
                raise ValueError("payload must be a dict with 'height'")
            return api.get_block({"height": int(payload["height"])})
        if action == "block_by_hash":
            if not isinstance(payload, dict) or "hash" not in payload:
                raise ValueError("payload must be a dict with 'hash'")
            return api.get_block({"hash": str(payload["hash"])})
        if action == "block_hash":
            if not isinstance(payload, dict) or "height" not in payload:
                raise ValueError("payload must be a dict with 'height'")
            return api.on_get_block_hash(int(payload["height"]))
        if action == "headers_range":
            if not isinstance(payload, dict) or not {"start_height", "end_height"} <= set(payload.keys()):
                raise ValueError("payload must be a dict with 'start_height' and 'end_height'")
            return api.get_block_headers_range(int(payload["start_height"]), int(payload["end_height"]))
        if action == "get_block":  # legacy alias
            if not isinstance(payload, dict) or not ({"height"} <= set(payload.keys()) or {"hash"} <= set(payload.keys())):
                raise ValueError("payload must be a dict with 'height' or 'hash'")
            return api.get_block(payload)
        if action == "tx":
            if not isinstance(payload, dict):
                raise ValueError("payload must be a dict with 'hash' or 'txid' (string) or 'hashes' (list)")
            if "hashes" in payload and isinstance(payload["hashes"], list):
                hashes = [str(h) for h in payload["hashes"]]
            else:
                h = payload.get("hash") or payload.get("txid")
                if not h or not isinstance(h, (str, bytes)):
                    raise ValueError("Provide 'hash' or 'txid' as a string, or 'hashes' as a list")
                hashes = [h.decode() if isinstance(h, bytes) else h]
            return api.get_transactions(hashes)
        if action == "tx_pool":
            return api.get_transaction_pool()
        if action == "sync_info":
            return api.sync_info()
        if action == "fee_estimate":
            grace = None
            if isinstance(payload, dict):
                grace = payload.get("grace_blocks")
            return api.get_fee_estimate(grace)
        if action == "hard_fork_info":
            return api.hard_fork_info()
        if action == "version":
            return api.get_version()
        if action == "connections":
            return api.get_connections()
        if action == "peers":
            return api.get_peer_list()
        raise ValueError(f"Unsupported monero action: {action}")

    # Wallet tool (no creation/open/close or RPC lifecycle here)
    def wallet(
        self,
        action: Literal[
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
            "get_height",
        ],
        payload: Any | None = None,
    ):
        """Monero wallet tool for TX and queries (no lifecycle here).

    Lifecycle (create/open/close/start/stop) is managed via Django
    management commands (create_wallet, start_wallet_rpc, stop_wallet_rpc).

    Actions (payload -> result):
    - balance: { account_index?:int, address_indices?:[int] } -> get_balance
    - address: { account_index?:int, address_index?:int|[int] } -> get_address
    - create_address: { account_index:int, label?:str } -> create_address
    - transfer: { destinations:[{address,amount}], ... } -> transfer
    - transfer_split: like transfer -> transfer_split
    - sweep_all: { address:str, account_index?:int, subaddr_indices?:[int] } -> sweep_all
    - transfers: standard get_transfers filters -> get_transfers
    - transfer_by_txid: { txid:str, account_index?:int } -> get_transfer_by_txid
    - refresh: { start_height?:int } -> refresh
    - rescan: null -> rescan_blockchain
    - query_key: { key_type:"mnemonic"|"view_key"|"spend_key" } -> query_key
    - integrated_address: { payment_id?:str } -> make_integrated_address
    - split_integrated: { integrated_address:str } -> split_integrated_address
    - get_height: null -> { height }

    Raises ValueError for invalid payloads. Transport/RPC failures bubble up.
    """
        api = self._api_client
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
        if action == "get_height":
            return api.get_wallet_height()
        raise ValueError(f"Unsupported wallet action: {action}")

    # Convenience helpers
    def _get_block_by_height(self, height: int) -> dict:
        return self._api_client.get_block({"height": height})
