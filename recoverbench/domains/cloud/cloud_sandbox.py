"""Cloud & Infrastructure domain sandbox."""

from __future__ import annotations
from typing import Any, Dict, List, Optional


class CloudResourceSandbox:
    """Manages cloud compute instances, service scaling, and configuration catalogs."""

    def __init__(self):
        self.services: Dict[str, Dict[str, Any]] = {}
        self.catalog_registry: Dict[str, List[str]] = {}

    def seed_service(self, service_name: str, desired_replicas: int, instance_type: str = "t3.medium") -> None:
        instances = [f"{service_name}-inst-{i+1}" for i in range(desired_replicas)]
        self.services[service_name] = {
            "service_name": service_name,
            "desired_replicas": desired_replicas,
            "instance_type": instance_type,
            "running_instances": instances.copy(),
        }
        self.catalog_registry[service_name] = instances.copy()

    # --- Tool Callables ---

    def scale_service(self, service_name: str, new_replicas: int) -> Dict[str, Any]:
        """Tool: Scale cloud compute instances to target count."""
        if service_name not in self.services:
            raise ValueError(f"Service {service_name} not found")
        svc = self.services[service_name]
        curr = len(svc["running_instances"])
        if new_replicas > curr:
            for i in range(curr, new_replicas):
                svc["running_instances"].append(f"{service_name}-inst-{i+1}")
        elif new_replicas < curr:
            svc["running_instances"] = svc["running_instances"][:new_replicas]

        svc["desired_replicas"] = new_replicas
        return {
            "service_name": service_name,
            "desired_replicas": new_replicas,
            "running_count": len(svc["running_instances"]),
        }

    def sync_discovery_catalog(self, service_name: str) -> Dict[str, Any]:
        """Tool: Register active running instances into the global service catalog."""
        if service_name not in self.services:
            raise ValueError(f"Service {service_name} not found")
        running = self.services[service_name]["running_instances"]
        self.catalog_registry[service_name] = running.copy()
        return {"service_name": service_name, "catalog_instances": len(running)}

    def provision_cluster_tier(self, tier_name: str, instance_count: int, instance_type: str = "c5.large") -> Dict[str, Any]:
        """Tool: Provision a compute cluster tier."""
        self.seed_service(tier_name, desired_replicas=instance_count, instance_type=instance_type)
        return {"tier_name": tier_name, "provisioned_count": instance_count, "instance_type": instance_type}

    def drain_and_terminate(self, service_name: str, instances_to_remove: int) -> Dict[str, Any]:
        """Tool: Drain and terminate compute instances from an autoscaling group."""
        if service_name not in self.services:
            raise ValueError(f"Service {service_name} not found")
        svc = self.services[service_name]
        current = len(svc["running_instances"])
        remaining = max(0, current - instances_to_remove)
        svc["running_instances"] = svc["running_instances"][:remaining]
        svc["desired_replicas"] = remaining
        return {"service_name": service_name, "terminated": instances_to_remove, "remaining": remaining}

    def deploy_green_service(self, service_name: str, version: str) -> Dict[str, Any]:
        """Tool: Spin up green deployment environment for service."""
        green_name = f"{service_name}-green"
        self.seed_service(green_name, desired_replicas=3)
        self.services[green_name]["version"] = version
        return {"green_service": green_name, "version": version, "status": "DEPLOYED"}

    def switch_traffic_routing(self, service_name: str, target_color: str) -> Dict[str, Any]:
        """Tool: Cutover ingress traffic router to green service."""
        self.catalog_registry[f"{service_name}-active"] = [f"route-to-{target_color}"]
        return {"service_name": service_name, "active_route": target_color, "status": "ROUTED"}

    # --- Oracle Inspection Methods ---

    def query_running_replicas(self, service_name: str) -> int:
        svc = self.services.get(service_name)
        return len(svc["running_instances"]) if svc else 0

    def query_catalog_count(self, service_name: str) -> int:
        return len(self.catalog_registry.get(service_name, []))

    def get_full_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "services": self.services.copy(),
            "catalogs": self.catalog_registry.copy(),
        }
        if len(self.services) == 1:
            only_svc = next(iter(self.services.values()))
            state["running_replicas"] = len(only_svc.get("running_instances", []))
            state["catalog_count"] = len(self.catalog_registry.get(only_svc["service_name"], []))
        return state
