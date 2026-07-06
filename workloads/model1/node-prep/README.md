# node-prep — hyper-thread sibling offlining

Model 1 requires each real-time logical CPU to own a **whole physical core**:
its hyper-thread sibling must be **offline** so there is zero sibling
interference. This directory detects the topology and offlines the siblings.

## What it does

1. Reads `/sys/devices/system/cpu/cpuN/topology/thread_siblings_list` for every
   online CPU and groups logical CPUs into physical cores.
2. Picks the first logical CPU of **core 0** for the **RT-under-test** and the
   first logical CPU of **core 1** for the **canary**.
3. Takes every *other* sibling **offline** (`echo 0 > .../cpuX/online`).
4. Writes the mapping to `/var/lib/model1/cpu-map.json` (consumed by the
   orchestrator for metadata and to know which CPU to pin rt-app to).
5. **Fails loudly** if topology is unreadable or fewer than 2 physical cores.

On `Standard_D4s_v5` (4 vCPU / 2 physical cores) this yields e.g.
`rt_cpu=0, canary_cpu=2, offline=[1,3]` — exact numbers come from the *real*
`thread_siblings_list`, not assumptions.

## Manual use (documented alternative to the DaemonSet)

```bash
sudo MAP_OUT=/var/lib/model1/cpu-map.json ./prepare-node.sh   # offline siblings
sudo DRY_RUN=1 ./prepare-node.sh                              # detect only, no changes
sudo ./restore-node.sh                                         # bring siblings back online
lscpu -e                                                       # cross-check topology
```

## DaemonSet (privileged, no custom image)

```bash
kubectl label node <NODE> model1/rt-node=true
./apply.sh
kubectl -n model1 logs ds/model1-node-prep
```

Offlining persists until reboot; the DaemonSet re-applies it after a reboot.
To undo: delete the DaemonSet and run `restore-node.sh` (or reboot the node).
