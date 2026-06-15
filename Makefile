CC = clang
CFLAGS = -Wall -O2 -lm

all: actuator orchestrator

actuator: actuator.c message.h
	$(CC) $(CFLAGS) -o actuator actuator.c

orchestrator: orchestrator.c message.h
	$(CC) $(CFLAGS) -o orchestrator orchestrator.c

clean:
	rm -f actuator orchestrator