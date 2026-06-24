package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	drapbv1 "k8s.io/kubelet/pkg/apis/dra/v1alpha3"

	nascrd "github.com/nasim-samimi/dra-rt-driver/api/example.com/resource/rt/nas/v1alpha1"
)

const (
	cgroupV2Root  = "/sys/fs/cgroup"
	rtPeriodFile  = "cpu.rt_period_us"
	rtRuntimeFile = "cpu.rt_runtime_us"

	// Generous RT reservation seeded into the shared parent slices (root,
	// kubepods.slice, QoS slices). 0.95 matches the kernel default RT
	// throttling ratio; the controller's worst-fit allocator guarantees the
	// sum of the per-claim reservations stays within node capacity, so the
	// shared parents only need to act as a roomy container.
	parentPeriodUs  = 1000000
	parentRuntimeUs = 950000
)

// seedRtCgroup writes cpu.rt_period_us THEN cpu.rt_runtime_us for a single
// cgroup-v2 slice.
//
// On the HCBS RT_GROUP_SCHED kernel a freshly created child slice defaults to
// cpu.rt_period_us = 0. Writing a non-zero runtime into a slice whose period is
// zero is rejected with EINVAL (runtime/0 is undefined), so the period MUST be
// written before the runtime. This ordering — not any kernel-branch
// difference — is what makes the RT budget admissible.
func seedRtCgroup(dir string, periodUs, runtimeUs int) error {
	periodPath := filepath.Join(dir, rtPeriodFile)
	runtimePath := filepath.Join(dir, rtRuntimeFile)
	if err := os.WriteFile(periodPath, []byte(strconv.Itoa(periodUs)), 0644); err != nil {
		return fmt.Errorf("writing %s: %w", periodPath, err)
	}
	if err := os.WriteFile(runtimePath, []byte(strconv.Itoa(runtimeUs)), 0644); err != nil {
		return fmt.Errorf("writing %s: %w", runtimePath, err)
	}
	return nil
}

// hasRtInterface reports whether a cgroup dir exists and exposes the RT files.
func hasRtInterface(dir string) bool {
	_, err := os.Stat(filepath.Join(dir, rtPeriodFile))
	return err == nil
}

// podSliceDir builds the cgroup-v2 pod slice path for a pod UID under the given
// QoS parent, using systemd slice naming (dashes in the UID become underscores,
// e.g. kubepods-besteffort-pod<uid>.slice).
func podSliceDir(parent, qosInfix, podUID string) string {
	uid := strings.ReplaceAll(podUID, "-", "_")
	return filepath.Join(parent, fmt.Sprintf("kubepods-%spod%s.slice", qosInfix, uid))
}

// UpdateParentCgroup seeds RT bandwidth down the cgroup-v2 slice tree so that
// the container leaf budget (written by RT-runc from the injected CDI env) is
// admitted by the kernel.
//
// RT_GROUP_SCHED bandwidth is hierarchical: a leaf can only receive budget if
// every ancestor already has budget, and each slice must have its period set
// before its runtime. The shared parents (root, kubepods.slice and the QoS
// slices) get a generous fixed reservation; the per-pod slice gets the claim's
// own runtime/period so multiple pods are accounted accurately against the QoS
// parent. The container leaf itself is written by RT-runc.
func UpdateParentCgroup(claim *drapbv1.Claim, crd nascrd.NodeAllocationStateSpec) error {
	alloc, ok := crd.AllocatedClaims[claim.Uid]
	if !ok || alloc.RtCpu == nil {
		return fmt.Errorf("claim %q has no RtCpu allocation", claim.Uid)
	}

	kubepods := filepath.Join(cgroupV2Root, "kubepods.slice")
	besteffort := filepath.Join(kubepods, "kubepods-besteffort.slice")
	burstable := filepath.Join(kubepods, "kubepods-burstable.slice")

	// 1. Shared parents, top-down, period-before-runtime. root + kubepods.slice
	//    are always present; the QoS slices only exist once a pod of that class
	//    is scheduled, so they are seeded only when present.
	for _, dir := range []string{cgroupV2Root, kubepods} {
		if err := seedRtCgroup(dir, parentPeriodUs, parentRuntimeUs); err != nil {
			return fmt.Errorf("seeding parent %s: %w", dir, err)
		}
		rtlog("UpdateParentCgroup claim=%s seeded parent=%s period=%d runtime=%d", claim.Uid, dir, parentPeriodUs, parentRuntimeUs)
	}
	for _, dir := range []string{besteffort, burstable} {
		if !hasRtInterface(dir) {
			continue
		}
		if err := seedRtCgroup(dir, parentPeriodUs, parentRuntimeUs); err != nil {
			return fmt.Errorf("seeding QoS parent %s: %w", dir, err)
		}
		rtlog("UpdateParentCgroup claim=%s seeded qos=%s period=%d runtime=%d", claim.Uid, dir, parentPeriodUs, parentRuntimeUs)
	}

	// 2. Per-pod slice gets the claim's own reservation. It may not exist yet at
	//    prepare time (the kubelet creates it around sandbox setup), so the
	//    first present QoS variant is seeded and the rest skipped. If none is
	//    present yet the parents are still seeded and the leaf admission is
	//    covered once RT-runc creates the slice tree.
	podUID := alloc.RtCpu.CgroupUID
	if podUID == "" || len(alloc.RtCpu.Cpuset) == 0 {
		rtlog("UpdateParentCgroup claim=%s missing CgroupUID/cpuset -> pod-slice seed skipped", claim.Uid)
		return nil
	}
	periodUs := alloc.RtCpu.Cpuset[0].Period
	runtimeUs := alloc.RtCpu.Cpuset[0].Runtime
	candidates := []string{
		podSliceDir(besteffort, "besteffort-", podUID),
		podSliceDir(burstable, "burstable-", podUID),
		podSliceDir(kubepods, "", podUID),
	}
	for _, dir := range candidates {
		if !hasRtInterface(dir) {
			continue
		}
		if err := seedRtCgroup(dir, periodUs, runtimeUs); err != nil {
			return fmt.Errorf("seeding pod slice %s: %w", dir, err)
		}
		rtlog("UpdateParentCgroup claim=%s seeded podslice=%s period=%d runtime=%d", claim.Uid, dir, periodUs, runtimeUs)
		return nil
	}
	rtlog("UpdateParentCgroup claim=%s pod slice not present yet (uid=%s) -> parents seeded, leaf deferred to RT-runc", claim.Uid, podUID)
	return nil
}
