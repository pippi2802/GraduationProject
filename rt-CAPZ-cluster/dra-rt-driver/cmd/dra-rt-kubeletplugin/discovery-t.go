package main

import (
	"fmt"

	"github.com/shirou/gopsutil/cpu"
	// v1beta1 "k8s.io/metrics/pkg/apis/metrics/v1alpha2"
)

func enumerateCpusets() (AllocatableRtCpus, error) {

	// var cfg *rest.Config
	// var err error

	// Use in-cluster configuration if running inside a Kubernetes pod
	// cfg, err = rest.InClusterConfig()
	// if err != nil {
	// 	return nil, fmt.Errorf("error building in-cluster config: %v", err)
	// }
	// fmt.Println("cluster config is ready")

	// c, err := kubernetes.NewForConfig(cfg)
	// if err != nil {
	// 	return nil, fmt.Errorf("error building kubernetes client: %v", err)
	// }
	// fmt.Println("kubernetes client is ready")

	// pod_list, e := c.CoreV1().Pods("").List(context.TODO(), metav1.ListOptions{})
	// if e != nil {
	// 	return nil, fmt.Errorf("error listing pods: %v", e)
	// }

	// for i, p := range pod_list.Items {
	// 	fmt.Printf("Pod %d: %s\n", i, p.Name)

	// }
	cpuInfo, err := cpu.Info()
	if err != nil {
		fmt.Printf("Error fetching CPU info: %v\n", err)
	}

	// Print the CPU IDs
	fmt.Println("CPU IDs:")
	for i, ci := range cpuInfo {
		fmt.Printf("CPU %d: %d\n", i, ci.CPU) // ci.CPU gives the CPU ID
	}

	// nodeName := os.Getenv("NODE_NAME")
	// nodes, _ := c.CoreV1().Nodes().List(context.TODO(), metav1.ListOptions{})
	// fmt.Println("nodeNames:", nodes)
	// node, err := c.CoreV1().Nodes().Get(context.TODO(), nodeName, metav1.GetOptions{})

	alldevices := make(AllocatableRtCpus)
	for i, ci := range cpuInfo {
		deviceInfo := &AllocatableCpusetInfo{
			RtCpuInfo: &RtCpuInfo{
				id:   int(ci.CPU),
				util: 0,
			},
		}
		alldevices[i] = deviceInfo
	}
	return alldevices, nil
}
