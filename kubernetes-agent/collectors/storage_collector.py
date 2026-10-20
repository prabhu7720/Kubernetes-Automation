"""Collects PVC / PV / StorageClass information for pods and namespaces."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.context import PodContext
from core.k8s_utils import dig

from .base import BaseCollector


class StorageCollector(BaseCollector):
    def __init__(self, client, settings, events):
        super().__init__(client, settings)
        self.events = events

    @staticmethod
    def claim_names(pod: Dict[str, Any]) -> List[str]:
        names = []
        pod_name = dig(pod, "metadata", "name")
        for vol in dig(pod, "spec", "volumes") or []:
            claim = dig(vol, "persistentVolumeClaim", "claimName")
            if claim:
                names.append(claim)
            elif vol.get("ephemeral"):
                names.append(f"{pod_name}-{vol.get('name')}")   # generic ephemeral volume naming
        return list(dict.fromkeys(names))

    def storage_classes(self, errors: List[str]) -> Dict[str, Dict[str, Any]]:
        items = self.safe(errors, "list storageclasses", self.client.list, "storageclasses", default=[])
        return {dig(sc, "metadata", "name"): sc for sc in items}

    def populate_pod(self, ctx: PodContext) -> None:
        errs = ctx.collection_errors
        ns = ctx.namespace
        claims = self.claim_names(ctx.pod)
        if not claims:
            return
        classes = None
        for claim in claims:
            try:
                pvc = self.client.get("persistentvolumeclaim", claim, ns)
            except Exception as exc:  # KubectlError, recorded but non-fatal
                errs.append(f"get pvc {claim}: {getattr(exc, 'short', exc)}")
                continue
            ctx.pvcs[claim] = pvc
            ctx.pvc_events[claim] = self.events.for_object("PersistentVolumeClaim", claim, ns, errs)
            if not pvc:
                continue
            pv_name = dig(pvc, "spec", "volumeName")
            if pv_name:
                ctx.pvs[pv_name] = self.safe(errs, f"get pv {pv_name}", self.client.get,
                                             "persistentvolume", pv_name)
            sc_name = dig(pvc, "spec", "storageClassName")
            if classes is None:
                classes = self.storage_classes(errs)
            if sc_name:
                ctx.storage_classes[sc_name] = classes.get(sc_name)
            else:
                default = next((sc for sc in classes.values() if dig(
                    sc, "metadata", "annotations", "storageclass.kubernetes.io/is-default-class") == "true"), None)
                ctx.storage_classes["<default>"] = default
