#!/bin/bash
# Docker SCHED_FIFO test - with single core constraint

echo "=========================================="
echo "Docker SCHED_FIFO Test (Single Core Constraint)"
echo "=========================================="
echo ""

docker run --rm \
  --cap-add=SYS_NICE \
  --cpuset-cpus=0 \
  -v /dev:/dev \
  -v $(pwd)/results_fifo:/PeriodicTask/results_fifo \
  periodic-task:latest \
  sh run_fifo_test.sh

echo ""
echo "Results saved to: results_fifo/"
echo ""
echo "Analyze with:"
echo "  ./compare_results.sh"
