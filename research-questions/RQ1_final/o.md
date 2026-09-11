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