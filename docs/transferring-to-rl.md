# Transferring MRWS to a Reinforcement Learning Setup

This document outlines how to convert the existing rule-based MRWS simulator into a reinforcement learning (RL) environment. It covers the current architecture, three design options at different abstraction levels, and concrete implementation guidance for integrating with Gymnasium.

## Current Architecture

The simulator is fully **reactive/rule-based**:

1. The `Scheduler` assigns targets (shelves, goals, homes) to robots based on one of four algorithms (simple, simple-interrupt, multi-robot, multi-robot-genetic).
2. `Warehouse.step()` runs one discrete time step: apply faults, decide each robot's action, move robots along A* paths, handle interactions, introduce dynamic orders.
3. Robots follow their schedule queues deterministically. Pathfinding is A*. There is no learned component.

### Robot Action Space (Current)

Each step, the engine resolves one action per robot based on its state:

| State | Action |
|---|---|
| `wait_steps > 0` | Wait (decrement counter) |
| Near sensor-faulted robot | Evade to first free cardinal neighbor |
| No target assigned | Request next schedule entry from scheduler |
| Target = home (idle, no fault) | Check for reassignment, else keep moving |
| Has target, not arrived | Move 1 cell along A* path (4-connected: N/S/E/W) |
| Has target, arrived | Interact (pick item from shelf / deliver to goal / charge at home) |

Movement is **one cell per step**, 4-connected grid (no diagonals). The robot does not choose; the engine selects the action deterministically from the robot's state and schedule.

## Design Options

### Option A: Low-Level — Robot as Agent (Per-Robot RL)

Each robot is an independent agent choosing movement actions each step.

| Component | Design |
|---|---|
| **State** | Local observation: robot position, inventory contents, current target, nearby cells (walls/robots/shelves/goals in a local window), fault status, remaining schedule |
| **Action** | `{move_N, move_S, move_E, move_W, wait, interact}` — 6 discrete actions |
| **Reward** | `+R` for order completion, small `-r` per step (time penalty), `-P` for collision, `+r` for picking up or delivering an item |
| **Episode** | One simulation run = one episode, terminates when all orders complete or step limit hit |

**Pros:**
- Simple action space, well-studied in multi-agent RL (MARL) literature.
- Each agent has a small, fixed action space regardless of warehouse size.
- Naturally supports decentralized execution.

**Cons:**
- Credit assignment is hard — a robot contributes to an order completion many steps later.
- Replaces A* pathfinding, which already works optimally for single-agent shortest paths.
- Collision avoidance must be learned from scratch.
- Scales poorly: with N robots, the joint action space is 6^N.

**When to use:** Research on learned multi-agent navigation, collision avoidance, or emergent coordination.

### Option B: High-Level — Scheduler as Agent (Recommended)

Replace the `Scheduler.schedule()` logic with a learned policy. Robots still use A* for pathfinding and the existing interaction/movement logic.

| Component | Design |
|---|---|
| **State** | Global: robot positions + statuses + inventories, order queue (items, priorities, assigned/unassigned), shelf positions + contents, goal occupancy, current assignments |
| **Action** | Assignment decisions: which robot to which order to which goal. Discrete combinatorial, or decomposed as sequential picks per free robot |
| **Reward** | `-1` per step (minimize total completion time), `+R` per order completed, bonus for priority-weighted completion |
| **Episode** | One simulation run = one episode |

**Pros:**
- This is where the actual decision-making happens — task allocation is the hard, interesting problem.
- A* pathfinding is kept (it is optimal for single-agent shortest path).
- Interactions, fault handling, and deadlock resolution stay unchanged.
- Directly comparable to the existing rule-based schedulers.

**Cons:**
- Combinatorial action space grows with `robots x orders x goals`. Needs action masking or decomposition.
- State representation must encode variable-length order lists.

**When to use:** Research on learned task allocation, order scheduling, or comparing RL vs. heuristic scheduling.

### Option C: Hybrid — Two-Level Hierarchy

Combine both levels with a hierarchical policy:

- **High-level policy** (event-driven): assigns orders to robots. Triggered when a robot becomes free, an order completes, or a new order arrives.
- **Low-level policy** (every step): local navigation and collision avoidance, conditioned on the assigned target.

**Pros:**
- Most complete and realistic for warehouse RL research.
- Each level has a tractable action space.
- High-level handles allocation; low-level handles reactive navigation.

**Cons:**
- Significantly more complex to implement and train.
- Requires hierarchical RL framework (options framework, feudal RL, etc.).
- Two reward functions to design and balance.

**When to use:** Full warehouse optimization research, or when both navigation and scheduling need to be learned jointly.

## Recommended Implementation: Option B (RL Scheduler)

### Mapping to the Codebase

The cleanest integration wraps `Warehouse` as a Gymnasium environment and replaces only the scheduling decisions:

```
Warehouse.__init__()
  |-- parse warehouse, create entities  (unchanged)
  |-- create entities, items, orders    (unchanged)
  +-- do NOT create rule-based Scheduler

GymnasiumEnv.step(action)
  |-- decode action into robot-order-goal assignments
  |-- for each robot: A* movement              (unchanged)
  |-- for each robot: interact at target       (unchanged)
  |-- compute reward
  +-- return obs, reward, terminated, truncated, info
```

What stays unchanged:
- Warehouse parsing, entity creation
- A* pathfinding (`engine/pathfinding.py`)
- Deadlock detection and resolution (`engine/deadlock.py`)
- Robot movement and collision detection
- Entity interactions (shelf, goal, home)
- Fault model
- Order generation (`engine/order_manager.py`)

What gets replaced:
- `Scheduler.schedule()` and its four algorithm variants
- `Scheduler.direct_robot()` — the RL agent decides assignments instead

### State (Observation) Encoding

```python
obs = {
    # Per-robot features: (num_robots, 7)
    "robots": np.array([
        [x, y, inventory_count, has_target, fault_status, priority, is_assigned]
        for robot in robots
    ], dtype=np.float32),

    # Per-order features: (max_orders, 4)
    # Padded to fixed size, with a validity mask
    "orders": np.array([
        [num_items, priority, is_active, is_assigned]
        for order in backlog + active orders
    ], dtype=np.float32),

    # Per-goal features: (num_goals, 3)
    "goals": np.array([
        [x, y, is_occupied]
        for goal in goals
    ], dtype=np.float32),

    # Per-shelf features: (num_shelves, 4)
    "shelves": np.array([
        [x, y, has_item, item_dependency]
        for shelf in shelves
    ], dtype=np.float32),
}
```

For a simpler flat representation, concatenate and pad to a fixed vector size.

### Action Encoding

Decompose the combinatorial assignment into sequential per-robot decisions:

**Per free robot:** select an order index from `{0, 1, ..., num_orders-1, IDLE}`.

- Goal assignment can be automatic (nearest free goal to the order's items) to reduce action space.
- This gives action space `num_orders + 1` per decision, which is tractable.
- Use **action masking** to prevent assigning already-taken orders or goals.

Alternatively, for a fixed-size discrete action:

```python
# Flat action: robot_index * (max_orders + 1) + order_index
action_space = Discrete(num_robots * (max_orders + 1))
```

### Reward Design

```python
reward = 0.0

# Time penalty: encourage fast completion
reward -= 1.0

# Order completion bonus (priority-weighted)
for completed_order in newly_completed_orders:
    reward += 100.0 * completed_order.priority

# Item delivery progress
for item_delivered_this_step in items_delivered:
    reward += 5.0

# Collision penalty (if using learned navigation)
for collision in collisions_this_step:
    reward -= 50.0

# Episode completion bonus
if all_orders_complete:
    reward += 500.0
```

### Gymnasium Env Skeleton

```python
import gymnasium as gym
from gymnasium import spaces
import numpy as np
from mrws.engine.warehouse import Warehouse

class WarehouseSchedulingEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, warehouse_file, num_items, robot_max_inventory=3,
                 step_limit=5000):
        super().__init__()
        self._warehouse_file = warehouse_file
        self._num_items = num_items
        self._robot_max_inventory = robot_max_inventory
        self._step_limit = step_limit

        # Create a temporary warehouse to read dimensions
        self._warehouse = self._make_warehouse()
        num_robots = len(self._warehouse._robots)
        num_goals = len(self._warehouse._order_stations)
        num_shelves = len(self._warehouse._shelves)

        # Observation and action spaces
        self.observation_space = spaces.Dict({
            "robots": spaces.Box(0, 1, shape=(num_robots, 7), dtype=np.float32),
            "orders": spaces.Box(0, 1, shape=(50, 4), dtype=np.float32),  # padded
            "goals": spaces.Box(0, 1, shape=(num_goals, 3), dtype=np.float32),
        })
        # Per free robot: pick an order or idle
        self.action_space = spaces.Discrete(50 + 1)  # max_orders + idle

    def _make_warehouse(self):
        return Warehouse(
            self._warehouse_file, self._num_items,
            self._robot_max_inventory, "simple",  # mode unused, we override scheduling
            [0, 0, 0, 0], True, self._step_limit,
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._warehouse = self._make_warehouse()
        obs = self._get_obs()
        return obs, {}

    def step(self, action):
        # 1. Decode action into assignments
        self._apply_assignments(action)

        # 2. Run one warehouse step (movement, interactions, faults)
        done = self._warehouse.step()

        # 3. Compute reward
        reward = self._compute_reward()

        # 4. Build observation
        obs = self._get_obs()
        truncated = self._warehouse.get_total_steps() >= self._step_limit

        return obs, reward, done, truncated, {}

    def _get_obs(self):
        # ... encode warehouse state into observation dict
        pass

    def _apply_assignments(self, action):
        # ... map action integers to robot-order-goal assignments
        # ... call scheduler methods or directly set robot targets
        pass

    def _compute_reward(self):
        # ... reward shaping as described above
        pass
```

### Key Implementation Decisions

| Decision | Recommendation |
|---|---|
| **When does the agent act?** | Every step (simplest), or event-driven (when a robot becomes free). Event-driven is more natural but variable-length episodes per decision. |
| **Multi-agent vs single-agent?** | Start with single centralized agent making all assignments. Move to MARL later if needed. |
| **Observation normalization** | Normalize coordinates to `[0, 1]` by dividing by grid width/height. |
| **Variable-size inputs** | Pad orders to a fixed max size with zero vectors + validity mask. Robots and goals are fixed per warehouse. |
| **Curriculum** | Train on small warehouses first (10x10, 3 robots), then scale up. |
| **Baseline comparison** | Run the existing `simple` and `multi-robot` schedulers on the same warehouse files and compare total completion steps. |

### File Structure

Suggested additions to the codebase:

```
simu/
  mrws/
    rl/
      __init__.py
      env.py              # Gymnasium environment wrapper
      obs.py              # Observation encoding utilities
      reward.py           # Reward computation
      wrappers.py         # Optional: action masking, normalization
  train.py                # Training script (SB3 / CleanRL / RLlib)
  evaluate.py             # Compare RL agent vs rule-based schedulers
```

### Training Framework Suggestions

- **Stable-Baselines3** — easiest to start, supports PPO/A2C/DQN with Dict observations and action masking via `sb3-contrib`.
- **CleanRL** — single-file implementations, good for understanding and customizing.
- **RLlib** — best for multi-agent RL if you go to Option C later.

## Next Steps

1. Implement `WarehouseSchedulingEnv` wrapping `Warehouse` (Option B).
2. Verify the env works with `gymnasium.utils.env_checker.check_env()`.
3. Train with PPO (Stable-Baselines3) on a small warehouse (10x10, 3 robots).
4. Compare learned scheduler vs rule-based schedulers on completion time.
5. Scale to larger warehouses and more robots.
