# node-prep — get the node ready, then isolate it, then harden it

Three steps, in order. Each is independent -- run only as many as you need
for a given round (e.g. `apply` only for a "vanilla" round, all three for
"hardened").

## 1. `apply.sh` — frequency pinning + results access

```bash
bash node-prep/apply.sh model1
```
Pins the CPU governor to `performance`, disables turbo, and mounts the
node's results path so `run_job.sh` can read `jobs.csv` off it. No reboot.

Verify:
```bash
kubectl -n rq1final-model1 exec ds/rq1-agent -- \
  cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor   # -> performance
```

## 2. `isolate.sh` — core isolation (needs a reboot)

```bash
bash node-prep/isolate.sh model1 apply     # stages isolcpus=/nohz_full=/rcu_nocbs=
# reboot the node yourself (Azure Portal / az vm restart / ssh + sudo reboot)
bash node-prep/isolate.sh model1 status    # confirm it actually took effect
```
Removes every logical cpu except cpu0 from the scheduler, stops the
periodic timer tick on them, and moves RCU callbacks off them. cpu0 stays
unisolated on purpose (kubelet/sshd/housekeeping) -- never place the target
there.

To undo: `bash node-prep/isolate.sh model1 restore` (also needs a reboot).

## 3. `harden.sh` — the extra isolation layers

```bash
bash node-prep/harden.sh model1 systemd-contain   # no reboot
bash node-prep/harden.sh model1 irq-steer         # no reboot
bash node-prep/harden.sh model1 boot-params       # stages grub -- reboot after
bash node-prep/harden.sh model1 status            # see current state of all of them
bash node-prep/harden.sh model1 restore-all       # undo everything from this step
```
- **systemd-contain** — clamps `system.slice`/`user.slice` (sshd, containerd,
  any interactive shell) to cpu0 only, hard-enforced by the kernel cgroup
  cpuset even against an explicit `taskset`. Never touches `kubepods.slice`
  -- that's where the target pod lives.
- **irq-steer** — moves every device interrupt onto cpu0, and installs a
  systemd unit so this re-applies on every future boot (interrupt affinity
  resets on its own after every reboot regardless of anything else).
- **boot-params** — adds `mitigations=off transparent_hugepage=never
  rcu_nocb_poll` to the same grub line `isolate.sh` uses. Needs a reboot;
  safe to re-run later if you add more tokens to this list.

Use `node-prep/isolation-audit.sh` (`snapshot <label>` before / after,
`report <a> <b>` to compare) to measure the actual effect of each step, not
just confirm the config changed.
