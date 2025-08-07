"""
Wallet utility functions for MoneroStack MCP.
"""

import os
import getpass
import re
import hashlib
import secrets
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger("mcp.wallet_utils")


def validate_monero_address(address: str) -> bool:
    """
    Validate Monero address format.
    
    Args:
        address: Monero address to validate
        
    Returns:
        True if address appears valid, False otherwise
    """
    if not address:
        return False
    
    # Mainnet addresses start with 4, testnet with 9/A/B, stagenet with 5
    if not address[0] in ['4', '5', '9', 'A', 'B']:
        return False
    
    # Standard address length is 95 characters
    if len(address) != 95:
        return False
    
    # Check if it contains only valid base58 characters
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return all(c in valid_chars for c in address)


def validate_integrated_address(address: str) -> bool:
    """
    Validate Monero integrated address format.
    
    Args:
        address: Integrated address to validate
        
    Returns:
        True if address appears valid, False otherwise
    """
    if not address:
        return False
    
    # Integrated addresses start with 4 (mainnet) and are 106 characters
    if not address.startswith('4') or len(address) != 106:
        return False
    
    # Check if it contains only valid base58 characters
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    return all(c in valid_chars for c in address)


def validate_payment_id(payment_id: str) -> bool:
    """
    Validate payment ID format.
    
    Args:
        payment_id: Payment ID to validate
        
    Returns:
        True if payment ID is valid, False otherwise
    """
    if not payment_id:
        return False
    
    # Payment IDs are 16 or 64 character hex strings
    if len(payment_id) not in [16, 64]:
        return False
    
    # Check if it's a valid hex string
    try:
        int(payment_id, 16)
        return True
    except ValueError:
        return False


def validate_mnemonic_seed(seed: str) -> bool:
    """
    Basic validation of mnemonic seed format.
    
    Args:
        seed: Mnemonic seed phrase to validate
        
    Returns:
        True if seed appears valid, False otherwise
    """
    if not seed:
        return False
    
    words = seed.strip().split()
    
    # Monero uses 25-word mnemonic seeds
    if len(words) != 25:
        return False
    
    # Basic check - all words should be alphabetic
    return all(word.isalpha() for word in words)


def xmr_to_atomic(xmr_amount: float) -> int:
    """
    Convert XMR to atomic units.
    
    Args:
        xmr_amount: Amount in XMR
        
    Returns:
        Amount in atomic units
    """
    return int(xmr_amount * 1e12)


def atomic_to_xmr(atomic_amount: int) -> float:
    """
    Convert atomic units to XMR.
    
    Args:
        atomic_amount: Amount in atomic units
        
    Returns:
        Amount in XMR
    """
    return atomic_amount / 1e12


def format_xmr(atomic_amount: int, decimals: int = 12) -> str:
    """
    Format atomic units as readable XMR string.
    
    Args:
        atomic_amount: Amount in atomic units
        decimals: Number of decimal places to show
        
    Returns:
        Formatted XMR string
    """
    xmr_amount = atomic_to_xmr(atomic_amount)
    return f"{xmr_amount:.{decimals}f} XMR"


def secure_password_prompt(prompt: str = "Enter wallet password: ") -> str:
    """
    Securely prompt for password without echoing to terminal.
    
    Args:
        prompt: Password prompt text
        
    Returns:
        Password string
    """
    return getpass.getpass(prompt)


def validate_password_strength(password: str) -> Dict[str, Any]:
    """
    Validate password strength and return detailed feedback.
    
    Args:
        password: Password to validate
        
    Returns:
        Dictionary with validation results
    """
    result = {
        "valid": False,
        "score": 0,
        "feedback": []
    }
    
    if not password:
        result["feedback"].append("Password cannot be empty")
        return result
    
    # Length check
    if len(password) < 12:
        result["feedback"].append("Password should be at least 12 characters long")
    else:
        result["score"] += 1
    
    # Character variety checks
    if not re.search(r'[a-z]', password):
        result["feedback"].append("Password should contain lowercase letters")
    else:
        result["score"] += 1
    
    if not re.search(r'[A-Z]', password):
        result["feedback"].append("Password should contain uppercase letters")
    else:
        result["score"] += 1
    
    if not re.search(r'\d', password):
        result["feedback"].append("Password should contain numbers")
    else:
        result["score"] += 1
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        result["feedback"].append("Password should contain special characters")
    else:
        result["score"] += 1
    
    # Common password check
    common_passwords = ['password', '123456', 'password123', 'admin', 'letmein']
    if password.lower() in common_passwords:
        result["feedback"].append("Password is too common")
    else:
        result["score"] += 1
    
    result["valid"] = result["score"] >= 4
    
    if result["valid"]:
        result["feedback"] = ["Password strength is good"]
    
    return result


def generate_secure_password(length: int = 16) -> str:
    """
    Generate a cryptographically secure password.
    
    Args:
        length: Password length
        
    Returns:
        Generated password
    """
    import string
    
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(characters) for _ in range(length))
    
    # Ensure it meets our strength requirements
    validation = validate_password_strength(password)
    if not validation["valid"]:
        # Regenerate if somehow it doesn't meet requirements
        return generate_secure_password(length)
    
    return password


def calculate_fee_priority(priority: int) -> str:
    """
    Convert numeric priority to descriptive string.
    
    Args:
        priority: Priority level (1-4)
        
    Returns:
        Description of priority level
    """
    priorities = {
        1: "Low (slow, cheap)",
        2: "Medium-Low",
        3: "Medium-High", 
        4: "High (fast, expensive)"
    }
    
    return priorities.get(priority, "Unknown")


def estimate_transfer_time(priority: int) -> str:
    """
    Estimate transfer confirmation time based on priority.
    
    Args:
        priority: Priority level (1-4)
        
    Returns:
        Estimated time string
    """
    times = {
        1: "20-40 minutes",
        2: "10-20 minutes",
        3: "4-10 minutes",
        4: "2-4 minutes"
    }
    
    return times.get(priority, "Unknown")


def parse_amount_input(amount_str: str) -> int:
    """
    Parse amount input and convert to atomic units.
    Supports both XMR and atomic unit inputs.
    
    Args:
        amount_str: Amount string (e.g., "1.5", "1.5 XMR", "1500000000000")
        
    Returns:
        Amount in atomic units
        
    Raises:
        ValueError: If amount format is invalid
    """
    if not amount_str:
        raise ValueError("Amount cannot be empty")
    
    amount_str = amount_str.strip().lower()
    
    # Remove "xmr" suffix if present
    if amount_str.endswith(" xmr") or amount_str.endswith("xmr"):
        amount_str = amount_str.replace("xmr", "").strip()
        is_xmr = True
    else:
        # If it looks like a decimal number, assume XMR
        is_xmr = "." in amount_str
    
    try:
        if is_xmr:
            xmr_amount = float(amount_str)
            if xmr_amount < 0:
                raise ValueError("Amount cannot be negative")
            return xmr_to_atomic(xmr_amount)
        else:
            atomic_amount = int(amount_str)
            if atomic_amount < 0:
                raise ValueError("Amount cannot be negative")
            return atomic_amount
    except (ValueError, OverflowError) as e:
        raise ValueError(f"Invalid amount format: {amount_str}") from e


def format_wallet_summary(wallet_data: Dict[str, Any]) -> str:
    """
    Format wallet information for display.
    
    Args:
        wallet_data: Wallet data dictionary
        
    Returns:
        Formatted wallet summary string
    """
    name = wallet_data.get("name", "Unknown")
    address = wallet_data.get("address", "N/A")
    created_at = wallet_data.get("created_at")
    
    summary = f"Wallet: {name}\n"
    summary += f"Address: {address}\n"
    
    if created_at:
        import datetime
        created_date = datetime.datetime.fromtimestamp(created_at)
        summary += f"Created: {created_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    return summary


def validate_wallet_name(name: str) -> bool:
    """
    Validate wallet name format.
    
    Args:
        name: Wallet name to validate
        
    Returns:
        True if name is valid, False otherwise
    """
    if not name:
        return False
    
    # Name should be alphanumeric with optional underscores/hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False
    
    # Reasonable length limits
    if len(name) < 1 or len(name) > 50:
        return False
    
    # Don't allow names that might conflict with system files
    reserved_names = ['con', 'prn', 'aux', 'nul', 'com1', 'lpt1']
    if name.lower() in reserved_names:
        return False
    
    return True


def create_backup_filename(wallet_name: str) -> str:
    """
    Create a backup filename with timestamp.
    
    Args:
        wallet_name: Original wallet name
        
    Returns:
        Backup filename
    """
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{wallet_name}_backup_{timestamp}"


def wallet_security_checklist() -> List[str]:
    """
    Return a security checklist for wallet users.
    
    Returns:
        List of security recommendations
    """
    return [
        "✓ Use a strong, unique password for your wallet",
        "✓ Write down your 25-word mnemonic seed and store it safely offline",
        "✓ Never share your mnemonic seed or private keys with anyone",
        "✓ Make regular backups of your wallet files",
        "✓ Keep your Monero software updated",
        "✓ Use a dedicated computer for large transactions",
        "✓ Verify recipient addresses carefully before sending",
        "✓ Consider using a hardware wallet for large amounts",
        "✓ Test wallet restoration with small amounts first",
        "✓ Keep multiple copies of your seed in different secure locations"
    ]


class WalletSecurityHelper:
    """Helper class for wallet security operations."""
    
    @staticmethod
    def check_wallet_permissions(wallet_dir: str) -> Dict[str, Any]:
        """
        Check wallet directory permissions.
        
        Args:
            wallet_dir: Wallet directory path
            
        Returns:
            Permission check results
        """
        result = {
            "secure": False,
            "issues": [],
            "recommendations": []
        }
        
        if not os.path.exists(wallet_dir):
            result["issues"].append("Wallet directory does not exist")
            return result
        
        # Check directory permissions
        dir_stat = os.stat(wallet_dir)
        dir_mode = oct(dir_stat.st_mode)[-3:]
        
        if dir_mode != "700":
            result["issues"].append(f"Directory permissions are {dir_mode}, should be 700")
            result["recommendations"].append("Run: chmod 700 " + wallet_dir)
        
        # Check wallet file permissions
        wallet_files = [f for f in os.listdir(wallet_dir) if f.endswith('.keys')]
        
        for wallet_file in wallet_files:
            file_path = os.path.join(wallet_dir, wallet_file)
            file_stat = os.stat(file_path)
            file_mode = oct(file_stat.st_mode)[-3:]
            
            if file_mode != "600":
                result["issues"].append(f"{wallet_file} permissions are {file_mode}, should be 600")
                result["recommendations"].append(f"Run: chmod 600 {file_path}")
        
        result["secure"] = len(result["issues"]) == 0
        
        if result["secure"]:
            result["recommendations"].append("Wallet directory security looks good!")
        
        return result
    
    @staticmethod
    def secure_delete_file(file_path: str, passes: int = 3) -> bool:
        """
        Securely delete a file by overwriting it multiple times.
        
        Args:
            file_path: Path to file to delete
            passes: Number of overwrite passes
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                return True
            
            file_size = os.path.getsize(file_path)
            
            with open(file_path, "r+b") as f:
                for _ in range(passes):
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())
            
            os.remove(file_path)
            return True
            
        except Exception as e:
            logger.error(f"Failed to securely delete {file_path}: {e}")
            return False
