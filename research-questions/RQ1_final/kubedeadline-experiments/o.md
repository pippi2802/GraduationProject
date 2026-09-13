nohup bash -c 'OUT_TAG=_round4 DELETE_SETTLE=2 PAIR_TYPE=sibling  COMPETITOR_TYPE=unreserved ./run_job.sh model3-sib-cfs'  > logs/run_model3_sib_cfs_round4.log 2>&1 &

nohup bash -c 'OUT_TAG=_round4 DELETE_SETTLE=2 PAIR_TYPE=sibling  COMPETITOR_TYPE=reserved   ./run_job.sh model3-sib-res'  > logs/run_model3_sib_res_round4.log 2>&1 &

nohup bash -c 'OUT_TAG=_round4 DELETE_SETTLE=2 PAIR_TYPE=physical COMPETITOR_TYPE=unreserved ./run_job.sh model3-phys-cfs' > logs/run_model3_phys_cfs_round4.log 2>&1 &

nohup bash -c 'OUT_TAG=_round4 DELETE_SETTLE=2 PAIR_TYPE=physical COMPETITOR_TYPE=reserved   ./run_job.sh model3-phys-res' > logs/run_model3_phys_res_round4.log 2>&1 &


nohup bash -c 'OUT_TAG=_round4 ./run_job.sh model1' > logs/run_model1_round4.log 2>&1 &

nohup bash -c 'OUT_TAG=_round4 ./run_job.sh model4' > logs/run_model4_round4.log 2>&1 &





-------------------------
nohup bash -c 'OUT_TAG=_round4 PIN_RTCPU=2 ./run_job.sh model1' > logs/run_model1_round4.log 2>&1 &

nohup bash -c 'OUT_TAG=_round4 PIN_RTCPUS=1,2 ./run_job.sh model4' > logs/run_model4_round4.log 2>&1 &

cd ~/GraduationProject/research-questions/RQ1_final/results
python3 -c "
import json, glob
from collections import Counter
for model in ['model1', 'model4']:
    cpus = Counter()
    for f in glob.glob(f'{model}_round1/*/*/placement.json'):
        cpus[json.load(open(f))['target_RT_CPUSET']] += 1
    print(model, dict(cpus))
"


OUT_TAG=_round4 nohup ./run_job.sh model5-phys > logs/run_model5_phys_round4.log 2>&1 &
OUT_TAG=_round4 nohup ./run_job.sh model5-smt  > logs/run_model5_smt_round4.log  2>&1 &

for model_ns in m5-phys:model5-phys m5-smt:model5-smt; do
    NS="${model_ns%%:*}"; MODEL="${model_ns##*:}"
    HOST_PATH="/host/var/lib/rq1final/$NS"
    AGENT=$(kubectl -n "$NS" get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')
    for ROUND in round4; do
      for scale in tight soft; do
        for u in 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 0.94; do
          out="results/${MODEL}_${ROUND}/$scale/U$u"
          mkdir -p "$out"
          kubectl exec -n "$NS" "$AGENT" -- cat "$HOST_PATH/$scale/U$u/target/jobs_2.csv" > "$out/jobs_2.csv" 2>/dev/null
        done
      done
    done
  done
