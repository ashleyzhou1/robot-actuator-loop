# Robot Actuator Loop

A simulated robot actuator control system: two C programs communicate over UDP on localhost, coordinated by a single-threaded orchestrator running a 1kHz control loop with periodic disk logging. Built to meet a p99 round-trip latency deadline of 200µs. See `report.md` for the full design report and benchmark results.

## Architecture

This project consists of two C programs that communicate over UDP on localhost: `actuator.c`, which simulates one robot joint, and `orchestrator.c`, which sends commands to all actuators and receives responses. Each instance of `actuator.c` listens on its own UDP port.

The message format is a fixed 20-byte little-endian struct (`actuator_id`, `counter`, `timestamp_ns`, `position`), shared by both programs via `message.h`.

The design consists of 3 "buses" (where each bus is a group of 3 actuators), for 9 actuators total. Each actuator gets a unique UDP port (`PORT_BASE + bus*3 + actuator_id`). This avoids ambiguity about which actuator receives a command.

The orchestrator runs a "fast tick" every 1ms, during which it sends 9 commands and collects 9 responses, each to one actuator. The orchestrator runs a "slow tick" every 1000 fast ticks, appending the last 1000 commands to a JSON log file (`commands.json`) on disk. Both fast and slow ticks run on a single OS thread.

### How the orchestrator learns which actuators to drive

The orchestrator uses a hardcoded `ActuatorTarget targets[]` array (`orchestrator.c`, lines 20-24) listing each actuator's `(id, bus)` pair, along with `num_targets` (currently 9). The current configuration drives all 9 actuators (3 per bus × 3 buses). To run a reduced configuration (e.g., 3 actuators, 1 per bus), edit `targets[]` and `num_targets` accordingly.

## Build Instructions

Requires `clang` and `make` (tested on macOS 26.1, Apple clang 17.0.0).

```bash
make
```

This builds the `actuator` and `orchestrator` binaries using `-Wall -O2 -lm`. Run `make clean` to remove the binaries.

## Reproduction Steps

### 1. Start the actuators

Each actuator is started with `--id` and `--bus` arguments. To run the full 9-actuator configuration (matching the default `targets[]`):

```bash
./actuator 0 0 &
./actuator 1 0 &
./actuator 2 0 &
./actuator 0 1 &
./actuator 1 1 &
./actuator 2 1 &
./actuator 0 2 &
./actuator 1 2 &
./actuator 2 2 &
```

Each actuator listens on port `51712 + (bus * 3) + id` (ports 51712-51720).

### 2. Start the orchestrator

```bash
./orchestrator
```

The orchestrator sends a command to each of the 9 targets every 1ms, collects responses via a non-blocking poll loop, and logs round-trip times to `latency.csv`. Every 1000 ticks (1 second), it appends the last 1000 commands to `commands.json`.

### 3. Run the full benchmark (5 × 5-minute runs)

```bash
./run_benchmark.sh
```

This automates steps 1-2: for each of 5 runs, it starts all 9 actuators, runs the orchestrator for 5 minutes, then saves the resulting latency data as `latency_run1.csv` through `latency_run5.csv`. Each run takes 5 minutes (25 minutes total).

### 4. Analyze results

Requires Python 3 with `pandas`, `numpy`, and `matplotlib`:

```bash
pip install pandas numpy matplotlib
python3 analyze.py
```

`analyze.py` reads `latency_run1.csv` through `latency_run5.csv` and produces:

- **Printed statistics**: per-run and aggregate distribution stats (min, median, mean, p95, p99, p99.9, max) for both raw and corrected RTT, a p99 summary table across all 5 runs, and the send-offset correction values (average RTT by `target_idx`, total gradient, overhead per send)
- **`latency_all_runs_corrected.csv`**: all 5 runs combined, with an added `rtt_corrected` column
- **Five graphs** (saved to the working directory, move to `images/`):

| File | Description |
|------|-------------|
| `p99_per_run.png` | Bar chart of p99 latency per run (raw vs corrected), with the 200µs deadline and mean lines. |
| `histogram_aggregate.png` | Histograms (raw left, corrected right) of all measurements combined. Shows the overall latency distribution shape. |
| `rtt_over_time_all_runs.png` | Five stacked line plots (one per run) of raw RTT over the first 5000 samples. |
| `gradient_raw_vs_corrected.png` | Bar chart of average RTT by `target_idx` (0-8), raw vs corrected. Visualizes the send-offset bias and correction. |
| `per_bus_p99.png` | Bar charts of p99 latency per bus (raw vs corrected). |

## CSV Output Format

`latency_run*.csv` columns:

| Column | Meaning |
|--------|---------|
| `counter` | Tick number (increments by 1 every 1ms) |
| `bus` | Which of the 3 buses this actuator belongs to (0, 1, or 2) |
| `target_id` | The actuator's ID on its bus (0, 1, or 2) |
| `target_idx` | Position in the send order for that tick (0-8); used for send-offset correction |
| `rtt_us` | Measured round-trip time in microseconds |

## Send-Offset Correction

Because the orchestrator sends commands to all 9 targets sequentially each tick, `target_idx=0`'s send timestamp is recorded earliest and `target_idx=8`'s latest — creating a systematic gradient in raw RTT (earlier-sent targets show inflated RTT due to time spent in the send loop). `analyze.py` corrects for this:

```
overhead_per_send = (avg_rtt_idx0 - avg_rtt_idx8) / 8
corrected_rtt = raw_rtt - ((8 - target_idx) * overhead_per_send)
```

See `report.md` for full discussion of this correction and its limitations.

## Results Summary

Across 5 independent 5-minute runs (10,166,040 total measurements), mean p99 RTT was **113.6µs raw / 94.4µs corrected**, both within the 200µs deadline. See `report.md` for the full design report, including the iterative design process, benchmark results, and discussion.

## File Structure

```
robot-actuator-loop/
├── actuator.c          # Simulated actuator (robot joint)
├── orchestrator.c      # Central control loop
├── message.h           # Shared 20-byte message format + now_ns()
├── Makefile            # Build configuration
├── run_benchmark.sh    # Runs 5 x 5-minute benchmark
├── analyze.py          # Latency analysis + graph generation
├── report.md           # Design report
├── README.md           # This file
└── images/
    ├── p99_per_run.png
    ├── histogram_aggregate.png
    ├── rtt_over_time_all_runs.png
    ├── gradient_raw_vs_corrected.png
    └── per_bus_p99.png
```

Raw benchmark data (`latency_run1.csv` through `latency_run5.csv`, `latency_all_runs_corrected.csv`) is available [here](https://drive.google.com/drive/folders/1En9gbcQD9aL_wza7Kfj1kzT3oaX-r1ND?usp=sharing) (Google Drive link) due to file size.