# PyQt6 Debug GUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real-time PyQt6 debug GUI that visualizes the warehouse simulation with robot inspection, order tracking, fault overlays, A* path display, and full playback controls.

**Architecture:** A single new file `simu/src/gui.py` containing all GUI classes, plus modifications to `simu/src/main.py` to add a `-g` flag that launches the GUI instead of the headless loop. The GUI uses `QGraphicsScene` for the grid and `QDockWidget` panels for robot/order inspection. A `QTimer` drives `warehouse.step()`.

**Tech Stack:** PyQt6 (QGraphicsScene, QGraphicsView, QDockWidget, QToolBar), Python 3.11+

---

### Task 1: Install PyQt6 dependency

**Files:**
- None (conda environment change)

**Step 1: Install PyQt6 in the MRWS conda environment**

Run: `conda run -n MRWS pip install PyQt6`
Expected: Successful install

**Step 2: Verify import works**

Run: `conda run -n MRWS python -c "from PyQt6.QtWidgets import QApplication; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: add PyQt6 dependency for debug GUI"
```

---

### Task 2: Create gui.py with main window skeleton and grid rendering

**Files:**
- Create: `simu/src/gui.py`

**Step 1: Create `gui.py` with the full GUI implementation**

```python
import sys
import math
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView,
    QDockWidget, QVBoxLayout, QWidget, QLabel, QToolBar,
    QSlider, QTreeWidget, QTreeWidgetItem, QSplitter, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QAction, QPolygonF
)
from PyQt6.QtCore import QPointF

CELL_SIZE = 60
ROBOT_RADIUS = 22

# Colors
COLOR_EMPTY = QColor(240, 240, 240)
COLOR_WALL = QColor(60, 60, 60)
COLOR_SHELF = QColor(160, 120, 60)
COLOR_GOAL = QColor(40, 180, 80)
COLOR_HOME = QColor(100, 150, 220)
COLOR_GRID_LINE = QColor(200, 200, 200)

COLOR_ROBOT_HEALTHY = QColor(50, 180, 50)
COLOR_ROBOT_BATTERY_LOW = QColor(230, 200, 30)
COLOR_ROBOT_BATTERY_CRIT = QColor(220, 40, 40)
COLOR_ROBOT_ACTUATOR = QColor(230, 140, 30)
COLOR_ROBOT_SENSOR = QColor(160, 60, 200)

COLOR_PATH = QColor(50, 120, 220, 120)
COLOR_SELECTED = QColor(255, 215, 0)


def get_robot_color(robot_obj):
    if robot_obj.battery_faulted_critical:
        return COLOR_ROBOT_BATTERY_CRIT
    if robot_obj.battery_faulted:
        return COLOR_ROBOT_BATTERY_LOW
    if robot_obj.actuators_faulted:
        return COLOR_ROBOT_ACTUATOR
    if robot_obj.sensors_faulted:
        return COLOR_ROBOT_SENSOR
    return COLOR_ROBOT_HEALTHY


class WarehouseScene(QGraphicsScene):
    def __init__(self, warehouse, parent=None):
        super().__init__(parent)
        self.warehouse = warehouse
        self.selected_robot_name = None
        self._robot_items = {}

    def render_full(self):
        self.clear()
        self._robot_items = {}
        w = self.warehouse
        width = w._width
        height = w._height

        # Draw cells
        for y in range(height):
            for x in range(width):
                cell = w._cells[y][x]
                sx = x * CELL_SIZE
                # Flip y so y=0 is at bottom visually
                sy = (height - 1 - y) * CELL_SIZE

                # Background
                color = COLOR_EMPTY
                has_wall = False
                has_shelf = False
                has_goal = False
                has_home = False
                shelf_name = None
                goal_name = None

                for entity_name in cell:
                    if "wall" in entity_name:
                        has_wall = True
                    elif "shelf" in entity_name:
                        has_shelf = True
                        shelf_name = entity_name
                    elif "goal" in entity_name:
                        has_goal = True
                        goal_name = entity_name
                    elif "home" in entity_name:
                        has_home = True

                if has_wall:
                    color = COLOR_WALL

                self.addRect(sx, sy, CELL_SIZE, CELL_SIZE,
                             QPen(COLOR_GRID_LINE), QBrush(color))

                # Draw home (blue dashed outline)
                if has_home and not has_wall:
                    home_pen = QPen(COLOR_HOME, 2, Qt.PenStyle.DashLine)
                    margin = 4
                    self.addRect(sx + margin, sy + margin,
                                 CELL_SIZE - 2 * margin, CELL_SIZE - 2 * margin,
                                 home_pen, QBrush(Qt.GlobalColor.transparent))

                # Draw shelf (brown rounded rect)
                if has_shelf:
                    shelf_pen = QPen(QColor(120, 80, 30), 2)
                    shelf_brush = QBrush(COLOR_SHELF)
                    margin = 8
                    rect_item = self.addRect(sx + margin, sy + margin,
                                             CELL_SIZE - 2 * margin, CELL_SIZE - 2 * margin,
                                             shelf_pen, shelf_brush)
                    # Label
                    if shelf_name:
                        label = self.addText(shelf_name.replace("shelf", "S"),
                                             QFont("Monospace", 8))
                        label.setDefaultTextColor(QColor(255, 255, 255))
                        label.setPos(sx + 12, sy + 18)

                # Draw goal (green diamond)
                if has_goal:
                    cx = sx + CELL_SIZE / 2
                    cy = sy + CELL_SIZE / 2
                    size = 20
                    diamond = QPolygonF([
                        QPointF(cx, cy - size),
                        QPointF(cx + size, cy),
                        QPointF(cx, cy + size),
                        QPointF(cx - size, cy),
                    ])
                    self.addPolygon(diamond, QPen(QColor(20, 120, 50), 2),
                                    QBrush(COLOR_GOAL))
                    if goal_name:
                        label = self.addText(goal_name.replace("goal", "G"),
                                             QFont("Monospace", 8))
                        label.setDefaultTextColor(QColor(255, 255, 255))
                        label.setPos(sx + 22, sy + 22)

        # Draw robots
        for robot_name, robot_obj in w._robots.items():
            rx, ry = robot_obj.get_position()
            sx = rx * CELL_SIZE + CELL_SIZE / 2
            sy = (height - 1 - ry) * CELL_SIZE + CELL_SIZE / 2

            color = get_robot_color(robot_obj)

            # Selection highlight
            if robot_name == self.selected_robot_name:
                self.addEllipse(sx - ROBOT_RADIUS - 4, sy - ROBOT_RADIUS - 4,
                                (ROBOT_RADIUS + 4) * 2, (ROBOT_RADIUS + 4) * 2,
                                QPen(COLOR_SELECTED, 3), QBrush(Qt.GlobalColor.transparent))

            # Robot circle
            robot_ellipse = self.addEllipse(
                sx - ROBOT_RADIUS, sy - ROBOT_RADIUS,
                ROBOT_RADIUS * 2, ROBOT_RADIUS * 2,
                QPen(QColor(30, 30, 30), 2), QBrush(color)
            )
            self._robot_items[robot_name] = robot_ellipse

            # Robot label
            short_name = robot_name.replace("robot", "R")
            label = self.addText(short_name, QFont("Monospace", 9, QFont.Weight.Bold))
            label.setDefaultTextColor(QColor(255, 255, 255))
            tw = label.boundingRect().width()
            th = label.boundingRect().height()
            label.setPos(sx - tw / 2, sy - th / 2)

            # Fault overlay letter
            fault_letter = ""
            if robot_obj.battery_faulted_critical:
                fault_letter = "X"
            elif robot_obj.battery_faulted:
                fault_letter = "B"
            elif robot_obj.actuators_faulted:
                fault_letter = "A"
            elif robot_obj.sensors_faulted:
                fault_letter = "S"

            if fault_letter:
                fl = self.addText(fault_letter, QFont("Monospace", 7, QFont.Weight.Bold))
                fl.setDefaultTextColor(QColor(255, 255, 255))
                fl.setPos(sx + ROBOT_RADIUS - 8, sy - ROBOT_RADIUS - 2)

            # Draw inventory count
            inv_count = robot_obj.get_inventory_usage()
            if inv_count > 0:
                inv_label = self.addText(str(inv_count), QFont("Monospace", 7))
                inv_label.setDefaultTextColor(QColor(255, 255, 100))
                inv_label.setPos(sx - ROBOT_RADIUS + 2, sy + ROBOT_RADIUS - 12)

        # Draw selected robot's A* path
        if self.selected_robot_name and self.selected_robot_name in w._robots:
            robot_obj = w._robots[self.selected_robot_name]
            path = robot_obj.get_movement_path()
            if path:
                path_pen = QPen(COLOR_PATH, 3, Qt.PenStyle.DashLine)
                prev_pos = robot_obj.get_position()
                for pos in path:
                    x1 = prev_pos[0] * CELL_SIZE + CELL_SIZE / 2
                    y1 = (height - 1 - prev_pos[1]) * CELL_SIZE + CELL_SIZE / 2
                    x2 = pos[0] * CELL_SIZE + CELL_SIZE / 2
                    y2 = (height - 1 - pos[1]) * CELL_SIZE + CELL_SIZE / 2
                    self.addLine(x1, y1, x2, y2, path_pen)
                    prev_pos = pos

            # Draw target marker
            target = robot_obj.get_target()
            if target is not None:
                tx, ty = target.get_position()
                tsx = tx * CELL_SIZE
                tsy = (height - 1 - ty) * CELL_SIZE
                target_pen = QPen(COLOR_SELECTED, 3, Qt.PenStyle.DashDotLine)
                self.addRect(tsx + 2, tsy + 2, CELL_SIZE - 4, CELL_SIZE - 4,
                             target_pen, QBrush(Qt.GlobalColor.transparent))


class WarehouseView(QGraphicsView):
    def __init__(self, scene, on_robot_click, parent=None):
        super().__init__(scene, parent)
        self.on_robot_click = on_robot_click
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        factor = 1.15
        if event.angleDelta().y() < 0:
            factor = 1.0 / factor
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            warehouse = self.scene().warehouse
            height = warehouse._height

            # Convert scene coords to grid coords
            gx = int(scene_pos.x() / CELL_SIZE)
            gy_scene = int(scene_pos.y() / CELL_SIZE)
            gy = height - 1 - gy_scene

            # Check if a robot is at this cell
            robot_name = warehouse._position_to_robot.get((gx, gy))
            if robot_name:
                self.on_robot_click(robot_name)
            else:
                self.on_robot_click(None)
        super().mousePressEvent(event)


class RobotInspectorPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel("Click a robot to inspect")
        self.title_label.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        self.info_tree = QTreeWidget()
        self.info_tree.setHeaderLabels(["Property", "Value"])
        self.info_tree.setColumnWidth(0, 120)
        layout.addWidget(self.info_tree)

    def update_robot(self, robot_name, warehouse):
        self.info_tree.clear()

        if robot_name is None or robot_name not in warehouse._robots:
            self.title_label.setText("Click a robot to inspect")
            return

        robot_obj = warehouse._robots[robot_name]
        self.title_label.setText(robot_name)

        def add_row(key, value):
            QTreeWidgetItem(self.info_tree, [str(key), str(value)])

        pos = robot_obj.get_position()
        add_row("Position", f"({pos[0]}, {pos[1]})")

        target = robot_obj.get_target()
        if target:
            tpos = target.get_position()
            add_row("Target", f"{target.get_name()} ({tpos[0]}, {tpos[1]})")
        else:
            add_row("Target", "None")

        add_row("Priority", robot_obj.get_prio())
        add_row("Wait Steps", robot_obj.get_wait_steps())
        add_row("Assigned Order", robot_obj.get_assigned_order())

        # Faults
        faults = []
        if robot_obj.battery_faulted_critical:
            faults.append("BATTERY CRITICAL")
        if robot_obj.battery_faulted:
            faults.append("Battery Low")
        if robot_obj.actuators_faulted:
            faults.append("Actuator")
        if robot_obj.sensors_faulted:
            faults.append("Sensor")
        add_row("Faults", ", ".join(faults) if faults else "None")

        # Inventory
        inv = robot_obj.report_inventory()
        inv_names = [f"{item.get_name()}(dep={item.get_dependency()})" for item in inv]
        add_row("Inventory", ", ".join(inv_names) if inv_names else "Empty")

        # Schedule
        scheduler = warehouse.get_scheduler()
        sched = scheduler._schedule.get(robot_name, [])
        sched_str = " -> ".join(list(sched)[:10])
        if len(sched) > 10:
            sched_str += f" ... (+{len(sched) - 10} more)"
        add_row("Schedule", sched_str if sched_str else "Empty")

        # Movement path length
        path = robot_obj.get_movement_path()
        add_row("Path Length", len(path))

        self.info_tree.expandAll()


class OrderPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel("Orders")
        self.title_label.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        self.order_tree = QTreeWidget()
        self.order_tree.setHeaderLabels(["Order", "Priority", "Status", "Details"])
        self.order_tree.setColumnWidth(0, 60)
        self.order_tree.setColumnWidth(1, 50)
        self.order_tree.setColumnWidth(2, 70)
        layout.addWidget(self.order_tree)

    def update_orders(self, warehouse):
        self.order_tree.clear()
        scheduler = warehouse.get_scheduler()
        order_manager = warehouse.get_order_manager()

        # Active orders
        for order_obj in scheduler._orders_active:
            oid = order_obj.get_id()
            prio = order_obj.get_prio()
            robots = scheduler._order_robots_assignment.get(oid, [])
            goal = scheduler._order_goal_assignment.get(oid, "?")
            items = [item.get_name() for item in order_obj.get_items()]
            details = f"Robots: {', '.join(robots)} | Goal: {goal} | Items: {', '.join(items)}"
            item_widget = QTreeWidgetItem(self.order_tree,
                                          [f"#{oid}", str(prio), "Active", details])
            item_widget.setForeground(2, QBrush(QColor(40, 180, 80)))

        # Backlog orders
        for order_obj in scheduler._orders_backlog:
            oid = order_obj.get_id()
            prio = order_obj.get_prio()
            items = [item.get_name() for item in order_obj.get_items()]
            details = f"Items: {', '.join(items)}"
            item_widget = QTreeWidgetItem(self.order_tree,
                                          [f"#{oid}", str(prio), "Backlog", details])
            item_widget.setForeground(2, QBrush(QColor(200, 150, 30)))

        # Completed orders
        for oid, completion_step in order_manager.get_order_finish_work_times().items():
            item_widget = QTreeWidgetItem(self.order_tree,
                                          [f"#{oid}", "-", "Done", f"Completed at step {completion_step}"])
            item_widget.setForeground(2, QBrush(QColor(150, 150, 150)))


class SimulationGUI(QMainWindow):
    def __init__(self, warehouse):
        super().__init__()
        self.warehouse = warehouse
        self.is_running = False
        self.sim_complete = False

        self.setWindowTitle("MRWS Debug GUI")
        self.resize(1200, 800)

        # Scene & View
        self.scene = WarehouseScene(warehouse)
        self.view = WarehouseView(self.scene, self.on_robot_click)
        self.setCentralWidget(self.view)

        # Robot Inspector Dock
        self.robot_inspector = RobotInspectorPanel()
        inspector_dock = QDockWidget("Robot Inspector", self)
        inspector_dock.setWidget(self.robot_inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, inspector_dock)

        # Order Panel Dock
        self.order_panel = OrderPanel()
        order_dock = QDockWidget("Orders", self)
        order_dock.setWidget(self.order_panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, order_dock)

        # Toolbar
        toolbar = QToolBar("Playback")
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, toolbar)

        self.play_action = QAction("Play", self)
        self.play_action.triggered.connect(self.play)
        toolbar.addAction(self.play_action)

        self.pause_action = QAction("Pause", self)
        self.pause_action.triggered.connect(self.pause)
        toolbar.addAction(self.pause_action)

        self.step_action = QAction("Step", self)
        self.step_action.triggered.connect(self.do_single_step)
        toolbar.addAction(self.step_action)

        toolbar.addSeparator()

        speed_label = QLabel(" Speed: ")
        toolbar.addWidget(speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setMinimum(10)
        self.speed_slider.setMaximum(1000)
        self.speed_slider.setValue(200)
        self.speed_slider.setFixedWidth(150)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        toolbar.addWidget(self.speed_slider)

        self.speed_value_label = QLabel(" 200ms ")
        toolbar.addWidget(self.speed_value_label)

        toolbar.addSeparator()

        self.step_label = QLabel(" Step: 0 ")
        self.step_label.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
        toolbar.addWidget(self.step_label)

        self.status_label = QLabel("")
        toolbar.addWidget(self.status_label)

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.do_single_step)

        # Initial render
        self.refresh_display()

        # Fit view to scene
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def play(self):
        if self.sim_complete:
            return
        self.is_running = True
        self.timer.start(self.speed_slider.value())

    def pause(self):
        self.is_running = False
        self.timer.stop()

    def do_single_step(self):
        if self.sim_complete:
            self.pause()
            return
        try:
            done = self.warehouse.step()
            if done:
                self.sim_complete = True
                self.status_label.setText("  SIMULATION COMPLETE")
                self.pause()
        except Exception as e:
            self.sim_complete = True
            self.status_label.setText(f"  ERROR: {e}")
            self.pause()
        self.refresh_display()

    def on_speed_changed(self, value):
        self.speed_value_label.setText(f" {value}ms ")
        if self.is_running:
            self.timer.setInterval(value)

    def on_robot_click(self, robot_name):
        self.scene.selected_robot_name = robot_name
        self.robot_inspector.update_robot(robot_name, self.warehouse)
        self.scene.render_full()

    def refresh_display(self):
        self.scene.render_full()
        self.step_label.setText(f" Step: {self.warehouse.get_total_steps()} ")
        self.order_panel.update_orders(self.warehouse)
        if self.scene.selected_robot_name:
            self.robot_inspector.update_robot(self.scene.selected_robot_name, self.warehouse)


def launch_gui(warehouse):
    app = QApplication.instance() or QApplication(sys.argv)
    window = SimulationGUI(warehouse)
    window.show()
    app.exec()
```

**Step 2: Verify the file can be imported**

Run: `cd simu/src && conda run -n MRWS python -c "import gui; print('OK')"`
Expected: `OK` (may warn about no display if headless, but no import errors)

**Step 3: Commit**

```bash
git add simu/src/gui.py
git commit -m "feat: add PyQt6 debug GUI with grid rendering, robot inspector, order panel, and playback controls"
```

---

### Task 3: Integrate GUI launch into main.py

**Files:**
- Modify: `simu/src/main.py:381-401`

**Step 1: Add `-g` flag and GUI launch path to `main.py`**

In the `__main__` block (line 381 onwards), add the `-g` argument and a GUI launch branch. The changes are:

1. Add argument: `parser.add_argument("-g", "--gui", action="store_true", help="Launch debug GUI")`
2. When `-g` is set, create the warehouse directly and pass it to `gui.launch_gui()`

Replace the `if __name__ == "__main__":` block (lines 381-401) with:

```python
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--transmit", action="store_true", help="Whether or not to transmit UDP packets.")
    parser.add_argument(
        "-n",
        "--num-sims",
        type=int,
        default=1000,
        help="Number of simulation cycles to run (default: 1000).",
    )
    parser.add_argument("-g", "--gui", action="store_true", help="Launch PyQt6 debug GUI (forces -n 1).")
    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        default="simple-interrupt",
        choices=["simple", "simple-interrupt", "multi-robot", "multi-robot-genetic"],
        help="Scheduling mode (default: simple-interrupt).",
    )
    args = parser.parse_args()
    os.environ["ROBOTSIM_TRANSMIT"] = str(args.transmit)

    faulty_scenario = [0.0001, 0.001, 0.001, 0.001]
    perfect_scenario = [0, 0, 0, 0]

    if args.gui:
        import gui
        simu = warehouse.Warehouse(
            os.path.join(DATA_DIR, "whouse2.txt"),
            10, 3, args.mode,
            perfect_scenario, True, 1000,
        )
        gui.launch_gui(simu)
    else:
        sim = Simulation(args.num_sims, os.path.join(DATA_DIR, "whouse2.txt"), 10, 3, args.mode,
                         perfect_scenario, True, 1000)
        sim.run_simulation(True, args.transmit)
```

**Step 2: Test headless mode still works**

Run: `cd simu/src && conda run -n MRWS python main.py -n 1`
Expected: Completes without error

**Step 3: Test GUI launch**

Run: `cd simu/src && conda run -n MRWS python main.py -g`
Expected: PyQt6 window opens showing the warehouse grid with robots, shelves, goals. Playback controls visible at bottom.

**Step 4: Commit**

```bash
git add simu/src/main.py
git commit -m "feat: add -g flag and -m mode flag to launch debug GUI from main.py"
```

---

### Task 4: Manual integration test

**Step 1: Launch GUI and verify all features**

Run: `cd simu/src && conda run -n MRWS python main.py -g`

Verify checklist:
- [ ] Window opens with warehouse grid
- [ ] Robots shown as colored circles with labels (R0, R1, etc.)
- [ ] Shelves shown as brown squares with labels
- [ ] Goals shown as green diamonds
- [ ] Homes shown as blue dashed outlines
- [ ] Click Play: simulation steps forward automatically
- [ ] Click Pause: simulation pauses
- [ ] Click Step: single step forward
- [ ] Speed slider changes simulation speed
- [ ] Step counter updates
- [ ] Click a robot: inspector panel populates with position, target, schedule, inventory, faults
- [ ] Selected robot shows yellow highlight and A* path (dashed blue line)
- [ ] Order panel shows Active/Backlog/Completed orders
- [ ] Scroll wheel zooms, drag pans the view
- [ ] Simulation completes and shows "SIMULATION COMPLETE"

**Step 2: Test different scheduling modes**

Run: `cd simu/src && conda run -n MRWS python main.py -g -m multi-robot`
Run: `cd simu/src && conda run -n MRWS python main.py -g -m multi-robot-genetic`

Verify: GUI works with all modes, order panel shows correct multi-robot assignments.

**Step 3: Test fault visualization**

Modify the launch temporarily to use faulty_scenario instead of perfect_scenario, run GUI, verify:
- Faulted robots change color (yellow/red/orange/purple)
- Fault letter overlay appears (B/S/A/X)
- Inspector panel shows fault status

---

## Summary of all files changed

| File | Action |
|------|--------|
| `simu/src/gui.py` | Create (new file, ~350 lines) |
| `simu/src/main.py` | Modify `__main__` block to add `-g` and `-m` flags |
