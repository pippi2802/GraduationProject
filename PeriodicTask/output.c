#include <inttypes.h>
#include <stdio.h>

#include "output.h"

void print_results(uint64_t *times, uint64_t *mytimes, uint64_t st, int task, int period, int n)
{
  int i;

  for (i = 0; i < n; i++) {
    printf("%d %d\t%"PRIu64"\t%"PRIu64"\t%"PRIu64"\t%f\n", task, i,
      times[i], times[i] - st - period * i,
      mytimes[i],
      ((double)times[i] - st - period * (i + 1)) / (double)period);
  }
}


