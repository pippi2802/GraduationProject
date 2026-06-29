/* Taken from some simulation course, at the university...
 */

#include "sim_rand.h"

#define N 2147483647
#define D 16807

#define R (N % D)
#define Q (N / D)

int n = 1;

double gen_rand(void)
{
  int q, r;

  q = n / Q;
  r = n % Q;

  n = D * r - R * q;
  if (n < 0) n += N;

  return (double)n / (double)N;
}
