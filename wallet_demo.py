#!/usr/bin/env python3
"""
Example script demonstrating MoneroStack wallet functionality.

This script shows how to use the extended MoneroStack MCP for wallet operations
including creating wallets, sending transactions, and managing keys.

SECURITY WARNING: This is for demonstration purposes only.
In production, never hardcode passwords or mnemonic seeds.
"""

import asyncio
import sys
import os
import getpass
from typing import Dict, Any

# Add the MoneroStack directory to the Python path
sys.path.insert(0, '/home/d3cline/monerostack')

from monerostack.mcprpc.mcp import MoneroTools
from monerostack.mcprpc.wallet_utils import (
    validate_monero_address, 
    validate_password_strength,
    xmr_to_atomic,
    atomic_to_xmr,
    format_xmr,
    parse_amount_input
)
from monerostack.mcprpc.wallet_config import WalletConfigManager


class WalletDemo:
    """Demonstration of wallet functionality."""
    
    def __init__(self):
        """Initialize the wallet demo."""
        self.monero_tools = MoneroTools()
        self.config_manager = WalletConfigManager()
        self.config = self.config_manager.load_config()
        
    def print_banner(self):
        """Print welcome banner."""
        print("=" * 60)
        print("🔒 MoneroStack Wallet Demo")
        print("=" * 60)
        print("This demo shows wallet functionality including:")
        print("• Creating and restoring wallets")
        print("• Checking balances")
        print("• Sending transactions")
        print("• Managing addresses and keys")
        print("• Security best practices")
        print("=" * 60)
        print()
    
    async def demo_node_connectivity(self):
        """Demonstrate node connectivity checking."""
        print("📡 Checking daemon node connectivity...")
        
        try:
            # Check node status
            status = self.monero_tools.monero("get_node_status")
            print(f"✅ Connected to: {status['current_node']}")
            print(f"📊 Total nodes available: {status['total_nodes']}")
            
            # Get basic blockchain info
            info = self.monero_tools.monero("get_info")
            height = info.get("height", 0)
            difficulty = info.get("difficulty", 0)
            
            print(f"🔗 Current height: {height:,}")
            print(f"⚡ Network difficulty: {difficulty:,}")
            print()
            
        except Exception as e:
            print(f"❌ Error checking nodes: {e}")
            return False
        
        return True
    
    async def demo_wallet_management(self):
        """Demonstrate wallet creation and management."""
        print("💼 Wallet Management Demo")
        print("-" * 30)
        
        try:
            # List existing wallets
            wallets = self.monero_tools.wallet("list")
            print(f"📁 Found {wallets['count']} existing wallets:")
            
            for wallet in wallets.get('wallets', []):
                print(f"  • {wallet['name']} - {wallet.get('address', 'N/A')[:20]}...")
            print()
            
            # Demo wallet creation (for demonstration only)
            demo_wallet_name = "demo_wallet_test"
            demo_password = "demo_password_123_SECURE!"
            
            print(f"🔧 Creating demo wallet: {demo_wallet_name}")
            print("⚠️  Using demo password for illustration only!")
            
            # Validate password strength
            password_check = validate_password_strength(demo_password)
            print(f"🔐 Password strength: {'✅ Good' if password_check['valid'] else '❌ Weak'}")
            
            # Create wallet (this would normally prompt for secure password)
            # Note: In production, never use hardcoded passwords!
            create_result = self.monero_tools.wallet("create", {
                "filename": demo_wallet_name,
                "password": demo_password,
                "language": "English"
            })
            
            print(f"✅ Wallet created successfully!")
            print(f"📍 Address: {create_result.get('address', 'N/A')}")
            print(f"🔑 Mnemonic seed available via query_key action")
            print()
            
        except Exception as e:
            print(f"❌ Error in wallet management: {e}")
            print()
    
    async def demo_address_operations(self):
        """Demonstrate address operations."""
        print("📮 Address Operations Demo")
        print("-" * 30)
        
        try:
            # Get primary address
            address_info = self.monero_tools.wallet("address")
            primary_address = address_info.get('address', 'N/A')
            
            print(f"🏠 Primary address: {primary_address}")
            
            # Validate the address
            is_valid = validate_monero_address(primary_address)
            print(f"✅ Address validation: {'Valid' if is_valid else 'Invalid'}")
            
            # Create a subaddress
            subaddress_result = self.monero_tools.wallet("create_address", {
                "account_index": 0,
                "label": "Demo subaddress"
            })
            
            print(f"📬 Created subaddress: {subaddress_result.get('address', 'N/A')}")
            print()
            
        except Exception as e:
            print(f"❌ Error in address operations: {e}")
            print()
    
    async def demo_balance_checking(self):
        """Demonstrate balance checking."""
        print("💰 Balance Checking Demo")
        print("-" * 30)
        
        try:
            balance_info = self.monero_tools.wallet("balance")
            
            balance_atomic = balance_info.get('balance', 0)
            unlocked_atomic = balance_info.get('unlocked_balance', 0)
            
            balance_xmr = atomic_to_xmr(balance_atomic)
            unlocked_xmr = atomic_to_xmr(unlocked_atomic)
            
            print(f"💵 Total balance: {format_xmr(balance_atomic)}")
            print(f"🔓 Unlocked balance: {format_xmr(unlocked_atomic)}")
            print(f"🔒 Locked balance: {format_xmr(balance_atomic - unlocked_atomic)}")
            print()
            
            if balance_atomic == 0:
                print("ℹ️  This is a new wallet with zero balance.")
                print("   Send some Monero to the address above to see transactions.")
                print()
            
        except Exception as e:
            print(f"❌ Error checking balance: {e}")
            print()
    
    async def demo_transaction_preparation(self):
        """Demonstrate transaction preparation (without sending)."""
        print("📤 Transaction Preparation Demo")
        print("-" * 30)
        
        try:
            # Example recipient address (this is a test address, not real)
            example_address = "4B6fX7B6P8R6YU9XfF2A8CqDvQ4GHJ7K2R8M9N5T6W7X8Y9Z1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P7Q8R9S0T1U2V3W4X5Y6Z7A8B9C0D1E2"
            
            print("🎯 Example transaction preparation:")
            print(f"   Recipient: {example_address[:20]}...")
            
            # Validate recipient address
            is_valid_recipient = validate_monero_address(example_address)
            print(f"   Address valid: {'✅ Yes' if is_valid_recipient else '❌ No'}")
            
            # Parse amount examples
            amount_examples = ["1.5", "0.001 XMR", "1000000000000"]
            
            print("\n💱 Amount parsing examples:")
            for amount_str in amount_examples:
                try:
                    atomic_amount = parse_amount_input(amount_str)
                    xmr_amount = atomic_to_xmr(atomic_amount)
                    print(f"   '{amount_str}' → {atomic_amount} atomic units ({xmr_amount:.12f} XMR)")
                except ValueError as e:
                    print(f"   '{amount_str}' → Error: {e}")
            
            print("\n⚠️  Note: This demo does not send actual transactions.")
            print("   Use the 'transfer' action with real addresses to send Monero.")
            print()
            
        except Exception as e:
            print(f"❌ Error in transaction preparation: {e}")
            print()
    
    async def demo_security_features(self):
        """Demonstrate security features."""
        print("🔐 Security Features Demo")
        print("-" * 30)
        
        try:
            # Show wallet security checklist
            from monerostack.mcprpc.wallet_utils import wallet_security_checklist
            
            checklist = wallet_security_checklist()
            print("📋 Wallet Security Checklist:")
            for item in checklist[:5]:  # Show first 5 items
                print(f"   {item}")
            print(f"   ... and {len(checklist) - 5} more recommendations")
            print()
            
            # Demo password strength validation
            test_passwords = ["weak", "Better123", "VerySecurePassword123!@#"]
            
            print("🔑 Password Strength Testing:")
            for password in test_passwords:
                strength = validate_password_strength(password)
                status = "✅ Strong" if strength['valid'] else "❌ Weak"
                print(f"   '{password}' → {status} (Score: {strength['score']}/6)")
            
            print()
            
        except Exception as e:
            print(f"❌ Error in security demo: {e}")
            print()
    
    async def demo_wallet_rpc_management(self):
        """Demonstrate wallet RPC management."""
        print("🔧 Wallet RPC Management Demo")
        print("-" * 30)
        
        try:
            # Start wallet RPC (for demonstration)
            print("🚀 Starting wallet RPC server...")
            
            rpc_result = self.monero_tools.wallet("start_rpc", {
                "wallet_name": "demo_wallet_test",
                "password": "demo_password_123_SECURE!",
                "port": 18082
            })
            
            print(f"✅ Wallet RPC started on: {rpc_result.get('rpc_url', 'N/A')}")
            print(f"📊 Status: {rpc_result.get('status', 'N/A')}")
            
            # Wait a moment for RPC to fully initialize
            await asyncio.sleep(2)
            
            # Test RPC connectivity by checking balance again
            balance_info = self.monero_tools.wallet("balance")
            print(f"🔗 RPC connectivity test: ✅ Success")
            
            print()
            
        except Exception as e:
            print(f"❌ Error in RPC management: {e}")
            print()
    
    async def cleanup(self):
        """Cleanup demo resources."""
        print("🧹 Cleaning up demo resources...")
        
        try:
            # Stop wallet RPC
            stop_result = self.monero_tools.wallet("stop_rpc")
            print(f"🛑 Wallet RPC stopped: {stop_result.get('status', 'N/A')}")
            
            # Note: In a real scenario, you might want to delete demo wallets
            # but we'll leave them for inspection
            
            print("✅ Cleanup completed")
            print()
            
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
            print()
    
    async def run_full_demo(self):
        """Run the complete wallet demo."""
        self.print_banner()
        
        # Check if Monero software is available
        if not os.system("which monero-wallet-rpc > /dev/null 2>&1") == 0:
            print("❌ monero-wallet-rpc not found in PATH")
            print("   Please install Monero software first:")
            print("   https://www.getmonero.org/downloads/")
            return
        
        try:
            # Run demo sections
            await self.demo_node_connectivity()
            await self.demo_wallet_management()
            await self.demo_wallet_rpc_management()
            await self.demo_address_operations()
            await self.demo_balance_checking()
            await self.demo_transaction_preparation()
            await self.demo_security_features()
            
            print("🎉 Demo completed successfully!")
            print()
            print("📚 Next steps:")
            print("• Read the wallet security checklist")
            print("• Practice with testnet before using mainnet")
            print("• Always backup your mnemonic seed securely")
            print("• Use hardware wallets for large amounts")
            
        except KeyboardInterrupt:
            print("\n⚠️  Demo interrupted by user")
        except Exception as e:
            print(f"\n❌ Demo error: {e}")
        finally:
            await self.cleanup()


def print_usage():
    """Print usage information."""
    print("MoneroStack Wallet Demo")
    print("Usage: python wallet_demo.py [command]")
    print()
    print("Commands:")
    print("  demo     Run full interactive demo")
    print("  test     Run basic functionality test")
    print("  help     Show this help message")
    print()


async def run_basic_test():
    """Run basic functionality test."""
    print("🧪 Running basic wallet functionality test...")
    
    tools = MoneroTools()
    
    try:
        # Test node connectivity
        status = tools.monero("get_node_status")
        print(f"✅ Node connectivity: {status['connection_status']}")
        
        # Test wallet listing
        wallets = tools.wallet("list")
        print(f"✅ Wallet listing: Found {wallets['count']} wallets")
        
        print("🎉 Basic test passed!")
        
    except Exception as e:
        print(f"❌ Basic test failed: {e}")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        command = "demo"
    else:
        command = sys.argv[1].lower()
    
    if command == "help":
        print_usage()
    elif command == "test":
        await run_basic_test()
    elif command == "demo":
        demo = WalletDemo()
        await demo.run_full_demo()
    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
