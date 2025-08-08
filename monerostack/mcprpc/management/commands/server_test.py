import json
import requests
from django.core.management.base import BaseCommand
from django.conf import settings

def rpc(url: str, method: str, params=None, timeout: int = 10):
    body = {"jsonrpc": "2.0", "id": "0", "method": method}
    if params is not None:
        body["params"] = params
    r = requests.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        return False, data["error"]
    return True, data.get("result", data)

class Command(BaseCommand):
    help = "Check all configured Monero nodes and report online status (get_info + last_block_header)."

    def handle(self, *args, **options):
        nodes = getattr(settings, "MONERO_NODES", {})
        timeout = getattr(settings, "MONERO_RPC_TIMEOUT", 15)

        if not nodes:
            self.stdout.write(self.style.ERROR("No MONERO_NODES configured in settings."))
            return

        keys = sorted(nodes.keys())
        total = 0
        ok_count = 0
        failures = []

        self.stdout.write(f"Testing {len(keys)} configured nodes (timeout={timeout}s)...")

        for name in keys:
            url = nodes[name]
            total += 1
            prefix = f"[{name}] "
            try:
                ok, res = rpc(url, "get_info", timeout=timeout)
            except requests.RequestException as e:
                failures.append((name, f"request error: {e}"))
                self.stdout.write(self.style.ERROR(prefix + f"OFFLINE -> {e}"))
                continue

            if not ok:
                failures.append((name, f"rpc error: {res}"))
                self.stdout.write(self.style.ERROR(prefix + f"OFFLINE (get_info error) -> {res}"))
                continue

            h = res.get("height")
            th = res.get("target_height") or h
            lag = (th or 0) - (h or 0)
            ok_count += 1
            self.stdout.write(self.style.SUCCESS(prefix + f"OK height={h} target={th} lag={lag}"))

            # Optional: try last_block_header for additional signal
            try:
                ok2, res2 = rpc(url, "get_last_block_header", timeout=timeout)
                if ok2:
                    bh = res2.get("block_header", {})
                    out = {
                        "height": bh.get("height"),
                        "hash": bh.get("hash"),
                        "timestamp": bh.get("timestamp"),
                    }
                    self.stdout.write(self.style.HTTP_INFO(prefix + "last_block_header " + json.dumps(out)))
                else:
                    self.stdout.write(self.style.WARNING(prefix + f"last_block_header -> {res2}"))
            except requests.RequestException as e:
                self.stdout.write(self.style.WARNING(prefix + f"last_block_header request error -> {e}"))

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Online: {ok_count}/{total}"))
        if failures:
            self.stdout.write(self.style.ERROR("Failures:"))
            for name, err in failures:
                self.stdout.write(self.style.ERROR(f"- {name}: {err}"))
        self.stdout.write("Done.")
