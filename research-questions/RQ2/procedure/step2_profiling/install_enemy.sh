#!/usr/bin/env bash
# Step 2, once per node: builds the enemy and installs it on the node as /usr/local/bin/rq2-enemy (through the node-prep agent).
#   ./install_enemy.sh <agent-namespace> <node>          e.g. ./install_enemy.sh rq2-node-prep-worker6 rt-k8s-worker-6
set -euo pipefail
cd "$(dirname "$0")"
NS="${1:?usage: install_enemy.sh <agent-namespace> <node>}"; NODE="${2:?usage: install_enemy.sh <agent-namespace> <node>}"
make -s enemy
AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent --field-selector "spec.nodeName=$NODE" -o jsonpath='{.items[0].metadata.name}')
[ -n "$AGENT" ] || { echo "no node-prep agent on $NODE in $NS" >&2; exit 1; }
kubectl -n "$NS" exec -i "$AGENT" -- nsenter --target 1 --mount -- bash -c 'cat > /usr/local/bin/rq2-enemy && chmod +x /usr/local/bin/rq2-enemy' < enemy
echo "installed /usr/local/bin/rq2-enemy on $NODE"
