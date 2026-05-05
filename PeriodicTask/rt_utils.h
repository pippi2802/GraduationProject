#ifndef __RT_UTILS__
#define __RT_UTILS__

struct periodic_task *start_periodic_timer(uint64_t offs, int t);
void wait_next_activation(struct periodic_task *t);
int make_rt(int p);
void set_next_interarrival(struct periodic_task *t, int p);
struct periodic_task *synch_periodic_timer(const struct periodic_task *t, int p);

int sched_set(uint32_t q, uint32_t t, uint32_t flags);
#endif
