from typing import Any, Dict, Literal, List, Optional
import logging
import requests
import os
import subprocess
import time
import json

from .utils import MCPTransport, MoneroNodeManager, MoneroNode, get_multi_node_transport, create_custom_nodes_list, MoneroRPCConfig
from mcp_server import MCPToolset

logger = logging.getLogger("mcp.monero")


# ────────────────────────────────────────────────────────────
# Monero RPC Client with Multi-Node Support
# ────────────────────────────────────────────────────────────
class MoneroAPI:
    def __init__(self, nodes: Optional[List[MoneroNode]] = None, rpc_url: Optional[str] = None, wallet_rpc_url: Optional[str] = None):
        """
        Initialize MoneroAPI with either a list of nodes or a single RPC URL.
        
        Args:
            nodes: List of MoneroNode instances for multi-node support
            rpc_url: Single RPC URL for backwards compatibility
            wallet_rpc_url: Wallet RPC URL for wallet operations
        """
        # Daemon transport setup
        if nodes:
            self.node_manager = MoneroNodeManager(nodes)
            self.transport = MCPTransport(node_manager=self.node_manager)
        elif rpc_url:
            # Backwards compatibility - create a single node
            config = MoneroRPCConfig.from_url(rpc_url)
            self.transport = MCPTransport(config)
            self.node_manager = None
        else:
            # Use default multi-node setup
            self.transport = get_multi_node_transport()
            self.node_manager = self.transport.node_manager
        
        # Wallet transport setup
        self.wallet_transport = None
        if wallet_rpc_url:
            wallet_config = MoneroRPCConfig.from_url(wallet_rpc_url)
            self.wallet_transport = MCPTransport(wallet_config)

    def _rpc_call(self, method: str, params: Dict[str, Any] | None = None, retry_on_other_nodes: bool = True, use_wallet: bool = False) -> Dict[str, Any]:
        """Make an RPC call with automatic node fallback."""
        try:
            if use_wallet and self.wallet_transport:
                return self.wallet_transport.call(method, params, retry_on_other_nodes=False)
            else:
                return self.transport.call(method, params, retry_on_other_nodes=retry_on_other_nodes)
        except Exception as e:
            logger.error(f"RPC call failed for method {method}: {e}")
            raise ConnectionError(f"Failed to connect to Monero RPC server: {e}") from e
    
    def get_info(self, data: Dict[str, Any] = None) -> dict:
        """Get general information about the state of Monero daemon."""
        return self._rpc_call("get_info", data or {})
    
    def get_height(self, data: Dict[str, Any] = None) -> dict:
        """Get the current blockchain height."""
        return self._rpc_call("get_height", data or {})
    
    def get_last_block_header(self, data: Dict[str, Any] = None) -> dict:
        """Get the header of the last block."""
        return self._rpc_call("get_last_block_header", data or {})

    def get_block(self, data: Dict[str, Any]) -> dict:
        """Get a block by height or hash."""
        return self._rpc_call("get_block", data)

    # ────────────────────────────────────────────────────────────
    # Wallet RPC Methods
    # ────────────────────────────────────────────────────────────
    def create_wallet(self, data: Dict[str, Any]) -> dict:
        """Create a new wallet."""
        return self._rpc_call("create_wallet", data, use_wallet=True)
    
    def restore_deterministic_wallet(self, data: Dict[str, Any]) -> dict:
        """Restore wallet from mnemonic seed."""
        return self._rpc_call("restore_deterministic_wallet", data, use_wallet=True)
    
    def open_wallet(self, data: Dict[str, Any]) -> dict:
        """Open an existing wallet."""
        return self._rpc_call("open_wallet", data, use_wallet=True)
    
    def close_wallet(self, data: Dict[str, Any] = None) -> dict:
        """Close the currently opened wallet."""
        return self._rpc_call("close_wallet", data or {}, use_wallet=True)
    
    def get_balance(self, data: Dict[str, Any] = None) -> dict:
        """Get wallet balance."""
        return self._rpc_call("get_balance", data or {}, use_wallet=True)
    
    def get_address(self, data: Dict[str, Any] = None) -> dict:
        """Get wallet address."""
        return self._rpc_call("get_address", data or {}, use_wallet=True)
    
    def create_address(self, data: Dict[str, Any] = None) -> dict:
        """Create a new address in current wallet."""
        return self._rpc_call("create_address", data or {}, use_wallet=True)
    
    def transfer(self, data: Dict[str, Any]) -> dict:
        """Send Monero to one or more destinations."""
        return self._rpc_call("transfer", data, use_wallet=True)
    
    def transfer_split(self, data: Dict[str, Any]) -> dict:
        """Send Monero using multiple transactions if needed."""
        return self._rpc_call("transfer_split", data, use_wallet=True)
    
    def sweep_all(self, data: Dict[str, Any]) -> dict:
        """Sweep all unlocked balance to an address."""
        return self._rpc_call("sweep_all", data, use_wallet=True)
    
    def get_transfers(self, data: Dict[str, Any] = None) -> dict:
        """Get list of transfers."""
        return self._rpc_call("get_transfers", data or {}, use_wallet=True)
    
    def get_transfer_by_txid(self, data: Dict[str, Any]) -> dict:
        """Get transfer details by transaction ID."""
        return self._rpc_call("get_transfer_by_txid", data, use_wallet=True)
    
    def refresh(self, data: Dict[str, Any] = None) -> dict:
        """Refresh wallet to sync with blockchain."""
        return self._rpc_call("refresh", data or {}, use_wallet=True)
    
    def rescan_blockchain(self, data: Dict[str, Any] = None) -> dict:
        """Rescan blockchain from scratch."""
        return self._rpc_call("rescan_blockchain", data or {}, use_wallet=True)
    
    def get_height(self, data: Dict[str, Any] = None) -> dict:
        """Get wallet blockchain height."""
        return self._rpc_call("get_height", data or {}, use_wallet=True)
    
    def query_key(self, data: Dict[str, Any]) -> dict:
        """Query wallet keys (view key, spend key, mnemonic)."""
        return self._rpc_call("query_key", data, use_wallet=True)
    
    def make_integrated_address(self, data: Dict[str, Any] = None) -> dict:
        """Create integrated address."""
        return self._rpc_call("make_integrated_address", data or {}, use_wallet=True)
    
    def split_integrated_address(self, data: Dict[str, Any]) -> dict:
        """Split integrated address into standard address and payment ID."""
        return self._rpc_call("split_integrated_address", data, use_wallet=True)


# ────────────────────────────────────────────────────────────
# Wallet Manager for Local Operations
# ────────────────────────────────────────────────────────────
class WalletManager:
    """Manages local wallet RPC processes and wallet files."""
    
    def __init__(self, wallet_dir: str = None, daemon_address: str = None):
        self.wallet_dir = wallet_dir or os.path.expanduser("~/.monero/wallets")
        self.daemon_address = daemon_address or "node.moneroworld.com:18089"
        self.rpc_port = 18082
        self.rpc_process = None
        self.ensure_wallet_dir()
    
    def ensure_wallet_dir(self):
        """Create wallet directory with secure permissions."""
        os.makedirs(self.wallet_dir, mode=0o700, exist_ok=True)
        os.chmod(self.wallet_dir, 0o700)
    
    def get_wallet_path(self, wallet_name: str) -> str:
        """Get full path to wallet file."""
        return os.path.join(self.wallet_dir, wallet_name)
    
    def wallet_exists(self, wallet_name: str) -> bool:
        """Check if wallet file exists."""
        wallet_path = self.get_wallet_path(wallet_name)
        return os.path.exists(f"{wallet_path}.keys")
    
    def start_wallet_rpc(self, wallet_name: str = None, password: str = None, port: int = None):
        """Start monero-wallet-rpc process."""
        if self.rpc_process:
            logger.warning("Wallet RPC already running, stopping first")
            self.stop_wallet_rpc()
        
        port = port or self.rpc_port
        cmd = [
            "monero-wallet-rpc",
            f"--rpc-bind-port={port}",
            "--disable-rpc-login",
            f"--daemon-address={self.daemon_address}",
            "--trusted-daemon"
        ]
        
        if wallet_name and password:
            wallet_path = self.get_wallet_path(wallet_name)
            cmd.extend([
                f"--wallet-file={wallet_path}",
                f"--password={password}"
            ])
        
        logger.info(f"Starting wallet RPC: {' '.join(cmd)}")
        self.rpc_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for RPC to start
        time.sleep(3)
        return f"http://127.0.0.1:{port}/json_rpc"
    
    def stop_wallet_rpc(self):
        """Stop wallet RPC process."""
        if self.rpc_process:
            self.rpc_process.terminate()
            try:
                self.rpc_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.rpc_process.kill()
            self.rpc_process = None
            logger.info("Wallet RPC stopped")
    
    def list_wallets(self) -> List[str]:
        """List all wallet files in wallet directory."""
        if not os.path.exists(self.wallet_dir):
            return []
        
        wallets = []
        for file in os.listdir(self.wallet_dir):
            if file.endswith('.keys'):
                wallet_name = file[:-5]  # Remove .keys extension
                wallets.append(wallet_name)
        
        return sorted(wallets)
    
    def create_wallet_config(self, wallet_name: str, address: str) -> str:
        """Create wallet configuration file."""
        config = {
            "name": wallet_name,
            "address": address,
            "created_at": time.time(),
            "daemon_address": self.daemon_address
        }
        
        config_path = os.path.join(self.wallet_dir, f"{wallet_name}.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        os.chmod(config_path, 0o600)
        
        return config_path
    
    def get_wallet_config(self, wallet_name: str) -> Dict[str, Any]:
        """Load wallet configuration."""
        config_path = os.path.join(self.wallet_dir, f"{wallet_name}.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def __del__(self):
        """Cleanup on destruction."""
        self.stop_wallet_rpc()


# ────────────────────────────────────────────────────────────
# MCP Toolset
# ────────────────────────────────────────────────────────────
class MoneroTools(MCPToolset):

    def __init__(self, custom_nodes: Optional[List[MoneroNode]] = None, **kwargs):
        """
        Initialize MoneroTools with optional custom nodes.
        
        Args:
            custom_nodes: Optional list of custom MoneroNode instances.
                         If None, uses default mainnet nodes.
            **kwargs: Additional arguments passed by MCP framework
        """
        super().__init__()
        self._custom_nodes = custom_nodes
        self._api_instance = None
        self._wallet_manager = None

    def monero(
        self,
        action: Literal["get_info", "get_height", "get_last_block_header", "get_block", "get_node_status"],
        payload: Any | None = None,
    ):
        """
        ---
        name: monero
        description: |
            Monero daemon RPC client with multi-node failover for blockchain data.

        parameters:
            type: object
            properties:
                action:
                    type: string
                    enum: [get_info, get_height, get_last_block_header, get_block, get_node_status]
                payload:
                    type: [object, "null"]
            required: [action]

        actions:
            get_info:
                summary: Get daemon info (height, difficulty, network status).
            get_height:
                summary: Get current blockchain height.
            get_last_block_header:
                summary: Get latest block header.
            get_block:
                summary: Get block by height or hash.
                payload:
                    type: object
                    properties:
                        height: { type: integer }
                        hash: { type: string }
            get_node_status:
                summary: Get multi-node connection status.
        """
        logger.info(f"monero tool called with action: {action} and payload: {payload}")
        
        # Create a dispatch table for API calls
        dispatch = {
            "get_info":       lambda p: self._api().get_info(),
            "get_height":     lambda p: self._api().get_height(),
            "get_last_block_header": lambda p: self._api().get_last_block_header(),
            "get_block":      lambda p: self._api().get_block(p),
            "get_node_status": lambda p: self.get_node_status(),
        }
        
        # Get the function from the dispatch table and call it
        api_call = dispatch.get(action)
        
        if not api_call:
            raise ValueError(f"Invalid action: {action}")
            
        # For actions that don't take a payload, call them without one
        if action in ["get_info", "get_height", "get_last_block_header", "get_node_status"]:
            return api_call(None)
        else:
            return api_call(payload or {})

    def wallet(
        self,
        action: Literal["create", "restore", "open", "close", "balance", "address", "create_address", 
                       "transfer", "transfer_split", "sweep_all", "transfers", "transfer_by_txid", 
                       "refresh", "rescan", "query_key", "integrated_address", "split_integrated", 
                       "list", "start_rpc", "stop_rpc"],
        payload: Any | None = None,
    ):
        """
        ---
        name: wallet
        description: |
            Monero wallet operations including creation, restoration, and transactions.
            Manages local wallet RPC and wallet files securely.

        parameters:
            type: object
            properties:
                action:
                    type: string
                    enum: [create, restore, open, close, balance, address, create_address, 
                           transfer, transfer_split, sweep_all, transfers, transfer_by_txid, 
                           refresh, rescan, query_key, integrated_address, split_integrated,
                           list, start_rpc, stop_rpc]
                payload:
                    type: [object, "null"]
            required: [action]

        actions:
            create:
                summary: Create a new wallet with mnemonic seed.
                payload:
                    type: object
                    properties:
                        filename: { type: string, description: "Wallet filename" }
                        password: { type: string, description: "Wallet password" }
                        language: { type: string, default: "English" }
            restore:
                summary: Restore wallet from mnemonic seed.
                payload:
                    type: object
                    properties:
                        filename: { type: string }
                        password: { type: string }
                        seed: { type: string, description: "25-word mnemonic seed" }
                        restore_height: { type: integer, default: 0 }
            open:
                summary: Open existing wallet.
                payload:
                    type: object
                    properties:
                        filename: { type: string }
                        password: { type: string }
            close:
                summary: Close currently opened wallet.
            balance:
                summary: Get wallet balance and unlocked balance.
            address:
                summary: Get primary wallet address.
            create_address:
                summary: Create new subaddress.
                payload:
                    type: object
                    properties:
                        account_index: { type: integer, default: 0 }
                        label: { type: string }
            transfer:
                summary: Send Monero to address(es).
                payload:
                    type: object
                    properties:
                        destinations: 
                            type: array
                            items:
                                type: object
                                properties:
                                    address: { type: string }
                                    amount: { type: integer, description: "Amount in atomic units" }
                        priority: { type: integer, default: 1, description: "Fee priority 1-4" }
                        get_tx_key: { type: boolean, default: true }
            transfers:
                summary: Get transfer history.
                payload:
                    type: object
                    properties:
                        in: { type: boolean, default: true }
                        out: { type: boolean, default: true }
                        pending: { type: boolean, default: true }
                        failed: { type: boolean, default: true }
            query_key:
                summary: Get wallet keys or mnemonic seed.
                payload:
                    type: object
                    properties:
                        key_type: { type: string, enum: [mnemonic, view_key, spend_key] }
            list:
                summary: List all available wallets.
            start_rpc:
                summary: Start wallet RPC server.
                payload:
                    type: object
                    properties:
                        wallet_name: { type: string }
                        password: { type: string }
                        port: { type: integer, default: 18082 }
            stop_rpc:
                summary: Stop wallet RPC server.
        """
        logger.info(f"wallet tool called with action: {action} and payload: {payload}")
        
        # Create a dispatch table for wallet operations
        dispatch = {
            "create": lambda p: self._create_wallet(p),
            "restore": lambda p: self._restore_wallet(p),
            "open": lambda p: self._open_wallet(p),
            "close": lambda p: self._close_wallet(p),
            "balance": lambda p: self._get_balance(p),
            "address": lambda p: self._get_address(p),
            "create_address": lambda p: self._create_address(p),
            "transfer": lambda p: self._transfer(p),
            "transfer_split": lambda p: self._transfer_split(p),
            "sweep_all": lambda p: self._sweep_all(p),
            "transfers": lambda p: self._get_transfers(p),
            "transfer_by_txid": lambda p: self._get_transfer_by_txid(p),
            "refresh": lambda p: self._refresh_wallet(p),
            "rescan": lambda p: self._rescan_blockchain(p),
            "query_key": lambda p: self._query_key(p),
            "integrated_address": lambda p: self._make_integrated_address(p),
            "split_integrated": lambda p: self._split_integrated_address(p),
            "list": lambda p: self._list_wallets(p),
            "start_rpc": lambda p: self._start_wallet_rpc(p),
            "stop_rpc": lambda p: self._stop_wallet_rpc(p),
        }
        
        # Get the function from the dispatch table and call it
        wallet_call = dispatch.get(action)
        
        if not wallet_call:
            raise ValueError(f"Invalid wallet action: {action}")
            
        return wallet_call(payload or {})

    def get_block_by_height(self, height: int) -> Dict[str, Any]:
        """A direct method to get a block by height for debugging."""
        api = self._api()
        return api.get_block({"height": height})

    def get_node_status(self) -> Dict[str, Any]:
        """Get information about configured nodes and current status with connectivity check."""
        api = self._api()
        
        # Perform connection test and get node info
        connection_status = self._test_node_connectivity(api)
        
        if api.node_manager:
            current_node = api.node_manager.get_current_node()
            base_status = {
                "current_node": current_node.name,
                "current_node_url": current_node.url,
                "available_nodes": api.node_manager.list_nodes(),
                "multi_node_enabled": True,
                "total_nodes": len(api.node_manager.nodes)
            }
        else:
            base_status = {
                "current_node": "Single node configuration",
                "current_node_url": "Unknown",
                "available_nodes": [],
                "multi_node_enabled": False,
                "total_nodes": 0
            }
        
        # Merge connection status with base status
        return {**base_status, **connection_status}
    
    def _test_node_connectivity(self, api: 'MoneroAPI') -> Dict[str, Any]:
        """Test connectivity and get basic node information for all available nodes."""
        connection_results = []
        successful_connection = False
        active_node_name = "None"

        nodes_to_test_info = []
        if api.node_manager:
            nodes_to_test_info = api.node_manager.list_nodes()
        else:
            # Single node config, create a mock node info for the loop
            nodes_to_test_info.append({
                "name": "Single Node",
                "url": api.transport.config.url,
                "description": "Single node configuration",
                "is_local": "127.0.0.1" in api.transport.config.url,
                "priority": 1,
                "response_time": 0,
                "success_rate": 1.0,
                "is_current": True,
            })

        original_config = api.transport.config
        
        for node_info in nodes_to_test_info:
            # Create a MoneroNode from the info dict
            node = MoneroNode(
                name=node_info["name"],
                url=node_info["url"],
                description=node_info["description"],
                is_local=node_info["is_local"],
                priority=node_info["priority"],
                response_time=node_info.get("response_time", 0.0),
                success_rate=node_info.get("success_rate", 1.0),
            )

            # Temporarily point the transport to the node we want to test
            api.transport.config = node.to_rpc_config()
            if api.transport._session:
                api.transport._session.close()
                api.transport._session = None

            logger.info(f"Testing connectivity to {node.name}...")
            
            try:
                result = self._test_single_node_quick(api, node)
                connection_results.append(result)
                
                if result["is_connected"]:
                    if not successful_connection:
                        successful_connection = True
                        active_node_name = node.name
                        logger.info(f"Successfully connected to {node.name}")
            except Exception as e:
                logger.error(f"Error testing {node.name}: {e}")
                connection_results.append({
                    "node_name": node.name,
                    "is_connected": False,
                    "error": str(e),
                    "test_duration": 0
                })

        # Restore the transport to its original state
        api.transport.config = original_config
        if api.transport._session:
            api.transport._session.close()
            api.transport._session = None
        
        # Summary of connection test
        return {
            "connection_status": "Connected" if successful_connection else "All nodes failed",
            "is_connected": successful_connection,
            "active_node": active_node_name,
            "connection_tests": connection_results,
            "total_nodes_tested": len(connection_results),
            "test_timestamp": __import__('time').time()
        }
    
    def _test_single_node_quick(self, api: 'MoneroAPI', node: Optional[object] = None) -> Dict[str, Any]:
        """Test a single node with quick timeout and return detailed results."""
        import time
        start_time = time.time()
        node_name = node.name if node else "Current node"
        
        try:
            # Try multiple quick tests in order of preference
            test_results = {}
            
            # Test 1: Basic version check (works on most RPC types)
            try:
                version_info = api._rpc_call("get_version", retry_on_other_nodes=False)
                test_results["version_check"] = {
                    "success": True,
                    "data": version_info
                }
            except Exception as e:
                test_results["version_check"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Test 2: Get blockchain height (daemon method)
            try:
                height_info = api._rpc_call("get_height", retry_on_other_nodes=False)
                test_results["height_check"] = {
                    "success": True,
                    "current_height": height_info.get("height", "Unknown")
                }
            except Exception as e:
                test_results["height_check"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Test 3: Get basic node info (daemon method)
            try:
                info_response = api._rpc_call("get_info", retry_on_other_nodes=False)
                test_results["info_check"] = {
                    "success": True,
                    "network": info_response.get("nettype", "Unknown"),
                    "synchronized": info_response.get("synchronized", False),
                    "tx_pool_size": info_response.get("tx_pool_size", 0)
                }
            except Exception as e:
                test_results["info_check"] = {
                    "success": False,
                    "error": str(e)
                }
            
            # Determine if connection is successful (any test passed)
            is_connected = any(result.get("success", False) for result in test_results.values())
            
            end_time = time.time()
            test_duration = end_time - start_time
            
            return {
                "node_name": node_name,
                "is_connected": is_connected,
                "test_duration": round(test_duration, 2),
                "test_results": test_results,
                "connection_quality": "Good" if test_duration < 3 else "Slow" if test_duration < 8 else "Very Slow"
            }
            
        except Exception as e:
            end_time = time.time()
            test_duration = end_time - start_time

    # ────────────────────────────────────────────────────────────
    # Wallet Operation Methods
    # ────────────────────────────────────────────────────────────
    def _create_wallet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new wallet."""
        filename = payload.get("filename")
        password = payload.get("password")
        language = payload.get("language", "English")
        
        if not filename or not password:
            raise ValueError("filename and password are required")
        
        # Ensure wallet manager is initialized
        wallet_manager = self._get_wallet_manager()
        
        # Start wallet RPC if not running
        if not self._api().wallet_transport:
            rpc_url = wallet_manager.start_wallet_rpc()
            self._api().wallet_transport = MCPTransport(MoneroRPCConfig.from_url(rpc_url))
        
        # Create wallet via RPC
        wallet_data = {
            "filename": wallet_manager.get_wallet_path(filename),
            "password": password,
            "language": language
        }
        
        result = self._api().create_wallet(wallet_data)
        
        # Create config file
        if "address" in result:
            wallet_manager.create_wallet_config(filename, result["address"])
        
        return {
            "filename": filename,
            "address": result.get("address"),
            "mnemonic": result.get("seed", "Created - use query_key action to retrieve"),
            "created_at": time.time()
        }
    
    def _restore_wallet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Restore wallet from mnemonic seed."""
        filename = payload.get("filename")
        password = payload.get("password")
        seed = payload.get("seed")
        restore_height = payload.get("restore_height", 0)
        
        if not filename or not password or not seed:
            raise ValueError("filename, password, and seed are required")
        
        wallet_manager = self._get_wallet_manager()
        
        if not self._api().wallet_transport:
            rpc_url = wallet_manager.start_wallet_rpc()
            self._api().wallet_transport = MCPTransport(MoneroRPCConfig.from_url(rpc_url))
        
        restore_data = {
            "filename": wallet_manager.get_wallet_path(filename),
            "password": password,
            "seed": seed,
            "restore_height": restore_height
        }
        
        result = self._api().restore_deterministic_wallet(restore_data)
        
        if "address" in result:
            wallet_manager.create_wallet_config(filename, result["address"])
        
        return {
            "filename": filename,
            "address": result.get("address"),
            "restored_at": time.time(),
            "restore_height": restore_height
        }
    
    def _open_wallet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Open existing wallet."""
        filename = payload.get("filename")
        password = payload.get("password")
        
        if not filename or not password:
            raise ValueError("filename and password are required")
        
        wallet_manager = self._get_wallet_manager()
        
        if not wallet_manager.wallet_exists(filename):
            raise ValueError(f"Wallet {filename} does not exist")
        
        if not self._api().wallet_transport:
            rpc_url = wallet_manager.start_wallet_rpc()
            self._api().wallet_transport = MCPTransport(MoneroRPCConfig.from_url(rpc_url))
        
        open_data = {
            "filename": wallet_manager.get_wallet_path(filename),
            "password": password
        }
        
        result = self._api().open_wallet(open_data)
        config = wallet_manager.get_wallet_config(filename)
        
        return {
            "filename": filename,
            "opened_at": time.time(),
            "config": config
        }
    
    def _close_wallet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Close currently opened wallet."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().close_wallet()
        return {
            "closed_at": time.time(),
            "status": "closed"
        }
    
    def _get_balance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get wallet balance."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().get_balance()
        
        # Convert to human-readable XMR
        balance_xmr = result.get("balance", 0) / 1e12
        unlocked_xmr = result.get("unlocked_balance", 0) / 1e12
        
        return {
            "balance": result.get("balance", 0),
            "unlocked_balance": result.get("unlocked_balance", 0),
            "balance_xmr": round(balance_xmr, 12),
            "unlocked_xmr": round(unlocked_xmr, 12),
            "multisig_import_needed": result.get("multisig_import_needed", False)
        }
    
    def _get_address(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get wallet address."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().get_address(payload)
        return result
    
    def _create_address(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create new subaddress."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().create_address(payload)
        return result
    
    def _transfer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send Monero transfer."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        destinations = payload.get("destinations", [])
        if not destinations:
            raise ValueError("destinations are required")
        
        # Validate destinations
        for dest in destinations:
            if not dest.get("address") or not dest.get("amount"):
                raise ValueError("Each destination must have address and amount")
        
        transfer_data = {
            "destinations": destinations,
            "priority": payload.get("priority", 1),
            "get_tx_key": payload.get("get_tx_key", True),
            "do_not_relay": payload.get("do_not_relay", False)
        }
        
        result = self._api().transfer(transfer_data)
        
        # Calculate total amount and fees
        total_amount = sum(dest["amount"] for dest in destinations)
        
        return {
            "tx_hash": result.get("tx_hash"),
            "tx_key": result.get("tx_key"),
            "amount": total_amount,
            "amount_xmr": round(total_amount / 1e12, 12),
            "fee": result.get("fee", 0),
            "fee_xmr": round(result.get("fee", 0) / 1e12, 12),
            "tx_blob": result.get("tx_blob"),
            "tx_metadata": result.get("tx_metadata")
        }
    
    def _transfer_split(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send transfer with automatic splitting."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().transfer_split(payload)
        
        # Process multiple transactions
        total_fee = sum(tx.get("fee", 0) for tx in result.get("fee_list", []))
        
        return {
            "tx_hash_list": result.get("tx_hash_list", []),
            "tx_key_list": result.get("tx_key_list", []),
            "amount_list": result.get("amount_list", []),
            "fee_list": result.get("fee_list", []),
            "total_fee": total_fee,
            "total_fee_xmr": round(total_fee / 1e12, 12)
        }
    
    def _sweep_all(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sweep all balance to address."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        address = payload.get("address")
        if not address:
            raise ValueError("address is required")
        
        result = self._api().sweep_all(payload)
        return result
    
    def _get_transfers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get transfer history."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().get_transfers(payload)
        return result
    
    def _get_transfer_by_txid(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get transfer by transaction ID."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        txid = payload.get("txid")
        if not txid:
            raise ValueError("txid is required")
        
        result = self._api().get_transfer_by_txid(payload)
        return result
    
    def _refresh_wallet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Refresh wallet to sync with blockchain."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().refresh(payload)
        return result
    
    def _rescan_blockchain(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Rescan blockchain from scratch."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().rescan_blockchain(payload)
        return result
    
    def _query_key(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Query wallet keys or mnemonic."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        key_type = payload.get("key_type", "mnemonic")
        query_data = {"key_type": key_type}
        
        result = self._api().query_key(query_data)
        return result
    
    def _make_integrated_address(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create integrated address."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().make_integrated_address(payload)
        return result
    
    def _split_integrated_address(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Split integrated address."""
        if not self._api().wallet_transport:
            raise ValueError("No wallet RPC connection available")
        
        result = self._api().split_integrated_address(payload)
        return result
    
    def _list_wallets(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """List all available wallets."""
        wallet_manager = self._get_wallet_manager()
        wallets = wallet_manager.list_wallets()
        
        wallet_info = []
        for wallet_name in wallets:
            config = wallet_manager.get_wallet_config(wallet_name)
            wallet_info.append({
                "name": wallet_name,
                "address": config.get("address"),
                "created_at": config.get("created_at")
            })
        
        return {
            "wallets": wallet_info,
            "count": len(wallets),
            "wallet_dir": wallet_manager.wallet_dir
        }
    
    def _start_wallet_rpc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Start wallet RPC server."""
        wallet_name = payload.get("wallet_name")
        password = payload.get("password")
        port = payload.get("port", 18082)
        
        wallet_manager = self._get_wallet_manager()
        
        # Stop existing RPC if running
        wallet_manager.stop_wallet_rpc()
        
        # Start new RPC
        rpc_url = wallet_manager.start_wallet_rpc(wallet_name, password, port)
        
        # Update API instance
        self._api().wallet_transport = MCPTransport(MoneroRPCConfig.from_url(rpc_url))
        
        return {
            "rpc_url": rpc_url,
            "wallet_name": wallet_name,
            "port": port,
            "status": "started"
        }
    
    def _stop_wallet_rpc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Stop wallet RPC server."""
        wallet_manager = self._get_wallet_manager()
        wallet_manager.stop_wallet_rpc()
        
        # Clear wallet transport
        if self._api().wallet_transport:
            self._api().wallet_transport = None
        
        return {
            "status": "stopped",
            "stopped_at": time.time()
        }
    
    def _get_wallet_manager(self) -> WalletManager:
        """Get or create wallet manager instance."""
        if self._wallet_manager is None:
            self._wallet_manager = WalletManager()
        return self._wallet_manager


    def _api(self) -> MoneroAPI:
        # Use cached instance or create new one with custom nodes if provided
        if self._api_instance is None:
            nodes = self._custom_nodes
            if not nodes:
                # No custom nodes, use default mainnet nodes
                from . import utils
                nodes = utils.load_nodes_from_config()
            self._api_instance = MoneroAPI(nodes=nodes)
        return self._api_instance
