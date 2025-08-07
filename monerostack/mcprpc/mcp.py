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
                         If None, uses default mainnet nodes.
            **kwargs: Additional arguments passed by MCP framework
        """
        super().__init__()
        self._custom_nodes = custom_nodes
        self._api_instance = None

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
