from typing import Any, Dict, Literal, List, Optional
import logging
import requests

from .utils import MCPTransport, MoneroNodeManager, MoneroNode, get_multi_node_transport, create_custom_nodes_list, MoneroRPCConfig
from mcp_server import MCPToolset

logger = logging.getLogger("mcp.monero")


# ────────────────────────────────────────────────────────────
# Monero RPC Client with Multi-Node Support
# ────────────────────────────────────────────────────────────
class MoneroAPI:
    def __init__(self, nodes: Optional[List[MoneroNode]] = None, rpc_url: Optional[str] = None):
        """
        Initialize MoneroAPI with either a list of nodes or a single RPC URL.
        
        Args:
            nodes: List of MoneroNode instances for multi-node support
            rpc_url: Single RPC URL for backwards compatibility
        """
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

    def _rpc_call(self, method: str, params: Dict[str, Any] | None = None, retry_on_other_nodes: bool = True) -> Dict[str, Any]:
        """Make an RPC call with automatic node fallback."""
        try:
            return self.transport.call(method, params, retry_on_other_nodes=retry_on_other_nodes)
        except Exception as e:
            logger.error(f"RPC call failed for method {method}: {e}")
            raise ConnectionError(f"Failed to connect to Monero RPC server: {e}") from e

    def get_balance(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("get_balance", data)

    def get_address(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("get_address", data)

    def create_address(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("create_address", data)

    def transfer(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("transfer", data)

    def get_transfers(self, data: Dict[str, Any]) -> dict:
        return self._rpc_call("get_transfers", data)
    
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
# MCP Toolset
# ────────────────────────────────────────────────────────────
class MoneroTools(MCPToolset):

    def __init__(self, custom_nodes: Optional[List[MoneroNode]] = None, **kwargs):
        """
        Initialize MoneroTools with optional custom nodes.
        
        Args:
            custom_nodes: Optional list of custom MoneroNode instances.
                         If None, uses default top 3 popular nodes.
            **kwargs: Additional arguments passed by MCP framework
        """
        super().__init__()
        self._custom_nodes = custom_nodes
        self._api_instance = None
        self._network = "mainnet"

    def monero(
        self,
        action: Literal["get_balance", "get_address", "create_address", "transfer", "get_transfers", "get_info", "get_height", "get_last_block_header", "get_block"],
        payload: Any | None = None,
        network: str = "mainnet",
    ):
        """
        ---
        name: monero
        description: |
            Manages a Monero wallet by wrapping the monero-wallet-rpc JSON-RPC API.
            This tool allows for checking balances, creating addresses, sending funds,
            and viewing transaction history. It connects to multiple Monero RPC servers
            with automatic failover for improved reliability.

        parameters:
            type: object
            properties:
                action:
                    type: string
                    enum: [get_balance, get_address, create_address, transfer, get_transfers, get_info, get_height, get_last_block_header, get_block]
                payload:
                    type: [object, "null"]
                network:
                    type: string
                    enum: ["mainnet", "testnet"]
                    default: "mainnet"
                    description: "The Monero network to use (mainnet or testnet)."
            required: [action]

        actions:
            get_balance:
                summary: Get the wallet's balance.
                payload:
                    type: object
                    properties:
                        account_index: { type: integer, description: "Index of the account to query.", default: 0 }
                response:
                    $ref: "#/components/schemas/Balance"
            get_address:
                summary: Get the wallet's primary address and subaddresses for an account.
                payload:
                    type: object
                    properties:
                        account_index: { type: integer, description: "Index of the account.", default: 0 }
                response:
                    $ref: "#/components/schemas/AddressInfo"
            create_address:
                summary: Create a new subaddress for an account.
                payload:
                    type: object
                    properties:
                        account_index: { type: integer, description: "Index of the account to create the address in.", default: 0 }
                        label: { type: string, description: "A label for the new address." }
                    required: [account_index]
                response:
                    $ref: "#/components/schemas/Subaddress"
            transfer:
                summary: Send Monero to one or more destinations.
                payload:
                    type: object
                    properties:
                        destinations:
                            type: array
                            items:
                                type: object
                                properties:
                                    amount: { type: integer, description: "Amount in piconeros (1 XMR = 1e12 piconeros)." }
                                    address: { type: string, description: "Destination public address." }
                                required: [amount, address]
                        priority: { type: integer, description: "Transaction priority (0-3 for unimportant, normal, elevated, priority).", default: 0 }
                        mixin: { type: integer, description: "Number of decoys to use.", default: 10 }
                        unlock_time: { type: integer, description: "Number of blocks before the transaction can be spent.", default: 0 }
                    required: [destinations]
                response:
                    $ref: "#/components/schemas/TransferResult"
            get_transfers:
                summary: Get a list of incoming and outgoing transfers.
                payload:
                    type: object
                    properties:
                        in: { type: boolean, default: true, description: "Include incoming transfers." }
                        out: { type: boolean, default: true, description: "Include outgoing transfers." }
                        pending: { type: boolean, default: true, description: "Include pending transfers." }
                        failed: { type: boolean, default: true, description: "Include failed transfers." }
                        pool: { type: boolean, default: true, description: "Include transfers in the transaction pool." }
                response:
                    $ref: "#/components/schemas/Transfers"
            get_info:
                summary: Get general information about the state of Monero daemon.
                payload:
                    type: object
                    properties: {}
                response:
                    $ref: "#/components/schemas/DaemonInfo"
            get_height:
                summary: Get the current blockchain height.
                payload:
                    type: object
                    properties: {}
                response:
                    $ref: "#/components/schemas/BlockHeight"
            get_last_block_header:
                summary: Get the header of the last block.
                payload:
                    type: object
                    properties: {}
                response:
                    $ref: "#/components/schemas/BlockHeader"
            get_block:
                summary: Get a block by height or hash.
                payload:
                    type: object
                    properties:
                        height: { type: integer, description: "Block height to retrieve." }
                        hash: { type: string, description: "Block hash to retrieve." }
                response:
                    $ref: "#/components/schemas/Block"

        components:
            schemas:
                Balance:
                    type: object
                    properties:
                        balance: { type: integer, description: "Total balance in piconeros." }
                        unlocked_balance: { type: integer, description: "Unlocked balance in piconeros." }
                        blocks_to_unlock: { type: integer }
                AddressInfo:
                    type: object
                    properties:
                        address: { type: string, description: "The main address for the account." }
                        addresses:
                            type: array
                            items:
                                $ref: "#/components/schemas/Subaddress"
                Subaddress:
                    type: object
                    properties:
                        address_index: { type: integer, description: "Index of the subaddress." }
                        address: { type: string, description: "The subaddress." }
                        label: { type: string }
                        used: { type: boolean }
                TransferResult:
                    type: object
                    properties:
                        tx_hash: { type: string, description: "The transaction hash." }
                        tx_key: { type: string, description: "The transaction secret key." }
                        amount: { type: integer }
                        fee: { type: integer }
                Transfer:
                    type: object
                    properties:
                        txid: { type: string }
                        type: { type: string }
                        amount: { type: integer }
                        fee: { type: integer }
                        height: { type: integer }
                        timestamp: { type: integer }
                        unlock_time: { type: integer }
                        destinations: { type: array, items: { type: object } }
                Transfers:
                    type: object
                    properties:
                        in: { type: array, items: { $ref: "#/components/schemas/Transfer" } }
                        out: { type: array, items: { $ref: "#/components/schemas/Transfer" } }
                        pending: { type: array, items: { $ref: "#/components/schemas/Transfer" } }
                        failed: { type: array, items: { $ref: "#/components/schemas/Transfer" } }
                        pool: { type: array, items: { $ref: "#/components/schemas/Transfer" } }
                DaemonInfo:
                    type: object
                    properties:
                        height: { type: integer, description: "Current blockchain height." }
                        difficulty: { type: integer, description: "Current network difficulty." }
                        target_height: { type: integer, description: "Target height for synchronization." }
                        synchronized: { type: boolean, description: "Whether the daemon is synchronized." }
                        nettype: { type: string, description: "Network type (mainnet, testnet, stagenet)." }
                        tx_pool_size: { type: integer, description: "Number of transactions in the mempool." }
                BlockHeight:
                    type: object
                    properties:
                        height: { type: integer, description: "Current blockchain height." }
                BlockHeader:
                    type: object
                    properties:
                        block_header: { 
                            type: object,
                            properties: {
                                height: { type: integer, description: "Block height." },
                                hash: { type: string, description: "Block hash." },
                                timestamp: { type: integer, description: "Block timestamp." },
                                difficulty: { type: integer, description: "Block difficulty." },
                                reward: { type: integer, description: "Block reward in piconeros." }
                            }
                        }
                Block:
                    type: object
                    properties:
                        blob: { type: string, description: "Hex-encoded block data." }
                        json: { type: string, description: "JSON-formatted block data." }
                        block_header: {
                            type: object,
                            properties: {
                                height: { type: integer, description: "Block height." },
                                hash: { type: string, description: "Block hash." },
                                timestamp: { type: integer, description: "Block timestamp." },
                                difficulty: { type: integer, description: "Block difficulty." },
                                reward: { type: integer, description: "Block reward in piconeros." }
                            }
                        }
        ...
        """
        # If network changes, invalidate the API instance to reconnect
        if self._network != network:
            self._network = network
            self._api_instance = None
        
        # Create a dispatch table for API calls
        dispatch = {
            "get_balance":    lambda p: self._api().get_balance(p),
            "get_address":    lambda p: self._api().get_address(p),
            "create_address": lambda p: self._api().create_address(p),
            "transfer":       lambda p: self._api().transfer(p),
            "get_transfers":  lambda p: self._api().get_transfers(p),
            "get_info":       lambda p: self._api().get_info(),
            "get_height":     lambda p: self._api().get_height(),
            "get_last_block_header": lambda p: self._api().get_last_block_header(),
            "get_block":      lambda p: self._api().get_block(p),
        }
        
        # Get the function from the dispatch table and call it
        api_call = dispatch.get(action)
        
        if not api_call:
            raise ValueError(f"Invalid action: {action}")
            
        # For actions that don't take a payload, call them without one
        if action in ["get_info", "get_height", "get_last_block_header"]:
            return api_call(None)
        else:
            return api_call(payload or {})

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


    def _api(self) -> MoneroAPI:
        # Use cached instance or create new one with custom nodes if provided
        if self._api_instance is None:
            nodes = self._custom_nodes
            if not nodes:
                # No custom nodes, use default from utils
                from . import utils
                if self._network == "testnet":
                    nodes = utils.get_testnet_nodes()
                else:
                    nodes = utils.load_nodes_from_config()
            self._api_instance = MoneroAPI(nodes=nodes)
        return self._api_instance
