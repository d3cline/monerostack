# MoneroStack MCP Bridge (Cake-Only, Zero-Local)

**What this is:**  
A tiny Django app that exposes **Monero daemon JSON-RPC** as MCP tools using [`django-mcp-server`](https://github.com/omarbenhamid/django-mcp-server).  
It talks directly to **Cake Wallet public nodes** (HTTPS), so there’s **no local daemon** and **no blockchain download**.

---

## Features
- **MCP-native**: tools appear at `POST /mcp`
- **Read-only daemon methods**: `get_info`, `get_block_count`, `get_last_block_header`, `get_block`, `get_block_headers_range`, `on_get_block_hash`, `get_transactions`
- **Region switch** at runtime (`us`, `eu`, `default`) via an MCP tool
- **No state files**, no URL parsing drama, no local wallet/daemon

---

## Setup

```bash
git clone <this-repo>
cd monerostack
python -m venv env
source env/bin/activate
pip install django django-mcp-server requests

