"""
Configuration settings for MoneroStack wallet functionality.
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class WalletConfig:
    """Configuration for wallet operations."""
    
    # Wallet directory settings
    wallet_dir: str = field(default_factory=lambda: os.path.expanduser("~/.monero/wallets"))
    backup_dir: str = field(default_factory=lambda: os.path.expanduser("~/.monero/backups"))
    
    # Default daemon settings
    default_daemon_address: str = "node.moneroworld.com:18089"
    trusted_daemon: bool = True
    
    # RPC settings
    default_rpc_port: int = 18082
    rpc_bind_ip: str = "127.0.0.1"
    disable_rpc_login: bool = True
    
    # Security settings
    require_password_strength: bool = True
    min_password_length: int = 12
    auto_backup_on_create: bool = True
    secure_delete_on_remove: bool = True
    
    # Transaction defaults
    default_priority: int = 1
    default_confirm_target: int = 10
    warn_on_large_transfers: bool = True
    large_transfer_threshold_xmr: float = 10.0
    
    # Network settings
    network: str = "mainnet"  # mainnet, testnet, stagenet
    
    # Logging
    log_transactions: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        """Ensure directories exist with proper permissions."""
        for directory in [self.wallet_dir, self.backup_dir]:
            os.makedirs(directory, mode=0o700, exist_ok=True)
            os.chmod(directory, 0o700)


@dataclass
class NodeConfig:
    """Configuration for Monero daemon nodes."""
    
    address: str
    port: int = 18081
    trusted: bool = False
    ssl: bool = False
    priority: int = 1
    description: str = ""
    
    @property
    def url(self) -> str:
        """Get full node URL."""
        scheme = "https" if self.ssl else "http"
        return f"{scheme}://{self.address}:{self.port}"


# Default trusted nodes for different networks
DEFAULT_MAINNET_NODES = [
    NodeConfig(
        address="node.moneroworld.com",
        port=18089,
        trusted=True,
        ssl=False,
        priority=1,
        description="MoneroWorld - community maintained"
    ),
    NodeConfig(
        address="node.sethforprivacy.com",
        port=443,
        trusted=True,
        ssl=True,
        priority=2,
        description="Seth for Privacy - HTTPS node"
    ),
    NodeConfig(
        address="node.xmrbackb.one",
        port=18081,
        trusted=True,
        ssl=False,
        priority=3,
        description="Snipa's Backbone - long-running node"
    )
]

DEFAULT_TESTNET_NODES = [
    NodeConfig(
        address="testnet.moneroworld.com",
        port=28081,
        trusted=True,
        ssl=False,
        priority=1,
        description="MoneroWorld Testnet"
    ),
    NodeConfig(
        address="testnet.community.nodes.monero.org",
        port=28081,
        trusted=True,
        ssl=True,
        priority=2,
        description="Community Testnet (SSL)"
    )
]

DEFAULT_STAGENET_NODES = [
    NodeConfig(
        address="stagenet.moneroworld.com",
        port=38081,
        trusted=True,
        ssl=False,
        priority=1,
        description="MoneroWorld Stagenet"
    )
]


class WalletConfigManager:
    """Manages wallet configuration files."""
    
    def __init__(self, config_file: str = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to configuration file
        """
        self.config_file = config_file or os.path.expanduser("~/.monero/wallet_config.json")
        self.config_dir = os.path.dirname(self.config_file)
        self._config: Optional[WalletConfig] = None
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, mode=0o700, exist_ok=True)
        os.chmod(self.config_dir, 0o700)
    
    def load_config(self) -> WalletConfig:
        """Load configuration from file or create default."""
        if self._config is not None:
            return self._config
        
        if os.path.exists(self.config_file):
            try:
                import json
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                self._config = WalletConfig(**config_data)
            except Exception as e:
                print(f"Error loading config file: {e}")
                print("Using default configuration")
                self._config = WalletConfig()
        else:
            self._config = WalletConfig()
            self.save_config()
        
        return self._config
    
    def save_config(self) -> bool:
        """Save configuration to file."""
        if self._config is None:
            return False
        
        try:
            import json
            from dataclasses import asdict
            
            config_data = asdict(self._config)
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            os.chmod(self.config_file, 0o600)
            return True
            
        except Exception as e:
            print(f"Error saving config file: {e}")
            return False
    
    def update_config(self, **kwargs) -> bool:
        """Update configuration values."""
        config = self.load_config()
        
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
            else:
                print(f"Warning: Unknown config option: {key}")
        
        return self.save_config()
    
    def get_nodes_for_network(self, network: str = None) -> List[NodeConfig]:
        """Get default nodes for specified network."""
        config = self.load_config()
        network = network or config.network
        
        if network == "mainnet":
            return DEFAULT_MAINNET_NODES
        elif network == "testnet":
            return DEFAULT_TESTNET_NODES
        elif network == "stagenet":
            return DEFAULT_STAGENET_NODES
        else:
            raise ValueError(f"Unknown network: {network}")
    
    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults."""
        self._config = WalletConfig()
        return self.save_config()


# Environment variable configuration
def get_env_config() -> Dict[str, Any]:
    """Get configuration from environment variables."""
    return {
        "wallet_dir": os.getenv("MONERO_WALLET_DIR", os.path.expanduser("~/.monero/wallets")),
        "default_daemon_address": os.getenv("MONERO_DAEMON_ADDRESS", "node.moneroworld.com:18089"),
        "default_rpc_port": int(os.getenv("MONERO_WALLET_RPC_PORT", "18082")),
        "network": os.getenv("MONERO_NETWORK", "mainnet"),
        "log_level": os.getenv("MONERO_LOG_LEVEL", "INFO"),
    }


# Default configuration instance
def get_default_config() -> WalletConfig:
    """Get default wallet configuration with environment overrides."""
    env_config = get_env_config()
    config = WalletConfig()
    
    # Override with environment variables
    for key, value in env_config.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    return config


# Validation functions
def validate_config(config: WalletConfig) -> List[str]:
    """
    Validate wallet configuration.
    
    Args:
        config: Configuration to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check directories
    try:
        if not os.path.exists(config.wallet_dir):
            os.makedirs(config.wallet_dir, mode=0o700, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create wallet directory: {e}")
    
    try:
        if not os.path.exists(config.backup_dir):
            os.makedirs(config.backup_dir, mode=0o700, exist_ok=True)
    except Exception as e:
        errors.append(f"Cannot create backup directory: {e}")
    
    # Check network
    if config.network not in ["mainnet", "testnet", "stagenet"]:
        errors.append(f"Invalid network: {config.network}")
    
    # Check ports
    if not (1024 <= config.default_rpc_port <= 65535):
        errors.append(f"Invalid RPC port: {config.default_rpc_port}")
    
    # Check priority
    if not (1 <= config.default_priority <= 4):
        errors.append(f"Invalid default priority: {config.default_priority}")
    
    # Check password settings
    if config.min_password_length < 8:
        errors.append("Minimum password length should be at least 8")
    
    return errors


# Security configuration
SECURITY_RECOMMENDATIONS = {
    "wallet_permissions": "700",
    "file_permissions": "600",
    "backup_frequency": "weekly",
    "seed_storage": "offline_paper_backup",
    "password_manager": "recommended",
    "hardware_wallet": "for_large_amounts",
    "network_isolation": "dedicated_system_preferred"
}
