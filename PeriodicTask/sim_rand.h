#ifndef __SIM_RAND__
#define __SIM_RAND__

double gen_rand(void);

#define UNIF(c1, c2) (c1 + gen_rand() * (c2 - c1))

#endif /* __SIM_RAND */
