# Graduation Project
The scope of this MSc thesis is to analyse the behavior of KubeDeadline on public cloud, that is Azure, and to try to characterize the influences of cloud related interferences on KubeDealine guarantees.

### Repo organization
This repo is organized in the following way:
- `./setup` → IaC for the Azure VMs in Bicep and scripts for automatic setup installation
- `./workloads` → workloads shared across the research questions
- `./research-questions` → results separated per research question
- `./docs` → logs and docs on findings/problems/troubles encountered
- `./other` → side projects

```
GraduationProject/
├── setup/                       # Infrastructure & provisioning
│   ├── CAPZ-cluster/            # Cluster API for Azure + image-builder
│   ├── rt-cluster/              # Bicep IaC (network, LB, VM modules)
│   └── scripts/                 # Control-plane / worker init scripts
├── workloads/                   # Shared experimental workloads
│   ├── PeriodicTask/            # RT periodic task (CFS/FIFO/deadline)
│   ├── rt-dra-verify/           # RT Dynamic Resource Allocation checks
│   ├── synthetic_workload/      # Carts + kdl synthetic benchmark
│   └── video-streamer-benchmark/ # Video streaming benchmark
├── research-questions/          # Per-RQ results
│   ├── RQ1/
│   ├── RQ2/
│   └── RQ3/
├── docs/                        # Findings, open problems, workbooks
└── other/                       # Side projects
    └── rt-grafana-extension/    # Prometheus client + dashboards
```

