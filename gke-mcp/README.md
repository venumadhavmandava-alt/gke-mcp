# 🚀 GKE MCP Server – Kubernetes Model Context Protocol

Welcome to the **first GCP-native Management Control Plane (MCP) Server** . This tool enables intelligent, safe, and automated control over your Kubernetes clusters using natural-language-powered operations and native Kubernetes tooling.

## 🎯 Objective

To **safely execute, automate, and assist** with GKE cluster and workload operations using Kubernetes-native tooling.  
**Core pillars:** Reliability • Observability • Cost Optimization • Operational Security

---
## ⚙️ Prerequisites

- **Python:** `>= 3.12`
- **Installed Tools:**
  - [`kubectl`]
  - [`gcloud`]
  - [`helm`]

### 📦 Install Python Dependencies

```bash
git clone https://github.com/venumadhavmandava-alt/gke-mcp.git
cd gke-mcp
pip install -r requirements.txt
```
---
### How to Run the MCP Server
```
python3 -m gke-mcp --transport stdio
```
📡 Supported --transport Options

| Transport Type      | Description                                                        |
| ------------------- | ------------------------------------------------------------------ |
| `stdio` *(default)* | CLI mode using standard input/output.                              |
| `sse`               | Server-Sent Events mode. Ideal for web-based streaming dashboards. |
| `http` or  `streamable-http`              | Launches an HTTP server for REST-style access to MCP.|


🌐 Optional Flags
| Flag          | Description                                       | Default |
| ------------- | ------------------------------------------------- | ------- |
| `--transport` | One of: `stdio`, `sse`, `http`, `streamable-http` | `stdio` |
| `--port`      | Port for `sse` or `http` transports               | `8001`  |
| `--path`      | API path for `http` transports                    | `/mcp`  |

---

## 🔧 Supported Operations

### 📦 Pod & Workload Management
- `get_pods`: List all pods in a namespace or the cluster.
- `get_deployments`: Retrieve all deployments.
- `create_deployment`: Safely create deployments from manifests or input.
- `delete_resource`: Delete any resource with confirmation.
- `scale_deployment`: Scale deployment up or down.
- `expose_deployment_with_service`: Expose pods/deployments via a Kubernetes Service.
- `create_persistent_volume`: Create Persistent Volumes.
- `create_persistent_volume_claim`: Create Persistent Volume Claims.
- `migrate_gke_node_pool_workloads`: Migrate workloads between GKE node pools for optimization.

### 📁 Cluster Configuration
- `get_namespaces`: List all namespaces.
- `get_nodes`: View node status and metadata.
- `get_configmaps`: Retrieve config map data.
- `get_secrets`: View secret metadata (values hidden unless authorized).
- `switch_context`: Change Kubernetes context.
- `get_current_context`: Show the current context.
- `get_api_resources`: List Kubernetes API resources.
- `kubectl_explain`: Get schema or field explanations.
- `connect_to_gke`: Authenticate and connect to Multi-GKE clusters.

### 🛠️ Helm Package Management
- `install_helm_chart`: Install Helm charts with values.
- `upgrade_helm_chart`: Upgrade Helm releases.
- `uninstall_helm_chart`: Safely remove releases.


### 🔐 RBAC & Security
- `get_rbac_roles`: View Roles and RoleBindings.
- `get_cluster_roles`: View ClusterRoles and ClusterRoleBindings.

### 📊 Monitoring & Diagnostics
- `get_events`: Get recent Kubernetes events.
- `get_pod_events`: Fetch pod-specific events.
- `check_pod_health`: Check pod readiness and status.
- `health_check`: Diagnose cluster or workload health.
- `get_logs`: Fetch logs from pods with filtering options.
- `port_forward`: Secure port forwarding to local ports.

---

## 🧠 Behavior Guidelines

1. ✅ Confirm intent before performing destructive operations.
2. 🔍 Default to **non-invasive** actions (dry-run/read-only).
3. ✅ Validate input before execution.
4. 📢 Always return clear feedback: results, errors, or next steps.
5. 📝 Log all actions for traceability (if supported).
6. 🛠️ Provide detailed error messages and resolution steps.
7. 🔐 Follow RBAC permissions; never exceed granted access.

---

## 🗣️ Response Style

- Technical, structured, and precise.
- Emphasizes **clarity**, **safety**, and **next steps**.
- Seeks clarification when commands are ambiguous.

---



https://github.com/user-attachments/assets/f390d0c3-b8d5-47ff-b263-4b87d2cec63d





---
## 🧪 Example Use Cases

```bash
> get_pods namespace=prod
> create_deployment name=nginx image=nginx:latest replicas=3
> migrate_gke_node_pool_workloads from=pool-a to=pool-b
> install_kubecost namespace=monitoring
> install_prometheus_stack namespace=monitoring
> get_logs pod=payment-service tail=100
> migrate_gke_node_pool_workloads= Migrate workloads from nodepool
```

(.venv) vmandav@MCHIMD45RXWR gke-mcp % kubectl config set-cluster kubernetes-admin --insecure-skip-tls-verify=true
Cluster "kubernetes-admin" set.
(.venv) vmandav@MCHIMD45RXWR gke-mcp % kubectl config set-cluster kubernetes-admin --insecure-skip-tls-verify=true
export KUBECONFIG=$(pwd)/config/dc15-c5.yaml  
export MCP_ROOT="/Users/vmandav/downloads/gke-mcp"   
export GOOGLE_CLOUD_LOCATION="global"  
export GOOGLE_GENAI_USE_VERTEXAI=True 
export MCP_CONFIG="/Users/vmandav/downloads/gke-mcp/config/mcp.yaml" 
pat.HgTKqISVTX-kQSVsWCHEcA.69606533b7a0fa7f519e90bc.5NzBaQl4c53rsMGuXJE2


kubectl config set-cluster gke_odev-elselk-rnd-indexer-faf9_us-central1_cos-rnd-cluster-2 --insecure-skip-tls-verify=true  export MCP_ROOT="/Users/vmandav/downloads/gke-mcp" 

export MCP_CONFIG="/Users/vmandav/downloads/gke-mcp/config/mcp.yaml"


create the frontend-app deployment in the dev namespace using the nginx:latest image and 2 replicas and create the namespace if it does not exist   . For the Entire Cluster (All Namespaces):

"KubeTalk, analyze the cluster health and give me a summary of any issues."
2. For a Specific Namespace (e.g., 'dev'):

"Check the health of the dev namespace."
3. To Focus Only on Failing Pods:

"Run a diagnostic scan for Pod issues in all namespaces."
4. To Investigate Why Something is Broken:

"Troubleshoot the cluster and tell me why things are failing."

List namespaces list pods scale up and scale down 

gcp-gke-module-demo-indexer

Pat token: pat.HgTKqISVTX-kQSVsWCHEcA.696433b98998c536086ac562.p1xo1PIVA2tBhkp0Emgb


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
    
    # Total SSL Bypass
    mcp_env["PYTHONHTTPSVERIFY"] = "0"
    mcp_env["REQUESTS_CA_BUNDLE"] = ""
    mcp_env["SSL_CERT_FILE"] = ""
    
    # Stability Fixes
    mcp_env["PYTHONUNBUFFERED"] = "1"
    mcp_env["LOG_LEVEL"] = "ERROR"

    return LlmAgent(
        model='gemini-2.5-flash',
        name='kubetalk',
        instruction="You are an AI DevOps agent...",
        tools=[
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
                    # --- CORRECTED: Use 'timeout' inside StdioConnectionParams ---
                    timeout=60 
                )
            )
        ]
    )

root_agent = create_root_agent()

