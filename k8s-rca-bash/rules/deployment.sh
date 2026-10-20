# shellcheck shell=bash
# Deployment rules: stuck rollouts, replica creation failures, unavailable replicas.

_dj() { jq -r "$1" "$CTX/deploy.json"; }
_dcmds() {
  lines "$CMD_PREFIX rollout status deployment/$CTX_NAME -n $CTX_NS --timeout=10s" \
        "$CMD_PREFIX rollout history deployment/$CTX_NAME -n $CTX_NS" \
        "$CMD_PREFIX describe deployment $CTX_NAME -n $CTX_NS" \
        "$CMD_PREFIX get rs,pods -n $CTX_NS -l $(_dj '[.spec.selector.matchLabels // {} | to_entries[] | "\(.key)=\(.value)"] | join(",")')"
}

RULE_META[rule_deployment_rollout]="K8S-DEPLOY-001|deployment|Rollout stuck (ProgressDeadlineExceeded)"
rule_deployment_rollout() {
  [[ $(_dj '[.status.conditions[]? | select(.type == "Progressing")][0] | "\(.status)/\(.reason)"') == "False/ProgressDeadlineExceeded" ]] || return 0
  local ev=("Progressing=False reason=ProgressDeadlineExceeded: $(_dj '[.status.conditions[]? | select(.type == "Progressing")][0].message')"
            "$(_dj '"Replicas desired=\(.spec.replicas // 1) updated=\(.status.updatedReplicas // 0) ready=\(.status.readyReplicas // 0) available=\(.status.availableReplicas // 0)"')"
            "progressDeadlineSeconds=$(_dj '.spec.progressDeadlineSeconds // 600')")
  local root="The new ReplicaSet's pods never became Ready within the progress deadline, so the rollout stalled."
  local diff; diff=$(jq -r '(.items | sort_by(.metadata.annotations["deployment.kubernetes.io/revision"] | tonumber)) as $r
      | if ($r | length) >= 2 then
          ([$r[-2].spec.template.spec.containers[].image] | join(",")) as $old | ([$r[-1].spec.template.spec.containers[].image] | join(",")) as $new
          | if $old != $new then "\($old) -> \($new)" else "" end
        else "" end' "$CTX/rs.json")
  if [[ -n $diff ]]; then
    ev+=("Image change: $diff")
    root+=" The rollout changed the image - the new version is the prime suspect (see pod findings)."
  fi
  emit --sev HIGH --title "Rollout stuck" --root "$root" --conf 92 --evidence "$(lines "${ev[@]}")" \
    --recs "$(lines "Diagnose the new pods (pod findings) - they explain why they are not Ready." \
                    "Roll back if needed: $CMD_PREFIX rollout undo deployment/$CTX_NAME -n $CTX_NS")" --cmds "$(_dcmds)"
}

RULE_META[rule_deployment_replicafailure]="K8S-DEPLOY-002|deployment|ReplicaSet cannot create pods"
rule_deployment_replicafailure() {
  local cond evs text
  cond=$(_dj '[.status.conditions[]? | select(.type == "ReplicaFailure" and .status == "True")][0].message // ""')
  evs=$(events_fmt FailedCreate | tail -3)
  [[ -z $cond && -z $evs ]] && return 0
  text="$cond $evs"
  grep -qiE 'exceeded quota|must specify (limits|requests)' <<<"$text" && return 0   # owned by K8S-RES-002
  local root conf rec
  if grep -qi 'violates PodSecurity' <<<"$text"; then
    root="The pod template violates the namespace Pod Security Standard (PSA)."; conf=95
    rec="Adjust securityContext (runAsNonRoot, drop capabilities, seccompProfile RuntimeDefault, no privileged/hostPath) or deliberately change the namespace enforce label."
  elif grep -qiE 'admission webhook .* denied' <<<"$text"; then
    root="An admission webhook / policy engine (Gatekeeper, Kyverno...) rejects the pod."; conf=93
    rec="Read the policy violation in the event and fix the pod template or request an exception."
  elif grep -qiE 'failed calling webhook|no endpoints available for service' <<<"$text"; then
    root="A failing admission webhook (unreachable service or bad certificate) blocks pod creation."; conf=92
    rec="Check the webhook's pods/service and caBundle; consider failurePolicy: Ignore for non-critical webhooks."
  elif grep -qiE 'serviceaccount .* not found|error looking up service account' <<<"$text"; then
    root="The ServiceAccount referenced by the pod template does not exist."; conf=96
    rec="Create the ServiceAccount or fix serviceAccountName in the template."
  elif grep -qi 'is forbidden' <<<"$text"; then
    root="Pod creation is forbidden by RBAC/admission (see message)."; conf=80; rec="Read the full FailedCreate message to find the rejecting component."
  else
    root="The ReplicaSet controller cannot create pods (see FailedCreate events)."; conf=70; rec="Inspect FailedCreate events."
  fi
  emit --sev HIGH --title "Pods cannot be created" --root "$root" --conf "$conf" \
    --evidence "$(lines "${cond:+ReplicaFailure: $cond}" "$evs")" --recs "$rec" \
    --cmds "$(lines "$(_dcmds)" "$CMD_PREFIX get events -n $CTX_NS --field-selector reason=FailedCreate")"
}

RULE_META[rule_deployment_unavailable]="K8S-DEPLOY-003|deployment|Unavailable replicas"
rule_deployment_unavailable() {
  if [[ $(_dj '.spec.paused // false') == true ]]; then
    emit --sev INFO --title "Rollout paused" --conf 100 --root "The deployment rollout is paused; template changes are not rolled out." \
      --evidence "spec.paused=true" --recs "Resume: $CMD_PREFIX rollout resume deployment/$CTX_NAME -n $CTX_NS" --cmds "$(_dcmds)"
    return 0
  fi
  local want avail
  want=$(_dj '.spec.replicas // 1'); avail=$(_dj '.status.availableReplicas // 0')
  [[ $want -eq 0 || $avail -ge $want ]] && return 0
  local miss=$((want - avail)) sev=MEDIUM tail=" - capacity is degraded."
  [[ $((miss * 2)) -ge $want ]] && sev=HIGH
  [[ $avail -eq 0 ]] && { sev=CRITICAL; tail=" - the service is DOWN."; }
  emit --sev "$sev" --title "Deployment has unavailable replicas" --conf 95 --symptom true \
    --root "$miss of $want replicas are unavailable$tail The pod-level findings identify why." \
    --evidence "$(lines "$(_dj '"desired=\(.spec.replicas // 1) available=\(.status.availableReplicas // 0) ready=\(.status.readyReplicas // 0) updated=\(.status.updatedReplicas // 0)"')" \
                        "Pods matched: $(jq '.items | length' "$CTX/pods.json")")" \
    --recs "Fix the root cause reported for the deployment's pods." --cmds "$(_dcmds)"
}
