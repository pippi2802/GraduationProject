cd ~/Documents/rt-k8s/dra-rt-driver
  helm upgrade --install dra-rt-driver deployments/helm/dra-rt-driver \
      --namespace dra-rt-driver --create-namespace \
      --set image.repository=pippina2/dra-rt-driver \
      --set image.tag=v1.0.3 \
      --set image.pullPolicy=Always
  kubectl apply -f deployments/helm/dra-rt-driver/crds/rt.resource.example.com_rtclaimparameters.yaml
  kubectl rollout restart deployment/dra-rt-driver-controller -n dra-rt-driver
  kubectl rollout restart daemonset/dra-rt-driver-kubeletplugin -n dra-rt-driver.




CV_THRESHOLD=0.3 WORKLOAD=primes PAIR_TYPE=sibling COMPETITOR_TYPE=unreserved OUT_TAG=_sib_cfs_primes_round4 nohup ./run_job.sh model3 > logs/model3_sib_cfs_primes_round4.log 2>&1 &
CV_THRESHOLD=0.3 WORKLOAD=primes PAIR_TYPE=sibling COMPETITOR_TYPE=reserved OUT_TAG=_sib_res_primes_round4 nohup ./run_job.sh model3-w2 > logs/model3-w2_sib_res_primes_round4.log 2>&1 &
CV_THRESHOLD=0.3 WORKLOAD=primes PAIR_TYPE=physical COMPETITOR_TYPE=unreserved OUT_TAG=_phys_cfs_primes_round4 nohup ./run_job.sh model3-w3 > logs/model3-w3_phys_cfs_primes_round4.log 2>&1 &
CV_THRESHOLD=0.3 WORKLOAD=primes PAIR_TYPE=physical COMPETITOR_TYPE=reserved OUT_TAG=_phys_res_primes_round4 nohup ./run_job.sh model3-w4 > logs/model3-w4_phys_res_primes_round4.log 2>&1 &



CV_THRESHOLD=0.3 WORKLOAD=primes OUT_TAG=_primes_round1 nohup ./run_job.sh model1 > logs/model1_primes_round1.log 2>&1 &
  pgrep -af run_job.sh
