#!/usr/bin/env python3

import json
import sys
import logging
import asyncio
import os
from typing import Dict, Any, List, Optional, Callable, Awaitable
import yaml
import warnings
warnings.filterwarnings(
    "ignore",
    category=RuntimeWarning,
    message=r".*found in sys.modules after import of package.*"
)

try:
    # Import the official MCP SDK with FastMCP
    from fastmcp import FastMCP


except ImportError:
    logging.error("MCP SDK not found. Installing...")
    import subprocess
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "mcp>=1.5.0"
        ])
        from fastmcp import FastMCP
    except Exception as e:
        logging.error(f"Failed to install MCP SDK: {e}")
        raise

from .natural_language import process_query

# Configure logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("mcp-server")

class MCPServer:
    """MCP server implementation."""

    def __init__(self, name: str, port: int, path: str):
        """Initialize the MCP server."""
        self.name = name
        self.port = port
        self.path = path
        print(path)
        # Create a new server instance using the FastMCP API
        self.server = FastMCP(name=name, port=port, host="127.0.0.1",json_response=True)
        # Check for required dependencies
        self.dependencies_available = self._check_dependencies()
        if not self.dependencies_available:
            logger.warning("Some dependencies are missing. Certain operations may not work correctly.")
        # Register tools using the new FastMCP API
        self.setup_tools()
    
    def setup_tools(self):
        """Set up the tools for the MCP server."""
        @self.server.tool()   
        def get_pods(namespace: str = None) -> Dict[str, Any]:
            """Get all pods in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                
                if namespace:
                    pods = v1.list_namespaced_pod(namespace)
                else:
                    pods = v1.list_pod_for_all_namespaces()
                
                return {
                    "success": True,
                    "pods": [
                        {
                            "name": pod.metadata.name,
                            "namespace": pod.metadata.namespace,
                            "status": pod.status.phase,
                            "ip": pod.status.pod_ip
                        }
                        for pod in pods.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting pods: {e}")
                return {"success": False, "error": str(e)}
        @self.server.tool()
        def get_namespaces() -> Dict[str, Any]:
            """Get all Kubernetes namespaces."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                namespaces = v1.list_namespace()
                return {
                    "success": True,
                    "namespaces": [ns.metadata.name for ns in namespaces.items]
                }
            except Exception as e:
                logger.error(f"Error getting namespaces: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_services(namespace: str = None) -> Dict[str, Any]:
            """Get all services in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                if namespace:
                    services = v1.list_namespaced_service(namespace)
                else:
                    services = v1.list_service_for_all_namespaces()
                return {
                    "success": True,
                    "services": [
                        {
                            "name": svc.metadata.name,
                            "namespace": svc.metadata.namespace,
                            "type": svc.spec.type,
                            "cluster_ip": svc.spec.cluster_ip
                        } for svc in services.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting services: {e}")
                return {"success": False, "error": str(e)}
        @self.server.tool()
        def expose_deployment_with_service(
            deployment_name: str = None,
            service_name: str = None,
            target_port: int = None,
            protocol: str = "TCP",
            service_type: str = None,
            namespace: str = None,
            port: int = None, # The port the service will listen on
            selector_labels: Dict[str, str] = None
        ) -> Dict[str, Any]:
            """
            Exposes a Kubernetes Deployment with a new Kubernetes Service.

            Args:
                deployment_name: The name of the Deployment to expose.
                service_name: The desired name for the new Service.
                target_port: The port on the pods that the service will forward traffic to.
                            This must match a port exposed by your Deployment's containers.
                protocol: The protocol of the service port (e.g., "TCP", "UDP"). Defaults to "TCP".
                service_type: The type of Kubernetes Service (e.g., "ClusterIP", "NodePort", "LoadBalancer").
                            Defaults to "ClusterIP".
                namespace: The Kubernetes namespace where the Deployment and Service reside. Defaults to "default".
                port: The port that the Service will expose. If not provided, it defaults to target_port.
                selector_labels: Optional. A dictionary of labels to use as the service selector.
                                If not provided, the function will attempt to get labels from the Deployment.

            Returns:
                A dictionary indicating success or failure, and details about the created service.
            """
            try:
                from kubernetes import client, config
                config.load_kube_config() # Load kubeconfig from default location or as configured

                api_core = client.CoreV1Api()
                api_apps = client.AppsV1Api()

                # 1. Get the Deployment to extract selector labels if not provided
                try:
                    deployment = api_apps.read_namespaced_deployment(name=deployment_name, namespace=namespace)
                    # Use deployment's template labels as selector if not explicitly given
                    if selector_labels is None:
                        selector_labels = deployment.spec.selector.match_labels
                        if not selector_labels:
                            raise ValueError(f"No selector labels found for Deployment '{deployment_name}' or provided manually. Cannot create Service.")
                        logger.info(f"Using selector labels from deployment '{deployment_name}': {selector_labels}")
                    else:
                        logger.info(f"Using provided selector labels: {selector_labels}")

                except client.ApiException as e:
                    if e.status == 404:
                        return {"success": False, "error": f"Deployment '{deployment_name}' not found in namespace '{namespace}'."}
                    else:
                        logger.error(f"Error reading deployment '{deployment_name}': {e}")
                        return {"success": False, "error": f"Error reading deployment: {e}"}
                except Exception as e:
                    logger.error(f"Failed to get deployment selector labels for '{deployment_name}': {e}")
                    return {"success": False, "error": f"Failed to determine selector labels: {e}"}

                # If port is not specified, use target_port as the service port
                if port is None:
                    port = target_port

                # 2. Define the Service object
                service_body = client.V1Service(
                    api_version="v1",
                    kind="Service",
                    metadata=client.V1ObjectMeta(
                        name=service_name,
                        namespace=namespace,
                        labels={"app": deployment_name} # Common practice to label the service
                    ),
                    spec=client.V1ServiceSpec(
                        selector=selector_labels, # Link service to deployment pods
                        ports=[
                            client.V1ServicePort(
                                protocol=protocol,
                                port=port,          # Port the service exposes
                                target_port=target_port # Port on the pod
                            )
                        ],
                        type=service_type # Type of service (ClusterIP, NodePort, LoadBalancer)
                    )
                )

                # 3. Create the Service
                try:
                    # Check if service already exists
                    existing_service = None
                    try:
                        existing_service = api_core.read_namespaced_service(name=service_name, namespace=namespace)
                    except client.ApiException as e:
                        if e.status != 404: # Ignore 404 (not found), re-raise other API errors
                            raise

                    if existing_service:
                        logger.info(f"Service '{service_name}' already exists. Attempting to patch it.")
                        created_service = api_core.patch_namespaced_service(name=service_name, namespace=namespace, body=service_body)
                    else:
                        logger.info(f"Creating new service '{service_name}' for deployment '{deployment_name}'.")
                        created_service = api_core.create_namespaced_service(namespace=namespace, body=service_body)

                    return {
                        "success": True,
                        "message": f"Service '{service_name}' of type '{service_type}' created/updated successfully for Deployment '{deployment_name}'.",
                        "service": {
                            "name": created_service.metadata.name,
                            "namespace": created_service.metadata.namespace,
                            "type": created_service.spec.type,
                            "cluster_ip": created_service.spec.cluster_ip,
                            "ports": [{"port": p.port, "target_port": p.target_port, "protocol": p.protocol} for p in created_service.spec.ports],
                            "selector": created_service.spec.selector
                        }
                    }
                except client.ApiException as e:
                    logger.error(f"Kubernetes API error creating/updating service: {e.status} - {e.reason} - {e.body}")
                    return {"success": False, "error": f"Kubernetes API error: {e.reason} - {e.body}"}
                except Exception as e:
                    logger.error(f"Unexpected error creating/updating service: {e}")
                    return {"success": False, "error": str(e)}

            except ImportError:
                logger.error("Kubernetes client library not installed. Please install with 'pip install kubernetes'")
                return {"success": False, "error": "Kubernetes client library not installed."}
            except Exception as e:
                logger.error(f"An unexpected error occurred in expose_deployment_with_service: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_nodes() -> Dict[str, Any]:
            """Get all nodes in the cluster."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                nodes = v1.list_node()
                return {
                    "success": True,
                    "nodes": [
                        {
                            "name": node.metadata.name,
                            "status": node.status.conditions[-1].type if node.status.conditions else None,
                            "addresses": [addr.address for addr in node.status.addresses]
                        } for node in nodes.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting nodes: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_configmaps(namespace: str = None) -> Dict[str, Any]:
            """Get all ConfigMaps in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                if namespace:
                    cms = v1.list_namespaced_config_map(namespace)
                else:
                    cms = v1.list_config_map_for_all_namespaces()
                return {
                    "success": True,
                    "configmaps": [
                        {
                            "name": cm.metadata.name,
                            "namespace": cm.metadata.namespace,
                            "data": cm.data
                        } for cm in cms.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting ConfigMaps: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_secrets(namespace: str = None) -> Dict[str, Any]:
            """Get all Secrets in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                if namespace:
                    secrets = v1.list_namespaced_secret(namespace)
                else:
                    secrets = v1.list_secret_for_all_namespaces()
                return {
                    "success": True,
                    "secrets": [
                        {
                            "name": secret.metadata.name,
                            "namespace": secret.metadata.namespace,
                            "type": secret.type
                        } for secret in secrets.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting Secrets: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def install_helm_chart(name: str, chart: str, namespace: str, repo: str = None, values: dict = None) -> Dict[str, Any]:
            """Install a Helm chart. Automatically installs Helm if missing."""
            
            # Check and install Helm if needed
            if not self._check_helm_availability():
                logger.warning("Helm not found. Attempting to install Helm...")
                if not _install_helm():
                    return {"success": False, "error": "Helm is not installed and automatic installation failed."}

            try:
                # Add repo if provided
                if repo:
                    repo_parts = repo.split('=')
                    if len(repo_parts) != 2:
                        return {"success": False, "error": "Repository format should be 'repo_name=repo_url'"}
                    
                    repo_name, repo_url = repo_parts
                    try:
                        subprocess.check_output(["helm", "repo", "add", repo_name, repo_url], stderr=subprocess.PIPE, text=True)
                        subprocess.check_output(["helm", "repo", "update"], stderr=subprocess.PIPE, text=True)
                        if '/' not in chart:
                            chart = f"{repo_name}/{chart}"
                    except subprocess.CalledProcessError as e:
                        return {"success": False, "error": f"Failed to add Helm repo: {e.stderr or str(e)}"}

                # Ensure namespace exists
                try:
                    subprocess.check_output(["kubectl", "get", "namespace", namespace], stderr=subprocess.PIPE, text=True)
                except subprocess.CalledProcessError:
                    try:
                        subprocess.check_output(["kubectl", "create", "namespace", namespace], stderr=subprocess.PIPE, text=True)
                    except subprocess.CalledProcessError as e:
                        return {"success": False, "error": f"Failed to create namespace: {e.stderr or str(e)}"}

                # Prepare values.yaml if needed
                cmd = ["helm", "install", name, chart, "-n", namespace]
                values_file = None
                if values:
                    with tempfile.NamedTemporaryFile("w", delete=False) as f:
                        yaml.dump(values, f)
                        values_file = f.name
                    cmd += ["-f", values_file]

                # Run Helm install
                result = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True)

                return {
                    "success": True,
                    "message": f"Helm chart {chart} installed as {name} in {namespace}",
                    "details": result
                }

            except subprocess.CalledProcessError as e:
                return {"success": False, "error": f"Failed to install Helm chart: {e.stderr or str(e)}"}
            except Exception as e:
                return {"success": False, "error": f"Unexpected error: {str(e)}"}
            finally:
                if values_file and os.path.exists(values_file):
                    os.unlink(values_file)
        @self.server.tool()
        # Helper to install Helm
        def _install_helm() -> bool:
            try:
                arch = platform.machine()
                if arch == "x86_64":
                    arch = "amd64"
                elif arch == "aarch64":
                    arch = "arm64"
                system = platform.system().lower()

                helm_version = "v3.14.4"
                helm_url = f"https://get.helm.sh/helm-{helm_version}-{system}-{arch}.tar.gz"
                logger.info(f"Downloading Helm from {helm_url}")

                with tempfile.TemporaryDirectory() as tmpdir:
                    archive_path = os.path.join(tmpdir, "helm.tar.gz")
                    subprocess.check_call(["curl", "-fsSL", "-o", archive_path, helm_url])
                    subprocess.check_call(["tar", "-zxvf", archive_path, "-C", tmpdir])
                    helm_bin = os.path.join(tmpdir, system + "-" + arch, "helm")
                    shutil.copy(helm_bin, "/usr/local/bin/helm")
                    os.chmod("/usr/local/bin/helm", 0o755)

                logger.info("Helm installed successfully.")
                return True

            except Exception as e:
                logger.error(f"Helm installation failed: {str(e)}")
                return False

        @self.server.tool()
        def upgrade_helm_chart(name: str, chart: str, namespace: str, repo: str = None, values: dict = None) -> Dict[str, Any]:
            """Upgrade a Helm release."""
            if not self._check_helm_availability():
                return {"success": False, "error": "Helm is not available on this system"}
            
            try:
                import subprocess, tempfile, yaml, os
                
                # Handle repo addition as a separate step if provided
                if repo:
                    try:
                        # Add the repository (assumed format: "repo_name=repo_url")
                        repo_parts = repo.split('=')
                        if len(repo_parts) != 2:
                            return {"success": False, "error": "Repository format should be 'repo_name=repo_url'"}
                        
                        repo_name, repo_url = repo_parts
                        repo_add_cmd = ["helm", "repo", "add", repo_name, repo_url]
                        logger.debug(f"Running command: {' '.join(repo_add_cmd)}")
                        subprocess.check_output(repo_add_cmd, stderr=subprocess.PIPE, text=True)
                        
                        # Update repositories
                        repo_update_cmd = ["helm", "repo", "update"]
                        logger.debug(f"Running command: {' '.join(repo_update_cmd)}")
                        subprocess.check_output(repo_update_cmd, stderr=subprocess.PIPE, text=True)
                        
                        # Use the chart with repo prefix if needed
                        if '/' not in chart:
                            chart = f"{repo_name}/{chart}"
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Error adding Helm repo: {e.stderr if hasattr(e, 'stderr') else str(e)}")
                        return {"success": False, "error": f"Failed to add Helm repo: {e.stderr if hasattr(e, 'stderr') else str(e)}"}
                
                # Prepare the upgrade command
                cmd = ["helm", "upgrade", name, chart, "-n", namespace]
                
                # Handle values file if provided
                values_file = None
                try:
                    if values:
                        with tempfile.NamedTemporaryFile("w", delete=False) as f:
                            yaml.dump(values, f)
                            values_file = f.name
                        cmd += ["-f", values_file]
                    
                    # Execute the upgrade command
                    logger.debug(f"Running command: {' '.join(cmd)}")
                    result = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True)
                    
                    return {
                        "success": True, 
                        "message": f"Helm release {name} upgraded with chart {chart} in {namespace}",
                        "details": result
                    }
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                    logger.error(f"Error upgrading Helm chart: {error_msg}")
                    return {"success": False, "error": f"Failed to upgrade Helm chart: {error_msg}"}
                finally:
                    # Clean up the temporary values file
                    if values_file and os.path.exists(values_file):
                        os.unlink(values_file)
            except Exception as e:
                logger.error(f"Unexpected error upgrading Helm chart: {str(e)}")
                return {"success": False, "error": f"Unexpected error: {str(e)}"}

        @self.server.tool()
        def uninstall_helm_chart(name: str, namespace: str) -> Dict[str, Any]:
            """Uninstall a Helm release."""
            if not self._check_helm_availability():
                return {"success": False, "error": "Helm is not available on this system"}
                
            try:
                import subprocess
                cmd = ["helm", "uninstall", name, "-n", namespace]
                logger.debug(f"Running command: {' '.join(cmd)}")
                
                try:
                    result = subprocess.check_output(cmd, stderr=subprocess.PIPE, text=True)
                    return {
                        "success": True, 
                        "message": f"Helm release {name} uninstalled from {namespace}",
                        "details": result
                    }
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                    logger.error(f"Error uninstalling Helm chart: {error_msg}")
                    return {"success": False, "error": f"Failed to uninstall Helm chart: {error_msg}"}
            except Exception as e:
                logger.error(f"Unexpected error uninstalling Helm chart: {str(e)}")
                return {"success": False, "error": f"Unexpected error: {str(e)}"}

        @self.server.tool()
        def get_rbac_roles(namespace: str = None) -> Dict[str, Any]:
            """Get all RBAC roles in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                rbac = client.RbacAuthorizationV1Api()
                if namespace:
                    roles = rbac.list_namespaced_role(namespace)
                else:
                    roles = rbac.list_role_for_all_namespaces()
                return {
                    "success": True,
                    "roles": [role.metadata.name for role in roles.items]
                }
            except Exception as e:
                logger.error(f"Error getting RBAC roles: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_cluster_roles() -> Dict[str, Any]:
            """Get all cluster-wide RBAC roles."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                rbac = client.RbacAuthorizationV1Api()
                roles = rbac.list_cluster_role()
                return {
                    "success": True,
                    "cluster_roles": [role.metadata.name for role in roles.items]
                }
            except Exception as e:
                logger.error(f"Error getting cluster roles: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_events(namespace: str = None) -> Dict[str, Any]:
            """Get all events in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                if namespace:
                    events = v1.list_namespaced_event(namespace)
                else:
                    events = v1.list_event_for_all_namespaces()
                return {
                    "success": True,
                    "events": [
                        {
                            "name": event.metadata.name,
                            "namespace": event.metadata.namespace,
                            "type": event.type,
                            "reason": event.reason,
                            "message": event.message
                        } for event in events.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting events: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_resource_usage(namespace: str = None) -> Dict[str, Any]:
            """Get resource usage statistics via kubectl top."""
            if not self._check_kubectl_availability():
                return {"success": False, "error": "kubectl is not available on this system"}
                
            try:
                import subprocess
                import json
                
                # Get pod resource usage
                pod_cmd = ["kubectl", "top", "pods", "--no-headers"]
                if namespace:
                    pod_cmd += ["-n", namespace]
                else:
                    pod_cmd += ["--all-namespaces"]
                
                pod_cmd += ["-o", "json"]
                
                # If the cluster doesn't support JSON output format for top command,
                # fall back to parsing text output
                try:
                    pod_output = subprocess.check_output(pod_cmd, stderr=subprocess.PIPE, text=True)
                    pod_data = json.loads(pod_output)
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    # Fall back to text output and manual parsing
                    pod_cmd = ["kubectl", "top", "pods"]
                    if namespace:
                        pod_cmd += ["-n", namespace]
                    else:
                        pod_cmd += ["--all-namespaces"]
                    
                    pod_output = subprocess.check_output(pod_cmd, stderr=subprocess.PIPE, text=True)
                    pod_data = {"text_output": pod_output}
                
                # Get node resource usage
                try:
                    node_cmd = ["kubectl", "top", "nodes", "--no-headers", "-o", "json"]
                    node_output = subprocess.check_output(node_cmd, stderr=subprocess.PIPE, text=True)
                    node_data = json.loads(node_output)
                except (subprocess.CalledProcessError, json.JSONDecodeError):
                    # Fall back to text output
                    node_cmd = ["kubectl", "top", "nodes"]
                    node_output = subprocess.check_output(node_cmd, stderr=subprocess.PIPE, text=True)
                    node_data = {"text_output": node_output}
                
                return {
                    "success": True, 
                    "pod_usage": pod_data,
                    "node_usage": node_data
                }
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                logger.error(f"Error getting resource usage: {error_msg}")
                return {"success": False, "error": f"Failed to get resource usage: {error_msg}"}
            except Exception as e:
                logger.error(f"Unexpected error getting resource usage: {str(e)}")
                return {"success": False, "error": f"Unexpected error: {str(e)}"}

        @self.server.tool()
        def switch_context(context_name: str) -> Dict[str, Any]:
            """Switch current kubeconfig context."""
            try:
                import subprocess
                cmd = ["kubectl", "config", "use-context", context_name]
                subprocess.check_output(cmd)
                return {"success": True, "message": f"Switched context to {context_name}"}
            except Exception as e:
                logger.error(f"Error switching context: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def connect_to_gke(project_id: str, zone: str, cluster_name: str) -> Dict[str, Any]:
            """
            Logs into a GKE cluster by updating the kubeconfig using `gcloud` command,
            if the context is not already present.

            Args:
                project_id: GCP project ID.
                zone: GKE zone (e.g., us-central1-a).
                cluster_name: Name of the GKE cluster.
                kubeconfig_path: Path to the kubeconfig file.

            Returns:
                A dictionary indicating success, and any output or error details.
            """
            kubeconfig_path = os.path.expanduser('~/.kube/config')
            context_name = f"gke_{project_id}_{zone}_{cluster_name}"

            try:
                import subprocess
                import yaml
                # Check if context already exists
                if os.path.exists(kubeconfig_path):
                    with open(kubeconfig_path, "r") as stream:
                        kubeconfig = yaml.safe_load(stream)
                        existing_contexts = [ctx["name"] for ctx in kubeconfig.get("contexts", [])]
                        if context_name in existing_contexts:
                            logger.info(f"Context '{context_name}' already present in kubeconfig.")
                            return {
                                "success": True,
                                "message": f"Already logged in. Context '{context_name}' exists in kubeconfig."
                            }

                logger.info(f"Context '{context_name}' not found. Attempting to login using gcloud...")

                gcloud_cmd = [
                    "gcloud", "container", "clusters", "get-credentials",
                    cluster_name,
                    f"--zone={zone}",
                    f"--project={project_id}",
                ]

                result = subprocess.run(gcloud_cmd, capture_output=True, text=True, check=True)

                logger.info(f"gcloud output:\n{result.stdout}")

                return {
                    "success": True,
                    "message": f"Kubeconfig updated. Logged into GKE cluster '{cluster_name}'.",
                    "gcloud_output": result.stdout
                }

            except FileNotFoundError:
                logger.error("gcloud command not found. Make sure Cloud SDK is installed.")
                return {"success": False, "error": "gcloud not found. Is Google Cloud SDK installed?"}
            except subprocess.CalledProcessError as e:
                logger.error(f"gcloud failed: {e.stderr}")
                return {"success": False, "error": e.stderr}
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return {"success": False, "error": str(e)}


        @self.server.tool()
        def get_current_context() -> Dict[str, Any]:
            """Get current kubeconfig context."""
            try:
                import subprocess
                cmd = ["kubectl", "config", "current-context"]
                output = subprocess.check_output(cmd, text=True).strip()
                return {"success": True, "context": output}
            except Exception as e:
                logger.error(f"Error getting current context: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def kubectl_explain(resource: str) -> Dict[str, Any]:
            """Explain a Kubernetes resource using kubectl explain."""
            try:
                import subprocess
                cmd = ["kubectl", "explain", resource]
                output = subprocess.check_output(cmd, text=True)
                return {"success": True, "explanation": output}
            except Exception as e:
                logger.error(f"Error explaining resource: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_api_resources() -> Dict[str, Any]:
            """List Kubernetes API resources."""
            try:
                import subprocess
                cmd = ["kubectl", "api-resources"]
                output = subprocess.check_output(cmd, text=True)
                return {"success": True, "resources": output}
            except Exception as e:
                logger.error(f"Error getting api-resources: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def health_check() -> Dict[str, Any]:
            """Check cluster health by pinging the API server."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                v1.get_api_resources()
                return {"success": True, "message": "Cluster API is reachable"}
            except Exception as e:
                logger.error(f"Cluster health check failed: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_pod_events(pod_name: str, namespace: str = "default") -> Dict[str, Any]:
            """Get events for a specific pod."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                field_selector = f"involvedObject.name={pod_name}"
                events = v1.list_namespaced_event(namespace, field_selector=field_selector)
                return {
                    "success": True,
                    "events": [
                        {
                            "name": event.metadata.name,
                            "type": event.type,
                            "reason": event.reason,
                            "message": event.message,
                            "timestamp": event.last_timestamp.isoformat() if event.last_timestamp else None
                        } for event in events.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting pod events: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def check_pod_health(pod_name: str, namespace: str = "default") -> Dict[str, Any]:
            """Check the health status of a pod."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                pod = v1.read_namespaced_pod(pod_name, namespace)
                status = pod.status
                return {
                    "success": True,
                    "phase": status.phase,
                    "conditions": [c.type for c in status.conditions] if status.conditions else []
                }
            except Exception as e:
                logger.error(f"Error checking pod health: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_deployments(namespace: str = None) -> Dict[str, Any]:
            """Get all deployments in the specified namespace."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                apps_v1 = client.AppsV1Api()
                if namespace:
                    deployments = apps_v1.list_namespaced_deployment(namespace)
                else:
                    deployments = apps_v1.list_deployment_for_all_namespaces()
                return {
                    "success": True,
                    "deployments": [
                        {
                            "name": d.metadata.name,
                            "namespace": d.metadata.namespace,
                            "replicas": d.status.replicas
                        } for d in deployments.items
                    ]
                }
            except Exception as e:
                logger.error(f"Error getting deployments: {e}")
                return {"success": False, "error": str(e)}


        @self.server.tool()
        def create_deployment(
            name: str,
            replicas: int,
            namespace: str = "default",
            containers: List[Dict[str, Any]] = None,
            init_containers: Optional[List[Dict[str, Any]]] = None,
            volumes: Optional[List[Dict[str, Any]]] = None,
            node_selector: Optional[Dict[str, str]] = None,
            pod_labels: Optional[Dict[str, str]] = None,
            tolerations: Optional[List[Dict[str, Any]]] = None,
            affinity: Optional[Dict[str, Any]] = None,
            pod_security_context: Optional[Dict[str, Any]] = None
        ) -> Dict[str, Any]:
            """Create a deployment with extended capabilities."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                apps_v1 = client.AppsV1Api()

                # Build container objects
                container_objs = []
                for c in containers or []:
                    liveness_probe = client.V1Probe(**c["liveness_probe"]) if "liveness_probe" in c else None
                    readiness_probe = client.V1Probe(**c["readiness_probe"]) if "readiness_probe" in c else None
                    env_vars = [
                        client.V1EnvVar(name=env["name"], value=env.get("value"), value_from=client.V1EnvVarSource(**env["value_from"]) if "value_from" in env else None)
                        for env in c.get("env", [])
                    ]
                    container_objs.append(client.V1Container(
                        name=c["name"],
                        image=c["image"],
                        command=c.get("command"),
                        args=c.get("args"),
                        env=env_vars,
                        volume_mounts=[client.V1VolumeMount(**vm) for vm in c.get("volume_mounts", [])],
                        resources=client.V1ResourceRequirements(**c["resources"]) if "resources" in c else None,
                        liveness_probe=liveness_probe,
                        readiness_probe=readiness_probe,
                        security_context=client.V1SecurityContext(**c["security_context"]) if "security_context" in c else None
                    ))

                # Init containers
                init_container_objs = []
                for ic in init_containers or []:
                    init_container_objs.append(client.V1Container(
                        name=ic["name"],
                        image=ic["image"],
                        command=ic.get("command"),
                        args=ic.get("args"),
                        env=[client.V1EnvVar(name=e["name"], value=e["value"]) for e in ic.get("env", [])],
                        volume_mounts=[client.V1VolumeMount(**vm) for vm in ic.get("volume_mounts", [])]
                    ))

                # Build PodSpec
                pod_spec = client.V1PodSpec(
                    containers=container_objs,
                    init_containers=init_container_objs or None,
                    volumes=[client.V1Volume(**v) for v in (volumes or [])],
                    node_selector=node_selector,
                    tolerations=[client.V1Toleration(**t) for t in (tolerations or [])],
                    affinity=client.V1Affinity(**affinity) if affinity else None,
                    security_context=client.V1PodSecurityContext(**pod_security_context) if pod_security_context else None
                )

                # Labels
                labels = {"app": name}
                if pod_labels:
                    labels.update(pod_labels)

                # Build Deployment
                deployment = client.V1Deployment(
                    metadata=client.V1ObjectMeta(name=name),
                    spec=client.V1DeploymentSpec(
                        replicas=replicas,
                        selector=client.V1LabelSelector(match_labels={"app": name}),
                        template=client.V1PodTemplateSpec(
                            metadata=client.V1ObjectMeta(labels=labels),
                            spec=pod_spec
                        )
                    )
                )

                apps_v1.create_namespaced_deployment(body=deployment, namespace=namespace)
                return {"success": True, "message": f"Deployment {name} created successfully"}

            except Exception as e:
                import logging
                logger = logging.getLogger("create_deployment")
                logger.error(f"Error creating deployment: {e}")
                return {"success": False, "error": str(e)}

                

        @self.server.tool()
        def delete_resource(resource_type: str, name: str, namespace: str = "default") -> Dict[str, Any]:
            """Delete a Kubernetes resource."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                
                if resource_type == "pod":
                    v1 = client.CoreV1Api()
                    v1.delete_namespaced_pod(name=name, namespace=namespace)
                elif resource_type == "deployment":
                    apps_v1 = client.AppsV1Api()
                    apps_v1.delete_namespaced_deployment(name=name, namespace=namespace)
                elif resource_type == "service":
                    v1 = client.CoreV1Api()
                    v1.delete_namespaced_service(name=name, namespace=namespace)
                else:
                    return {"success": False, "error": f"Unsupported resource type: {resource_type}"}
                
                return {
                    "success": True,
                    "message": f"{resource_type} {name} deleted successfully"
                }
            except Exception as e:
                logger.error(f"Error deleting resource: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def get_logs(pod_name: str, namespace: str = "default", container: str = None, tail: int = None) -> Dict[str, Any]:
            """Get logs from a pod."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()
                
                logs = v1.read_namespaced_pod_log(
                    name=pod_name,
                    namespace=namespace,
                    container=container,
                    tail_lines=tail
                )
                
                return {
                    "success": True,
                    "logs": logs
                }
            except Exception as e:
                logger.error(f"Error getting logs: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def port_forward(pod_name: str, local_port: int, pod_port: int, namespace: str = "default") -> Dict[str, Any]:
            """Forward local port to pod port."""
            try:
                import subprocess
                
                cmd = [
                    "kubectl", "port-forward",
                    f"pod/{pod_name}",
                    f"{local_port}:{pod_port}",
                    "-n", namespace
                ]
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                return {
                    "success": True,
                    "message": f"Port forwarding started: localhost:{local_port} -> {pod_name}:{pod_port}",
                    "process_pid": process.pid
                }
            except Exception as e:
                logger.error(f"Error setting up port forward: {e}")
                return {"success": False, "error": str(e)}

        @self.server.tool()
        def scale_deployment(name: str, replicas: int, namespace: str = "default") -> Dict[str, Any]:
            """Scale a deployment."""
            try:
                from kubernetes import client, config
                config.load_kube_config()
                apps_v1 = client.AppsV1Api()
                
                # Get the deployment
                deployment = apps_v1.read_namespaced_deployment(
                    name=name,
                    namespace=namespace
                )
                
                # Update replicas
                deployment.spec.replicas = replicas
                
                # Apply the update
                apps_v1.patch_namespaced_deployment(
                    name=name,
                    namespace=namespace,
                    body=deployment
                )
                
                return {
                    "success": True,
                    "message": f"Deployment {name} scaled to {replicas} replicas"
                }
            except Exception as e:
                logger.error(f"Error scaling deployment: {e}")
                return {"success": False, "error": str(e)}
        @self.server.tool()
        def create_persistent_volume(
            name: str,
            storage_class: str,
            capacity: str,
            access_modes: List[str],
            host_path: str = None,
            nfs_path: str = None,
            nfs_server: str = None
        ) -> Dict[str, Any]:
            """
            Create a PersistentVolume (PV).
            Supports hostPath or NFS volume source.
            """
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()

                volume_source = None
                if host_path:
                    volume_source = client.V1HostPathVolumeSource(path=host_path)
                elif nfs_path and nfs_server:
                    volume_source = client.V1NFSVolumeSource(path=nfs_path, server=nfs_server)
                else:
                    return {"success": False, "error": "Either host_path or (nfs_path + nfs_server) must be provided"}

                pv = client.V1PersistentVolume(
                    metadata=client.V1ObjectMeta(name=name),
                    spec=client.V1PersistentVolumeSpec(
                        capacity={"storage": capacity},
                        access_modes=access_modes,
                        storage_class_name=storage_class,
                        persistent_volume_reclaim_policy="Retain",
                        host_path=volume_source if host_path else None,
                        nfs=volume_source if nfs_path else None
                    )
                )

                v1.create_persistent_volume(pv)
                return {"success": True, "message": f"PV {name} created successfully"}

            except Exception as e:
                import logging
                logging.getLogger("create_pv").error(str(e))
                return {"success": False, "error": str(e)}
            
        @self.server.tool()    
        def create_persistent_volume_claim(
            name: str,
            namespace: str,
            storage_class: str,
            access_modes: List[str],
            storage_request: str
        ) -> Dict[str, Any]:
            """
            Create a PersistentVolumeClaim (PVC) in the specified namespace.
            """
            try:
                from kubernetes import client, config
                config.load_kube_config()
                v1 = client.CoreV1Api()

                pvc = client.V1PersistentVolumeClaim(
                    metadata=client.V1ObjectMeta(name=name),
                    spec=client.V1PersistentVolumeClaimSpec(
                        access_modes=access_modes,
                        storage_class_name=storage_class,
                        resources=client.V1ResourceRequirements(
                            requests={"storage": storage_request}
                        )
                    )
                )

                v1.create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)
                return {"success": True, "message": f"PVC {name} created successfully in {namespace}"}

            except Exception as e:
                import logging
                logging.getLogger("create_pvc").error(str(e))
                return {"success": False, "error": str(e)}
        @self.server.tool()
        def migrate_gke_node_pool_workloads(
            source_node_pool: str,
            dry_run: bool = False
        ) -> Dict[str, Any]:
            """
            Migrate workloads from a GKE node pool by cordoning and draining its nodes.
            Does NOT resize node pools.
            """
            try:
                from kubernetes import client, config
                config.load_kube_config()
                core_v1 = client.CoreV1Api()

                # Step 1: Find nodes in the source node pool
                label_selector = f"cloud.google.com/gke-nodepool={source_node_pool}"
                nodes = core_v1.list_node(label_selector=label_selector).items
                if not nodes:
                    return {"success": False, "message": f"No nodes found in node pool '{source_node_pool}'"}

                node_names = [node.metadata.name for node in nodes]

                if dry_run:
                    return {
                        "success": True,
                        "dry_run": True,
                        "message": f"Would cordon and drain nodes: {node_names}"
                    }

                # Step 2: Cordon and drain
                drained_pods = {}
                for node_name in node_names:
                    core_v1.patch_node(node_name, {"spec": {"unschedulable": True}})
                    pods = core_v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items

                    evicted = []
                    for pod in pods:
                        if pod.metadata.owner_references:
                            if any(owner.kind == "DaemonSet" for owner in pod.metadata.owner_references):
                                continue  # Skip DaemonSet pods

                        eviction = client.V1Eviction(
                            metadata=client.V1ObjectMeta(name=pod.metadata.name, namespace=pod.metadata.namespace),
                            delete_options=client.V1DeleteOptions(grace_period_seconds=30)
                        )
                        try:
                            core_v1.create_namespaced_pod_eviction(
                                name=pod.metadata.name,
                                namespace=pod.metadata.namespace,
                                body=eviction
                            )
                            evicted.append(f"{pod.metadata.namespace}/{pod.metadata.name}")
                        except Exception as e:
                            # Force delete if eviction fails
                            core_v1.delete_namespaced_pod(
                                name=pod.metadata.name,
                                namespace=pod.metadata.namespace,
                                grace_period_seconds=30
                            )
                            evicted.append(f"{pod.metadata.namespace}/{pod.metadata.name} (forced)")

                    drained_pods[node_name] = evicted

                return {
                    "success": True,
                    "message": f"Nodes from node pool '{source_node_pool}' cordoned and drained",
                    "nodes": node_names,
                    "drained_pods": drained_pods
                }

            except Exception as e:
                import logging
                logger = logging.getLogger("migrate_gke_node_pool_workloads")
                logger.error(f"Error migrating workloads: {e}")
                return {"success": False, "error": str(e)}


    def _check_dependencies(self) -> bool:
        """Check for required command-line tools."""
        all_available = True
        for tool in ["kubectl", "helm"]:
            if not self._check_tool_availability(tool):
                logger.warning(f"{tool} not found in PATH. Operations requiring {tool} will not work.")
                all_available = False
        return all_available
    
    def _check_tool_availability(self, tool: str) -> bool:
        """Check if a specific tool is available."""
        try:
            import subprocess, shutil
            # Use shutil.which for more reliable cross-platform checking
            if shutil.which(tool) is None:
                return False
            # Also verify it runs correctly
            if tool == "kubectl":
                subprocess.check_output([tool, "version", "--client"], stderr=subprocess.PIPE)
            elif tool == "helm":
                subprocess.check_output([tool, "version"], stderr=subprocess.PIPE)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _check_kubectl_availability(self) -> bool:
        """Check if kubectl is available."""
        return self._check_tool_availability("kubectl")
    
    def _check_helm_availability(self) -> bool:
        """Check if helm is available."""
        return self._check_tool_availability("helm")
    
    async def serve_stdio(self):
        """Serve the MCP server over stdio transport."""
        # Add detailed logging for debugging Cursor integration
        logger.info("Starting MCP server with stdio transport")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Python executable: {sys.executable}")
        logger.info(f"Python version: {sys.version}")
        
        # Log Kubernetes configuration
        kube_config = os.environ.get('KUBECONFIG', '~/.kube/config')
        expanded_path = os.path.expanduser(kube_config)
        logger.info(f"KUBECONFIG: {kube_config} (expanded: {expanded_path})")
        if os.path.exists(expanded_path):
            logger.info(f"Kubernetes config file exists at {expanded_path}")
        else:
            logger.warning(f"Kubernetes config file does not exist at {expanded_path}")
        
        # Log dependency check results
        logger.info(f"Dependencies check result: {'All available' if self.dependencies_available else 'Some missing'}")
        
        # Continue with normal server startup
        await self.server.run_stdio_async()
    
    async def serve_sse(self, port: int):
        """Serve the MCP server over SSE transport."""
        logger.info(f"Starting MCP server with SSE transport on port {port}")
        # await self.server.run_sse_async(port=port)
        await self.server.run_sse_async()

    async def serve_http(self, port: int, path: str):
        """Serve the MCP server over http transport."""
        logger.info(f"Starting MCP server with http transport on port {port} and path {path}")
        # await self.server.run_sse_async(port=port)
        await self.server.run_http_async()
            
        
if __name__ == "__main__":
    import asyncio
    import argparse
    # Ensure that logging, os, sys, FastMCP, MCPServer, and the logger instance
    # are imported or defined earlier in the file as needed.
    # Based on our previous views, most of these should already be in place.

    parser = argparse.ArgumentParser(description="Run the Kubectl MCP Server.")
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse", "http"],
        default="stdio",
        help="Communication transport to use (stdio or sse). Default: stdio.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to use for SSE transport. Default: 8080.",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="/mcp",
        help="path to use for http transport. Default: /mcp.",
    )     
    args = parser.parse_args()

    server_name = "gke_mcp_server"
    # Ensure MCPServer class is defined above this block
    mcp_server = MCPServer(name=server_name) 
    # Ensure logger is defined at the module level
    # logger = logging.getLogger(__name__) # Or 
    # however it's set up

    loop = asyncio.get_event_loop()
    try:
        if args.transport == "stdio":
            logger.info(f"Starting {server_name} with stdio transport.")
            loop.run_until_complete(mcp_server.serve_stdio())
        elif args.transport == "sse":
            logger.info(f"Starting {server_name} with SSE transport on port {args.port}.")
            loop.run_until_complete(mcp_server.serve_sse(port=args.port))
        elif args.transport == "http":
             logger.info(f"Starting {server_name} with http transport on port {args.port} and path {args.path}.")
             loop.run_until_complete(mcp_server.serve_http(port=args.port, path=args.path))
    except KeyboardInterrupt:
        logger.info("Server shutdown requested by user.")
    except Exception as e:
        logger.error(f"Server exited with error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down server.")
