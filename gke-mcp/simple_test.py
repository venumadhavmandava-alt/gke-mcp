import asyncio
import os
import sys
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Your verified GKE context
CTX = "gke_odev-elselk-rnd-indexer-faf9_us-central1_cos-rnd-cluster-2"

async def main():
    cmd = sys.executable 
    args = ["-m", "gke-mcp", "--transport", "stdio", "--path", "./config"]

    # Environment Setup
    env = os.environ.copy()
    env["USE_GKE_GCLOUD_AUTH_PLUGIN"] = "True"
    
    # Keep these for general gcloud/python library stability behind the proxy
    ca_cert = os.path.expanduser("~/netskope-ca.pem")
    if os.path.exists(ca_cert):
        env["REQUESTS_CA_BUNDLE"] = ca_cert
        env["SSL_CERT_FILE"] = ca_cert

    server_params = StdioServerParameters(command=cmd, args=args, env=env)

    try:
        async with stdio_client(server_params) as (stdio, write):
            async with ClientSession(stdio, write) as session:
                await session.initialize()
                print("✅ Connected to MCP server.")

                # 1. Target the correct cluster
                print(f"--- Switching to context: {CTX} ---")
                await session.call_tool("switch_context", {"context_name": CTX})

                # 2. Fetch namespaces
                print("\n--- Namespaces Found ---")
                result = await session.call_tool("get_namespaces", {})
                
                # FastMCP returns a list of TextContent objects
                for item in result.content:
                    # The response you saw was a JSON string inside the text field
                    data = json.loads(item.text)
                    if data.get("success"):
                        for ns in data.get("namespaces", []):
                            print(f" - {ns}")
                    else:
                        print(f"Error: {data.get('error')}")

    except Exception as e:
        print(f"💥 Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

