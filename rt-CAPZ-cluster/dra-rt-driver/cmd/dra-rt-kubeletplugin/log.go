package main

import (
	"fmt"

	"k8s.io/klog/v2"
)

// rtlog emits a uniformly-prefixed line so the whole RT-DRA prepare/unprepare
// flow can be followed in the kubeletplugin logs with:
//
//	kubectl -n dra-rt-driver logs ds/dra-rt-driver-kubeletplugin | grep RT-DRA
//
// It deliberately does not change any control flow; it only makes the existing
// behaviour (including the WriteCgroupToCDI -> CreateClaimSpecFile race)
// observable step by step.
func rtlog(format string, args ...interface{}) {
	klog.InfoDepth(1, "[RT-DRA] "+fmt.Sprintf(format, args...))
}
