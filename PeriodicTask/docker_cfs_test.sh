#!/bin/bash
# Docker CFS test - with single core constraint

echo "=========================================="
echo "Docker CFS Test (Single Core Constraint)"
echo "=========================================="
echo ""

docker run --rm \
  --cap-add=SYS_NICE \
  --cpuset-cpus=0 \
  -v /dev:/dev \
  -v $(pwd)/results_cfs:/PeriodicTask/results_cfs \
  periodic-task:latest \
  sh run_cfs_test.sh

echo ""
echo "Results saved to: results_cfs/"
echo ""
echo "Analyze with:"
echo "  ./compare_results.sh"
