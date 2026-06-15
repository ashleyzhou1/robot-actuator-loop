#ifndef MESSAGE_H
#define MESSAGE_H

#ifdef __APPLE__
#include <mach/mach_time.h>
#endif

#include <stdint.h>
#include <time.h>

typedef struct __attribute__((packed)) {
    uint32_t actuator_id;
    uint32_t counter;
    uint64_t timestamp_ns;
    float    position;
} Message;

// Get current time in nanoseconds
static inline uint64_t now_ns(void) {
#ifdef __APPLE__
    static mach_timebase_info_data_t tb;
    if (tb.denom == 0) mach_timebase_info(&tb);
    return (mach_absolute_time() * tb.numer) / tb.denom;
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ULL + ts.tv_nsec;
#endif
}

#endif // MESSAGE_H