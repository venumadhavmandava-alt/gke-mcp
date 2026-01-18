# new-mcp/agents/kubernetes_devops/agent.py
import os
import ssl
import logging
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams
from google.adk.planners import BuiltInPlanner
from google.genai import types
from google.adk.apps.app import App, ContextCacheConfig, EventsCompactionConfig
from mcp import StdioServerParameters

# --- Global SSL Bypass (Local Dev Only) ---
try:
    ssl._create_default_https_context = ssl._create_unverified_context
    logging.info("SSL verification bypass applied.")
except Exception as e:
    logging.warning(f"Failed to apply SSL bypass: {e}")

def create_root_agent():
    # Force use of global endpoint for 2026 Gemini 3 Preview models
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

    mcp_root = os.getenv("MCP_ROOT")
    config_path = os.getenv("MCP_CONFIG")

    mcp_env = os.environ.copy()
    mcp_env["PYTHONPATH"] = mcp_root
    mcp_env["USE_GKE_GCLOUD_AUTH_PLUGIN"] = "True"

    # Total SSL Bypass (Essential for GKE and Nutanix Prism Central self-signed certs)
    mcp_env["PYTHONHTTPSVERIFY"] = "0"
    mcp_env["REQUESTS_CA_BUNDLE"] = ""
    mcp_env["SSL_CERT_FILE"] = ""

    # Stability Fixes for MCP Subprocesses
    mcp_env["PYTHONUNBUFFERED"] = "1"
    mcp_env["LOG_LEVEL"] = "ERROR"

    return LlmAgent(
        model='gemini-3-pro-preview',  # Standard January 2026 Resource ID
        name='kubetalk',
        instruction=(
            "You are a high-reasoning AI DevOps agent. "
            "You have tools to manage GKE clusters via Kubernetes APIs and "
            "private cloud infrastructure via Nutanix APIs. "
            "Use these tools to troubleshoot, deploy, and scale resources across both platforms."
        ),
        # 2026 Planner Config for Deep Reasoning
        planner=BuiltInPlanner(
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=2048  # Increased for multi-platform planning
            )
        ),
        tools=[
            # TOOLSET 1: GKE / Kubernetes
            MCPToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="python3",
                        args=["-m", "gke-mcp", "--transport", "stdio", "--path", config_path],
                        env=mcp_env
                    ),
                    timeout=300  # Prevent timeout during long GKE operations
                )
            ),
        ]
    )

root_agent = create_root_agent()

app = App(
    name='kubetalk',
    root_agent=root_agent,

    # 2026 Caching Strategy: Optimized for high-reasoning turn-around
    context_cache_config=ContextCacheConfig(
        min_tokens=32768,
        ttl_seconds=7200,
        cache_intervals=5
    ),

    # 2026 Compaction: Keeps the session state small to prevent Pydantic/Storage errors
    events_compaction_config=EventsCompactionConfig(
        compaction_interval=3,
        overlap_size=1
    )
)
