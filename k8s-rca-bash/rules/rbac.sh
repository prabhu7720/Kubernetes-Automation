# shellcheck shell=bash
# RBAC / IAM permission failures, missing service accounts, agent permission gaps.

RULE_META[rule_pod_rbac]="K8S-RBAC-001|security|RBAC / IAM permission failure"
rule_pod_rbac() {
  local sa; sa=$(cat "$CTX/sa.name" 2>/dev/null || echo default)
  local hits; hits=$(log_hits 'is forbidden: User "[^"]+" cannot [a-z-]+ resource')
  if [[ -n $hits ]]; then
    local line user verb res group ns
    line=$(head -1 <<<"$hits")
    user=$(sed -nE 's/.*User "([^"]+)".*/\1/p' <<<"$line")
    verb=$(sed -nE 's/.*cannot ([a-z-]+) resource.*/\1/p' <<<"$line")
    res=$(sed -nE 's/.*resource "([^"]+)".*/\1/p' <<<"$line")
    group=$(sed -nE 's/.*in API group "([^"]*)".*/\1/p' <<<"$line")
    ns=$(sed -nE 's/.*in the namespace "([^"]+)".*/\1/p' <<<"$line")
    local kind=ClusterRole scope="cluster scope"; [[ -n $ns ]] && { kind=Role; scope="namespace '$ns'"; }
    local snippet="Grant the minimal permission with a $kind + ${kind}Binding to the service account, e.g.: kubectl create ${kind,,} $sa-$verb-${res//\//-} --verb=$verb --resource=$res${ns:+ -n $ns} && kubectl create ${kind,,}binding $sa-$verb-${res//\//-} --${kind,,}=$sa-$verb-${res//\//-} --serviceaccount=$CTX_NS:$sa${ns:+ -n $ns}"
    emit --sev "$(impact_sev)" --title "RBAC permission denied" --conf 95 \
      --root "'$user' is not allowed to $verb $res (API group '${group:-core}') at $scope; the application calls the Kubernetes API without the required RBAC permission." \
      --evidence "$(lines "$hits" "Pod service account: $sa")" \
      --recs "$(lines "$snippet" "Confirm the pod uses the intended serviceAccountName.")" \
      --cmds "$(lines "$CMD_PREFIX auth can-i $verb $res --as=$user${ns:+ -n $ns}" \
                      "$CMD_PREFIX get rolebindings,clusterrolebindings -A -o wide | grep $sa" \
                      "$CMD_PREFIX describe serviceaccount $sa -n $CTX_NS")"
    return 0
  fi
  local cloud; cloud=$(log_hits 'AccessDenied|not authorized to perform|AuthorizationFailed|PERMISSION_DENIED|AccessDeniedException')
  if [[ -n $cloud ]]; then
    local ident=""
    [[ -f $CTX/sa.json ]] && ident=$(jq -r '.metadata.annotations // {} | to_entries[]
        | select(.key == "eks.amazonaws.com/role-arn" or .key == "iam.gke.io/gcp-service-account" or .key == "azure.workload.identity/client-id")
        | "\(.key)=\(.value)"' "$CTX/sa.json")
    local root="The workload is denied by the cloud provider IAM (not Kubernetes RBAC): the identity bound to the service account lacks the permission"
    [[ -z $ident ]] && root+=", and the service account has no workload-identity annotation (the pod falls back to the node role)."
    [[ -n $ident ]] && root+="."
    emit --sev "$(impact_sev)" --title "Cloud IAM permission denied" --conf "$([[ -n $ident ]] && echo 85 || echo 80)" --root "$root" \
      --evidence "$(lines "$cloud" "Service account: $sa" "Workload identity annotations: ${ident:-none}")" \
      --recs "$(lines "Add the missing action to the IAM policy of the workload identity role." \
                      "Annotate the service account for IRSA / GKE Workload Identity / Azure WI and restart the pods." \
                      "Check the role trust policy allows this namespace/service account.")" \
      --cmds "$(lines "$CMD_PREFIX get sa $sa -n $CTX_NS -o yaml" "$CMD_PREFIX exec $CTX_NAME -n $CTX_NS -- env | grep -Ei 'AWS_ROLE_ARN|AWS_WEB_IDENTITY|GOOGLE|AZURE'")"
    return 0
  fi
  local tok; tok=$(log_hits 'serviceaccount/token.*(no such file|not found)' '*' 2)
  if [[ -n $tok || ( -n $(log_hits 'Unauthorized|401' '*' 1) && $(pj '.spec.automountServiceAccountToken') == false ) ]]; then
    emit --sev HIGH --title "Service account token not mounted" --conf 85 \
      --root "The application needs the Kubernetes API but automountServiceAccountToken is disabled, so API calls are rejected." \
      --evidence "$(lines "$tok" "automountServiceAccountToken: $(pj '.spec.automountServiceAccountToken')")" \
      --recs "Set automountServiceAccountToken: true on the pod (or service account)." \
      --cmds "$CMD_PREFIX get pod $CTX_NAME -n $CTX_NS -o jsonpath='{.spec.automountServiceAccountToken}'"
  fi
}

RULE_META[rule_pod_serviceaccount]="K8S-RBAC-002|security|ServiceAccount missing"
rule_pod_serviceaccount() {
  [[ -f $CTX/sa.missing ]] || return 0
  local sa; sa=$(cat "$CTX/sa.name")
  emit --sev MEDIUM --title "ServiceAccount missing" --conf 92 --corr "serviceaccount:$CTX_NS/$sa" \
    --root "ServiceAccount '$sa' used by the pod no longer exists; new pods for this workload will be rejected and token refresh will fail." \
    --evidence "$(lines "serviceAccountName: $sa" "ServiceAccount $CTX_NS/$sa: NOT FOUND")" \
    --recs "Recreate it: $CMD_PREFIX create serviceaccount $sa -n $CTX_NS (plus RBAC bindings / IAM annotations), or fix serviceAccountName." \
    --cmds "$CMD_PREFIX get serviceaccount $sa -n $CTX_NS"
}

RULE_META[rule_all_agent_permissions]="K8S-RBAC-003|agent|Diagnostic agent lacks permissions"
rule_all_agent_permissions() {
  local denied; denied=$(jq -r --arg g "$CUR_RES" 'select(.group == $g) | .msg' "$WORK/errors.jsonl" | grep -iE 'forbidden|rbac' | sort -u | head -8)
  [[ -z $denied ]] && return 0
  emit --sev INFO --title "Analysis incomplete: agent RBAC" --conf 100 \
    --root "The kubeconfig identity used by the agent cannot read some resources, so related rules could not be evaluated." \
    --evidence "$denied" --recs "Grant the read-only ClusterRole in deploy/rbac-readonly.yaml to the identity used by the agent." \
    --cmds "$CMD_PREFIX auth can-i --list"
}
