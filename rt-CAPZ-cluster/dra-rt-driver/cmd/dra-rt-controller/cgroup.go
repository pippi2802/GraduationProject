package main

// func (rt *rtdriver) containerCgroups(podCgroup map[string]nascrd.PodCgroup, allocated []nascrd.AllocatedCpu, podClaimName string, pod *corev1.Pod, claimParams *rtcrd.RtClaimParametersSpec) (map[string]nascrd.ClaimCgroup, error) {

// 	claimRuntime := claimParams.Runtime
// 	claimPeriod := claimParams.Period

// 	// containerCgroup := make(map[string]nascrd.ContainerCgroup)
// 	var builder strings.Builder
// 	fmt.Println("cgroup.go, allocated:", allocated)
// 	for _, allocatedCpu := range allocated {

// 		if builder.Len() > 0 {
// 			builder.WriteString("-") // TODO: change this later to comma
// 		}
// 		builder.WriteString(strconv.Itoa(allocatedCpu.ID))
// 	}
// 	fmt.Println("cgroup.go, builder:", builder.String())
// 	claimCpuset := builder.String()
// 	if claimCpuset == "" {
// 		claimCpuset = "0"
// 	}
// 	cgroup := nascrd.ClaimCgroup{
// 		ContainerRuntime: claimRuntime,
// 		ContainerPeriod:  claimPeriod,
// 		ContainerCpuset:  claimCpuset,
// 	}
// 	containerCgroup := make(map[string]nascrd.ClaimCgroup)
// 	for _, c := range pod.Spec.Containers {
// 		for _, n := range c.Resources.Claims {
// 			if n.Name == podClaimName {
// 				if _, exists := podCgroup[string(pod.UID)].Containers[c.Name]; exists {
// 					fmt.Println("Container already exists:", podCgroup[string(pod.UID)].Containers[c.Name])
// 					containerCgroup[c.Name] = cgroup
// 					return containerCgroup, nil
// 				}
// 				podCgroup[string(pod.UID)].Containers[c.Name] = cgroup
// 				containerCgroup[c.Name] = cgroup
// 				return containerCgroup, nil
// 			}
// 		}
// 	}
// 	podCgroup[string(pod.UID)] = nascrd.PodCgroup{
// 		Containers: podCgroup[string(pod.UID)].Containers,
// 		PodName:    pod.Name,
// 	}

// 	return containerCgroup, nil
// }

// func setPodAnnotations(podCG map[string]nascrd.PodCgroup, pod *corev1.Pod) {
// 	annotations := pod.GetAnnotations()
// 	if pod.GetAnnotations() == nil {
// 		annotations = make(map[string]string)
// 	}
// 	if _, exists := podCG[string(pod.UID)]; exists {
// 		if pod.GetAnnotations()["rtdevice"] == "exists" {
// 			fmt.Println("Pod already exists")
// 			return
// 		}
// 		for c, cg := range podCG[string(pod.UID)].Containers {
// 			runtime := strconv.Itoa(cg.ContainerRuntime)
// 			period := strconv.Itoa(cg.ContainerPeriod)
// 			cpuset := cg.ContainerCpuset
// 			annotations[c+"runtime"] = runtime
// 			annotations[c+"period"] = period
// 			annotations[c+"cpus"] = cpuset
// 			annotations["rtdevice"] = "exists"
// 		}

// 	} else {
// 		return
// 	}

// 	// pod.SetAnnotations(annotations)

// 	return
// }

// func setClaimAnnotations(containerCG map[string]nascrd.ClaimCgroup, pod *corev1.Pod, claim *resourcev1.ResourceClaim) {

// 	if containerCG == nil {
// 		return
// 	}
// 	if claim.GetAnnotations()["rtdevice"] == "exists" {
// 		fmt.Println("Claim already exists")
// 		return
// 	}
// 	annotations := make(map[string]string)
// 	for c, cg := range containerCG {
// 		runtime := strconv.Itoa(cg.ContainerRuntime)
// 		period := strconv.Itoa(cg.ContainerPeriod)
// 		cpuset := cg.ContainerCpuset
// 		annotations[c+"runtime"] = runtime
// 		annotations[c+"period"] = period
// 		annotations[c+"cpus"] = cpuset
// 		annotations["rtdevice"] = "exists"
// 	}
// 	claim.SetAnnotations(annotations)
// 	return
// }

// func (rt *rtdriver) podCgroups(containerCgroups map[string]nascrd.ContainerCgroup, crd *nascrd.NodeAllocationState, pod *corev1.Pod) nascrd.PodCgroup {
// 	// cgroupUID:=cgroupUIDGenerator()
// 	if _, exists := crd.Spec.AllocatedPodCgroups[string(pod.UID)]; exists {
// 		fmt.Println("Pod already exists")
// 		fmt.Println("Pod already exists:", crd.Spec.AllocatedPodCgroups[string(pod.UID)])
// 		return crd.Spec.AllocatedPodCgroups[string(pod.UID)]

// 	}
// 	fmt.Println("in pod cgroups function:", containerCgroups)
// 	if len(containerCgroups) == 0 {
// 		return nascrd.PodCgroup{}
// 	}
// 	return nascrd.PodCgroup{
// 		Containers: containerCgroups,
// 		PodName:    pod.Name,
// 	}
// 	// return nil
// }

//can we have a separate struct for cgroups to keep cgroup data?

// func cgroupUIDGenerator() string {
// 	return uuid.NewString()
// }
