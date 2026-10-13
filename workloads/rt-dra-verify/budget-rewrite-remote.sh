#!/usr/bin/env bash
#
# Run budget-rewrite-test.sh against a running RT pod from the control plane
# (any machine with a working kubeconfig). Resolves pod -> UID + node, then
# executes the node-side script on that worker.
#
# Usage:
#   ./budget-rewrite-remote.sh <pod> [-n namespace] [-c cpu]
#
# Env:
#   SSH_TARGET=user@host   use ssh (+sudo) instead of `kubectl debug node`
#   WATCH_SECS=60          passive revert-watch window
#   DEBUG_IMAGE=ubuntu:24.04
#
# Default transport: `kubectl debug node/<node> --profile=sysadmin` (privileged,
# hostPID) + chroot /host. The temporary debug pod is deleted afterwards.

set -uo pipefail

POD="${1:?usage: $0 <pod> [-n namespace] [-c cpu]}"; shift
NS=default; CPU=0
while getopts "n:c:" o; do
  case "$o" in n) NS="$OPTARG";; c) CPU="$OPTARG";; *) exit 2;; esac
done

HERE="$(cd "$(dirname "$0")" && pwd)"
NODE_SCRIPT="$HERE/budget-rewrite-test.sh"
[ -f "$NODE_SCRIPT" ] || { echo "missing $NODE_SCRIPT"; exit 1; }

phase="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.status.phase}')" || exit 1
[ "$phase" = Running ] || { echo "pod $NS/$POD is $phase, need Running"; exit 1; }
UID_="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.metadata.uid}')"
NODE="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.spec.nodeName}')"
echo "pod=$NS/$POD uid=$UID_ node=$NODE cpu=$CPU"

B64="$(base64 -w0 < "$NODE_SCRIPT")"
REMOTE="echo $B64 | base64 -d > /tmp/budget-rewrite-test.sh && WATCH_SECS=${WATCH_SECS:-60} bash /tmp/budget-rewrite-test.sh $UID_ $CPU"

if [ -n "${SSH_TARGET:-}" ]; then
  ssh "$SSH_TARGET" "sudo bash -c '$REMOTE'"
  exit $?
fi

IMAGE="${DEBUG_IMAGE:-ubuntu:24.04}"
# snapshot existing debugger pods so only ours gets cleaned up
before="$(kubectl -n "$NS" get pods -o name | grep "node-debugger-$NODE" || true)"
trap '
  for p in $(kubectl -n "$NS" get pods -o name | grep "node-debugger-$NODE" || true); do
    echo "$before" | grep -qx "$p" || kubectl -n "$NS" delete "$p" --wait=false >/dev/null 2>&1
  done' EXIT

kubectl -n "$NS" debug "node/$NODE" --profile=sysadmin --image="$IMAGE" -i --quiet -- \
  chroot /host bash -c "$REMOTE"
