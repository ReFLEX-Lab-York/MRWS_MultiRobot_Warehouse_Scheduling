# MRWS: A MultiRobot Warehouse Simulator
A Python simulator for a robotic smart warehouse, with many configurable properties. The aim is to develop and evaluate various path planning, scheduling and allocation algorithms.

## Project Structure

- `doc/`: documentations
- `simu/`: simulator (Python)
- `viz/`: visualisor (Unity)

## Requirements

Simulation:

- Python >= 3.11
- pygad
- matplotlib

Visualisation:

- Unity == 6000..0.41f1

## Usage

Run `python main.py -t` to transmit positions to the visualiser.

Setting parameter `slow_for_transit` to `true` when calling `run_simulation()` on a simulator object may be useful to reduce the speed of the simulator for visualisation.
