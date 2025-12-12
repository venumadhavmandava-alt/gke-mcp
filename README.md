# 🚀 GKE MCP Server – Kubernetes Model Context Protocol

Welcome to the **first GCP-native Management Control Plane (MCP) Server** built by [Shrey Batham](mailto:shreybatham14@gmail.com). This tool enables intelligent, safe, and automated control over your Kubernetes clusters using natural-language-powered operations and native Kubernetes tooling.

---

## 👤 Owner

**Name:** Shrey Batham  
**Email:** [shreybatham14@gmail.com](mailto:shreybatham14@gmail.com)
**Access Level:** Full Kubernetes Admin, Helm, and kubectl CLI

---

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
git clone https://github.com/bathas2021/gke-mcp.git
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

