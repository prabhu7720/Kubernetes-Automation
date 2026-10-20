# shellcheck shell=bash
# -----------------------------------------------------------------------------
# common.sh - shared helpers: logging, read-only kubectl wrapper, JSONL writers,
#             context accessors used by rules, redaction, quantity parsing.
# Nothing here performs network I/O except the kubectl subprocess.
# -----------------------------------------------------------------------------

SEV_LEVELS=(INFO LOW MEDIUM HIGH CRITICAL)

log()  { [[ ${VERBOSE:-0} -ge 1 ]] && printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >&2; return 0; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$1" >&2; exit "${2:-2}"; }
need() { command -v "$1" >/dev/null 2>&1 || die "'$1' is required but not installed"; }

sev_num() { case "${1^^}" in INFO) echo 0;; LOW) echo 1;; MEDIUM) echo 2;; HIGH) echo 3;; CRITICAL) echo 4;; *) echo -1;; esac; }

# lines "a" "b" -> newline-joined string (used to pass lists to emit)
lines() { local x; for x in "$@"; do [[ -n $x ]] && printf '%s\n' "$x"; done; }

# orv VALUE DEFAULT : treat "-", "null" and "" as unset
orv() { if [[ -z $1 || $1 == "-" || $1 == "null" ]]; then printf '%s' "$2"; else printf '%s' "$1"; fi; }

# ------------------------------------------------------------------ kubectl
# Only read verbs are allowed. KUBECTL_CMD and KFLAGS are set by k8s-rca.sh.
kube() {
  case "$1" in
    get|logs|top|version|config|auth) ;;
    *) die "refusing to run non read-only kubectl verb: $1" ;;
  esac
  "${KUBECTL_CMD[@]}" "${KFLAGS[@]}" "--request-timeout=${REQUEST_TIMEOUT}s" "$@"
}

# kube_json OUTFILE ARGS... -> 0 ok | 1 not found | 2 other error (recorded)
kube_json() {
  local out=$1; shift
  local err="$WORK/.kerr.$$"
  if kube "$@" -o json >"$out" 2>"$err"; then
    [[ -s $out ]] || echo '{}' >"$out"
    return 0
  fi
  if grep -qiE 'unable to connect to the server|connection refused|no such host|i/o timeout|TLS handshake timeout' "$err"; then
    die "cannot reach the Kubernetes API server: $(head -1 "$err")"
  fi
  if grep -qiE '\(NotFound\)| not found' "$err" && ! grep -qi "doesn't have a resource type" "$err"; then
    echo '{}' >"$out"; return 1
  fi
  if grep -qi "doesn't have a resource type" "$err"; then
    echo '{}' >"$out"; return 3
  fi
  record_error "kubectl $(printf '%s ' "$@" | cut -c1-80): $(head -1 "$err" | cut -c1-220)"
  echo '{}' >"$out"
  return 2
}

# kube_cached KEY ARGS... -> prints path of cached JSON file; same rc semantics
kube_cached() {
  local key=$1; shift
  local f="$WORK/cache/${key//\//_}.json"
  if [[ -f $f ]]; then echo "$f"; return "$(cat "$f.rc" 2>/dev/null || echo 0)"; fi
  kube_json "$f" "$@"; local rc=$?
  echo "$rc" >"$f.rc"; echo "$f"; return "$rc"
}

# names only via server-side table printer (no secret data transferred)
kube_names() { # resource namespace outfile
  local err="$WORK/.kerr.$$"
  if kube get "$1" -n "$2" --no-headers --ignore-not-found 2>"$err" | awk 'NF{print $1}' >"$3"; then
    if [[ -s $err ]] && grep -qi forbidden "$err"; then record_error "list $1 names: forbidden (RBAC)"; rm -f "$3"; return 2; fi
    return 0
  fi
  record_error "list $1 names: $(head -1 "$err")"; rm -f "$3"; return 2
}

# ------------------------------------------------------------------ JSONL stores
add_resource() { # kind name ns parent
  jq -nc --arg k "$1 ${3:+$3/}$2" --arg kind "$1" --arg n "$2" --arg ns "$3" --arg p "$4" \
    '{key:$k, kind:$kind, name:$n, namespace:$ns, parent:$p}' >>"$WORK/resources.jsonl"
}
add_fact()     { jq -nc --arg g "$CUR_RES" --arg f "$1" '{group:$g, fact:$f}' >>"$WORK/facts.jsonl"; }
record_error() { jq -nc --arg g "${CUR_RES:-global}" --arg m "$1" '{group:$g, msg:$m}' >>"$WORK/errors.jsonl"; log "collection warning: $1"; }

# ------------------------------------------------------------------ redaction
redact() {
  local out p
  out=$(_redact_base)
  for p in "${REDACT_PATTERNS[@]}"; do
    [[ -n $p ]] && out=$(printf '%s\n' "$out" | sed -E "s/$p/***REDACTED***/g")
  done
  printf '%s\n' "$out"
}
_redact_base() {
  sed -E \
    -e 's/((password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|client[_-]?secret|private[_-]?key|authorization)("?[[:space:]]*[:=][[:space:]]*"?))[^[:space:]"'"'"',;&}]+/\1***REDACTED***/Ig' \
    -e 's/[Bb]earer [A-Za-z0-9._~+\/-]+=*/Bearer ***REDACTED***/g' \
    -e 's/eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}/***REDACTED***/g' \
    -e 's/(AKIA|ASIA)[0-9A-Z]{16}/***REDACTED***/g' \
    -e 's#([a-zA-Z][a-zA-Z0-9+.-]*://)[^:/[:space:]@]+:[^@[:space:]/]+@#\1***REDACTED***@#g' \
    -e "s/\x1b\[[0-9;]*m//g"
}

# ------------------------------------------------------------------ quantities
to_bytes() { # 512Mi -> bytes
  awk -v q="$1" 'BEGIN{ if(q==""||q=="-"){print ""; exit}
    n=q; s=q; sub(/[A-Za-z]+$/,"",n); sub(/^[0-9.eE+-]+/,"",s);
    m["Ki"]=1024;m["Mi"]=1048576;m["Gi"]=1073741824;m["Ti"]=1099511627776;
    m["k"]=1e3;m["K"]=1e3;m["M"]=1e6;m["G"]=1e9;m["T"]=1e12;m["m"]=0.001;m[""]=1;
    printf "%.0f\n", n*m[s] }'
}
to_milli() { # 250m -> 250, 2 -> 2000
  awk -v q="$1" 'BEGIN{ if(q==""||q=="-"){print ""; exit}
    if (q ~ /m$/){sub(/m$/,"",q); printf "%.0f\n", q} else if (q ~ /n$/){sub(/n$/,"",q); printf "%.0f\n", q/1e6}
    else printf "%.0f\n", q*1000 }'
}
pct() { awk -v a="$1" -v b="$2" 'BEGIN{ if(b==""||b==0||a==""){print ""} else printf "%.1f\n", 100*a/b }'; }

# ------------------------------------------------------------------ pod context accessors
# Rules run with CTX=<context dir>, CTX_NS, CTX_NAME, CUR_RES set by the analyzer.
pj() { jq -r "$1" "$CTX/pod.json"; }

# One TSV line per container status (init first). "-" marks empty fields because
# bash `read` collapses consecutive tabs.
# name restarts ready waitReason waitMsg termReason termExit lastReason lastExit finishedAt image init startedAt
statuses_tsv() {
  jq -r '
    ((.status.initContainerStatuses // []) | map(. + {init:true})) +
    ((.status.containerStatuses // []) | map(. + {init:false})) | .[] |
    [ .name, (.restartCount // 0), (.ready // false),
      (.state.waiting.reason // "-"), ((.state.waiting.message // "-") | gsub("[\t\n]"; " ") | if .=="" then "-" else . end),
      (.state.terminated.reason // "-"), (.state.terminated.exitCode // "-"),
      (.lastState.terminated.reason // "-"), (.lastState.terminated.exitCode // "-"),
      (.lastState.terminated.finishedAt // .state.terminated.finishedAt // "-"), (.image // "-"), .init,
      (.lastState.terminated.startedAt // .state.terminated.startedAt // "-") ] | map(tostring) | @tsv' "$CTX/pod.json"
}

# cspec CONTAINER JQPATH -> value from the container spec ("-" if unset)
cspec() {
  jq -r --arg c "$1" "[(.spec.initContainers // [])[], (.spec.containers // [])[]] | map(select(.name==\$c))[0] | ($2) // \"-\" | tostring" "$CTX/pod.json"
}

pod_ready()   { [[ $(pj '[.status.conditions[]? | select(.type=="Ready")][0].status // "False"') == "True" ]]; }
pod_restarts(){ pj '[(.status.initContainerStatuses // [])[], (.status.containerStatuses // [])[] | .restartCount // 0] | add // 0'; }
pod_phase()   { pj '.status.phase // "Unknown"'; }
# HIGH when the pod is crashing / not ready, else MEDIUM
impact_sev()  { if ! pod_ready || [[ $(pod_restarts) -gt 0 ]]; then echo "${1:-HIGH}"; else echo "${2:-MEDIUM}"; fi; }

# events_fmt REASON_REGEX [MESSAGE_REGEX] [CONTAINER] [FILE]
events_fmt() {
  jq -r --arg r "$1" --arg m "${2:-.}" --arg c "${3:-}" '
    (.items // []) | sort_by(.lastTimestamp // .eventTime // "") | .[]
    | select((.reason // "") | test("^(" + $r + ")$"))
    | select((.message // "") | test($m; "i"))
    | select($c == "" or ((.involvedObject.fieldPath // "") | contains("{" + $c + "}")))
    | "Event \(.type)/\(.reason) (x\(.count // .series.count // 1), last \(.lastTimestamp // .eventTime // "?")): \((.message // "") | gsub("\\s+"; " ") | .[0:300])"' \
    "${4:-$CTX/events.json}" 2>/dev/null
}
event_count() { # same filters, returns summed count
  jq -r --arg r "$1" --arg m "${2:-.}" --arg c "${3:-}" '
    [(.items // [])[] | select((.reason // "") | test("^(" + $r + ")$")) | select((.message // "") | test($m; "i"))
     | select($c == "" or ((.involvedObject.fieldPath // "") | contains("{" + $c + "}"))) | (.count // .series.count // 1)] | add // 0' \
    "${4:-$CTX/events.json}" 2>/dev/null
}
last_event_msg() { events_fmt "$@" | tail -1 | sed -E 's/^Event [^:]+\): //'; }

# log_hits ERE [CONTAINER] [MAX] -> "[c previous log] line" (deduplicated, previous logs first)
log_hits() {
  local re=$1 c=${2:-*} max=${3:-$MAX_EVIDENCE} f base src
  shopt -s nullglob
  for f in "$CTX"/logs/$c.previous "$CTX"/logs/$c.current; do
    [[ -s $f ]] || continue
    base=$(basename "$f"); src=${base##*.}; base=${base%.*}
    grep -Ei -- "$re" "$f" 2>/dev/null | sed "s/^/[$base $src log] /"
  done | awk '{k=$0; sub(/^\[[^]]*\] /,"",k); gsub(/[0-9]+/,"#",k); if(!seen[k]++) print}' | head -n "$max"
  shopt -u nullglob
}
last_log_lines() { # container n
  local f="$CTX/logs/$1.previous"; [[ -s $f ]] || f="$CTX/logs/$1.current"
  [[ -s $f ]] && grep -v '^[[:space:]]*$' "$f" | tail -n "$2" | sed "s/^/[$1 last log line] /"
}

c_describe() { echo "$CMD_PREFIX describe pod $CTX_NAME -n $CTX_NS"; }
c_events()   { echo "$CMD_PREFIX get events -n $CTX_NS --field-selector involvedObject.kind=${2:-Pod},involvedObject.name=${1:-$CTX_NAME} --sort-by=.lastTimestamp"; }
c_logs()     { echo "$CMD_PREFIX logs $CTX_NAME -n $CTX_NS -c $1 --tail=100${2:+ --previous}"; }

# jq health scorer shared by triage (deployment/namespace/cluster modes)
JQ_HEALTH='
def health($thr):
  (.status.phase // "Unknown") as $ph
  | if $ph == "Succeeded" then 0 else
    ([ ((.status.initContainerStatuses // []) + (.status.containerStatuses // []))[]
       | ((.state.waiting.reason // "") as $w | if ($w != "" and $w != "ContainerCreating" and $w != "PodInitializing") then 60 else 0 end)
       + (if (.state.terminated.exitCode // 0) != 0 then 40 else 0 end)
       + (if (.restartCount // 0) >= $thr then ([.restartCount, 50] | min) else 0 end)
       + (if .lastState.terminated.reason == "OOMKilled" then 30 else 0 end) ] | add // 0)
    + (if ($ph == "Pending" or $ph == "Failed" or $ph == "Unknown") then 40 else 0 end)
    + (if .status.reason == "Evicted" then 50 else 0 end)
    + (if ($ph == "Running" and .metadata.deletionTimestamp == null and
          ([.status.conditions[]? | select(.type == "Ready" and .status != "True")] | length) > 0) then 30 else 0 end)
    end;'
