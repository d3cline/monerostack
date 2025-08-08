"""
Django management command for starting Monero wallet RPC.
"""
from django.core.management.base import BaseCommand, CommandError
import subprocess
import os
import time
import requests
import json
from pathlib import Path


class Command(BaseCommand):
    help = 'Start Monero wallet RPC service'

    def add_arguments(self, parser):
        parser.add_argument('--wallet', type=str, help='Wallet name')
        parser.add_argument('--password', type=str, help='Wallet password')
        parser.add_argument('--port', type=int, default=18081, help='RPC port')

    def handle(self, *args, **options):
        try:
            port = options['port']
            wallet_name = options.get('wallet')
            password = options.get('password')
            
            # Check if already running
            if self.is_wallet_rpc_running(port):
                self.stdout.write(
                    self.style.WARNING(f"Wallet RPC already running on port {port}")
                )
                return
            
            # Build command
            cmd = [
                "monero-wallet-rpc",
                f"--rpc-bind-port={port}",
                "--disable-rpc-login",
                "--daemon-address=node.moneroworld.com:18089",
                "--trusted-daemon",
                "--rpc-bind-ip=127.0.0.1"
            ]
            
            # Add wallet-specific options if provided
            if wallet_name and password:
                wallet_dir = os.path.expanduser("~/.monero/wallets")
                os.makedirs(wallet_dir, mode=0o700, exist_ok=True)
                cmd.extend([
                    f"--wallet-file={wallet_dir}/{wallet_name}",
                    f"--password={password}"
                ])
            else:
                # For wallet creation, specify wallet directory only
                wallet_dir = os.path.expanduser("~/.monero/wallets")
                os.makedirs(wallet_dir, mode=0o700, exist_ok=True)
                cmd.append(f"--wallet-dir={wallet_dir}")
            
            # Start the process
            self.stdout.write(f"Starting wallet RPC: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            
            # Wait for startup
            time.sleep(3)
            
            # Test connection
            if self.is_wallet_rpc_running(port):
                result = {
                    "status": "started",
                    "pid": process.pid,
                    "port": port,
                    "rpc_url": f"http://127.0.0.1:{port}/json_rpc"
                }
                if wallet_name:
                    result["wallet_name"] = wallet_name
                
                self.stdout.write(
                    self.style.SUCCESS(json.dumps(result, indent=2))
                )
            else:
                raise CommandError("Wallet RPC failed to start")
                
        except Exception as e:
            raise CommandError(f'Failed to start wallet RPC: {e}')
    
    def is_wallet_rpc_running(self, port):
        """Check if wallet RPC is running on the specified port."""
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
