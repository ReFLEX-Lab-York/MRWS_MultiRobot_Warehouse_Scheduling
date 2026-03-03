# MRWS: A MultiRobot Warehouse Simulator

A Python simulator for a robotic smart warehouse, with many configurable properties. The aim is to develop and evaluate various path planning, scheduling and allocation algorithms.

## Project Structure

```text
Simulator (Python)
    |-- GUI (can be turned on/off)
    `-- Visualiser (Unity via UDP)
```

- `simu/`: Core simulation engine, scheduling logic, and CLI entrypoint.
- `viz/`: Unity project for real-time visualisation of simulation state.


## Requirements

Simulation:

- Python >= 3.11
- pygad
- matplotlib

Visualisation:

- Unity 6000.0.41f1


## Usage

Run simulations from the `simu/` directory:

```bash
cd simu
python main.py           # Run simulation without visualisation
python main.py -t        # Run with UDP transmission to Unity visualiser
```

When running with `-t`, setting `slow_for_transmit` to `True` when calling `run_simulation()` adds a delay between each simulation step so the visualiser can keep up.


### Configurations

Simulations are configured by constructing a `Simulation` object in `main.py`:

```python
sim = Simulation(
    num_sims=1000,                       # Number of simulation runs
    whouse="whouse2.txt",                # Warehouse layout file
    num_items=10,                        # Number of distinct items (must match shelf count)
    inv_size=3,                          # Robot inventory capacity
    schedule_mode="simple-interrupt",    # Scheduling algorithm
    fault_rates=[0, 0, 0, 0],            # Fault rates: [battery_critical, battery_low, actuator, sensor]
    fault_mode=True,                     # Enable fault-tolerant rescheduling
    step_limit=1000                      # Max simulation steps before timeout
)
sim.run_simulation(reraise_error=True, slow_for_transmit=False)
```

### Scheduling Algorithms

- `simple` — one robot per order, FIFO assignment
- `simple-interrupt` — one robot per order with priority-based preemption
- `multi-robot` — multiple robots per order when beneficial
- `multi-robot-genetic` — uses a genetic algorithm (pygad) to optimise multi-robot schedules

### Warehouse Layout Files

Warehouse layouts are text files where each character represents a grid cell:

| Char | Meaning |
|------|---------|
| `R`  | Robot (and its home/charging position) |
| `S`  | Shelf containing an item |
| `G`  | Order station (goal/delivery point) |
| `X`  | Empty traversable cell |
| `W`  | Wall |

Example (`whouse2.txt`):

```
XXXXXXXXXXX
GXXSSXSSXXX
GRXSSXSSXXX
GRXXSXSXXXX
GRXXXXXXXXX
GRXXXXXXXXX
XXXXXXXXXXX
```

Custom layouts can be created as `.txt` files in the `simu/` directory. The number of `S` cells must equal the `num_items` parameter.

### Fault Simulation

Robot fault rates are specified as a list of four probabilities (per step, per robot):

1. **Battery critical** — permanent failure, robot becomes inoperable
2. **Battery low** — robot must return home and charge before resuming
3. **Actuator** — temporary movement halt (overheating)
4. **Sensor** — robot can no longer detect surroundings

Set all to `0` for a fault-free simulation. When `fault_mode=True`, the scheduler reassigns orders from faulted robots.

### Batch Experiments

`main.py` includes helper functions for running batch experiments with matplotlib visualisation:

- `run_completion_time_test(fault_rates)` — compares all four scheduling algorithms over 500 runs
- `run_fault_test(scheduling_mode)` — compares fault-tolerant vs non-fault-tolerant strategies
- `run_simulation_performance_test(scheduling_mode, robots_max, size_max, step_limit)` — benchmarks step time across varying warehouse sizes and robot counts
