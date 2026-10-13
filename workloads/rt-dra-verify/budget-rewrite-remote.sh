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
#   SSH_TARGET=user@host   use ssh (+sudo) instead of the privileged pod
#   WATCH_SECS=60          passive revert-watch window
#   DEBUG_IMAGE=ubuntu:24.04
#
# Default transport: a temporary privileged hostPID pod pinned to the node
# (kubectl run --rm) + chroot /host.

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
RUNNER="budget-rewrite-$RANDOM"
# Own privileged pod pinned to the node (no `kubectl debug --profile`, which old
# kubectl lacks). --rm deletes it when the command ends. The command MUST be in
# the override: trailing `-- args` are dropped and the image's default bash runs.
OVERRIDES='{"spec":{"nodeName":"'"$NODE"'","hostPID":true,"hostNetwork":true,
 "tolerations":[{"operator":"Exists"}],
 "containers":[{"name":"'"$RUNNER"'","image":"'"$IMAGE"'","stdin":true,
   "command":["chroot","/host","bash","-c","'"$REMOTE"'"],
   "securityContext":{"privileged":true},
   "volumeMounts":[{"name":"host","mountPath":"/host"}]}],
 "volumes":[{"name":"host","hostPath":{"path":"/"}}]}}'

kubectl -n "$NS" run "$RUNNER" --rm -i --quiet --restart=Never --image="$IMAGE" \
  --overrides="$OVERRIDES"
