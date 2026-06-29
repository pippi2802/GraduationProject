#include <inttypes.h>

#include "cputime.h"
#include "cpu_consume.h"

//static uint64_t t;

uint64_t calibrate(unsigned int c)
{
  uint64_t t, cnt, t0;

  cnt = 0;
  t = t0 = rdtsc();
  while (t - t0 < c) {
    t = rdtsc();
    cnt++;
  }

  return cnt++;
}

void consume(uint64_t n)
{
  uint64_t t, cnt, t0;

  cnt = 0;
  t = t0 = rdtsc();
  while (cnt < n) {
    t = rdtsc();
    t = t - t0;
    cnt++;
  }
}
