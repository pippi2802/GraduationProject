#define _POSIX_C_SOURCE 200112L
#include <unistd.h>
#include <getopt.h>
#include <stdlib.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdbool.h>
#include <pthread.h>

#include "rt_utils.h"
#include "gettime.h"
#include "cputime.h"
#include "cpu_consume.h"
#include "task.h"
#include "output.h"
#include "affinity.h"

#define MAX_TH 10
#define MAX_N 1000
unsigned int N = MAX_N;

static uint64_t times[MAX_TH * MAX_N];
static uint64_t mytimes[MAX_TH * MAX_N];
static uint64_t start_time;
static bool pin_threads;

int parse_int(const char *v, int min)
{
  int res;

  res = atoi(v);
  if (res < min) {
    res = min;
  }

  return res;
}

#define Q     15000
#define P    100000
#define CMIN  10000
#define CMAX  10000
#define T    100000
int args_parse(int argc, char *argv[], struct task_p *p)
{
  int v;
  int q_th = 0, p_th = 0, t_th = 0, c_th = 0, r_th = 0, prio_th = 0;
  int n = 4;

  for (v = 0; v < MAX_TH; v++) {
    p[v].max_budget = Q;
    p[v].cbs_period = P;
    p[v].bcet = CMIN;
    p[v].wcet = CMAX;
    p[v].period = T;
    p[v].prio = 0;
    p[v].offset = 500 * 1000;
  }

  while((v = getopt(argc, argv, "N:R:q:t:p:C:c:r:P:n:a")) != -1) {
    switch(v) {
      case 'q':
        p[q_th].max_budget = parse_int(optarg, 1000);
        fprintf(stderr, "Q[%d] = %d\n", q_th, p[q_th].max_budget);
        q_th++;
        break;
      case 't':
        p[p_th].cbs_period = parse_int(optarg, 5000);
        fprintf(stderr, "Server Period [%d] = %d\n", p_th, p[p_th].cbs_period);
        p_th++;
        break;
      case 'p':
        p[t_th].period = parse_int(optarg, 5000);
        fprintf(stderr, "T[%d] = %d\n", t_th, p[t_th].period);
        t_th++;
        break;
      case 'C':
        p[c_th].bcet = p[c_th].wcet = parse_int(optarg, 100);
        fprintf(stderr, "Fixed C[%d] = %d\n", c_th, p[c_th].wcet);
        c_th++;
        break;
      case 'c':
        sscanf(optarg, "%d/%d", &p[c_th].bcet, &p[c_th].wcet);
        fprintf(stderr, "Uniform C[%d] = [%d, %d]\n", c_th, p[c_th].bcet, p[c_th].wcet);
        c_th++;
        break;
      case 'r':
        p[r_th].offset = atoi(optarg);
        fprintf(stderr, "Offset: %d\n", p[r_th].offset);
        r_th++;
        break;
      case 'P':
        p[prio_th].prio = atoi(optarg);
        prio_th++;
        break;
      case 'N':
        N = atoi(optarg);
        if (N > MAX_N) N = MAX_N;
        break;
      case 'R':
        cnt = atoi(optarg);
        break;
      case 'n':
        n = atoi(optarg);
        break;
      case 'a':
        pin_threads = true;
        break;
      default:
        fprintf(stderr, "Exiting because of illegal option!\n");

        exit(-1);
    }
  }

  return n;
}

int main(int argc, char *argv[])
{
  int err, i;
  void *returnvalue;
  pthread_t th_id[MAX_TH];
  struct task_p params[MAX_TH];
  int n;

  n = args_parse(argc, argv, params);
  make_rt(1);
  
  if (cnt == 0) {
    uint64_t hz;

    hz = cpu_speed();
    printf("#CPU Speed: %"PRIu64"\n", hz);
    cnt = calibrate(calib_len * hz);
  }

  printf("#Cycles: %"PRIu64"\n", cnt);
  start_time = gettime() + params[0].offset;
  params[0].h = start_periodic_timer(params[0].offset, params[0].period);
  if (params[0].h == NULL) {
    perror("Start Periodic Timer");

    return -1;
  }
  params[0].times      = times;
  params[0].mytimes    = mytimes;

  for (i = 1; i < n; i++) {
    /* Hack, to synchronize the start times! */
    params[i].h = synch_periodic_timer(params[0].h, params[i].period);
    params[i].times      = times   + i * N;
    params[i].mytimes    = mytimes + i * N;
  }
  for (i = 0; i < n; i++) {
    fprintf(stderr, "%d --- (%d %d) (%d %d)\n", i, params[i].wcet, params[i].period, params[i].max_budget, params[i].cbs_period);
    err = pthread_create(&th_id[i], NULL, task_body, &params[i]);
    if (err != 0)
      perror("pthread_create");
    if (pin_threads) {
      thread_pin(th_id[i], i + 1);
    }
  }

  /* We wait the end of the threads we just created. */
  for (i = 0; i < n; i++) {
    pthread_join(th_id[i], &returnvalue);
  }

  printf("#Start: %"PRIu64"\n", start_time);
  for (i = 0; i < n; i++) {
    print_results(&times[N * i], &mytimes[N * i], start_time, i, params[i].period, N);
  }

  return 0;
}
