#define _POSIX_C_SOURCE 200112L
#include <time.h>
#include <inttypes.h>

#include "gettime.h"

uint64_t gettime(void)
{
  struct timespec tv;
  int res;

  res = clock_gettime(CLOCK_MONOTONIC, &tv);
  if (res < 0) {
    return 0;
  }

  return (uint64_t)tv.tv_nsec / 1000UL + tv.tv_sec * 1000000UL;
}

uint64_t getmytime(void)
{
  struct timespec tv;
  int res;

  res = clock_gettime(CLOCK_THREAD_CPUTIME_ID, &tv);
  if (res < 0) {
    return 0;
  }

  return (uint64_t)tv.tv_nsec / 1000UL + tv.tv_sec * 1000000UL;
}


