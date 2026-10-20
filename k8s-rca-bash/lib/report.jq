# report.jq - renders the analysis (resources/facts/findings/errors JSONL) as
# text, markdown or json. Also: $fmt == "maxsev" prints the worst severity number.
#
# Inputs:  --slurpfile R resources  --slurpfile F facts  --slurpfile X findings  --slurpfile E errors
# Args:    fmt minsev generated context version showfacts

def sevnum: {"INFO":0,"LOW":1,"MEDIUM":2,"HIGH":3,"CRITICAL":4}[.] // 0;
def sevname: ["Info","Low","Medium","High","Critical"][.];
def cap: .[0:1] + (.[1:] | ascii_downcase);
def skey: [-(.severity | sevnum), (if .is_symptom then 1 else 0 end), -.confidence, .rule_id];
def indent($d): [range($d)] | map("  ") | join("");
def LINE: "====================================================";
def SUB:  "----------------------------------------------------";
def HASH: "####################################################";

# de-duplicate, filter, correlate (same corr key => first is primary, rest symptoms), sort
def prep:
  unique_by([.rule_id, .title, .container, .root_cause, .resource])
  | map(select((.severity | sevnum) >= ($minsev | sevnum)))
  | sort_by(skey)
  | reduce .[] as $f ({out: [], seen: {}};
      if ($f.corr != "" and .seen[$f.corr] != null)
      then .out += [$f + {is_symptom: true, related: [.seen[$f.corr]]}]
      else (if $f.corr != "" then .seen[$f.corr] = $f.rule_id else . end) | .out += [$f + {related: []}]
      end)
  | .out | sort_by(skey);

def fs($k): [$X[] | select(.group == $k)] | prep;
def kids($k): [$R[] | select(.parent == $k)];
def desc($k): [kids($k)[] | ., desc(.key)[]];
def allfs($k): [fs($k)[], (desc($k)[] | fs(.key)[])] | sort_by(skey);
def maxsev($k): allfs($k) | map(.severity | sevnum) | max;
def sevlabel($k): maxsev($k) | if . == null then "Healthy" else sevname end;
def errs($k): [$E[] | select(.group == $k) | .msg] | unique;
def facts($k): [$F[] | select(.group == $k) | .fact];
def primary($k): fs($k) | ([.[] | select(.is_symptom | not)] + .)[0];

# ------------------------------------------------------------------ text
def issue($i):
  [SUB,
   "[\($i)] \(.severity) | \(.title)\(if .is_symptom then " (symptom)" else "" end) | \(.rule_id)"
     + (if .container != "" then " | container: \(.container)" else "" end)
     + (if .resource != .group then " | \(.resource)" else "" end),
   SUB, "Severity:", "  \(.severity | cap)", "Root Cause:", "  \(.root_cause)"]
  + (if (.evidence | length) > 0 then ["Evidence:"] + (.evidence | map("  " + .)) else [] end)
  + ["Confidence:", "  \(.confidence)%"]
  + (if (.related | length) > 0 then ["Related Findings:", "  " + (.related | join(", "))] else [] end)
  + (if (.recommendations | length) > 0
     then ["Recommended Actions:"] + [.recommendations | to_entries[] | "  \(.key + 1). \(.value)"] else [] end)
  + (if (.commands | length) > 0 then ["Validation Commands:"] + (.commands | map("  " + .)) else [] end);

def block($r):
  fs($r.key) as $f
  | ["Resource:", "  \($r.key)", "", "Severity:", "  \(sevlabel($r.key))", ""]
  + (primary($r.key) as $p | if $p then ["Primary Root Cause:", "  \($p.title): \($p.root_cause)", ""] else [] end)
  + (facts($r.key) as $fa | if ($fa | length) > 0 and $showfacts == "true"
       then ["Findings:"] + ($fa | map(if startswith("  ") then "      " + ltrimstr("  ") else "  - " + . end)) + [""]
       else [] end)
  + (if ($f | length) > 0
       then ["Issues Detected: \($f | length)"] + [$f | to_entries[] | .key as $i | .value | issue($i + 1)[]]
       elif (kids($r.key) | length) == 0 then ["Issues Detected:", "  None - no diagnostic rule matched; the resource looks healthy."]
       else [] end)
  + (errs($r.key) as $e | if ($e | length) > 0 then ["", "Collection Warnings:"] + ($e | map("  ! " + .)) else [] end);

def tree($k; $d):
  kids($k)[] as $c
  | ("\(indent($d))- [\(sevlabel($c.key))] \($c.key): \(allfs($c.key)[0].title // "no issues")"), tree($c.key; $d + 1);

def text($root):
  [LINE, "KUBERNETES ROOT CAUSE ANALYSIS REPORT", LINE,
   "Generated: \($generated)   Agent: k8s-rca.sh v\($version)",
   "Cluster context: \($context)",
   "Analysis engine: local rule-based (bash + kubectl + jq, no external APIs / LLMs)", ""]
  + block($root)
  + (if (kids($root.key) | length) > 0
     then ["", LINE, "RESOURCE SUMMARY", LINE] + [tree($root.key; 0)]
          + [desc($root.key)[] | select((fs(.key) | length) > 0 or (errs(.key) | length) > 0)
             | (["", HASH, "> \(.key)", HASH] + block(.))[]]
     else [] end)
  + ["", LINE, "END OF REPORT", LINE]
  | join("\n");

# ------------------------------------------------------------------ markdown
def mdblock($r; $h):
  fs($r.key) as $f
  | ["\($h) \($r.key)", "", "**Severity:** \(sevlabel($r.key))", ""]
  + (facts($r.key) as $fa | if ($fa | length) > 0 and $showfacts == "true"
       then ["**Findings:**", ""] + ($fa | map("- " + ltrimstr("  "))) + [""] else [] end)
  + [$f | to_entries[] | .key as $i | .value
     | ["\($h)# \($i + 1). \(.title)\(if .is_symptom then " (symptom)" else "" end) - \(.severity | cap)", "",
        "- **Rule:** `\(.rule_id)`\(if .container != "" then "  **Container:** `\(.container)`" else "" end)",
        "- **Confidence:** \(.confidence)%", "- **Root cause:** \(.root_cause)", "", "**Evidence:**", "", "```"]
       + .evidence + ["```", "", "**Recommended actions:**", ""]
       + [.recommendations | to_entries[] | "\(.key + 1). \(.value)"]
       + ["", "**Validation commands:**", "", "```bash"] + .commands + ["```", ""] | .[]]
  + (errs($r.key) as $e | if ($e | length) > 0 then ["**Collection warnings:**", ""] + ($e | map("- " + .)) + [""] else [] end);

def markdown($root):
  ["# Kubernetes Root Cause Analysis Report", "",
   "*Generated \($generated) - k8s-rca.sh v\($version) - local rule-based engine - context `\($context)`*", ""]
  + mdblock($root; "##")
  + (if (kids($root.key) | length) > 0
     then ["", "## Resource Summary", "", "| Severity | Resource | Top issue |", "|---|---|---|"]
          + [desc($root.key)[] | "| \(sevlabel(.key)) | \(.key) | \(allfs(.key)[0].title // "no issues") |"]
          + [desc($root.key)[] | select((fs(.key) | length) > 0) | ([""] + mdblock(.; "###"))[]]
     else [] end)
  | join("\n");

# ------------------------------------------------------------------ json
def json($root):
  {metadata: {generated_at: $generated, agent: "k8s-rca.sh", version: $version, context: $context,
              engine: "local rule-based (no external APIs / LLMs)"},
   summary: {severity: sevlabel($root.key), issues: (allfs($root.key) | length), primary_root_cause: (allfs($root.key)[0] // null)},
   resources: [$R[] | . + {severity: sevlabel(.key), facts: facts(.key), findings: fs(.key), errors: errs(.key)}]};

($R | map(select(.parent == ""))[0]) as $root
| if $fmt == "maxsev" then (maxsev($root.key) // -1)
  elif $fmt == "json" then json($root)
  elif $fmt == "markdown" then markdown($root)
  else text($root) end
