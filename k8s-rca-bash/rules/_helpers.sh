# shellcheck shell=bash
# Shared rule helpers (sourced before rule files; defines no rules).

exit_meaning() {
  case $1 in
    0) echo "process exited successfully - for a long-running workload the main process finished unexpectedly" ;;
    1) echo "generic application error" ;;
    2) echo "invalid arguments / shell misuse" ;;
    126) echo "command found but not executable (permissions)" ;;
    127) echo "command not found (wrong command/entrypoint or missing binary)" ;;
    134) echo "SIGABRT - process aborted" ;;
    137) echo "SIGKILL - OOM killer or forced kill after the grace period" ;;
    139) echo "SIGSEGV - segmentation fault" ;;
    143) echo "SIGTERM - asked to stop (liveness failure, eviction, rollout)" ;;
    -|"") echo "unknown exit code" ;;
    *) if [[ $1 =~ ^[0-9]+$ && $1 -gt 128 && $1 -lt 160 ]]; then echo "terminated by signal $(( $1 - 128 ))"; else echo "application-defined error code"; fi ;;
  esac
}

exit_rec() {
  case $1 in
    0) echo "Ensure the main process runs in the foreground and does not finish; use a Job for batch work." ;;
    126) echo "Make the entrypoint executable (chmod +x) and check ownership vs runAsUser." ;;
    127) echo "Fix command/args/entrypoint - the binary does not exist in the image." ;;
    137) echo "Check for OOM, liveness kills, or shutdown slower than terminationGracePeriodSeconds." ;;
    139) echo "Segfault - check native libraries, base image and CPU architecture." ;;
    143) echo "Correlate with liveness failures, evictions or rollouts." ;;
    *) echo "Read the previous container logs for the stack trace / error and fix the application or its config." ;;
  esac
}

FATAL_RE='Traceback \(most recent call last\)|panic:|fatal|Exception in thread|unhandled (promise )?rejection|[A-Z][A-Za-z0-9]+(Exception|Error)\b|ERROR.*(failed|cannot|unable|could not|refused|denied|invalid|missing)|segmentation fault|exec format error|permission denied|no such file or directory|address already in use|OutOfMemoryError|heap out of memory|APPLICATION FAILED TO START'
DEP_RE='connection refused|ECONNREFUSED|no such host|name resolution|ENOTFOUND|UnknownHostException|x509:|certificate verify failed|PKIX|is forbidden: User "|i/o timeout|ETIMEDOUT'
DNS_RE='no such host|temporary failure in name resolution|name or service not known|could not resolve host|getaddrinfo (ENOTFOUND|EAI_AGAIN)|NXDOMAIN|UnknownHostException|nodename nor servname provided|server misbehaving|failed to resolve|Name does not resolve'
REFUSED_RE='connection refused|ECONNREFUSED|actively refused|could not connect to server'
TIMEOUT_RE='i/o timeout|connection timed out|ETIMEDOUT|connect timeout|context deadline exceeded|SocketTimeoutException'
CERT_RE='x509:|certificate verify failed|CERTIFICATE_VERIFY_FAILED|PKIX path building failed|unable to (get local issuer|verify the first) certificate|SSLHandshakeException|tls: (bad certificate|unknown certificate authority|handshake failure|failed to verify)|self[- ]signed certificate|certificate (has )?expired|ERR_TLS_CERT_ALTNAME_INVALID|subject alternative names|CERT_HAS_EXPIRED|SELF_SIGNED_CERT_IN_CHAIN'

port_name() {
  case $1 in
    5432) echo PostgreSQL ;; 3306) echo MySQL ;; 6379) echo Redis ;; 27017) echo MongoDB ;; 9092) echo Kafka ;;
    5672) echo RabbitMQ ;; 9200) echo Elasticsearch ;; 2181) echo ZooKeeper ;; 11211) echo Memcached ;;
    1433) echo "SQL Server" ;; 443) echo HTTPS ;; 80) echo HTTP ;; *) echo "" ;;
  esac
}

# node helpers (work on $CTX/node.json for both pod and node contexts)
node_cond() { jq -r --arg t "$1" "[.status.conditions[]? | select(.type == \$t)][0] | .$2 // \"-\"" "$CTX/node.json"; }
node_name() { jq -r '.metadata.name' "$CTX/node.json"; }
