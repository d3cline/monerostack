"""
Django management command for stopping Monero wallet RPC.
"""
from django.core.management.base import BaseCommand, CommandError
import sys
from pathlib import Path
import json

# Universal import for service manager - works from anywhere in the project
def get_service_manager():
    """Import and return the service manager with universal path handling."""
    # Try multiple import paths
    import_paths = [
        # From project root
        lambda: __import__('monerostack.management.commands.service_manager', fromlist=['get_service_manager']).get_service_manager(),
        # From standalone management dir
        lambda: sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent)) or 
                __import__('monerostack.management.commands.service_manager', fromlist=['get_service_manager']).get_service_manager(),
        # Direct path resolution
        lambda: _import_from_management_dir()
    ]
    
    for import_func in import_paths:
        try:
            return import_func()
        except (ImportError, AttributeError):
            continue
    
    raise ImportError("Could not import service manager from any location")

def _import_from_management_dir():
    """Direct import from the management directory."""
    management_dir = Path(__file__).parent.parent.parent.parent.parent / "monerostack" / "management" / "commands"
    if management_dir.exists():
        sys.path.insert(0, str(management_dir.parent.parent))
        from management.commands.service_manager import get_service_manager as _get_service_manager
        return _get_service_manager
    raise ImportError("Management directory not found")


class Command(BaseCommand):
    help = 'Stop Monero wallet RPC service'

    def handle(self, *args, **options):
        try:
            service_manager_func = get_service_manager()
            service_manager = service_manager_func()
            
            result = service_manager.stop_service("wallet-rpc")
            
            self.stdout.write(
                self.style.SUCCESS(json.dumps(result, indent=2, default=str))
            )
            
        except Exception as e:
            raise CommandError(f'Failed to stop wallet RPC: {e}')
