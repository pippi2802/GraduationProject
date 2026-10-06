#!/usr/bin/env bash
# campaign_stop_enemies.sh - runs ON THE WORKER NODE (piped via
# `bash -s -- < this-file` through nsenter, by run_campaign.sh). Sends
# SIGTERM to every pid in /tmp/rq2_campaign_enemy.pids, POLLS until each is
# actually gone (never just trusts the signal), escalates to SIGKILL after
# a grace period, and exits nonzero only if something still won't die even
# after that - the thing that matters is that this never returns while an
# enemy from the current condition might still be running into the next one.
set -u

[ -f /tmp/rq2_campaign_enemy.pids ] || { echo "no pidfile, nothing to stop"; exit 0; }
pids="$(cat /tmp/rq2_campaign_enemy.pids)"

for pid in $pids; do kill "$pid" 2>/dev/null || true; done

for _ in $(seq 1 20); do
    alive=""
    for pid in $pids; do
        kill -0 "$pid" 2>/dev/null && alive="$alive $pid"
    done
    if [ -z "$alive" ]; then
        echo "confirmed all stopped"
        rm -f /tmp/rq2_campaign_enemy.pids
        exit 0
    fi
    sleep 0.5
done

echo "still alive after SIGTERM+10s, escalating to SIGKILL:$alive"
for pid in $alive; do kill -9 "$pid" 2>/dev/null || true; done
sleep 1

still=""
for pid in $alive; do
    kill -0 "$pid" 2>/dev/null && still="$still $pid"
done
rm -f /tmp/rq2_campaign_enemy.pids

if [ -n "$still" ]; then
    echo "STILL_ALIVE_AFTER_SIGKILL:$still"
    exit 1
fi
echo "confirmed all stopped (after SIGKILL escalation)"
