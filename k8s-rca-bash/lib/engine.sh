# shellcheck shell=bash
# -----------------------------------------------------------------------------
# engine.sh - rule discovery, evaluation and finding emission.
#
# Plugin contract: any rules/*.sh file (or file in EXTRA_RULE_DIRS) may define
# functions named   rule_<scope>_<name>   where scope is one of
#   pod | deployment | node | namespace | cluster | all
# and optionally register metadata for `rules list`:
#   RULE_META[rule_pod_oom]="K8S-OOM-001|resources|Container OOMKilled"
# Rules read the current context (CTX dir, CTX_NS, CTX_NAME) and call `emit`.
# Files starting with "_" are shared helpers: sourced first, define no rules.
# -----------------------------------------------------------------------------

declare -gA RULE_META=()
declare -gA SEV_OVERRIDE=()

load_rules() {
  local dir f
  shopt -s nullglob
  for dir in "$AGENT_HOME/rules" "${EXTRA_RULE_DIRS[@]}"; do
    [[ $dir != /* ]] && dir="$AGENT_HOME/$dir"
    [[ -d $dir ]] || { warn "rule directory not found: $dir"; continue; }
    # helper files (_*.sh) first, then rule files
    for f in "$dir"/_*.sh "$dir"/[!_]*.sh; do
      # shellcheck source=/dev/null
      if ! source "$f"; then warn "failed to load rule file $f"; fi
    done
  done
  shopt -u nullglob
  local o
  for o in "${SEVERITY_OVERRIDES[@]}"; do SEV_OVERRIDE[${o%%=*}]=${o#*=}; done
}

rules_for_scope() { declare -F | awk '{print $3}' | grep -E "^rule_($1|all)_" | sort; }

is_disabled() {
  local id=$1 fn=$2 d
  for d in "${DISABLED_RULES[@]}"; do [[ $d == "$id" || $d == "$fn" ]] && return 0; done
  return 1
}

# run_rules SCOPE  (CTX / CUR_RES must be set)
run_rules() {
  local fn
  while read -r fn; do
    [[ -z $fn ]] && continue
    local id=${RULE_META[$fn]%%|*}
    is_disabled "$id" "$fn" && continue
    CURRENT_RULE=$fn
    log "  rule $fn on $CUR_RES"
    "$fn" || true          # a failing rule never aborts the analysis
  done < <(rules_for_scope "$1")
  CURRENT_RULE=""
}

# emit --sev S --id ID --title T --root R [--conf N] [--container C] [--evidence "l1\nl2"]
#      [--recs "..."] [--cmds "..."] [--symptom true] [--corr KEY] [--resource "Kind ns/name"]
emit() {
  local sev=MEDIUM id="${RULE_META[$CURRENT_RULE]%%|*}" title="" root="" conf=50 container="" \
        evidence="" recs="" cmds="" symptom=false corr="" res="$CUR_RES"
  while [[ $# -gt 0 ]]; do
    case $1 in
      --sev) sev=$2 ;; --id) id=$2 ;; --title) title=$2 ;; --root) root=$2 ;; --conf) conf=$2 ;;
      --container) container=$2 ;; --evidence) evidence=$2 ;; --recs) recs=$2 ;; --cmds) cmds=$2 ;;
      --symptom) symptom=$2 ;; --corr) corr=$2 ;; --resource) res=$2 ;;
      *) warn "emit: unknown option $1"; return 1 ;;
    esac
    shift 2
  done
  is_disabled "$id" "" && return 0
  [[ -n ${SEV_OVERRIDE[$id]:-} ]] && sev=${SEV_OVERRIDE[$id]}
  [[ $conf -lt ${MIN_CONFIDENCE:-0} ]] && return 0
  evidence=$(printf '%s\n' "$evidence" | redact | cut -c1-400)
  root=$(printf '%s\n' "$root" | redact)
  jq -nc --arg group "$CUR_RES" --arg id "$id" --arg title "$title" --arg sev "${sev^^}" --arg res "$res" \
         --arg root "$root" --argjson conf "$conf" --arg c "$container" --arg ev "$evidence" --arg recs "$recs" \
         --arg cmds "$cmds" --argjson sym "$symptom" --arg corr "$corr" '
    def l: split("\n") | map(select(length > 0));
    {group:$group, rule_id:$id, title:$title, severity:$sev, resource:$res, container:$c, root_cause:$root,
     evidence:($ev|l), confidence:$conf, recommendations:($recs|l), commands:($cmds|l), is_symptom:$sym, corr:$corr}' \
    >>"$WORK/findings.jsonl"
}

list_rules() {
  local fn meta scope n=0
  printf '%-16s %-11s %-14s %s\n' ID SCOPE CATEGORY NAME
  while read -r fn; do
    meta=${RULE_META[$fn]:-"?|?|$fn"}
    scope=${fn#rule_}; scope=${scope%%_*}
    IFS='|' read -r id cat name <<<"$meta"
    printf '%-16s %-11s %-14s %s\n' "$id" "$scope" "$cat" "$name"
    n=$((n + 1))
  done < <(declare -F | awk '{print $3}' | grep -E '^rule_(pod|deployment|node|namespace|cluster|all)_' | sort)
  printf '\n%d rule functions loaded\n' "$n"
}
