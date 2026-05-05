#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

uint64_t rdtsc(void)
{
  unsigned long long int val;

  __asm__ __volatile__("rdtsc" : "=A" (val));

  return val;
}

unsigned int cpu_speed(void)
{
  FILE *f;
  char line[160];

  f = fopen("/proc/cpuinfo", "r");
  if (f == NULL) {
    return 0;
  }

  while(!feof(f)) {
    char *res;

    res = fgets(line, 160, f);
    if (res != NULL) {
      if (memcmp(line, "cpu MHz\t\t: ", 11) == 0) {
        float s;
        s = atof(line + 10);

        return s * 1000.0;
      }
    }
  }
  
  return 0;
}
