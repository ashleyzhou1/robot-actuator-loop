#!/bin/bash

RUNS=5
DURATION=300  # 5 minutes in seconds

echo "Starting benchmark — $RUNS runs of $DURATION seconds each"

for run in $(seq 1 $RUNS); do
    echo ""
    echo "=========================================="
    echo "RUN $run of $RUNS"
    echo "=========================================="

    # Kill any leftover processes
    pkill actuator 2>/dev/null
    pkill orchestrator 2>/dev/null
    sleep 1

    # Start all 9 actuators in background
    ./actuator 0 0 &
    ./actuator 1 0 &
    ./actuator 2 0 &
    ./actuator 0 1 &
    ./actuator 1 1 &
    ./actuator 2 1 &
    ./actuator 0 2 &
    ./actuator 1 2 &
    ./actuator 2 2 &

    sleep 1

    # Run orchestrator for DURATION seconds
    sleep $DURATION & SLEEP_PID=$!
    ./orchestrator 2>&1 | tee output_run${run}.txt &
    ORCH_PID=$!
    wait $SLEEP_PID
    kill $ORCH_PID 2>/dev/null

    # Kill actuators
    pkill actuator 2>/dev/null
    sleep 1

    # Save CSV for this run
    cp latency.csv latency_run${run}.csv
    echo "Run $run complete — saved latency_run${run}.csv"

    # Clear commands.json for next run
    rm -f commands.json
done

echo ""
echo "All $RUNS runs complete!"
echo "Files saved: latency_run1.csv through latency_run${RUNS}.csv"
