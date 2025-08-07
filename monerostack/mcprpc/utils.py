"""
Utility classes for Monero RPC communication and MCP transport layer.
"""

import os
import logging
import urllib.parse
import random
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass, field
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import pickle
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed


logger = logging.getLogger("mcp.transport")


@dataclass
class MoneroRPCConfig:
    """Configuration for Monero RPC connections."""
    host: str = "127.0.0.1"
    port: int = 18081  # Default daemon port
    path: str = "/json_rpc"
    scheme: str = "http"
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 8  # Reduced from 10 to 8 seconds for faster failover
    max_retries: int = 1  # Reduced from 2 to 1 retry for quicker failover
    backoff_factor: float = 0.3  # Reduced for quicker failover
    rpc_type: str = "daemon"  # "daemon" or "wallet"
    
    @property
    def url(self) -> str:
        """Construct the full RPC URL."""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
        
        return f"{self.scheme}://{auth}{self.host}:{self.port}{self.path}"
    
    @classmethod
    def from_environment(cls) -> "MoneroRPCConfig":
        """Create configuration from environment variables."""
        return cls(
            host=os.getenv("MONERO_RPC_HOST", "127.0.0.1"),
            port=int(os.getenv("MONERO_RPC_PORT", "18081")),  # Changed default to daemon port
            path=os.getenv("MONERO_RPC_PATH", "/json_rpc"),
            scheme=os.getenv("MONERO_RPC_SCHEME", "http"),
            username=os.getenv("MONERO_RPC_USER"),
            password=os.getenv("MONERO_RPC_PASSWORD"),
            timeout=int(os.getenv("MONERO_RPC_TIMEOUT", "8")),  # Reduced default timeout
            max_retries=int(os.getenv("MONERO_RPC_MAX_RETRIES", "1")),  # Reduced retries
            backoff_factor=float(os.getenv("MONERO_RPC_BACKOFF_FACTOR", "0.3")),
            rpc_type=os.getenv("MONERO_RPC_TYPE", "daemon"),
        )
    
    @classmethod
    def from_url(cls, url: str, rpc_type: str = "daemon") -> "MoneroRPCConfig":
        """Create configuration from a URL string."""
        parsed = urllib.parse.urlparse(url)
        
        # Determine default port based on RPC type
        if rpc_type == "wallet":
            default_port = 18082
        else:
            default_port = 18081
        
        return cls(
            scheme=parsed.scheme or "http",
            host=parsed.hostname or "127.0.0.1",
            port=parsed.port or (443 if parsed.scheme == "https" else default_port),
            path=parsed.path or "/json_rpc",
            username=parsed.username,
            password=parsed.password,
            rpc_type=rpc_type,
        )


@dataclass
class MoneroNode:
    """Configuration for a Monero node."""
    name: str
    url: str
    description: str = ""
    is_local: bool = False
    priority: int = 1  # Lower number = higher priority
    response_time: float = 0.0  # Average response time in seconds
    last_tested: float = 0.0  # Timestamp of last test
    success_rate: float = 1.0  # Success rate (0.0 to 1.0)
    
    def to_rpc_config(self) -> MoneroRPCConfig:
        """Convert to MoneroRPCConfig."""
        return MoneroRPCConfig.from_url(self.url)


# Cache configuration
CACHE_FILE = os.path.expanduser("~/.monero_nodes_cache.pkl")
CACHE_EXPIRY = 3600  # 1 hour in seconds
MIN_REFRESH_INTERVAL = 300  # 5 minutes minimum between refreshes


class MoneroNodeCache:
    """Manages cached node list with periodic refresh and performance tracking."""
    
    def __init__(self):
        self._nodes: List[MoneroNode] = []
        self._lock = threading.Lock()
        self._last_refresh = 0.0
        self._refresh_in_progress = False
        
    def get_random_node(self) -> Optional[MoneroNode]:
        """Get a random node from the cached list, weighted by performance."""
        with self._lock:
            if not self._nodes:
                self._refresh_if_needed()
                if not self._nodes:
                    return None
            
            # Weight nodes by inverse response time and success rate
            weights = []
            for node in self._nodes:
                # Higher success rate and lower response time = higher weight
                weight = node.success_rate / max(node.response_time, 0.1)
                weights.append(weight)
            
            # Random selection weighted by performance
            if weights:
                selected = random.choices(self._nodes, weights=weights, k=1)[0]
                logger.debug(f"Randomly selected node: {selected.name} (response: {selected.response_time:.2f}s, success: {selected.success_rate:.2f})")
                return selected
            
            return random.choice(self._nodes)
    
    def get_all_nodes(self) -> List[MoneroNode]:
        """Get all cached nodes."""
        with self._lock:
            self._refresh_if_needed()
            return self._nodes.copy()
    
    def mark_node_failure(self, node_url: str):
        """Mark a node as failed and potentially refresh the cache."""
        with self._lock:
            for node in self._nodes:
                if node.url == node_url:
                    # Reduce success rate
                    node.success_rate = max(0.1, node.success_rate * 0.8)
                    logger.warning(f"Marked node {node.name} as failed, new success rate: {node.success_rate:.2f}")
                    break
            
            # If we have too many failures, force refresh
            healthy_nodes = [n for n in self._nodes if n.success_rate > 0.5]
            if len(healthy_nodes) < 2:
                logger.warning("Too many failed nodes, forcing refresh")
                self._force_refresh()
    
    def _refresh_if_needed(self):
        """Refresh the cache if needed."""
        current_time = time.time()
        
        # Check if we need to refresh
        if (current_time - self._last_refresh > CACHE_EXPIRY or 
            not self._nodes or 
            len([n for n in self._nodes if n.success_rate > 0.5]) < 2):
            
            if not self._refresh_in_progress and (current_time - self._last_refresh > MIN_REFRESH_INTERVAL):
                self._force_refresh()
    
    def _force_refresh(self):
        """Force a refresh of the node cache."""
        if self._refresh_in_progress:
            return
        
        self._refresh_in_progress = True
        
        # Start refresh in background thread
        threading.Thread(target=self._background_refresh, daemon=True).start()
    
    def _background_refresh(self):
        """Background refresh of node cache."""
        try:
            logger.info("Starting background node cache refresh...")
            
            # Try to load from monero.fail
            new_nodes = self._fetch_and_test_nodes()
            
            if new_nodes:
                with self._lock:
                    self._nodes = new_nodes
                    self._last_refresh = time.time()
                    self._save_to_cache()
                    logger.info(f"Cache refreshed with {len(new_nodes)} nodes")
            else:
                # Fallback to cached file or hardcoded nodes
                self._load_fallback()
                
        except Exception as e:
            logger.error(f"Background refresh failed: {e}")
            self._load_fallback()
        finally:
            self._refresh_in_progress = False
    
    def _fetch_and_test_nodes(self) -> List[MoneroNode]:
        """Fetch nodes from monero.fail and test them for performance."""
        try:
            # Fetch from monero.fail API
            response = requests.get("https://monero.fail/nodes.json", timeout=15)
            response.raise_for_status()
            data = response.json()
            
            clearnet_nodes = data.get("monero", {}).get("clear", [])[:20]  # Top 20 for testing
            
            if not clearnet_nodes:
                return []
            
            # Test nodes in parallel
            tested_nodes = []
            
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Submit test tasks
                future_to_url = {
                    executor.submit(self._test_node_performance, url): url 
                    for url in clearnet_nodes
                }
                
                # Collect results
                for future in as_completed(future_to_url, timeout=30):
                    try:
                        node = future.result()
                        if node and node.success_rate > 0.3:  # Only keep reasonably working nodes
                            tested_nodes.append(node)
                    except Exception as e:
                        logger.warning(f"Node test failed: {e}")
            
            # Sort by performance (success rate * inverse response time)
            tested_nodes.sort(key=lambda n: n.success_rate / max(n.response_time, 0.1), reverse=True)
            
            # Return top performing nodes
            return tested_nodes[:10]
            
        except Exception as e:
            logger.error(f"Failed to fetch and test nodes: {e}")
            return []
    
    def _test_node_performance(self, node_url: str) -> Optional[MoneroNode]:
        """Test a single node's performance."""
        try:
            parsed = urllib.parse.urlparse(node_url)
            
            # Create proper JSON-RPC URL
            if parsed.path and parsed.path != "/":
                json_rpc_url = node_url
            else:
                json_rpc_url = f"{parsed.scheme}://{parsed.netloc}/json_rpc"
            
            # Quick performance test
            start_time = time.time()
            
            test_session = requests.Session()
            test_session.timeout = 5  # Quick test timeout
            
            # Test with get_version (lightweight call)
            payload = {
                "jsonrpc": "2.0",
                "id": "test",
                "method": "get_version",
                "params": {}
            }
            
            response = test_session.post(json_rpc_url, json=payload, timeout=5)
            response.raise_for_status()
            
            response_time = time.time() - start_time
            
            # Check if response is valid JSON-RPC
            data = response.json()
            success = "result" in data or "error" in data  # Valid RPC response
            
            # Generate node info
            hostname = parsed.hostname or "unknown"
            is_https = parsed.scheme == "https"
            
            node_name = f"MF-{hostname.replace('.', '-')}"
            if is_https:
                node_name += "-SSL"
            
            description = f"Auto-tested from monero.fail"
            if is_https:
                description += " (HTTPS)"
            description += f" - {response_time:.2f}s"
            
            return MoneroNode(
                name=node_name,
                url=json_rpc_url,
                description=description,
                is_local=False,
                priority=0 if is_https else 1,
                response_time=response_time,
                last_tested=time.time(),
                success_rate=1.0 if success else 0.3
            )
            
        except Exception as e:
            logger.debug(f"Node test failed for {node_url}: {e}")
            return None
    
    def _load_fallback(self):
        """Load nodes from cache file or hardcoded fallback."""
        try:
            # Try to load from cache file
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'rb') as f:
                    cached_data = pickle.load(f)
                    if isinstance(cached_data, dict) and 'nodes' in cached_data:
                        with self._lock:
                            self._nodes = cached_data['nodes']
                            logger.info(f"Loaded {len(self._nodes)} nodes from cache file")
                            return
        except Exception as e:
            logger.warning(f"Failed to load cache file: {e}")
        
        # Final fallback to hardcoded nodes
        with self._lock:
            self._nodes = get_fallback_nodes()
            logger.info("Using hardcoded fallback nodes")
    
    def _save_to_cache(self):
        """Save current nodes to cache file."""
        try:
            cache_data = {
                'nodes': self._nodes,
                'timestamp': time.time()
            }
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.debug(f"Saved {len(self._nodes)} nodes to cache")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")


# Global node cache instance
_node_cache = MoneroNodeCache()


def get_fallback_nodes() -> List[MoneroNode]:
    """Fallback node list if config file is not available."""
    return [
        MoneroNode(
            name="Snipa's Backbone",
            url="http://node.xmrbackb.one:18081/json_rpc",
            description="Online since 2017, run by long-time dev Snipa; trusted by community",
            is_local=False,
            priority=0
        ),
        MoneroNode(
            name="Seth for Privacy",
            url="https://node.sethforprivacy.com/json_rpc",
            description="Privacy-focused HTTPS node with published configs and cert fingerprint",
            priority=1
        ),
        MoneroNode(
            name="MoneroWorld",
            url="http://node.moneroworld.com:18089/json_rpc", 
            description="Maintained by dEBRUYNE crew; points to high-uptime boxes",
            priority=2
        ),
    ]


def get_testnet_nodes() -> List[MoneroNode]:
    """A list of public Monero testnet nodes."""
    return [
        MoneroNode(
            name="moneroworld-testnet",
            url="http://testnet.moneroworld.com:28081/json_rpc",
            description="Testnet node by MoneroWorld",
            priority=0
        ),
        MoneroNode(
            name="community-testnet-2",
            url="https://testnet.community.nodes.monero.org:28081/json_rpc",
            description="Community-provided testnet node (SSL)",
            priority=1
        ),
    ]


def fetch_nodes_from_monero_fail() -> List[MoneroNode]:
    """
    Fetch the most secure and reliable nodes from monero.fail API.
    Prioritizes HTTPS nodes with high uptime and good performance.
    """
    try:
        logger.info("Fetching nodes from monero.fail API...")
        
        # Fetch node data from monero.fail
        response = requests.get("https://monero.fail/nodes.json", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Extract clearnet nodes (avoid Tor for simplicity)
        clearnet_nodes = data.get("monero", {}).get("clear", [])
        
        if not clearnet_nodes:
            logger.warning("No clearnet nodes found in monero.fail API")
            return get_fallback_nodes()
        
        # Filter and rank nodes by security and reliability
        secure_nodes = []
        
        for i, node_url in enumerate(clearnet_nodes[:15]):  # Limit to top 15 for performance
            try:
                # Parse URL to extract details
                parsed = urllib.parse.urlparse(node_url)
                
                # Prioritize HTTPS nodes
                is_https = parsed.scheme == "https"
                
                # Prioritize standard ports (18081 for daemon, 18089 for public)
                port = parsed.port or (443 if is_https else 18081)
                is_standard_port = port in [18081, 18089, 443]
                
                # Create node URL with /json_rpc endpoint
                if parsed.path and parsed.path != "/":
                    json_rpc_url = node_url
                else:
                    json_rpc_url = f"{parsed.scheme}://{parsed.netloc}/json_rpc"
                
                # Calculate priority (lower is better)
                # HTTPS nodes get priority 0-4, HTTP nodes get priority 5-9
                base_priority = 0 if is_https else 5
                position_penalty = min(i // 3, 4)  # Group nodes by position
                
                priority = base_priority + position_penalty
                
                # Generate node name
                hostname = parsed.hostname or "unknown"
                node_name = f"MoneroFail-{hostname.replace('.', '-')}"
                if is_https:
                    node_name += "-HTTPS"
                
                description = f"Auto-selected from monero.fail (rank {i+1})"
                if is_https:
                    description += " - SECURE HTTPS"
                if is_standard_port:
                    description += f" - Port {port}"
                
                node = MoneroNode(
                    name=node_name,
                    url=json_rpc_url,
                    description=description,
                    is_local=False,
                    priority=priority
                )
                
                secure_nodes.append(node)
                
            except Exception as e:
                logger.warning(f"Failed to process node {node_url}: {e}")
                continue
        
        if not secure_nodes:
            logger.warning("No valid nodes processed from monero.fail API")
            return get_fallback_nodes()
        
        # Sort by priority (HTTPS first, then by position in list)
        secure_nodes.sort(key=lambda x: x.priority)
        
        # Return top 3 most secure nodes
        top_nodes = secure_nodes[:3]
        
        logger.info(f"Selected {len(top_nodes)} secure nodes from monero.fail:")
        for node in top_nodes:
            logger.info(f"  - {node.name}: {node.url} (priority {node.priority})")
        
        return top_nodes
        
    except Exception as e:
        logger.error(f"Failed to fetch nodes from monero.fail: {e}")
        logger.info("Falling back to hardcoded trusted nodes")
        return get_fallback_nodes()


# This ensures we always use the most up-to-date node list
def load_nodes_from_config() -> List[MoneroNode]:
    """Load nodes using the new dynamic cache system."""
    # Try to get nodes from the cache
    nodes = _node_cache.get_all_nodes()
    if nodes:
        logger.info(f"Loaded {len(nodes)} nodes from dynamic cache")
        return nodes
    
    # Fallback to hardcoded nodes
    logger.info("Using hardcoded fallback nodes")
    return get_fallback_nodes()


# Default nodes loaded from configuration (but cache system preferred)
DEFAULT_MONERO_NODES = load_nodes_from_config()


class MoneroNodeManager:
    """Manages multiple Monero nodes with random selection and performance tracking."""
    
    def __init__(self, nodes: Optional[List[MoneroNode]] = None, prefer_local: bool = False):
        """
        Initialize with a list of nodes or use cached nodes.
        
        Args:
            nodes: List of MoneroNode instances. If None, uses cached dynamic nodes.
            prefer_local: Whether to prefer local nodes (disabled for privacy).
        """
        if nodes:
            self.nodes = nodes
            self._use_cache = False
        else:
            # Use dynamic cache if no nodes are provided
            self._use_cache = True
            self.nodes = _node_cache.get_all_nodes()
        
        self.prefer_local = prefer_local
        self._current_node: Optional[MoneroNode] = None
        self._failure_count = 0
        
    def get_current_node(self) -> MoneroNode:
        """Get a randomly selected node for privacy."""
        if self._use_cache:
            # Get random node from cache for privacy
            node = _node_cache.get_random_node()
            if node:
                self._current_node = node
                return node
            # Fallback if cache fails
            if not self.nodes:
                self.nodes = get_fallback_nodes()
        
        if not self.nodes:
            raise ValueError("No nodes configured or available")
        
        # Random selection from static list
        self._current_node = random.choice(self.nodes)
        return self._current_node
    
    def get_next_node(self) -> Optional[MoneroNode]:
        """Get another random node (for privacy - no fixed order)."""
        if self._use_cache:
            # Mark current node as failed if we're switching
            if self._current_node:
                _node_cache.mark_node_failure(self._current_node.url)
            
            # Get new random node
            node = _node_cache.get_random_node()
            if node and node != self._current_node:
                self._current_node = node
                logger.info(f"Switched to random node: {node.name}")
                return node
        
        # Fallback: random selection from static list
        if len(self.nodes) <= 1:
            return None
        
        # Get a different random node
        available_nodes = [n for n in self.nodes if n != self._current_node]
        if available_nodes:
            self._current_node = random.choice(available_nodes)
            logger.info(f"Switched to random node: {self._current_node.name}")
            return self._current_node
        
        return None
    
    def reset_to_random_node(self):
        """Reset to a random node (maintains privacy)."""
        if self._use_cache:
            self._current_node = _node_cache.get_random_node()
        else:
            self._current_node = random.choice(self.nodes) if self.nodes else None
        
        if self._current_node:
            logger.info(f"Reset to random node: {self._current_node.name}")
    
    def mark_node_failure(self, node_url: str):
        """Mark a node as failed for performance tracking."""
        if self._use_cache:
            _node_cache.mark_node_failure(node_url)
        
        self._failure_count += 1
        
        # If too many failures, force a refresh
        if self._failure_count > 3:
            logger.warning("Too many node failures, forcing cache refresh")
            if self._use_cache:
                _node_cache._force_refresh()
            self._failure_count = 0
    
    def add_node(self, node: MoneroNode):
        """Add a new node to the static list."""
        if not self._use_cache:
            self.nodes.append(node)
    
    def remove_node(self, name: str) -> bool:
        """Remove a node by name from static list."""
        if self._use_cache:
            return False  # Can't remove from dynamic cache
        
        for i, node in enumerate(self.nodes):
            if node.name == name:
                del self.nodes[i]
                return True
        return False
    
    def list_nodes(self) -> List[Dict[str, Any]]:
        """List all available nodes with their details."""
        if self._use_cache:
            nodes = _node_cache.get_all_nodes()
        else:
            nodes = self.nodes
        
        current_url = self._current_node.url if self._current_node else None
        
        return [
            {
                "name": node.name,
                "url": node.url,
                "description": node.description,
                "is_local": node.is_local,
                "priority": node.priority,
                "response_time": getattr(node, 'response_time', 0.0),
                "success_rate": getattr(node, 'success_rate', 1.0),
                "is_current": node.url == current_url
            }
            for node in nodes
        ]


class MCPTransportError(Exception):
    """Base exception for MCP transport errors."""
    pass


class MoneroRPCError(MCPTransportError):
    """Exception raised for Monero RPC specific errors."""
    def __init__(self, message: str, error_code: Optional[int] = None, error_data: Optional[Dict] = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_data = error_data


class MCPTransport:
    """
    Transport layer for Monero RPC communication with enhanced error handling,
    connection pooling, retry logic, and multi-node fallback support.
    """
    
    def __init__(self, config: Optional[MoneroRPCConfig] = None, node_manager: Optional[MoneroNodeManager] = None):
        """
        Initialize the transport with configuration.
        
        Args:
            config: MoneroRPCConfig instance. If None, will attempt to load from environment.
            node_manager: MoneroNodeManager for multi-node support. If provided, overrides config.
        """
        self.node_manager = node_manager
        if self.node_manager:
            # Use the first node from the manager
            self.config = self.node_manager.get_current_node().to_rpc_config()
        else:
            self.config = config or MoneroRPCConfig.from_environment()
        
        self._session: Optional[requests.Session] = None
        self._request_id = 0
        
        logger.info(f"Initialized MCPTransport for {self.config.host}:{self.config.port}")
    
    @property
    def session(self) -> requests.Session:
        """Lazy initialization of requests session with retry strategy."""
        if self._session is None:
            self._session = requests.Session()
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=self.config.max_retries,
                backoff_factor=self.config.backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "POST"]
            )
            
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            
            # Set default timeout
            self._session.timeout = self.config.timeout
            
            # Set authentication if provided
            if self.config.username and self.config.password:
                self._session.auth = (self.config.username, self.config.password)
                
        return self._session
    
    def _get_next_request_id(self) -> str:
        """Generate a unique request ID."""
        self._request_id += 1
        return str(self._request_id)
    
    def _try_next_node(self) -> bool:
        """Try switching to the next node if node manager is available."""
        if not self.node_manager:
            return False
        
        next_node = self.node_manager.get_next_node()
        if next_node:
            self.config = next_node.to_rpc_config()
            # Reset session to pick up new config
            if self._session:
                self._session.close()
                self._session = None
            logger.info(f"Switched to node: {next_node.name} ({self.config.url})")
            return True
        return False
    
    def call(self, method: str, params: Optional[Dict[str, Any]] = None, retry_on_other_nodes: bool = True) -> Dict[str, Any]:
        """
        Make a JSON-RPC call to the Monero daemon/wallet with automatic fallback.
        
        Args:
            method: The RPC method name
            params: Optional parameters for the method
            retry_on_other_nodes: Whether to try other nodes on failure
            
        Returns:
            The result from the RPC call
            
        Raises:
            MoneroRPCError: If the RPC call returns an error
            MCPTransportError: If there's a transport-level error
        """
        payload = {
            "jsonrpc": "2.0",
            "id": self._get_next_request_id(),
            "method": method,
            "params": params or {}
        }
        
        logger.debug(f"Making RPC call to {method} with params: {params}")
        
        # Keep track of tried nodes to avoid infinite loops
        tried_nodes = set()
        current_node_name = self.node_manager.get_current_node().name if self.node_manager else "default"
        
        while True:
            tried_nodes.add(current_node_name)
            
            try:
                # Handle get_height via REST-like endpoint as it seems to fail on JSON-RPC for some public nodes
                if method == "get_height":
                    rest_url = self.config.url.replace('/json_rpc', '/getheight')
                    try:
                        response = self.session.get(
                            rest_url,
                            timeout=self.config.timeout,
                        )
                        response.raise_for_status()
                        # The REST-like endpoints return the result directly
                        logger.debug(f"REST call to {method} completed successfully")
                        return response.json()
                    except (requests.RequestException, ValueError) as e:
                        logger.warning(f"REST call to {rest_url} failed, falling back to JSON-RPC: {e}")
                        # Fallback to JSON-RPC call below if REST-like call fails

                response = self.session.post(
                    self.config.url,
                    json=payload,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                
                # Parse JSON response
                try:
                    response_data = response.json()
                except ValueError as e:
                    error_msg = f"Invalid JSON response from {method}: {response.text}"
                    logger.error(error_msg)
                    raise MCPTransportError(error_msg) from e
                
                # Check for JSON-RPC errors
                if "error" in response_data:
                    error_info = response_data["error"]
                    error_msg = error_info.get("message", "Unknown RPC error")
                    error_code = error_info.get("code")
                    error_data = error_info.get("data")
                    
                    logger.error(f"Monero RPC error in {method}: {error_msg} (code: {error_code})")
                    raise MoneroRPCError(error_msg, error_code, error_data)
                
                # Success! Reset to a random node for next time to maintain privacy
                if self.node_manager:
                    self.node_manager.reset_to_random_node()
                    self.config = self.node_manager.get_current_node().to_rpc_config()
                    if self._session:
                        self._session.close()
                        self._session = None
                
                # Return the result
                result = response_data.get("result", {})
                logger.debug(f"RPC call {method} completed successfully")
                return result
                
            except requests.exceptions.Timeout as e:
                error_msg = f"Timeout calling {method} on {self.config.url}"
                logger.error(error_msg)
                # Mark node as failed for performance tracking
                if self.node_manager:
                    self.node_manager.mark_node_failure(self.config.url)
                
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error calling {method} on {self.config.url}. Is the Monero RPC server running?"
                logger.error(error_msg)
                # Mark node as failed for performance tracking
                if self.node_manager:
                    self.node_manager.mark_node_failure(self.config.url)
                
            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP error {response.status_code} calling {method}: {response.text}"
                logger.error(error_msg)
                # Mark node as failed for performance tracking
                if self.node_manager:
                    self.node_manager.mark_node_failure(self.config.url)
                
            except requests.exceptions.RequestException as e:
                error_msg = f"Request error calling {method}: {str(e)}"
                logger.error(error_msg)
                # Mark node as failed for performance tracking
                if self.node_manager:
                    self.node_manager.mark_node_failure(self.config.url)
            
            # Try next node if available and we haven't tried all nodes
            if retry_on_other_nodes and self._try_next_node():
                current_node_name = self.node_manager.get_current_node().name
                if current_node_name not in tried_nodes:
                    logger.info(f"Retrying {method} on {current_node_name}")
                    continue
            
            # If we get here, all nodes failed or no node manager available
            raise MCPTransportError(f"Failed to connect to any Monero RPC server for method {method}")
    
    def test_connection(self) -> bool:
        """
        Test if the RPC server is reachable and responding.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try a simple call that should work on both daemon and wallet RPC
            # For wallet RPC, we'll try get_version as it's usually available
            self.call("get_version", retry_on_other_nodes=False)
            logger.info(f"Connection test successful for {self.config.url}")
            return True
        except (MCPTransportError, MoneroRPCError) as e:
            logger.warning(f"Connection test failed for {self.config.url}: {e}")
            return False
    
    def close(self):
        """Close the underlying session."""
        if self._session:
            self._session.close()
            self._session = None
            logger.debug("MCPTransport session closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_transport_from_settings() -> MCPTransport:
    """
    Create an MCPTransport instance using Django settings or environment variables.
    
    This function checks for Django settings first, then falls back to environment variables.
    """
    try:
        from django.conf import settings
        
        # Check if Django settings has Monero RPC configuration
        if hasattr(settings, 'MONERO_RPC_CONFIG'):
            config_dict = settings.MONERO_RPC_CONFIG
            config = MoneroRPCConfig(**config_dict)
        elif hasattr(settings, 'MONERO_RPC_URL'):
            config = MoneroRPCConfig.from_url(settings.MONERO_RPC_URL)
        else:
            # Fall back to environment variables
            config = MoneroRPCConfig.from_environment()
            
    except ImportError:
        # Django not available, use environment variables
        config = MoneroRPCConfig.from_environment()
    
    return MCPTransport(config)


# Convenience functions for common use cases
def get_default_transport() -> MCPTransport:
    """Get a default transport instance using environment/settings configuration."""
    return create_transport_from_settings()


def get_multi_node_transport(nodes: Optional[List[MoneroNode]] = None) -> MCPTransport:
    """Get a transport instance with multi-node fallback support."""
    node_manager = MoneroNodeManager(nodes)
    return MCPTransport(node_manager=node_manager)


def create_transport(url: str) -> MCPTransport:
    """Create a transport instance from a URL string."""
    config = MoneroRPCConfig.from_url(url)
    return MCPTransport(config)


def create_custom_nodes_list() -> List[MoneroNode]:
    """
    Create a customizable list of curated privacy-focused Monero nodes.
    Returns a small, trusted set of nodes with quick timeout settings.
    """
    return load_nodes_from_config()


def load_nodes_from_config() -> List[MoneroNode]:
    """Load nodes using the new dynamic cache system."""
    # Try to get nodes from the cache
    nodes = _node_cache.get_all_nodes()
    if nodes:
        logger.info(f"Loaded {len(nodes)} nodes from dynamic cache")
        return nodes
    
    # Fallback to hardcoded nodes
    logger.info("Using hardcoded fallback nodes")
    return get_fallback_nodes()


# Load nodes from configuration file
# This ensures we always use the most up-to-date node list
def _load_default_nodes():
    """Load default nodes, with fallback if config is not available."""
    try:
        return load_nodes_from_config()
    except:
        return get_fallback_nodes()

def create_wallet_transport(port: int = 18082, host: str = "127.0.0.1") -> MCPTransport:
    """Create a transport instance for wallet RPC."""
    config = MoneroRPCConfig(
        host=host,
        port=port,
        rpc_type="wallet"
    )
    return MCPTransport(config)


def create_daemon_transport(nodes: Optional[List[MoneroNode]] = None) -> MCPTransport:
    """Create a transport instance for daemon RPC with multi-node support."""
    return get_multi_node_transport(nodes)


# Default nodes loaded from configuration (but cache system preferred)
DEFAULT_MONERO_NODES = _load_default_nodes()
