#define _GNU_SOURCE
#include <stdio.h>
#include <pthread.h>

#include "affinity.h"

int thread_pin(pthread_t id, unsigned int n)
{
  int res;
  cpu_set_t cpuset;

  CPU_ZERO(&cpuset);
  CPU_SET(n, &cpuset);
  res = pthread_setaffinity_np(id, sizeof(cpu_set_t), &cpuset);
  if (res != 0) {
    perror("pthread_setaffinity");

    return -1;
  }

  return 0;
}

