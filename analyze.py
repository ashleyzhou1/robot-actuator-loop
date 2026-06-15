"""
analyze.py — Latency Analysis for Robot Actuator Loop Benchmark
See README for full documentation of calculations and methodology.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# ── Config ─────────────────────────────────────────────────────────────────
NUM_RUNS = 5
RUN_FILES = [f"latency_run{i}.csv" for i in range(1, NUM_RUNS + 1)]
COLORS = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974"]

# ── Load all runs ──────────────────────────────────────────────────────────
print("Loading data...")
runs = []
for i, f in enumerate(RUN_FILES):
    if os.path.exists(f):
        df = pd.read_csv(f).dropna()
        df["run"] = i + 1
        runs.append(df)
        print(f"  Run {i+1}: {len(df):,} measurements")
    else:
        print(f"  Run {i+1}: FILE NOT FOUND — skipping")

all_data = pd.concat(runs, ignore_index=True)
print(f"\nTotal measurements across all runs: {len(all_data):,}")

# ── Send offset correction ─────────────────────────────────────────────────
# target_idx=0 sent first (earliest timestamp), target_idx=8 sent last
# overhead_per_send = (avg_rtt_idx0 - avg_rtt_idx8) / 8
# corrected_rtt = raw_rtt - ((8 - target_idx) * overhead_per_send)
avg_by_idx = all_data.groupby("target_idx")["rtt_us"].mean()
print("\nAverage RTT by target_idx (across all runs):")
for idx, avg in avg_by_idx.items():
    print(f"  idx={idx}: {avg:.1f}µs")

avg_idx0 = avg_by_idx[0]
avg_idx8 = avg_by_idx[8]
total_gradient = avg_idx0 - avg_idx8
overhead_per_send = total_gradient / 8
print(f"\nTotal gradient (idx0 - idx8): {total_gradient:.2f}µs")
print(f"Overhead per send:            {overhead_per_send:.2f}µs")

# Apply correction to all data
all_data["rtt_corrected"] = all_data["rtt_us"] - ((8 - all_data["target_idx"]) * overhead_per_send)
all_data["rtt_corrected"] = all_data["rtt_corrected"].clip(lower=1)

for df in runs:
    df["rtt_corrected"] = df["rtt_us"] - ((8 - df["target_idx"]) * overhead_per_send)
    df["rtt_corrected"] = df["rtt_corrected"].clip(lower=1)

# ── Summary stats function ─────────────────────────────────────────────────
def stats(series, name):
    print(f"\n{'='*45}")
    print(f"{name}")
    print(f"{'='*45}")
    print(f"  Count:   {len(series):,}")
    print(f"  Min:     {series.min():.1f}µs")
    print(f"  Median:  {series.median():.1f}µs")
    print(f"  Mean:    {series.mean():.1f}µs")
    print(f"  p95:     {np.percentile(series, 95):.1f}µs")
    print(f"  p99:     {np.percentile(series, 99):.1f}µs")
    print(f"  p99.9:   {np.percentile(series, 99.9):.1f}µs")
    print(f"  Max:     {series.max():.1f}µs")
    return np.percentile(series, 99)

# Per-run stats
run_p99_raw = []
run_p99_corr = []

print("\n--- PER RUN STATS ---")
for i, df in enumerate(runs):
    p99r = stats(df["rtt_us"],        f"Run {i+1} — Raw RTT")
    p99c = stats(df["rtt_corrected"], f"Run {i+1} — Corrected RTT")
    run_p99_raw.append(p99r)
    run_p99_corr.append(p99c)

# Aggregate stats
print("\n--- AGGREGATE STATS (all runs combined) ---")
p99_raw_agg  = stats(all_data["rtt_us"],        "AGGREGATE Raw RTT")
p99_corr_agg = stats(all_data["rtt_corrected"], "AGGREGATE Corrected RTT")

# p99 summary table
print("\n--- P99 SUMMARY TABLE ---")
print(f"{'Run':<8} {'Raw p99':>12} {'Corrected p99':>15}")
print("-" * 37)
for i in range(len(runs)):
    print(f"Run {i+1:<4} {run_p99_raw[i]:>11.1f}µs {run_p99_corr[i]:>14.1f}µs")
print("-" * 37)
print(f"{'Mean':<8} {np.mean(run_p99_raw):>11.1f}µs {np.mean(run_p99_corr):>14.1f}µs")
print(f"{'Std Dev':<8} {np.std(run_p99_raw):>11.1f}µs {np.std(run_p99_corr):>14.1f}µs")
print(f"{'Min':<8} {np.min(run_p99_raw):>11.1f}µs {np.min(run_p99_corr):>14.1f}µs")
print(f"{'Max':<8} {np.max(run_p99_raw):>11.1f}µs {np.max(run_p99_corr):>14.1f}µs")


# ── Plot 1: p99 per run ────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))
x = np.arange(len(runs))
width = 0.35
ax.bar(x - width/2, run_p99_raw,  width, label="Raw p99",
       color="steelblue", alpha=0.85)
ax.bar(x + width/2, run_p99_corr, width, label="Corrected p99",
       color="tomato", alpha=0.85)
ax.axhline(y=200, color="red", linewidth=1.5,
           linestyle="--", label="200µs deadline")
ax.axhline(y=np.mean(run_p99_raw), color="steelblue",
           linewidth=1, linestyle=":",
           label=f"Mean raw p99={np.mean(run_p99_raw):.0f}µs")
ax.axhline(y=np.mean(run_p99_corr), color="tomato",
           linewidth=1, linestyle=":",
           label=f"Mean corrected p99={np.mean(run_p99_corr):.0f}µs")
for i in range(len(runs)):
    ax.text(i - width/2, run_p99_raw[i]  + 1,
            f"{run_p99_raw[i]:.0f}", ha="center", fontsize=9, fontweight="bold")
    ax.text(i + width/2, run_p99_corr[i] + 1,
            f"{run_p99_corr[i]:.0f}", ha="center", fontsize=9, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels([f"Run {i+1}" for i in range(len(runs))])
ax.set_ylabel("p99 Latency (µs)", fontsize=12)
ax.set_title("p99 Latency Per Run — Raw vs Corrected\n(9 Actuators, 3 Buses, 1kHz, 5 min each)",
             fontsize=13, fontweight="bold")
ax.legend(fontsize=9)
ax.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("p99_per_run.png", dpi=150)
plt.close()
print("\nSaved: p99_per_run.png")

# ── Plot 2: Aggregate histogram raw vs corrected ───────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, col, name, color in zip(
    axes,
    ["rtt_us", "rtt_corrected"],
    ["Raw RTT (all runs)", "Corrected RTT (all runs)"],
    ["steelblue", "tomato"]
):
    clipped = all_data[col].clip(upper=500)
    ax.hist(clipped, bins=100, color=color, alpha=0.8, edgecolor="white")
    ax.axvline(x=200, color="red", linewidth=1.5,
               linestyle="--", label="200µs deadline")
    p99 = np.percentile(all_data[col], 99)
    ax.axvline(x=p99, color="black", linewidth=1.5,
               linestyle="-", label=f"p99={p99:.0f}µs")
    ax.set_title(name, fontsize=13, fontweight="bold")
    ax.set_xlabel("RTT (µs) — clipped at 500µs", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
plt.suptitle("Aggregate RTT Distribution — Raw vs Corrected (5 × 5min Runs)",
             fontsize=14, fontweight="bold")
plt.tight_layout()
plt.savefig("histogram_aggregate.png", dpi=150)
plt.close()
print("Saved: histogram_aggregate.png")

# ── Plot 3: RTT over time per run ─────────────────────────────────────────
fig, axes = plt.subplots(len(runs), 1,
                         figsize=(14, 3*len(runs)), sharex=False)
if len(runs) == 1:
    axes = [axes]
for i, (ax, df) in enumerate(zip(axes, runs)):
    sample = df.head(5000)
    ax.plot(sample.index, sample["rtt_us"],
            color=COLORS[i], linewidth=0.4, alpha=0.7)
    ax.axhline(y=200, color="red", linewidth=1,
               linestyle="--", label="200µs deadline")
    p99 = np.percentile(df["rtt_us"], 99)
    ax.axhline(y=p99, color="black", linewidth=1,
               linestyle="-", label=f"p99={p99:.0f}µs")
    ax.set_title(f"Run {i+1} — Raw RTT", fontsize=11, fontweight="bold")
    ax.set_ylabel("RTT (µs)", fontsize=9)
    ax.set_ylim(0, 500)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
axes[-1].set_xlabel("Sample Index", fontsize=11)
plt.suptitle("Raw RTT Over Time — All Runs (first 5000 samples)",
             fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig("rtt_over_time_all_runs.png", dpi=150)
plt.close()
print("Saved: rtt_over_time_all_runs.png")

# ── Plot 4: Send offset gradient ──────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
corrected_avg = all_data.groupby("target_idx")["rtt_corrected"].mean()
ax.bar(avg_by_idx.index - 0.175, avg_by_idx.values,
       width=0.35, color="steelblue", alpha=0.8,
       edgecolor="white", label="Raw avg RTT")
ax.bar(corrected_avg.index + 0.175, corrected_avg.values,
       width=0.35, color="tomato", alpha=0.8,
       edgecolor="white", label="Corrected avg RTT")
ax.set_xlabel("Target Index (0=first sent, 8=last sent)", fontsize=11)
ax.set_ylabel("Average RTT (µs)", fontsize=11)
ax.set_title("Send Offset Gradient — Raw vs Corrected\n"
             "Shows systematic bias from sequential send timestamps",
             fontsize=12, fontweight="bold")
ax.set_xticks(range(9))
ax.legend(fontsize=10)
ax.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("gradient_raw_vs_corrected.png", dpi=150)
plt.close()
print("Saved: gradient_raw_vs_corrected.png")

# ── Plot 5: Per-bus p99 aggregate ─────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 5))
for ax, col, name in zip(
    axes,
    ["rtt_us", "rtt_corrected"],
    ["Raw RTT", "Corrected RTT"]
):
    bus_p99 = []
    for bus in [0, 1, 2]:
        rtt = all_data[all_data["bus"] == bus][col]
        bus_p99.append(np.percentile(rtt, 99))
    ax.bar(["Bus 0", "Bus 1", "Bus 2"], bus_p99,
           color=["#4C72B0", "#55A868", "#C44E52"],
           edgecolor="white")
    ax.axhline(y=200, color="red", linewidth=1.5,
               linestyle="--", label="200µs deadline")
    for i, val in enumerate(bus_p99):
        ax.text(i, val + 1, f"{val:.0f}µs",
                ha="center", fontsize=11, fontweight="bold")
    ax.set_title(f"Per-Bus p99 — {name}", fontsize=12, fontweight="bold")
    ax.set_ylabel("p99 Latency (µs)", fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(True, axis="y", alpha=0.3)
    ax.set_ylim(0, max(bus_p99) * 1.3)
plt.suptitle("Per-Bus p99 — Aggregate (5 Runs)", fontsize=13, fontweight="bold")
plt.tight_layout()
plt.savefig("per_bus_p99.png", dpi=150)
plt.close()
print("Saved: per_bus_p99.png")

# ── Save corrected data ────────────────────────────────────────────────────
all_data.to_csv("latency_all_runs_corrected.csv", index=False)
print("Saved: latency_all_runs_corrected.csv")

print("\ndone")