#!/usr/bin/env bash
# campaign_start_enemies.sh <size-kb> <stride-bytes> <cpus-csv>
#
# Runs ON THE WORKER NODE (piped via `bash -s -- ARGS < this-file` through
# nsenter, by run_campaign.sh). Starts one enemy per cpu in <cpus-csv>,
# confirms each is genuinely running (not just started-then-stuck), prints
# OK/MISSING/LOW_CPU per pid, exits nonzero if anything didn't check out.
set -u

SIZE_KB="$1"
STRIDE="$2"
CPUS_CSV="$3"

rm -f /tmp/rq2_campaign_enemy.pids
IFS=',' read -ra cpus <<< "$CPUS_CSV"
for cpu in "${cpus[@]}"; do
    nohup /usr/local/bin/rq2-enemy --size-kb "$SIZE_KB" --stride-bytes "$STRIDE" --mode rw --cpu "$cpu" \
        >"/tmp/rq2_campaign_enemy_${cpu}.log" 2>&1 &
    echo $! >> /tmp/rq2_campaign_enemy.pids
done
disown -a
sleep 8

bad=0
while read -r pid; do
    line=$(ps -o pid=,psr=,pcpu=,comm= -p "$pid" 2>/dev/null)
    if [ -z "$line" ]; then
        echo "MISSING pid=$pid"
        bad=1
    else
        echo "OK $line"
        pcpu=$(echo "$line" | awk '{print $3}')
        if awk -v p="$pcpu" 'BEGIN{exit !(p+0 < 20)}'; then
            echo "LOW_CPU pid=$pid pcpu=$pcpu (expected a busy loop, this looks stuck)"
            bad=1
        fi
    fi
done < /tmp/rq2_campaign_enemy.pids

exit "$bad"
