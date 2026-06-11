#include "timing.h"

uint64_t now_ns(clockid_t clk) {
    struct timespec ts;
    clock_gettime(clk, &ts);
    return ts_to_ns(&ts);
}
