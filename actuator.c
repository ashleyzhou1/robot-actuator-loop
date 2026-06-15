#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <math.h>
#include "message.h"

#define PORT_BASE 51712  // bus 0 starts here

int main(int argc, char *argv[]) {
    // Step 1 — parse arguments
    int id  = atoi(argv[1]);  // --id N
    int bus = atoi(argv[2]);  // --bus N
    int port = PORT_BASE + (bus * 3) + id;
    
    printf("Actuator %d listening on port %d\n", id, port);
    
    // Step 2 — create UDP socket
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("socket");
        return 1;
    }

    int reuse = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEPORT, &reuse, sizeof(reuse));
    
    // Step 3 — bind to port
    struct sockaddr_in addr = {0};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;
    addr.sin_port        = htons(port);
    
    if (bind(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        return 1;
    }
    
    // Step 4 — main loop
    Message cmd, response;
    struct sockaddr_in sender;
    socklen_t sender_len = sizeof(sender);
    uint64_t start_ns = now_ns();
    
    while (1) {
        // receive command
        recvfrom(sock, &cmd, sizeof(cmd), 0,
                 (struct sockaddr *)&sender, &sender_len);
        
        // ignore commands not for us
        if (cmd.actuator_id != (uint32_t)id) continue;
        
        // build response
        double t = (now_ns() - start_ns) / 1e9;  // seconds since start
        
        response.actuator_id  = cmd.actuator_id;
        response.counter      = cmd.counter;       // echo back unchanged
        response.timestamp_ns = now_ns();
        response.position     = 180.0f * sinf(2.0f * M_PI * t);
        
        // send response back to orchestrator
        sendto(sock, &response, sizeof(response), 0,
               (struct sockaddr *)&sender, sender_len);
    }
    
    close(sock);
    return 0;
}