# Django MCP ↔ Monero Bridge

> **Say it, ship it, stack the sats.**  
> A drop-in [django-mcp-server](https://github.com/opalstack/django-mcp-server) toolset that lets any MCP client (Copilot chat, CLI, whatever) talk straight to **`monero-wallet-rpc`**—with multi-node fail-over, performance-aware caching, and privacy-first defaults.

---

## ✨ Features

| Feature | Why it matters |
|---------|----------------|
| **Full wallet API coverage** — balances, sub-addresses, transfers, daemon info & more | Everything you need for a SaaS wallet or payment rail in one tool. |
| **Dynamic node pool from monero.fail** — auto-benchmarks the healthiest public nodes every hour | Lowest latency without hand-curating a list yourself. |
| **Static fallback list** — Snipa, Seth-for-Privacy, MoneroWorld | Keeps you online even if `monero.fail` is down. |
| **Automatic multi-node fail-over** with connection-quality scoring | Keep rolling even when a node ghosts you. |
| **Battle-hardened transport layer** — pooling, retries, JSON-RPC error bubbling | Less boilerplate; clearer stack traces. |
| **Pure Django app** — no migrations, no models, no drama | Plug into any project in 60 seconds. |

---

## 🏃‍♂️ Quick-start

```bash
# (Optional) point at your own RPC and bypass the node pool
export MONERO_RPC_HOST=127.0.0.1
export MONERO_RPC_PORT=28088

pip install -r requirements.in
python manage.py migrate
python manage.py runserver
````

---

## ⚡ Using it from an MCP client

```text
chat: monero get_balance {"account_index":0}
chat: monero transfer {"destinations":[{"address":"84…","amount":1000000000000}]}
chat: monero get_info
```

Each call is just an **`action`** plus an optional **`payload`**—exactly the schema defined in `MoneroTools.monero`. Your client gets raw JSON from `monero-wallet-rpc`, with any transport errors bubbled up verbatim.

---

## 🌐 How node selection works

1. **Cold start**

   * Fetches `https://monero.fail/nodes.json`, pings the candidates, and keeps the ten fastest clearnet nodes.
   * Can’t reach `monero.fail`? Falls back to the baked-in list (Snipa, Seth-for-Privacy, MoneroWorld).

2. **Warm runs**

   * Reads the cached, already-benchmarked node pool from `~/.monero_nodes_cache.pkl`.
   * A background thread refreshes from **monero.fail** hourly or sooner if too many nodes flake out.

3. **Forcing your own node**

   * Set `MONERO_RPC_HOST`, `MONERO_RPC_PORT`, and optionally `MONERO_RPC_SCHEME`.
   * The dynamic pool and fallback list are skipped entirely.

---

## 🔧 Configuration

| Env var                  | Default                     | Purpose                                   |
| ------------------------ | --------------------------- | ----------------------------------------- |
| `MONERO_RPC_HOST`        | *(None)*                    | Hostname / IP of a single node to force   |
| `MONERO_RPC_PORT`        | *(None)*                    | Port for that node                        |
| `MONERO_RPC_SCHEME`      | `http`                      | Switch to `https` if the node supports it |
| `MONERO_RPC_TIMEOUT`     | `8` seconds                 | Fail-over speed                           |
| `MONERO_RPC_MAX_RETRIES` | `1`                         | Retries before jumping nodes              |
| `MONERO_NODE_CACHE_PATH` | `~/.monero_nodes_cache.pkl` | Where the ping results live               |
| `MONERO_NODE_CACHE_TTL`  | `3600` (s)                  | How often to refresh from **monero.fail** |

---

## 🛡️ Security notes

* **Hot wallet** — `monero-wallet-rpc` holds your spend key; treat it like any secret.
* **Privacy** — Default is random public nodes; for maximum op-sec run your own daemon + wallet.
* **HTTPS** — Use SSL endpoints whenever possible; static list already does.

---

## 📈 Roadmap

* [ ] Integration tests against `stagenet`

---

## 🤝 Contributing

1. Fork & clone
2. Send a PR—contributors get a shout-out (and probably a 🎉).

---

## 📜 License

Released under the **GNU General Public License v3.0**.
Share, modify, distribute—just keep derivatives under GPL-3 and include the license text. No warranty, express or implied.

---

*Built by the Opalstack crew & the Monero fam. Vibe Deploy and ride the magic internet money wave.*


