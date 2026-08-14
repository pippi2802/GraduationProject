cd ~/Documents/rt-k8s/dra-rt-driver
  helm upgrade --install dra-rt-driver deployments/helm/dra-rt-driver \
      --namespace dra-rt-driver --create-namespace \
      --set image.repository=pippina2/dra-rt-driver \
      --set image.tag=v1.0.3 \
      --set image.pullPolicy=Always
  kubectl apply -f deployments/helm/dra-rt-driver/crds/rt.resource.example.com_rtclaimparameters.yaml
  kubectl rollout restart deployment/dra-rt-driver-controller -n dra-rt-driver
  kubectl rollout restart daemonset/dra-rt-driver-kubeletplugin -n dra-rt-driver