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
    help = "Quick remote node test against the configured Cake region (get_info + last header)."

    def handle(self, *args, **options):
        region = getattr(settings, "MONERO_REGION", "us")
        url = settings.MONERO_NODES.get(region, settings.MONERO_NODES["default"])
        self.stdout.write(f"Node: {url} (region={region})")

        ok, res = rpc(url, "get_info", timeout=15)
        if not ok:
            self.stdout.write(self.style.ERROR(f"get_info -> {res}"))
            return
        h = res.get("height")
        th = res.get("target_height") or h
        lag = (th or 0) - (h or 0)
        self.stdout.write(self.style.SUCCESS(f"get_info: height={h} target={th} lag={lag}"))

        ok2, res2 = rpc(url, "get_last_block_header", timeout=15)
        if ok2:
            bh = res2.get("block_header", {})
            out = {"height": bh.get("height"), "hash": bh.get("hash"), "timestamp": bh.get("timestamp")}
            self.stdout.write(self.style.SUCCESS("last_block_header: " + json.dumps(out)))
        else:
            self.stdout.write(self.style.WARNING(f"last_block_header -> {res2}"))

        self.stdout.write("Done.")
