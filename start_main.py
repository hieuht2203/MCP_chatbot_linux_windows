"""Headless entrypoint to run MCP pipe and manage config on Linux/CLI.

This replaces the previous Tkinter GUI. It provides simple commands to
save configuration and to start the background service that runs
`mcp_pipe.py` and `hieu.py`.
"""

import argparse
import os
import subprocess
import sys
from config_manager import load_config, save_config


def start_service(foreground: bool = False) -> int:
    """Start the service that runs mcp_pipe.py and hieu.py.

    If foreground is True, this function will replace the current process
    with the mcp_pipe process (so logs flow to stdout). Otherwise it will
    start it as a background subprocess and return the PID.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_script = os.path.join(current_dir, "mcp_pipe.py")
    web_search_script = os.path.join(current_dir, "hieu.py")

    if foreground:
        # exec the mcp script so it inherits stdio
        os.execv(sys.executable, [sys.executable, mcp_script, web_search_script])

    proc = subprocess.Popen([sys.executable, mcp_script, web_search_script], cwd=current_dir)
    print(f"Started service in background with PID {proc.pid}")
    return proc.pid


def cli_save_config(mcp_endpoint: str) -> None:
    cfg = load_config()
    cfg["MCP_ENDPOINT"] = mcp_endpoint
    save_config(cfg)
    print("Configuration saved:", cfg)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Headless MCP service manager")
    sub = parser.add_subparsers(dest="command")

    save = sub.add_parser("save-config", help="Save MCP endpoint to config.json")
    save.add_argument("--mcp-endpoint", required=True, help="MCP endpoint URL")

    start = sub.add_parser("start", help="Start the service in background")
    start.add_argument("--foreground", action="store_true", help="Run service in foreground (attach stdout)")

    args = parser.parse_args(argv)

    if args.command == "save-config":
        cli_save_config(args.mcp_endpoint)
        return

    if args.command == "start":
        if args.foreground:
            print("Starting service in foreground...")
            start_service(foreground=True)
        else:
            pid = start_service(foreground=False)
            print(f"Service started (PID: {pid})")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
