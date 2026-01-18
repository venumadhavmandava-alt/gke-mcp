#!/usr/bin/env python3
import asyncio
import argparse
import logging
import ssl
import sys
import os
from .mcp_server import MCPServer

# --- FIX 1: IMMEDIATE REDIRECT ---
# Configure logging to ONLY use stderr and do it BEFORE anything else
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr  # Directs all logs away from the MCP data channel
)
logger = logging.getLogger("mcp-server-main")

# --- SSL Bypass ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    logger.info("SSL certificate verification is globally disabled.")
except Exception as e:
    logger.warning(f"Could not disable default SSL verification: {e}")

def main():
    parser = argparse.ArgumentParser(description="Run the Kubectl MCP Server.")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument('--path', type=str, required=True)
    args = parser.parse_args()

    mcp_server = MCPServer(name="kubernetes", port=args.port, path=args.path)

    # Use asyncio.run for cleaner startup on Python 3.10+
    try:
        if args.transport == "stdio":
            # Ensure no buffer delay
            os.environ["PYTHONUNBUFFERED"] = "1"
            asyncio.run(mcp_server.serve_stdio())
        else:
            asyncio.run(mcp_server.serve_sse(port=args.port))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Server crash: {e}", exc_info=True)

if __name__ == "__main__":
    main()
