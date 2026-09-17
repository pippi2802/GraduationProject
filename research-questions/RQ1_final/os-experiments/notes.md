  python3 generate_yaml.py 08-model5
  python3 generate_yaml.py 08-model1

cd ~/GraduationProject/research-questions/RQ1_final/os-experiments
A1=$(kubectl -n 07-model1 get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')
A5=$(kubectl -n 07-model5 get pod -l app=rq1-agent -o jsonpath='{.items[0].metadata.name}')

kubectl -n 07-model1 exec -i "$A1" -- nsenter --target 1 --mount --pid -- bash -s < ~/GraduationProject/setup/scripts/rt-budget-seed.sh
kubectl -n 07-model5 exec -i "$A5" -- nsenter --target 1 --mount --pid -- bash -s < ~/GraduationProject/setup/scripts/rt-budget-seed.sh


CV_THRESHOLD=0.06 U_MAX=0.7 OUT_TAG=_round4 nohup ./run_job.sh 07-model1 > logs/run_07-model1_round4.log 2>&1 &
CV_THRESHOLD=0.06 U_MAX=0.7 OUT_TAG=_round4 nohup ./run_job.sh 07-model5 > logs/run_07-model5_round4.log 2>&1 &


OUT_TAG=_round4 nohup ./run_job.sh 08-model1 > logs/run_08-model1_round4.log 2>&1 &
OUT_TAG=_round4 nohup ./run_job.sh 08-model5 > logs/run_08-model5_round4.log 2>&1 &
