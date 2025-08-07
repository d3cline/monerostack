# MoneroStack Wallet Functionality

This document describes the extended wallet functionality added to the MoneroStack MCP server.

## Overview

The MoneroStack MCP now supports comprehensive wallet operations alongside the existing daemon RPC functionality. This includes:

- **Wallet Creation & Restoration**: Create new wallets or restore from mnemonic seeds
- **Transaction Management**: Send Monero, check balances, view transaction history
- **Address Management**: Generate addresses and subaddresses
- **Key Management**: Access private keys and mnemonic seeds securely
- **RPC Management**: Control local wallet RPC processes

## Architecture

### Dual RPC Support

The system now supports both:
- **Daemon RPC**: Connects to public nodes for blockchain data (existing functionality)
- **Wallet RPC**: Connects to local `monero-wallet-rpc` for wallet operations (new)

### Security Model

- **Local Only**: Wallet RPC runs locally for security
- **Encrypted Storage**: Wallet files are encrypted with user passwords
- **Secure Permissions**: Wallet directories use restrictive file permissions (700)
- **No Remote Access**: Wallet operations never send private keys over network

## Installation Requirements

### Monero Software

Install the official Monero software:

```bash
# Download from https://www.getmonero.org/downloads/
# Or install via package manager:

# Ubuntu/Debian
sudo apt install monero

# macOS (Homebrew)
brew install monero

# Verify installation
monero-wallet-rpc --version
```

### Python Dependencies

The wallet functionality uses the existing dependencies with additions for subprocess management and security utilities.

## Configuration

### Environment Variables

```bash
# Wallet-specific settings
export MONERO_WALLET_DIR="$HOME/.monero/wallets"
export MONERO_WALLET_RPC_PORT="18082"
export MONERO_DAEMON_ADDRESS="node.moneroworld.com:18089"

# Security settings
export MONERO_NETWORK="mainnet"  # or "testnet", "stagenet"
```

### Configuration File

The system creates a configuration file at `~/.monero/wallet_config.json`:

```json
{
  "wallet_dir": "/home/user/.monero/wallets",
  "backup_dir": "/home/user/.monero/backups",
  "default_daemon_address": "node.moneroworld.com:18089",
  "default_rpc_port": 18082,
  "require_password_strength": true,
  "min_password_length": 12,
  "network": "mainnet"
}
```

## API Reference

### Wallet Tool Actions

#### Wallet Management

```python
# Create new wallet
result = monero_tools.wallet("create", {
    "filename": "my_wallet",
    "password": "secure_password_123",
    "language": "English"
})

# Restore from seed
result = monero_tools.wallet("restore", {
    "filename": "restored_wallet",
    "password": "secure_password_123",
    "seed": "25-word mnemonic seed phrase here...",
    "restore_height": 0
})

# Open existing wallet
result = monero_tools.wallet("open", {
    "filename": "my_wallet",
    "password": "secure_password_123"
})

# Close wallet
result = monero_tools.wallet("close")

# List all wallets
result = monero_tools.wallet("list")
```

#### Balance and Addresses

```python
# Get balance
balance = monero_tools.wallet("balance")
print(f"Balance: {balance['balance_xmr']} XMR")
print(f"Unlocked: {balance['unlocked_xmr']} XMR")

# Get primary address
address_info = monero_tools.wallet("address")
print(f"Address: {address_info['address']}")

# Create subaddress
subaddress = monero_tools.wallet("create_address", {
    "account_index": 0,
    "label": "Shopping address"
})
```

#### Transactions

```python
# Send transaction
tx_result = monero_tools.wallet("transfer", {
    "destinations": [{
        "address": "4B6fX7B6P8R6YU9X...",
        "amount": 1000000000000  # 1 XMR in atomic units
    }],
    "priority": 1,  # 1=low, 2=medium, 3=high, 4=highest
    "get_tx_key": True
})

# Send to multiple recipients
multi_tx = monero_tools.wallet("transfer", {
    "destinations": [
        {"address": "address1...", "amount": 500000000000},
        {"address": "address2...", "amount": 300000000000}
    ],
    "priority": 2
})

# Sweep all balance
sweep_result = monero_tools.wallet("sweep_all", {
    "address": "destination_address...",
    "priority": 1
})

# Get transaction history
transfers = monero_tools.wallet("transfers", {
    "in": True,
    "out": True,
    "pending": True
})
```

#### Key Management

```python
# Get mnemonic seed
seed_info = monero_tools.wallet("query_key", {
    "key_type": "mnemonic"
})

# Get view key
view_key = monero_tools.wallet("query_key", {
    "key_type": "view_key"
})

# Get spend key (use with extreme caution!)
spend_key = monero_tools.wallet("query_key", {
    "key_type": "spend_key"
})
```

#### RPC Management

```python
# Start wallet RPC
rpc_info = monero_tools.wallet("start_rpc", {
    "wallet_name": "my_wallet",
    "password": "secure_password_123",
    "port": 18082
})

# Stop wallet RPC
monero_tools.wallet("stop_rpc")
```

## Security Best Practices

### 1. Password Security

```python
from monerostack.mcprpc.wallet_utils import validate_password_strength

# Check password strength
strength = validate_password_strength("your_password")
if not strength['valid']:
    print("Password too weak:", strength['feedback'])
```

**Requirements:**
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- Avoid common passwords

### 2. Seed Storage

**Critical:** Your 25-word mnemonic seed is the master key to your wallet.

```python
# Get seed securely
seed_result = monero_tools.wallet("query_key", {"key_type": "mnemonic"})
seed = seed_result['key']

# Store offline:
# 1. Write on paper, store in safe
# 2. Use metal backup plates
# 3. Never store digitally
# 4. Never share with anyone
```

### 3. File Permissions

The system automatically sets secure permissions:

```bash
# Wallet directory: owner access only
chmod 700 ~/.monero/wallets

# Wallet files: owner read/write only
chmod 600 ~/.monero/wallets/*.keys
```

### 4. Network Security

```python
# Use trusted daemon
monero_tools.wallet("start_rpc", {
    "wallet_name": "my_wallet",
    "password": "password",
    "daemon_address": "your-trusted-node:18081"
})
```

## Utility Functions

### Amount Conversion

```python
from monerostack.mcprpc.wallet_utils import (
    xmr_to_atomic, atomic_to_xmr, format_xmr, parse_amount_input
)

# Convert XMR to atomic units
atomic = xmr_to_atomic(1.5)  # 1500000000000

# Convert atomic to XMR
xmr = atomic_to_xmr(1000000000000)  # 1.0

# Format for display
formatted = format_xmr(1500000000000)  # "1.500000000000 XMR"

# Parse user input
amount = parse_amount_input("1.5 XMR")  # 1500000000000
```

### Address Validation

```python
from monerostack.mcprpc.wallet_utils import validate_monero_address

# Validate address
is_valid = validate_monero_address("4B6fX7B6P8R6YU9X...")
if not is_valid:
    print("Invalid Monero address")
```

## Example Workflows

### Complete Wallet Setup

```python
import asyncio
from monerostack.mcprpc.mcp import MoneroTools
from monerostack.mcprpc.wallet_utils import validate_password_strength

async def setup_new_wallet():
    tools = MoneroTools()
    
    # 1. Create wallet
    wallet_result = tools.wallet("create", {
        "filename": "my_new_wallet",
        "password": "VerySecurePassword123!",
        "language": "English"
    })
    
    print(f"Wallet created: {wallet_result['address']}")
    
    # 2. Get and backup seed
    seed_result = tools.wallet("query_key", {"key_type": "mnemonic"})
    print("⚠️  BACKUP THIS SEED SECURELY:")
    print(seed_result['key'])
    
    # 3. Create receiving address
    subaddress = tools.wallet("create_address", {
        "label": "Primary receiving"
    })
    print(f"Receiving address: {subaddress['address']}")
    
    # 4. Check initial balance
    balance = tools.wallet("balance")
    print(f"Balance: {balance['balance_xmr']} XMR")

# Run the setup
asyncio.run(setup_new_wallet())
```

### Send Transaction

```python
async def send_transaction():
    tools = MoneroTools()
    
    # 1. Check balance
    balance = tools.wallet("balance")
    if balance['unlocked_balance'] == 0:
        print("No unlocked balance available")
        return
    
    # 2. Prepare transaction
    tx_result = tools.wallet("transfer", {
        "destinations": [{
            "address": "recipient_address_here",
            "amount": 1000000000000  # 1 XMR
        }],
        "priority": 2  # Medium priority
    })
    
    print(f"Transaction sent!")
    print(f"Hash: {tx_result['tx_hash']}")
    print(f"Fee: {tx_result['fee_xmr']} XMR")

asyncio.run(send_transaction())
```

## Troubleshooting

### Common Issues

1. **"monero-wallet-rpc not found"**
   - Install Monero software from getmonero.org
   - Ensure it's in your PATH

2. **"Permission denied"**
   - Check wallet directory permissions: `ls -la ~/.monero/`
   - Fix with: `chmod 700 ~/.monero/wallets`

3. **"Connection refused"**
   - Wallet RPC may not be running
   - Check with: `netstat -ln | grep 18082`

4. **"Invalid password"**
   - Ensure password matches wallet creation
   - Passwords are case-sensitive

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now wallet operations will show detailed logs
```

## Testing

### Demo Script

Run the comprehensive demo:

```bash
cd /home/d3cline/monerostack
python wallet_demo.py demo
```

### Basic Test

Test core functionality:

```bash
python wallet_demo.py test
```

### Testnet Usage

For safe testing:

```bash
export MONERO_NETWORK="testnet"
export MONERO_DAEMON_ADDRESS="testnet.moneroworld.com:28081"

# Now create testnet wallets for safe testing
```

## Integration with VS Code MCP

The wallet functionality is fully integrated with the VS Code MCP interface. You can use all wallet operations through VS Code:

1. Open VS Code
2. Use Ctrl+Shift+P → "MCP: Chat"
3. Ask for wallet operations like:
   - "Create a new Monero wallet"
   - "Check my wallet balance"
   - "Send 1 XMR to address..."

## Security Considerations

**CRITICAL WARNINGS:**

1. **Never store private keys or seeds in plain text**
2. **Always use hardware wallets for large amounts**
3. **Test everything on testnet first**
4. **Keep software updated**
5. **Use dedicated machines for large transactions**
6. **Verify all addresses before sending**
7. **Make multiple backup copies of your seed**

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review Monero documentation: https://www.getmonero.org/resources/
3. Check MoneroStack issues on GitHub

## License

This wallet functionality follows the same license as the main MoneroStack project.
