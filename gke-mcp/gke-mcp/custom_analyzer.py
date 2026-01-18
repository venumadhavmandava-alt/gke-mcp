# gke-mcp/custom_analyzer.py
import json
from kubernetes import client, config

class K8sCustomAnalyzer:
    def __init__(self, kubeconfig_path):
        config.load_kube_config(config_file=kubeconfig_path)
        self.v1 = client.CoreV1Api()
        self.apps = client.AppsV1Api()
        self.batch = client.BatchV1Api()
        self.networking = client.NetworkingV1Api()

    def run_analysis(self, namespace="all", filter_resource=None, output_json=False, anonymize=False):
        findings = []
        is_all = namespace.lower() == "all"
        ns = None if is_all else namespace

        # Analyzer Registry (Enabled by default)
        analyzers = {
            "Pod": self._pod_analyzer,
            "Deployment": self._deployment_analyzer,
            "Service": self._service_analyzer,
            "Event": self._event_analyzer,
            "Node": self._node_analyzer,
            "Job": self._job_analyzer,
            "Ingress": self._ingress_analyzer
        }

        # Filter Logic (e.g., --filter=Service)
        targets = {filter_resource: analyzers[filter_resource]} if filter_resource in analyzers else analyzers

        for name, func in targets.items():
            try:
                findings.extend(func(ns))
            except Exception as e:
                findings.append({"resource": name, "name": "System", "issue": f"Analyzer Error: {str(e)}"})

        # Anonymization Logic
        if anonymize:
            for f in findings:
                f["name"] = "ANONYMIZED-RESOURCE"
                f["issue"] = f["issue"].replace("transunion", "REDACTED-ORG")

        # Output Formatting
        if output_json:
            return json.dumps(findings, indent=2)
        
        if not findings:
            return f"No issues detected in namespace: {namespace}"

        return "\n".join([f"[{f['resource']}] {f['name']}: {f['issue']}" for f in findings])

    def _pod_analyzer(self, ns):
        res = self.v1.list_pod_for_all_namespaces() if not ns else self.v1.list_namespaced_pod(ns)
        return [{"resource": "Pod", "name": p.metadata.name, "issue": s.state.waiting.reason} 
                for p in res.items for s in (p.status.container_statuses or []) if s.state.waiting]

    def _deployment_analyzer(self, ns):
        res = self.apps.list_deployment_for_all_namespaces() if not ns else self.apps.list_namespaced_deployment(ns)
        return [{"resource": "Deployment", "name": d.metadata.name, "issue": "Unhealthy Replicas"} 
                for d in res.items if d.status.ready_replicas != d.status.replicas]

    def _service_analyzer(self, ns):
        res = self.v1.list_service_for_all_namespaces() if not ns else self.v1.list_namespaced_service(ns)
        return [{"resource": "Service", "name": s.metadata.name, "issue": "No Selector/Endpoints"} 
                for s in res.items if not s.spec.selector]

    def _event_analyzer(self, ns):
        res = self.v1.list_event_for_all_namespaces() if not ns else self.v1.list_namespaced_event(ns)
        return [{"resource": "Event", "name": e.involved_object.name, "issue": e.message} 
                for e in res.items if e.type == "Warning"]

    def _node_analyzer(self, _):
        res = self.v1.list_node()
        return [{"resource": "Node", "name": n.metadata.name, "issue": "NotReady"} 
                for n in res.items if any(c.type == 'Ready' and c.status != 'True' for c in n.status.conditions)]

    def _job_analyzer(self, ns):
        res = self.batch.list_job_for_all_namespaces() if not ns else self.batch.list_namespaced_job(ns)
        return [{"resource": "Job", "name": j.metadata.name, "issue": "Execution Failed"} 
                for j in res.items if j.status.failed]

    def _ingress_analyzer(self, ns):
        res = self.networking.list_ingress_for_all_namespaces() if not ns else self.networking.list_namespaced_ingress(ns)
        return [{"resource": "Ingress", "name": i.metadata.name, "issue": "Unhealthy/No IP"} 
                for i in res.items if not i.status.load_balancer.ingress]
