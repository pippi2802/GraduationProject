

This is for associating the image with the workload registered with the container registry to the aks cluster.
```
az aks update --resource-group AKS_experiment_1 --name AKS_baseline --attach-acr baselineaks
```
Then, run this to deploy the pod
```
kubectl apply -f k8s/workload-solo.yaml
```

Then to check whether everything is running smoothly, run this:
```
kubectl get pods
```