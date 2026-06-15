#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <math.h>
#include <time.h>
#include <fcntl.h>
#include "message.h"

#define PORT_BASE 51712
#define NUM_BUSES 3

// Actuator target configuration
// Change num_targets and targets[] to switch between configurations
// 1 actuator per bus (3 total): num_targets = 3
// 3 actuators per bus (9 total): num_targets = 9
typedef struct { int id; int bus; } ActuatorTarget;

ActuatorTarget targets[] = {
    {0, 0}, {1, 0}, {2, 0},  // bus 0: actuators 0,1,2
    {0, 1}, {1, 1}, {2, 1},  // bus 1: actuators 0,1,2
    {0, 2}, {1, 2}, {2, 2},  // bus 2: actuators 0,1,2
};
int num_targets = 9;

// port formula: PORT_BASE + (bus * 3) + actuator_id
// bus 0: ports 51712, 51713, 51714
// bus 1: ports 51715, 51716, 51717
// bus 2: ports 51718, 51719, 51720
#define TARGET_PORT(bus, id) (PORT_BASE + (bus * 3) + id)

#define LOG_SIZE 1000
#define LOG_FILE "commands.json"

typedef struct {
    uint32_t counter;
    uint32_t actuator_id;
    uint64_t timestamp_ns;
    float    position;
} LogEntry;

LogEntry log_buffer[LOG_SIZE];
int log_index = 0;

void write_log(void) {
    FILE *f = fopen(LOG_FILE, "a");
    if (!f) return;
    
    fprintf(f, "[\n");
    for (int i = 0; i < LOG_SIZE; i++) {
        fprintf(f, "  {\"counter\": %u, \"actuator_id\": %u, "
                "\"timestamp_ns\": %llu, \"position\": %.4f}%s\n",
                log_buffer[i].counter,
                log_buffer[i].actuator_id,
                (unsigned long long)log_buffer[i].timestamp_ns,
                log_buffer[i].position,
                i < LOG_SIZE - 1 ? "," : "");
    }
    fprintf(f, "]\n");
    fflush(f);
    fclose(f);
}

FILE *csv_file = NULL;

void open_csv(void) {
    csv_file = fopen("latency.csv", "w");
    fprintf(csv_file, "counter,bus,target_id,target_idx,rtt_us\n");
}

void log_rtt(uint32_t counter, int bus, int target_id, int target_idx, uint64_t rtt_us) {
    if (csv_file) {
        fprintf(csv_file, "%u,%d,%d,%d,%llu\n",
                counter, bus, target_id, target_idx,
                (unsigned long long)rtt_us);
    }
}

int main(void) {
    // Step 1 — create one socket per target (unique port per actuator)
    int socks[9];
    struct sockaddr_in target_addr[9];

    for (int i = 0; i < num_targets; i++) {
        socks[i] = socket(AF_INET, SOCK_DGRAM, 0);
        if (socks[i] < 0) {
            perror("socket");
            return 1;
        }

        fcntl(socks[i], F_SETFL, O_NONBLOCK);

        memset(&target_addr[i], 0, sizeof(target_addr[i]));
        target_addr[i].sin_family      = AF_INET;
        target_addr[i].sin_port        = htons(TARGET_PORT(targets[i].bus, targets[i].id));
        inet_pton(AF_INET, "127.0.0.1", &target_addr[i].sin_addr);
    }

    printf("Orchestrator started\n");
    open_csv();

    // main loop
    uint32_t counter = 0;
    Message cmd, response;
    uint64_t send_times[9];

    while (1) {
        uint64_t tick_start = now_ns();

        // send command to each target actuator
        for (int i = 0; i < num_targets; i++) {
            cmd.actuator_id  = targets[i].id;
            cmd.counter      = counter;
            cmd.timestamp_ns = now_ns();
            cmd.position     = 0.0f;
            send_times[i]    = cmd.timestamp_ns;

            sendto(socks[i], &cmd, sizeof(cmd), 0,
                (struct sockaddr *)&target_addr[i],
                sizeof(target_addr[i]));
        }

        // non-blocking poll loop — collect responses from all targets
        int received[9] = {0};
        int total_received = 0;
        uint64_t deadline = tick_start + 900000;

        while (total_received < num_targets && now_ns() < deadline) {
            for (int i = 0; i < num_targets; i++) {
                if (received[i]) continue;

                struct sockaddr_in from;
                socklen_t from_len = sizeof(from);

                ssize_t n = recvfrom(socks[i], &response, sizeof(response), 0,
                                    (struct sockaddr *)&from, &from_len);

                if (n == sizeof(Message)) {
                    uint64_t now = now_ns();
                    uint64_t rtt = now - send_times[i];
                    printf("target=%d bus=%d counter=%u rtt=%llu us\n",
                            targets[i].id, targets[i].bus, response.counter,
                            (unsigned long long)(rtt / 1000));
                    log_rtt(counter, targets[i].bus, targets[i].id, i, rtt / 1000);

                    int idx = log_index % LOG_SIZE;
                    log_buffer[idx].counter      = cmd.counter;
                    log_buffer[idx].actuator_id  = targets[i].id;
                    log_buffer[idx].timestamp_ns = send_times[i];
                    log_buffer[idx].position     = cmd.position;
                    log_index++;

                    received[i] = 1;
                    total_received++;
                }
            }
        }

        counter++;

        // slow tick — write log every 1000 ticks (1 second)
        if (counter % 1000 == 0) {
            write_log();
            printf("--- log written at counter=%u ---\n", counter);
        }

        // sleep until next 1ms tick
        uint64_t elapsed = now_ns() - tick_start;
        if (elapsed < 1000000) {
            struct timespec ts;
            ts.tv_sec  = 0;
            ts.tv_nsec = (long)(1000000 - elapsed);
            nanosleep(&ts, NULL);
        }
    }

    if (csv_file) fclose(csv_file);
    for (int i = 0; i < num_targets; i++) close(socks[i]);
    return 0;
}