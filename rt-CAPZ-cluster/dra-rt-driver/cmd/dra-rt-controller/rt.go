/*
 * Copyright 2023 The Kubernetes Authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package main

import (
	"fmt"
	"sort"
	"strconv"
	"sync"

	nascrd "github.com/nasim-samimi/dra-rt-driver/api/example.com/resource/rt/nas/v1alpha1"

	corev1 "k8s.io/api/core/v1"
	resourcev1 "k8s.io/api/resource/v1alpha2"
	"k8s.io/dynamic-resource-allocation/controller"

	rtcrd "github.com/nasim-samimi/dra-rt-driver/api/example.com/resource/rt/v1alpha1"
)

type rtdriver struct {
	PendingAllocatedClaims *PerNodeAllocatedClaims
}

func NewRtDriver() *rtdriver {
	return &rtdriver{
		PendingAllocatedClaims: NewPerNodeAllocatedClaims(),
	}
}

func (g *rtdriver) ValidateClaimParameters(claimParams *rtcrd.RtClaimParametersSpec) error {
	if claimParams.Count < 1 {
		return fmt.Errorf("invalid number of HCBS requested: %v", claimParams.Count)
	}
	// TODO: add more validation
	return nil
}

func (g *rtdriver) Allocate(crd *nascrd.NodeAllocationState, claim *resourcev1.ResourceClaim, claimParams *rtcrd.RtClaimParametersSpec, class *resourcev1.ResourceClass, classParams *rtcrd.DeviceClassParametersSpec, selectedNode string) (OnSuccessCallback, error) {
	claimUID := string(claim.UID)

	if !g.PendingAllocatedClaims.Exists(claimUID, selectedNode) {
		return nil, fmt.Errorf("no allocations generated for claim '%v' on node '%v' yet", claim.UID, selectedNode)
	}
	fmt.Println("/////////////////////////////////////////ALLOCATE/////////////////////////////////////////////////////////////")
	fmt.Println("Allocate, crd.Spec.AllocatedUtilToCpu before getting value from pending:", crd.Spec.AllocatedUtilToCpu)
	if _, exists := crd.Spec.AllocatedClaims[claimUID]; exists {
		fmt.Println("Allocate, the claim is already allocated:", crd.Spec.AllocatedClaims[claimUID].RtCpu.Cpuset)
		return nil, nil
	}
	crd.Spec.AllocatedClaims[claimUID] = g.PendingAllocatedClaims.Get(claimUID, selectedNode)
	fmt.Println("selected node is:", selectedNode)
	crd.SetUtilisation(crd.Spec.AllocatedClaims[claimUID], claimUID)
	fmt.Println("Allocate, crd.Spec.AllocatedClaims:", crd.Spec.AllocatedClaims)
	fmt.Println("Allocate, crd.Spec.AllocatedUtilToCpu after setutilisation:", crd.Spec.AllocatedUtilToCpu)
	fmt.Println("//////////////////////////////////////////////////////////////////////////////////////////////////////")
	// for nodes, _ := range g.PendingAllocatedClaims.utilisation {
	// 	fmt.Println("Allocate, pending claims after set:", nodes, g.PendingAllocatedClaims.allocations[claimUID][nodes].RtCpu.Cpuset)
	// }
	onSuccess := func() {
		// g.PendingAllocatedClaims.RemoveUtil(claimUID)
		g.PendingAllocatedClaims.RemoveUtilOtherNodes(claimUID, selectedNode)
		// for nodes, _ := range g.PendingAllocatedClaims.utilisation {
		// 	fmt.Println("Allocate, pending claims after remove:", nodes, g.PendingAllocatedClaims.allocations[claimUID][nodes].RtCpu.Cpuset)
		// }
		g.PendingAllocatedClaims.Remove(claimUID)
	}

	return onSuccess, nil
}

func (g *rtdriver) Deallocate(crd *nascrd.NodeAllocationState, claim *resourcev1.ResourceClaim, selectedNode string) error {
	claimUID := string(claim.UID)
	fmt.Println(" before Deallocate(rtdriver), crd.Spec.AllocatedClaims:", crd.Spec.AllocatedClaims)
	fmt.Println(" before Deallocate, g.PendingAllocatedClaims:", g.PendingAllocatedClaims)
	g.PendingAllocatedClaims.RemoveUtil(claimUID)
	// crd.Spec.AllocatedUtilToCpu = g.PendingAllocatedClaims.GetUtil(selectedNode)
	g.PendingAllocatedClaims.Remove(claimUID)
	fmt.Println(" after Deallocate, crd.Spec.AllocatedClaims:", crd.Spec.AllocatedClaims)
	fmt.Println(" after Deallocate, g.PendingAllocatedClaims:", g.PendingAllocatedClaims)
	return nil
}

var utilLock sync.Mutex

func (rt *rtdriver) UnsuitableNode(crd *nascrd.NodeAllocationState, pod *corev1.Pod, rtcas []*controller.ClaimAllocation, allcas []*controller.ClaimAllocation, potentialNode string) error {
	rt.PendingAllocatedClaims.VisitNode(potentialNode, func(claimUID string, allocation nascrd.AllocatedCpuset, utilisation nascrd.AllocatedUtilset) {
		if _, exists := crd.Spec.AllocatedClaims[claimUID]; exists {
			fmt.Println("////////////////////////////////////////////UNSUITABLENODE//////////////////////////////////////////////////////////")
			fmt.Println("unsuitableNode, the claim:", claimUID, " is already allocated while visiting the node:", potentialNode)
			rt.PendingAllocatedClaims.Remove(claimUID)
		} else {
			crd.Spec.AllocatedClaims[claimUID] = allocation
			// crd.Spec.AllocatedUtilToCpu = utilisation
			crd.SetUtilisation(allocation, claimUID)
			fmt.Println("on node:", potentialNode, "the allocated utils are:", crd.Spec.AllocatedUtilToCpu)
		}
	})

	fmt.Println("////////////////////////////////////////////STILLUNSUITABLENODE//////////////////////////////////////////////////////////")
	fmt.Println("let's check the allocated claims and utilisation after visiting the node:", potentialNode, crd.Spec.AllocatedClaims, crd.Spec.AllocatedUtilToCpu)
	// utilLock.Lock() // Lock to prevent race condition
	// defer utilLock.Unlock()
	cgroupUID := string(pod.UID)

	allocated, _ := rt.allocate(crd, pod, rtcas, allcas, potentialNode)
	util := make(map[string]nascrd.AllocatedUtil)
	for id, cpu := range crd.Spec.AllocatedUtilToCpu.Cpus {
		util[id] = nascrd.AllocatedUtil{
			Util: cpu.Util,
		}
	}
	fmt.Println("get utilisation from pending:", util)
	for _, ca := range rtcas {
		claimUID := string(ca.Claim.UID)
		if _, exists := crd.Spec.AllocatedClaims[claimUID]; exists {
			fmt.Println("unsuitableNode, the claim is already allocated:", claimUID)
			continue
		}

		fmt.Println("unsuitableNode, claimUID:", claimUID)
		claimParams, _ := ca.ClaimParameters.(*rtcrd.RtClaimParametersSpec)
		if claimParams.Count != len(allocated[claimUID]) {
			for _, ca := range allcas {
				ca.UnsuitableNodes = append(ca.UnsuitableNodes, potentialNode)
			}
			return nil
		} // it puts everything on only one node
		claimUtil := (claimParams.Runtime * 1000 / claimParams.Period)
		var devices []nascrd.AllocatedCpu
		for _, cpu := range allocated[claimUID] {
			device := cpu
			devices = append(devices, device)
		}

		allocatedDevices := nascrd.AllocatedCpuset{
			RtCpu: &nascrd.AllocatedRtCpu{
				Cpuset:    devices,
				CgroupUID: cgroupUID,
			},
		}
		for _, allocatedCpu := range devices {
			util[strconv.Itoa(allocatedCpu.ID)] = nascrd.AllocatedUtil{
				Util: util[strconv.Itoa(allocatedCpu.ID)].Util + claimUtil,
			}
		}
		fmt.Println("show allocated devices and the new utilisation:", devices, util)

		rt.PendingAllocatedClaims.Set(claimUID, potentialNode, allocatedDevices)
		fmt.Println("unsuitableNode, pending claims after set:", rt.PendingAllocatedClaims.allocations)
		fmt.Println("unsuitableNode, crd.Spec.AllocatedClaims:", crd.Spec.AllocatedClaims)

	}
	allocatedUtilisations := nascrd.AllocatedUtilset{
		Cpus: util,
	}
	rt.PendingAllocatedClaims.SetUtil(potentialNode, allocatedUtilisations)
	fmt.Println("unsuitableNode, pending utils after set util:", rt.PendingAllocatedClaims.utilisation)
	fmt.Println("unsuitableNode, crd.Spec.AllocatedUtilToCpu:", crd.Spec.AllocatedUtilToCpu)
	fmt.Println("////////////////////////////////////////////ENDUNSUITABLENODE//////////////////////////////////////////////////////////")

	return nil
}

func (rt *rtdriver) allocate(crd *nascrd.NodeAllocationState, pod *corev1.Pod, cpucas []*controller.ClaimAllocation, allcas []*controller.ClaimAllocation, node string) (map[string][]nascrd.AllocatedCpu, map[string]nascrd.AllocatedUtil) {
	available := make(map[int]*nascrd.AllocatableCpu)
	// util := crd.Spec.AllocatedUtilToCpu.Cpus
	util := make(map[string]nascrd.AllocatedUtil)
	fmt.Println("/////////////////////////////////////////////////allocate/////////////////////////////////////////////////////")
	for id, cpu := range crd.Spec.AllocatedUtilToCpu.Cpus {
		util[id] = nascrd.AllocatedUtil{
			Util: cpu.Util,
		}
	}
	allocated := make(map[string][]nascrd.AllocatedCpu)

	for _, device := range crd.Spec.AllocatableCpuset {
		switch device.Type() {
		case nascrd.RtCpuType:
			available[device.RtCpu.ID] = device.RtCpu
		default:
			// skip other devices
		}
	}

	for _, ca := range cpucas {
		claimUID := string(ca.Claim.UID)
		fmt.Println("allocate, claimUID:", claimUID)
		if _, exists := crd.Spec.AllocatedClaims[claimUID]; exists {
			devices := crd.Spec.AllocatedClaims[claimUID].RtCpu.Cpuset
			for _, device := range devices {
				allocated[claimUID] = append(allocated[claimUID], device)
			}
			fmt.Println("the claim is already allocated and its devices are:", devices)

			continue
		}

		claimParams, _ := ca.ClaimParameters.(*rtcrd.RtClaimParametersSpec)
		claimUtil := (claimParams.Runtime * 1000 / claimParams.Period)
		var devices []nascrd.AllocatedCpu
		worstFitCpus, err := cpuPartitioning(util, claimUtil, claimParams.Count, "worstFit") //must get the policy from the user
		if err != nil {
			return nil, nil
		}
		fmt.Println("worstFitCpus:", worstFitCpus)
		for i := 0; i < claimParams.Count; i++ {
			// for _, device := range available {

			worstFitCpusStr, _ := strconv.Atoi(worstFitCpus[i])
			d := nascrd.AllocatedCpu{
				ID:      worstFitCpusStr,
				Runtime: claimParams.Runtime,
				Period:  claimParams.Period,
			}
			util[strconv.Itoa(d.ID)] = nascrd.AllocatedUtil{
				Util: util[strconv.Itoa(d.ID)].Util + claimUtil,
			}
			if util[strconv.Itoa(d.ID)].Util > 950 {
				delete(available, d.ID)
			}
			devices = append(devices, d)
		}
		allocated[claimUID] = devices
		fmt.Println("allocate, allocated:", allocated)

	}
	fmt.Println("it picked the worstfit cpus for the claim and the utils are:", util)
	fmt.Println("/////////////////////////////////////////////endallocate////////////////////////////////////////////////////////")

	return allocated, util
}

func cpuPartitioning(spec map[string]nascrd.AllocatedUtil, reqUtil int, reqCpus int, policy string) ([]string, error) {
	type scoredCpu struct {
		cpu   string
		score int
	}
	var scoredCpus []scoredCpu
	for id, cpuinfo := range spec {
		score := 950 - cpuinfo.Util - reqUtil //TODO: make the threshold a parameter
		if score > 0 {
			scoredCpus = append(scoredCpus, scoredCpu{
				cpu:   id,
				score: score,
			})
		}
	}

	if int(len(scoredCpus)) < reqCpus {
		return nil, fmt.Errorf("not enough cpus to allocate")
	}
	switch policy {
	case "worstFit":
		sort.SliceStable(scoredCpus, func(i, j int) bool {
			if scoredCpus[i].score > scoredCpus[j].score {
				return true
			}
			return false
		})
	case "bestFit":
		sort.SliceStable(scoredCpus, func(i, j int) bool {
			if scoredCpus[i].score < scoredCpus[j].score {
				return true
			}
			return false
		})
	default:
		sort.SliceStable(scoredCpus, func(i, j int) bool {
			if scoredCpus[i].score > scoredCpus[j].score {
				return true
			}
			return false
		}) //default is worstFit
	}

	var fittingCpus []string
	for i := int(0); i < reqCpus; i++ {
		fittingCpus = append(fittingCpus, scoredCpus[i].cpu)
	}

	return fittingCpus, nil
}
