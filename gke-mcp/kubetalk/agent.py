# new-mcp/agents/kubernetes_devops/agent.py
import os
import ssl
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

# --- Global SSL Bypass ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    logging.info("SSL verification bypass applied.")
except Exception as e:
    logging.warning(f"Failed to apply SSL bypass: {e}")

def create_root_agent():
    mcp_root = os.getenv("MCP_ROOT")
    config_path = os.getenv("MCP_CONFIG")
    
    mcp_env = os.environ.copy()

    mcp_env["PYTHONPATH"] = mcp_root
    mcp_env["USE_GKE_GCLOUD_AUTH_PLUGIN"] = "True"

    # --- 2026 ALPN AUTH FIX ---
    # This resolves the 'missing selected ALPN property' error with Vertex AI
    mcp_env["GRPC_ENFORCE_ALPN_ENABLED"] = "false"
    
    # Total SSL Bypass
    mcp_env["PYTHONHTTPSVERIFY"] = "0"
    mcp_env["REQUESTS_CA_BUNDLE"] = ""
    mcp_env["SSL_CERT_FILE"] = ""
    
    # Stability Fixes
    mcp_env["PYTHONUNBUFFERED"] = "1"
    mcp_env["LOG_LEVEL"] = "ERROR"

    return LlmAgent(
#        model='gemini-2.0-flash',
        model='gemini-2.5-flash',
        name='kubetalk',
        instruction=(
            "You are an AI DevOps agent. "
        ),
        tools=[
            # Single Toolset: The K8sGPT-style analyzer is now NATIVE to gke-mcp
            MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="python3",
                        args=[
                            "-m", "gke-mcp", 
                            "--transport", "stdio", 
                            "--path", config_path
                        ],
                        env=mcp_env
                    ),
                    timeout=60 
                )
            )
        ]
    )

root_agent = create_root_agent()
