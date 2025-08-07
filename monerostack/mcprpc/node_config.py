"""
Monero Node Configuration

This file contains the definitive list of Monero nodes used by the MCP server.
Only trusted, privacy-focused nodes are included with quick timeout settings.
"""

from typing import List
from dataclasses import dataclass

@dataclass
class MoneroNodeConfig:
    """Configuration for a Monero node."""
    name: str
    url: str
    description: str = ""
    is_local: bool = False
    priority: int = 1  # Lower number = higher priority
    timeout: int = 8   # Quick timeout in seconds


# ============================================================================
# DEFINITIVE NODE LIST - EDIT HERE TO CHANGE NODES
# ============================================================================

# Curated list of ONLY trusted, external nodes - NO LOCAL INSTANCE
# These are the top 3 trusted nodes from the community
TRUSTED_MONERO_NODES = [
    MoneroNodeConfig(
        name="Snipa's Backbone",
        url="http://node.xmrbackb.one:18081/json_rpc",
        description="Online since 2017, run by long-time dev Snipa; trusted by community",
        is_local=False,
        priority=0,
        timeout=10
    ),
    MoneroNodeConfig(
        name="Seth for Privacy",
        url="https://node.sethforprivacy.com/json_rpc",
        description="Privacy-focused HTTPS node with published configs and cert fingerprint",
        is_local=False,
        priority=1,
        timeout=10
    ),
    MoneroNodeConfig(
        name="MoneroWorld",
        url="http://node.moneroworld.com:18089/json_rpc",
        description="Maintained by dEBRUYNE crew; points to high-uptime boxes",
        is_local=False,
        priority=2,
        timeout=10
    ),
]


# ============================================================================
# ALTERNATIVE CONFIGURATIONS (commented out - uncomment to enable)
# ============================================================================

# Uncomment this section if you want additional backup nodes
# EXTENDED_TRUSTED_NODES = TRUSTED_MONERO_NODES + [
#     MoneroNodeConfig(
#         name="Triplebit",
#         url="https://xmr.triplebit.org:443/json_rpc",
#         description="Additional HTTPS backup node",
#         is_local=False,
#         priority=3,
#         timeout=8
#     ),
# ]

# Ultra-minimal config (local + one remote)
MINIMAL_NODES = [
    MoneroNodeConfig(
        name="Local Wallet RPC",
        url="http://127.0.0.1:28088/json_rpc",
        description="Local monero-wallet-rpc instance",
        is_local=True,
        priority=0,
        timeout=5
    ),
    MoneroNodeConfig(
        name="Seth for Privacy",
        url="https://node.sethforprivacy.com/json_rpc",
        description="Single trusted remote node",
        is_local=False,
        priority=1,
        timeout=8
    ),
]


# ============================================================================
# ACTIVE CONFIGURATION - CHANGE THIS TO SWITCH NODE SETS
# ============================================================================

# This is the active node list used by the MCP server
# Change this variable to switch between different node configurations
ACTIVE_NODES = TRUSTED_MONERO_NODES

# Alternative configurations you can switch to:
# ACTIVE_NODES = MINIMAL_NODES
# ACTIVE_NODES = EXTENDED_TRUSTED_NODES


def get_active_nodes() -> List[MoneroNodeConfig]:
    """Get the currently active node configuration."""
    return ACTIVE_NODES.copy()


def get_node_by_name(name: str) -> MoneroNodeConfig | None:
    """Get a specific node by name."""
    for node in ACTIVE_NODES:
        if node.name == name:
            return node
    return None


def list_available_nodes() -> List[str]:
    """Get a list of available node names."""
    return [node.name for node in ACTIVE_NODES]


def get_local_nodes() -> List[MoneroNodeConfig]:
    """Get only local nodes."""
    return [node for node in ACTIVE_NODES if node.is_local]


def get_remote_nodes() -> List[MoneroNodeConfig]:
    """Get only remote nodes."""
    return [node for node in ACTIVE_NODES if not node.is_local]


def validate_node_config() -> bool:
    """Validate that the node configuration is reasonable."""
    if not ACTIVE_NODES:
        return False
    
    # Check for at least one local node
    has_local = any(node.is_local for node in ACTIVE_NODES)
    if not has_local:
        print("WARNING: No local node configured")
    
    # Check for reasonable timeouts
    for node in ACTIVE_NODES:
        if node.timeout > 15:
            print(f"WARNING: Node {node.name} has high timeout: {node.timeout}s")
    
    return True


if __name__ == "__main__":
    # Quick validation when run directly
    print("=== Monero Node Configuration ===")
    print(f"Active nodes: {len(ACTIVE_NODES)}")
    
    for node in ACTIVE_NODES:
        local_str = " (LOCAL)" if node.is_local else ""
        print(f"  {node.priority}: {node.name} - {node.url} ({node.timeout}s){local_str}")
    
    print(f"\nConfiguration valid: {validate_node_config()}")
