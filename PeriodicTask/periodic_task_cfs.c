#define _POSIX_C_SOURCE 200112L
#include <unistd.h>
#include <getopt.h>
#include <stdlib.h>
#include <inttypes.h>
#include <stdio.h>
#include <sys/resource.h>

#include "rt_utils.h"
#include "gettime.h"
#include "cputime.h"
#include "cpu_consume.h"
#include "task.h"
#include "output.h"

#define MAX_N 1000
unsigned int N = MAX_N;
static uint64_t times[MAX_N];
static uint64_t mytimes[MAX_N];
static uint64_t start_time;

struct task_p param;

int args_parse(int argc, char *argv[], int *nice_val)
{
  int v;

  param.bcet = 10000;
  param.wcet = 10000;
  param.period = 100000;
  param.offset = 500 * 1000;
  *nice_val = 0;
  
  while((v = getopt(argc, argv, "C:p:n:N:")) != -1) {
    switch(v) {
      case 'C':
        param.bcet = param.wcet = atoi(optarg);
        printf("#WCET = %d\n", param.wcet);
        break;
      case 'p':
        param.period = atoi(optarg);
        printf("#Period = %d\n", param.period);
        break;
      case 'n':
        *nice_val = atoi(optarg);
        printf("#Nice = %d\n", *nice_val);
        break;
      case 'N':
        N = atoi(optarg);
        if (N > MAX_N) N = MAX_N;
        printf("#Iterations = %d\n", N);
        break;
      default:
        fprintf(stderr, "Usage: periodic_task_cfs -C <wcet> -p <period> -n <nice> [-N <iterations>]\n");
        fprintf(stderr, "  -C : WCET in microseconds\n");
        fprintf(stderr, "  -p : Period in microseconds\n");
        fprintf(stderr, "  -n : Nice value (-20 to +19)\n");
        fprintf(stderr, "  -N : Number of iterations (default 1000)\n");
        exit(-1);
    }
  }

  return 1;
}

int main(int argc, char *argv[])
{
  int nice_val;

  args_parse(argc, argv, &nice_val);
  
  /* Set nice value for CFS scheduler */
  setpriority(PRIO_PROCESS, 0, nice_val);
  
  printf("#Scheduler: CFS (SCHED_OTHER)\n");
  
  if (cnt == 0) {
    uint64_t hz;
    hz = cpu_speed();
    printf("#CPU Speed: %"PRIu64"\n", hz);
    cnt = calibrate(calib_len / hz);
  }

  start_time = gettime() + param.offset;
  param.h = start_periodic_timer(param.offset, param.period);
  if (param.h == NULL) {
    perror("Start Periodic Timer");
    return -1;
  }
  param.times = times;
  param.mytimes = mytimes;

  printf("#PID: %u\n", getpid());
  printf("#Cycles: %"PRIu64"\n", cnt);

  task_body(&param);

  printf("#Start: %"PRIu64"\n", start_time);
  print_results(times, mytimes, start_time, 0, param.period, N);

  return 0;
}
