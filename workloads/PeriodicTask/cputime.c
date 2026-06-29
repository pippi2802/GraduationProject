#define _POSIX_C_SOURCE 200112L
#include <time.h>
#include <inttypes.h>

uint64_t rdtsc(void)
{
  struct timespec tv;
  int res;

  res = clock_gettime(CLOCK_MONOTONIC, &tv);
  if (res < 0) {
    return 0;
  }

  return (uint64_t)tv.tv_nsec / 1000UL + tv.tv_sec * 1000000UL;
}

unsigned int cpu_speed(void)
{
  return 1;
}
