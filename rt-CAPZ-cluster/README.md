

In order to install RT-DRA on the VMs, you have to follow the instruction on the RT-DRA repo, with some adjustments.

First, check whether your VM has GO installed, otherwise, make sure to install it:\
```bash
sudo apt install -y golang-go
go verision
```

```bash
git clone -b rt https://github.com/nasim-samimi/containerd.git
cd containerd
make
sudo make install
```
Then 


For installing runc, follow these steps:
```bash

git clone -b rt https://github.com/nasim-samimi/runc.git
cd runc
make

sudo kubeadm init --config=kubeadm-config.yaml

```


Running the cluster in CAPZ:
```bash
clusterctl init --infrastructure azure
kubectl apply -f rt-capi.yaml
```

To check for the correct deployemnt:
```bash
 kubectl describe azurecluster rt-capi
 kubectl get clusters
 kubectl describe clsuter rt-capi
 kubectl get azurecluster rt-capi -o yaml

```

if the deployment goes wrong, delete the cluster and re-deploy it:
```bash
kubectl delete cluster rt-capi

kubectl patch cluster rt-capi --type merge -p '{"metadata":{"finalizers":[]}}'
```
or force delete
```bash
kubectl delete cluster rt-capi --force --grace-period=0
```
