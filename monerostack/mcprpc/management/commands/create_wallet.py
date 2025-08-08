"""
Django management command for creating Monero wallets.
"""
from django.core.management.base import BaseCommand, CommandError
import requests
import json
import time
import subprocess
import os


class Command(BaseCommand):
    help = 'Create a new Monero wallet'

    def add_arguments(self, parser):
        parser.add_argument('--wallet', type=str, required=True, help='Wallet name')
        parser.add_argument('--password', type=str, required=True, help='Wallet password')
        parser.add_argument('--language', type=str, default='English', help='Wallet language')
        parser.add_argument('--port', type=int, default=18081, help='RPC port')

    def handle(self, *args, **options):
        try:
            port = options['port']
            wallet_name = options['wallet']
            password = options['password']
            language = options['language']
            
            # Ensure wallet RPC is running (without a specific wallet)
            if not self.is_wallet_rpc_running(port):
                self.start_wallet_rpc_for_creation(port)
                time.sleep(3)
            
            # Create the wallet
            result = self.create_wallet_via_rpc(port, wallet_name, password, language)
            
            self.stdout.write(
                self.style.SUCCESS(json.dumps(result, indent=2))
            )
            
        except Exception as e:
            raise CommandError(f'Failed to create wallet: {e}')
    
    def is_wallet_rpc_running(self, port):
        """Check if wallet RPC is running."""
        try:
            response = requests.post(
                f"http://127.0.0.1:{port}/json_rpc",
                json={
                    "jsonrpc": "2.0",
                    "id": "0",
                    "method": "get_version"
                },
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    def start_wallet_rpc_for_creation(self, port):
        """Start wallet RPC without a specific wallet for creation."""
        wallet_dir = os.path.expanduser("~/.monero/wallets")
        os.makedirs(wallet_dir, mode=0o700, exist_ok=True)
        
        cmd = [
            "monero-wallet-rpc",
            f"--rpc-bind-port={port}",
            "--disable-rpc-login",
            "--daemon-address=node.moneroworld.com:18089",
            "--trusted-daemon",
            "--rpc-bind-ip=127.0.0.1",
            f"--wallet-dir={wallet_dir}"
        ]
        
        self.stdout.write(f"Starting wallet RPC for creation: {' '.join(cmd)}")
        
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid
        )
    
    def create_wallet_via_rpc(self, port, filename, password, language):
        """Create wallet via RPC call."""
        payload = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": "create_wallet",
            "params": {
                "filename": filename,
                "password": password,
                "language": language
            }
        }
        
        response = requests.post(
            f"http://127.0.0.1:{port}/json_rpc",
            json=payload,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(f"HTTP error: {response.status_code}")
        
        data = response.json()
        if "error" in data:
            raise Exception(f"RPC error: {data['error']}")
        
        return {
            "status": "created",
            "wallet_name": filename,
            "message": "Wallet created successfully"
        }
