extern unsigned int N;
extern uint64_t cnt;
extern uint64_t calib_len;

struct task_p {
  struct periodic_task *h;
  int      bcet;
  int      wcet;
  int      period;
  int      offset;
  int      max_budget;
  int      cbs_period;
  int      cbs_flags;
  int      prio;
  uint64_t *times;
  uint64_t *mytimes;
};

void *task_body(void *param);

