MCP-chatbot — local MCP helper and multi-source web search

Short summary
- A small project that provides a local MCP tool (via `hieu.py`) which aggregates web search results from multiple sources (SerpAPI, Serper, DuckDuckGo HTML). The `mcp_pipe.py` connects an MCP WebSocket endpoint to run the MCP script. The previous Tkinter GUI has been removed — use `start_main.py` (headless) to configure and run the service.

How to run (Linux / macOS / WSL)
1. Create and activate a virtual environment and install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Configure API keys
- `config.json` in the repo can contain keys (SERPAPI_KEY is present). Prefer putting secrets in a `.env` file for runtime or in your OS environment variables.

3. Configure and run headless service
- Save a MCP endpoint to config.json:

```bash
python start_main.py save-config --mcp-endpoint "wss://your-mcp-endpoint"
```

- Start the service in background:

```bash
python start_main.py start
```

- Run the service in foreground (logs to stdout):

```bash
python start_main.py start --foreground
```

Notes & recommended fixes
- `hieu.py` expects a package `mcp.server.fastmcp` (FastMCP). Make sure `fastmcp` is available or adapt imports.
- `mcp_pipe.py` reads `MCP_ENDPOINT` from `config_manager.load_config()` and sets it as an env var. Ensure `CONFIG_PATH` in `config_manager.py` is writable.
Notes
- `start_main.py` replaces the previous GUI and uses `sys.executable` to spawn the service so it respects your virtual environment/interpreter.
- `hieu.py` expects a package `mcp.server.fastmcp` (FastMCP). Make sure `fastmcp` is available or adapt imports.
- `mcp_pipe.py` reads `MCP_ENDPOINT` from `config_manager.load_config()` and sets it as an env var. Ensure `CONFIG_PATH` in `config_manager.py` is writable.

Security
- Don't commit `config.json` or `.env` with API keys. `.gitignore` added to help.

Next steps
- Add unit tests for the search adapters (happy path + network failure)
- Add graceful shutdown handling for subprocesses in `main.py` and more robust logging rotation
