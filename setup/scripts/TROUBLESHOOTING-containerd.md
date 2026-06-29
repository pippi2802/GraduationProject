# Troubleshooting: worker pods crash-loop every ~74s (stock containerd shadows the RT build)

## Symptoms

- On the **worker** node, long-lived pods restart on a fixed ~70–75 s cycle and
  pile up huge `RESTARTS` counts:

  ```text
  dra-rt-driver-kubeletplugin-xxxxx   1/1/CrashLoopBackOff   300+ restarts
  kube-proxy-xxxxx                    CrashLoopBackOff       300+ restarts
  ```

- **Both** the DRA kubeletplugin **and** `kube-proxy` cycle in lockstep — any
  pod on the worker is affected, not just DRA.
- The DRA kubeletplugin container exits cleanly: `Last State: Terminated,
  Reason: Completed, Exit Code: 0` (no panic, no error in its logs).
- `kubectl describe pod` events show `Killing / Stopping container` and
  `Pod sandbox changed, it will be killed and re-created`.
- rtdra workload pods get stuck `Pending` / `ContainerCreating` waiting for
  `NodePrepareResources` (the plugin is down most of the time).

## Root cause

A stray **Docker / `containerd.io`** package was (re)installed on the worker. It
dropped **stock `/usr/bin/containerd`** and a stock unit at
`/lib/systemd/system/containerd.service`, which **shadowed** the RT-patched
containerd built from source at `/usr/local/bin/containerd`.

Two consequences:

1. The systemd unit ran the **wrong binary** (`ExecStart=/usr/bin/containerd`),
   so the kubelet talked to **stock containerd**, not the RT fork. The RT cgroup
   support (`cpu.rt_multi_runtime_us`) the DRA driver needs was therefore absent.
2. Stock containerd's `config default` set **`SystemdCgroup = false`** while the
   kubelet uses **`cgroupDriver: systemd`**. With that mismatch, systemd
   periodically reaps the mis-parented container cgroups, sending a clean
   **SIGTERM (exit 0)** to every pod on the node every ~74 s.

It is **not** a bug in the DRA driver, the pod manifest, or the benchmark
harness — the driver's `main()` correctly blocks on `<-sigc` and only exits when
it is signalled.

## Diagnosis (run on the worker)

```bash
# Which containerd is actually running vs installed?
which -a containerd
systemctl show -p ExecStart containerd | grep -o '/[^ ;]*containerd'
/usr/bin/containerd --version        2>/dev/null   # stock (e.g. v2.2.4) if present
/usr/local/bin/containerd --version                # RT fork (e.g. v1.7.19-…)

# Stock packages present?
dpkg -l | grep -iE 'containerd|docker'

# cgroup driver mismatch?
sudo grep -i cgroupDriver /var/lib/kubelet/config.yaml          # systemd
sudo grep -iE 'SystemdCgroup' /etc/containerd/config.toml       # false => mismatch
```

If `ExecStart` points at `/usr/bin/containerd` and/or `SystemdCgroup = false`,
apply the fix below.

## Fix (run on the worker)

```bash
# 1. Stop services
sudo systemctl stop kubelet containerd docker 2>/dev/null

# 2. Purge stock Docker + containerd.io (the shadowing packages)
sudo apt-get purge -y docker-ce docker-ce-cli docker-ce-rootless-extras \
  docker-buildx-plugin docker-compose-plugin containerd.io
sudo apt-get autoremove -y

# 3. Remove stock binaries + stock unit so nothing shadows the RT build
sudo rm -f /usr/bin/containerd /usr/bin/containerd-shim* /usr/sbin/runc
sudo rm -f /lib/systemd/system/containerd.service

# 4. Confirm the RT binary is now the only containerd
which -a containerd
/usr/local/bin/containerd --version          # expect v1.7.19-…RT
ls -l /usr/local/sbin/runc                   # RT runc must exist

# 5. Recreate the RT systemd unit (points at /usr/local/bin/containerd)
sudo tee /etc/systemd/system/containerd.service >/dev/null <<'EOF'
[Unit]
Description=containerd container runtime (RT build)
Documentation=https://containerd.io
After=network.target local-fs.target

[Service]
ExecStartPre=-/sbin/modprobe overlay
ExecStart=/usr/local/bin/containerd
Type=notify
Delegate=yes
KillMode=process
Restart=always
RestartSec=5
LimitNPROC=infinity
LimitCORE=infinity
LimitNOFILE=1048576
TasksMax=infinity
OOMScoreAdjust=-999

[Install]
WantedBy=multi-user.target
EOF

# 6. Regenerate config.toml with the RT binary and re-apply the required patches
sudo install -d -m 0755 /etc/containerd
sudo /usr/local/bin/containerd config default | sudo tee /etc/containerd/config.toml >/dev/null
sudo sed -i 's|SystemdCgroup = false|SystemdCgroup = true|'            /etc/containerd/config.toml
sudo sed -i 's|BinaryName = ""|BinaryName = "/usr/local/sbin/runc"|'   /etc/containerd/config.toml
sudo sed -i 's|enable_cdi = false|enable_cdi = true|'                  /etc/containerd/config.toml
grep -q 'cdi_spec_dirs' /etc/containerd/config.toml || \
  sudo sed -i 's|enable_cdi = true|enable_cdi = true\n    cdi_spec_dirs = ["/etc/cdi", "/var/run/cdi"]|' /etc/containerd/config.toml

# 7. Verify all four settings
sudo grep -iE 'SystemdCgroup|BinaryName|enable_cdi|cdi_spec_dirs' /etc/containerd/config.toml
# expect:
#   enable_cdi = true
#   cdi_spec_dirs = ["/etc/cdi", "/var/run/cdi"]
#   BinaryName = "/usr/local/sbin/runc"
#   SystemdCgroup = true

# 8. Start the RT runtime
sudo systemctl daemon-reload
sudo systemctl enable --now containerd
sudo systemctl restart kubelet
systemctl show -p ExecStart containerd | grep -o '/[^ ;]*containerd'   # /usr/local/bin/containerd
```

> Note: containerd 1.7.x already ships an `enable_cdi = false` key, so it must be
> `sed`-flipped to `true` (a naive "insert if absent" will skip it).
> Purging `containerd.io` removes `/etc/containerd/`, so step 6 re-creates it.

## Verify the fix

```bash
# From the control-plane: worker must report the RT fork, not stock 2.2.4
kubectl get nodes -o wide
#   rt-cluster-worker-0 … containerd://1.7.19-27-g2c5bb9047

# Restart counters must FREEZE (the "Xm ago" keeps growing, count stays put)
kubectl get pods -A -o wide | grep rt-cluster-worker-0
```

Success = the worker runtime shows `1.7.19-…` and both
`dra-rt-driver-kubeletplugin` and `kube-proxy` stay `1/1 Running` with
non-increasing restart counts for 5+ minutes.

## Prevention

- Do **not** install Docker / `containerd.io` on RT nodes — they ship a stock
  containerd + systemd unit that shadow the RT build at `/usr/local/bin`.
- The provisioning script
  [`common.sh`](common.sh) already purges these and installs the RT build; make
  sure nothing re-installs Docker afterwards.
- Quick post-provision check on every worker:

  ```bash
  systemctl show -p ExecStart containerd | grep -q '/usr/local/bin/containerd' \
    && echo "OK: RT containerd active" || echo "BAD: stock containerd shadowing RT build"
  ```

## Key facts

- Control-plane and workers **do not** need the same containerd version.
- Workers **must** run the RT-patched containerd + runc (they write
  `cpu.rt_multi_runtime_us`); stock containerd lacks RT cgroup support.
- `cgroupDriver` (kubelet) and `SystemdCgroup` (containerd) **must** agree —
  both `systemd` here.
