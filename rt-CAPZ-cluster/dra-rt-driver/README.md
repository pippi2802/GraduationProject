# RT Resource Driver for Dynamic Resource Allocation (RT-DRA)

This repository contains the resource driver for deploying containers using sched_deadline policy in real-time linux kernel for use with the [Dynamic
Resource Allocation
(DRA)](https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/)
feature of Kubernetes.

## Quickstart

Before diving into the details of how this example driver is constructed, it's
useful to run through a quick demo of it in action.


### Prerequisites

<!-- * [GNU Make 3.81+](https://www.gnu.org/software/make/)
* [GNU Tar 1.34+](https://www.gnu.org/software/tar/) -->
* [docker v20.10+ (including buildx)](https://docs.docker.com/engine/install/)
* [golang v1.22.5+](https://go.dev/doc/install)
* [helm v3.7.0+](https://helm.sh/docs/intro/install/)
* [kubeadm v1.28+](https://kubernetes.io/docs/reference/setup-tools/kubeadm/)

### Install Kubernetes
To make sure that RT-DRA can be recognised by the Kubernetes and perform correctly, we must install RT-containerd and RT-runc as container runtimes and enable the DRA feature when initiating the Kubernetes cluster. 

For installing the Kubernetes, we follow the steps for a normal installation from [here](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/install-kubeadm/).
However, we install a custom container runtime (RT-containerd and RT-runc).

To install the RT-containerd, we must clone it's repository, compile, and install it:

```bash
git clone -b rt https://github.com/nasm-samimi/containerd.git
cd containerd
make
sudo make install
```
create the config file for 

```bash
containerd config default > /etc/containerd/config.toml 
```

containerd requires CNI plugins which can be installed as explained [here](https://github.com/containerd/containerd/blob/main/docs/getting-started.md).

To install the RT-runc, we must clone it's repository, compile, and install it:
```bash
sudo apt install libseccomp-dev
git clone -b rt https://github.com/nasm-samimi/runc.git
cd runc
make
sudo install -D -m0755 runc /usr/local/sbin/runc
```

We prepared a configuration file that enables the DRA feature at cluster initiation. To use the configuation file, we run:
```bash
sudo kubeadn init --config=kubeadm-config.yaml
```
After installing CNI plugin, run the following commands:
```bash
sudo systemctl daemon-reload
sudo systemctl restart containerd
sudo systemctl restart kubelet
```

To join the worker nodes, first we run get the token from the master node by running the following command on the master node:
```bash
kubeadm token create --print-join-command
```
After receiving the token and hash code from the previous command, replae the toke and hash fields in the `worker-config.yaml`. Then to join the worker node run the following command from the worker node:

```bash
sudo kubeadm join --config=worker-config.yaml
```

### Demo
We start by first cloning this repository and `cd`ing into its `demo`
subdirectory. All of the scripts and example Pod specs used in this demo are
contained here, so take a moment to browse through the various files and see
what's available:
```bash
git clone https://github.com/nasm-samimi/dra-rt-driver.git
cd dra-rt-driver/demo
```


coming up as expected:
```console
$ kubectl get pod -A

```

And then install the RT-DRA via `helm`:
```bash
helm upgrade -i \
  --create-namespace \
  --namespace dra-rt-driver \
  dra-rt-driver \
  deployments/helm/dra-rt-driver
```

Double check the driver components have come up successfully:
```console
$ kubectl get pod -n dra-rt-driver

```

And show the initial state of available GPU devices on the worker node:
```console
$ kubectl describe -n dra-rt-driver nas/dra-example-driver-cluster-worker
...
Spec:
  Allocatable Cpuset:
    Rtcpu:
      Id:    2
      Util:  0
    Rtcpu:
      Id:    3
      Util:  0
    Rtcpu:
      Id:    4
      Util:  0
    Rtcpu:
      Id:    0
      Util:  0
    Rtcpu:
      Id:    1
      Util:  0
...
```

Next, deploy four example apps that demonstrate how `ResourceClaim`s,
`ResourceClaimTemplate`s, and custom `ClaimParameter` objects can be used to
request access to resources in various ways:
```bash
kubectl create -f rt-test{1,2,3,4}.yaml
```

And verify that they are coming up successfully:
```console
$ kubectl get pod -A
...
```

Use your favorite editor to look through each of the `gpu-test{1,2,3,4}.yaml`
files and see what they are doing. The semantics of each match the figure
below:

![Demo Apps Figure](demo/demo-apps.png?raw=true "Semantics of the applications requesting resources from the example DRA resource driver.")

Then dump the logs of each app to verify that CPUs were allocated to them
according to these semantics:
```bash

```

This should produce output similar to the following:
```bash

```


Likewise, looking at the `ClaimAllocations` section of the
`NodeAllocationState` object on the worker node will show which GPUs have been
allocated to a given `ResourceClaim` by the resource driver:
```console
$ kubectl describe -n dra-rt-driver nas/dra-rt-driver-cluster-worker
...
Spec:
  ...
  Prepared Claims:

```

Once you have verified everything is running correctly, delete all of the
example apps:
```bash
kubectl delete --wait=false --f rt-test{1,2,3,4}.yaml
```

Wait for them to terminate:
```console
$ kubectl get pod -A

...
```

And show that the `ClaimAllocations` section of the `NodeAllocationState`
object on the worker node is now back to its initial state:
```console
$ kubectl describe -n dra-rt-driver nas/dra-example-driver-cluster-worker
...
Spec:
```

## Anatomy of a DRA resource driver

TBD


## References

For more information on the DRA Kubernetes feature and developing custom resource drivers, see the following resources:

* [Dynamic Resource Allocation in Kubernetes](https://kubernetes.io/docs/concepts/scheduling-eviction/dynamic-resource-allocation/)


## Building the code 
We start by first cloning this repository and `cd`ing into its `demo`
subdirectory:
```
git clone https://github.com/nasim-samimi/dra-rt-driver.git
cd dra-rt-driver/demo
```
We build the image for the example resource driver:
```bash
./build-driver.sh
```
<!-- error with containrd

ls -l /usr/bin/containerd
ls -l /usr/local/bin/containerd

sudo rm -f /usr/bin/containerd  # Remove the existing /usr/bin/containerd binary
sudo ln -s /usr/local/bin/containerd /usr/bin/containerd  # Create a symbolic link -->