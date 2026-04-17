# PyQt6 Debug GUI for MRWS

## Summary

Add a real-time debug GUI to the MRWS warehouse simulator using PyQt6 with QGraphicsScene. Launched via `-g` flag on `main.py`. Provides grid visualization, robot inspection, order tracking, fault status overlays, A* path display, and full playback controls.

## Architecture

New file: `simu/src/gui.py`
Modified file: `simu/src/main.py` (add `-g` flag, GUI launch path)

The simulation runs inline — the GUI process directly accesses the `Warehouse` object. A `QTimer` drives `warehouse.step()` calls, replacing the `while` loop when in GUI mode.

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Main Window (QMainWindow)                                        │
│ ┌──────────────────────────────────┐ ┌─────────────────────────┐ │
│ │                                  │ │  Robot Inspector (Dock)  │ │
│ │   Warehouse Grid View            │ │  - Name, position       │ │
│ │   (QGraphicsView + Scene)        │ │  - Target, schedule     │ │
│ │                                  │ │  - Inventory items      │ │
│ │   Robots: colored circles        │ │  - Fault status         │ │
│ │   Shelves: brown squares         │ │  - Wait steps, priority │ │
│ │   Goals: green diamonds          │ │  - Assigned order       │ │
│ │   Homes: blue outlines           │ │                         │ │
│ │   Walls: dark gray blocks        │ ├─────────────────────────┤ │
│ │   A* paths: dotted lines         │ │  Order Panel (Dock)     │ │
│ │                                  │ │  - Active orders        │ │
│ │   Click robot → Inspector        │ │  - Backlog orders       │ │
│ │   Scroll to zoom, drag to pan    │ │  - Completed orders     │ │
│ │                                  │ │  - Items, assignments   │ │
│ └──────────────────────────────────┘ └─────────────────────────┘ │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │  Toolbar: [Play] [Pause] [Step] [Speed: ████░░░░] Step: 42  │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Grid Rendering

- Cell size: 60x60 px
- Robots: Circles, color-coded by fault state (green=healthy, yellow=battery low, red=critical, orange=actuator, purple=sensor)
- Shelves: Brown rounded rectangles with item count label
- Goals: Green diamonds
- Homes: Blue dashed outlines
- Walls: Dark gray filled squares
- Empty: Light gray

## Debug Overlays

### A* Path Overlay
Selected robot's `_movement_path` drawn as dotted line through waypoints. Full schedule shown as text labels at target positions.

### Fault Status Indicators
Robot circles color-coded by fault state. Letter overlay (B/S/A) for fault type. Red X for critical faults.

### Robot Inspector Panel (Right Dock)
Click a robot to see: name, position, target, schedule queue, inventory, fault flags, wait steps, priority, assigned order.

### Order Tracking Panel (Right Dock)
Three sections: Active, Backlog, Completed. Each shows: order ID, priority, items, assigned robots, goal.

## Playback Controls (Toolbar)

- Play: Start/resume (QTimer)
- Pause: Stop timer
- Step: Single warehouse.step()
- Speed slider: 10ms to 1000ms interval
- Step counter: current _total_steps

## Integration

- `-g` flag on main.py enables GUI mode
- Forces `-n 1` (single simulation)
- QApplication created, warehouse built, handed to GUI window
- GUI owns simulation loop via QTimer
