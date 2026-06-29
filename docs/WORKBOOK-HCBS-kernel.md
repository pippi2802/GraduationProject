# HCBS RT Kernel — Installation & Troubleshooting Workbook

> Scope: building, installing, capturing, and debugging the **HCBS-patched real-time
> kernel** that provides RT group scheduling (`cpu.rt_runtime_us`, `cpu.rt_period_us`,
> and the custom `cpu.rt_multi_runtime_us`) required by the RT-DRA driver.
>
> HCBS = **Hierarchical Constant Bandwidth Server** — the scheduling mechanism KubeDeadline
> relies on for RT bandwidth enforcement.

---

## 0. TL;DR — what "working" looks like
On the worker, after booting the HCBS kernel on **cgroup v2**:
```bash
uname -r                                   # 6.16.0-rc4+  (or your built version)
stat -f -c %T /sys/fs/cgroup               # cgroup2fs
cat /sys/fs/cgroup/cpu.rt_runtime_us       # 950000 (root pool)
cat /sys/fs/cgroup/cpu.rt_period_us        # 1000000
# child cgroups expose all three RT files once cpu is delegated:
cat /sys/fs/cgroup/kubepods.slice/cpu.rt_multi_runtime_us   # e.g. "0 0 0 0" (4 CPUs)
grep CONFIG_RT_GROUP_SCHED /boot/config-$(uname -r)         # =y
```

---

## 1. Requirements

### Build host (separate VM — do NOT build on the worker)
- Ubuntu 24.04, plenty of CPU/RAM/disk (kernel build is heavy).
- Build VM used in this project: `rt-VM220-1406`.
- HCBS patch source tree: `~/HCBS-patch` (kernel base `6.16.0-rc4`).

### Build dependencies
```bash
sudo apt update
sudo apt install -y build-essential flex bison libssl-dev libelf-dev bc \
    dwarves rsync kmod cpio debhelper libdw-dev
```
> Missing `debhelper` / `libdw-dev` is a common failure (`bindeb-pkg` errors). Install both.

### Target node requirements
- Azure Gen2 VM, **TrustedLaunch with secure boot OFF** (unsigned kernel must boot).
  - In `rt-cluster/modules/vm.bicep`: `secure_boot_enabled = false`.
- Boot on **cgroup v2** (default). Do NOT set `systemd.unified_cgroup_hierarchy=0`.

---

## 2. Build the HCBS kernel with RT group scheduling

```bash
cd ~/HCBS-patch                     # the HCBS-patched kernel source tree

# Start from the running kernel's config
cp /boot/config-$(uname -r) .config

# CRITICAL: enable RT group scheduling (compile-time only — cannot be toggled at runtime)
scripts/config --enable CONFIG_RT_GROUP_SCHED
# Ensure it is active by default (not disabled):
scripts/config --disable CONFIG_RT_GROUP_SCHED_DEFAULT_DISABLED

# CRITICAL: disable signing / trusted-key options. The stock Ubuntu .config points at
# Canonical signing certs (canonical-certs.pem) that do NOT exist on the build VM, so the
# build fails with "No rule to make target 'debian/canonical-certs.pem'".
scripts/config --disable SYSTEM_TRUSTED_KEYS
scripts/config --disable SYSTEM_REVOCATION_KEYS
scripts/config --disable MODULE_SIG_KEY       # only if it also points at a missing key

# Resolve remaining symbols non-interactively
make olddefconfig

# Confirm the signing keys are now empty (and RT flag is on)
grep -E 'SYSTEM_TRUSTED_KEYS|SYSTEM_REVOCATION_KEYS|RT_GROUP_SCHED' .config
#   CONFIG_SYSTEM_TRUSTED_KEYS=""
#   CONFIG_SYSTEM_REVOCATION_KEYS=""
#   CONFIG_RT_GROUP_SCHED=y
# Safe here because secure boot is OFF on the worker -> unsigned kernel+modules boot fine.

# Confirm the flags stuck BEFORE building
grep -E 'CONFIG_RT_GROUP_SCHED|RT_GROUP_SCHED_DEFAULT_DISABLED' .config
#   CONFIG_RT_GROUP_SCHED=y
#   # CONFIG_RT_GROUP_SCHED_DEFAULT_DISABLED is not set

# Build Debian packages (parallel)
make -j"$(nproc)" bindeb-pkg
```
Output `.deb` files land in the **parent** directory (`~/`):
`linux-image-*.deb`, `linux-headers-*.deb`.

### Install on the build VM (to capture as image)
```bash
sudo dpkg -i ../linux-image-*.deb ../linux-headers-*.deb
sudo reboot
# after reboot:
uname -r
grep CONFIG_RT_GROUP_SCHED /boot/config-$(uname -r)   # =y
```

---

## 3. Capture the Azure image (so workers boot this kernel)

- Gallery: `rtUbuntu`  | Image definition: `rtUbuntu24.04` (Gen2, TrustedLaunch,
  secure boot off).
- After installing the kernel + deps on the build VM, generalize and capture a **new image
  version**, then point the worker VM (in `rt-cluster/`) at that version and redeploy.
- See `rt-cluster/README.md` + `image-builder-packer/README.md` for the gallery/capture flow.

### 3a. Pre-flight — confirm the new kernel is the default boot entry
Do this BEFORE generalizing (you should not log back in afterwards):
```bash
uname -r                                   # currently-booted = the new HCBS kernel
grep CONFIG_RT_GROUP_SCHED /boot/config-$(uname -r)   # =y
sudo update-grub                           # ensure GRUB lists the new kernel first/default
```

### 3b. Inside the VM — deprovision with waagent (generalize step 1)
Removes machine-specific state (SSH host keys, the user account, hostname, leases) so the
image is reusable. `+user` also deletes the current login user (e.g. `azureuser`) — expected;
the new VM gets a fresh user at deploy time.
```bash
sudo waagent -deprovision+user -force
exit                                       # close SSH immediately; do NOT run more commands
```
> Generalizing is **one-way** — the build VM is unusable afterwards. Snapshot its OS disk
> first, or keep a separate untouched build VM, if you want to keep building.

### 3c. From Azure CLI (local) — deallocate, generalize, capture (step 2)
```powershell
$RG      = "<your-resource-group>"
$VM      = "rt-VM220-1406"
$GAL     = "rtUbuntu"
$IMGDEF  = "rtUbuntu24.04"
$VERSION = "1.0.$(Get-Date -Format yyyyMMdd)"        # e.g. 1.0.20260622

az vm deallocate  --resource-group $RG --name $VM
az vm generalize  --resource-group $RG --name $VM

az sig image-version create `
  --resource-group $RG `
  --gallery-name $GAL `
  --gallery-image-definition $IMGDEF `
  --gallery-image-version $VERSION `
  --virtual-machine $(az vm show -g $RG -n $VM --query id -o tsv)
```
> If `--virtual-machine` isn't supported on your CLI version, use
> `--managed-image $(az vm show -g $RG -n $VM --query id -o tsv)` instead.

### 3d. Point the worker at the new image version and redeploy
Update the gallery image version referenced in `rt-cluster/` (Bicep/params), then redeploy
the worker VM so it boots from the new HCBS image.

> **Lesson:** re-imaging the worker WIPES `/etc/cni/net.d` and Calico state → node goes
> NotReady until Calico is reinstalled. (See RT-DRA workbook §Troubleshooting / Calico.)

---

## 4. Verify the kernel on the worker

```bash
# 1. Right kernel booted
uname -r

# 2. cgroup v2 active
stat -f -c %T /sys/fs/cgroup            # must be cgroup2fs

# 3. RT group sched compiled in
grep CONFIG_RT_GROUP_SCHED /boot/config-$(uname -r)   # =y

# 4. RT files present at the root pool
cat /sys/fs/cgroup/cpu.rt_runtime_us /sys/fs/cgroup/cpu.rt_period_us

# 5. Custom HCBS per-CPU file on a child slice (one value per CPU)
cat /sys/fs/cgroup/kubepods.slice/cpu.rt_multi_runtime_us   # "0 0 0 0" on 4 vCPU
```

### cgroup-v2 architecture facts (important)
- On v2 the root `cpu.rt_*` files appear only when the **`cpu` controller** is in
  `/sys/fs/cgroup/cgroup.controllers` and enabled in `cgroup.subtree_control`.
- A child cgroup gets RT files only after `cpu` is delegated:
  `echo +cpu > /sys/fs/cgroup/<parent>/cgroup.subtree_control`.
- `cpu.rt_multi_runtime_us` format = **space-separated per-CPU runtime values**
  (e.g. `0 0 0 0` for 4 CPUs). This is a custom HCBS file, not in mainline.
- **Root** pool has only `rt_runtime_us` / `rt_period_us` (no multi file). **Children**
  have all three. Children start at `0` and must be allocated budget.

---

## 5. Troubleshooting matrix

| Symptom | Likely cause | Fix |
|---|---|---|
| `cpu.rt_*` files missing entirely | kernel lacks `CONFIG_RT_GROUP_SCHED` | rebuild with the flag (§2); it's compile-time only |
| `cpu.rt_*` missing on a child slice only | `cpu` controller not delegated | `echo +cpu > <parent>/cgroup.subtree_control` |
| `/sys/fs/cgroup` is `tmpfs`/v1, no `cpu.rt_multi_runtime_us` | booted cgroup **v1** (stale GRUB flag) | remove `systemd.unified_cgroup_hierarchy=0` from `/etc/default/grub`, `update-grub`, reboot |
| `bindeb-pkg` fails (`debhelper-compat`, `dwz`/`libdw`) | build deps missing | `sudo apt install -y debhelper libdw-dev` (and §1 list) |
| Build fails: `No rule to make target 'debian/canonical-certs.pem'` (or `*.pem ... No such file`) | stock `.config` references Canonical signing/trusted-key certs absent on build VM | `scripts/config --disable SYSTEM_TRUSTED_KEYS; scripts/config --disable SYSTEM_REVOCATION_KEYS; scripts/config --disable MODULE_SIG_KEY; make olddefconfig` (secure boot off → unsigned OK) |
| Kernel won't boot on Azure | secure boot rejects unsigned kernel | set `secure_boot_enabled=false` in `modules/vm.bicep`, redeploy |
| New kernel boots but RT writes don't take | **kernel/userspace ABI drift** — HCBS file semantics differ between kernel versions | match the kernel version that RT-runc/driver were validated against (see Known Issue) |
| Worker `NotReady` after re-image | re-image wiped CNI | reinstall Calico (RT-DRA workbook) |

### Remove a stale cgroup-v1 GRUB flag (frequent issue)
```bash
sudo sed -i 's/ *systemd.unified_cgroup_hierarchy=0//' /etc/default/grub
sudo update-grub
sudo reboot
stat -f -c %T /sys/fs/cgroup     # cgroup2fs
```

---

## 6. KNOWN OPEN ISSUE (as of 2026-06-15) — enforcement not yet active

- **Confirmed with the HCBS authors:** the original rt-DRA was validated on
  **cgroup v1 + an older kernel**. Our environment is **cgroup v2 + kernel 6.16.0-rc4+**.
- Consequence: although the kernel **exposes** `cpu.rt_multi_runtime_us` on v2, the RT-runc
  leaf write does not produce a usable RT budget in the container cgroup
  (`cpu.rt_multi_runtime_us = 0 0 0 0` inside the pod → `chrt -f` denied).
- This is a **version/cgroup-mode mismatch**, not a kernel build error. Two paths:
  1. **Reproduce on the authors' exact kernel + cgroup v1** to get a green baseline.
  2. **Port** the driver/RT-runc to cgroup v2 + the newer kernel (larger effort).
- **Questions to resolve with the authors:** exact validated kernel version + HCBS patch
  commit; expected format/semantics of `cpu.rt_multi_runtime_us` on their kernel; whether a
  v2 branch exists.

---

## 7. Reference commands cheat-sheet
```bash
# What CPU/util does the root pool advertise?
cat /sys/fs/cgroup/cpu.rt_runtime_us            # 950000
cat /sys/fs/cgroup/cpu.rt_period_us             # 1000000

# Inspect the full pod->container chain budget (run on worker)
for d in /sys/fs/cgroup \
         /sys/fs/cgroup/kubepods.slice \
         /sys/fs/cgroup/kubepods.slice/kubepods-besteffort.slice; do
  echo "== $d =="
  cat "$d/cpu.rt_runtime_us" "$d/cpu.rt_period_us" "$d/cpu.rt_multi_runtime_us" 2>/dev/null
done
```
