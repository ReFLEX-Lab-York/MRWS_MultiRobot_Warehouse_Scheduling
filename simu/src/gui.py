"""
PyQt6 Debug GUI for the MRWS Warehouse Simulator.

Provides a real-time visual debugger for the warehouse simulation, including
a grid display, robot inspector, and order panel.
"""

import sys
import math
from collections import deque

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsScene,
    QGraphicsView,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsPolygonItem,
    QGraphicsSimpleTextItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QPushButton,
    QSlider,
    QLabel,
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
)
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QPen,
    QFont,
    QPainterPath,
    QPolygonF,
    QWheelEvent,
    QMouseEvent,
    QPainter,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CELL_SIZE = 60

# Entity colours
COLOR_EMPTY = QColor(220, 220, 220)
COLOR_WALL = QColor(80, 80, 80)
COLOR_SHELF = QColor(139, 90, 43)
COLOR_GOAL = QColor(34, 139, 34)
COLOR_HOME = QColor(70, 130, 180)
COLOR_SELECTED_HIGHLIGHT = QColor(255, 255, 0, 160)
COLOR_PATH_LINE = QColor(50, 120, 220, 180)
COLOR_TARGET_OUTLINE = QColor(218, 165, 32)

# Robot fault colours
COLOR_ROBOT_HEALTHY = QColor(50, 180, 50)
COLOR_ROBOT_BATTERY_LOW = QColor(230, 230, 0)
COLOR_ROBOT_BATTERY_CRITICAL = QColor(220, 40, 40)
COLOR_ROBOT_ACTUATOR = QColor(230, 140, 30)
COLOR_ROBOT_SENSOR = QColor(160, 50, 200)


# ---------------------------------------------------------------------------
# WarehouseScene
# ---------------------------------------------------------------------------
class WarehouseScene(QGraphicsScene):
    """Renders the warehouse grid and all entities."""

    def __init__(self, warehouse, parent=None):
        super().__init__(parent)
        self._warehouse = warehouse
        self._width = warehouse._width
        self._height = warehouse._height
        self._selected_robot_name = None

    # -- coordinate helpers --------------------------------------------------

    def _scene_y(self, wy):
        """Convert warehouse y to scene y (flip)."""
        return (self._height - 1 - wy) * CELL_SIZE

    def _scene_xy(self, wx, wy):
        return wx * CELL_SIZE, self._scene_y(wy)

    # -- full redraw ---------------------------------------------------------

    def rebuild(self, selected_robot_name=None):
        """Clear the scene and redraw everything from scratch."""
        self._selected_robot_name = selected_robot_name
        self.clear()

        wh = self._warehouse

        # 1) Background cells
        for wy in range(self._height):
            for wx in range(self._width):
                sx, sy = self._scene_xy(wx, wy)
                cell = wh._cells[wy][wx]
                self._draw_cell_background(sx, sy, cell)

        # 2) Shelves
        for shelf_name, shelf_obj in wh._shelves.items():
            sx, sy = self._scene_xy(*shelf_obj.get_position())
            self._draw_shelf(sx, sy, shelf_name)

        # 3) Goals (order stations)
        for goal_name, goal_obj in wh._order_stations.items():
            sx, sy = self._scene_xy(*goal_obj.get_position())
            self._draw_goal(sx, sy, goal_name)

        # 4) Homes
        for home_name, home_obj in wh._homes.items():
            sx, sy = self._scene_xy(*home_obj.get_position())
            self._draw_home(sx, sy, home_name)

        # 5) Robots (drawn last so they are on top)
        selected_robot_obj = None
        for robot_name, robot_obj in wh._robots.items():
            sx, sy = self._scene_xy(*robot_obj.get_position())
            is_selected = (robot_name == selected_robot_name)
            self._draw_robot(sx, sy, robot_name, robot_obj, is_selected)
            if is_selected:
                selected_robot_obj = robot_obj

        # 6) Selected robot overlays (path + target highlight)
        if selected_robot_obj is not None:
            self._draw_robot_path(selected_robot_obj)
            self._draw_target_highlight(selected_robot_obj)

    # -- cell background -----------------------------------------------------

    def _draw_cell_background(self, sx, sy, cell):
        has_wall = any("wall" in name for name in cell)
        color = COLOR_WALL if has_wall else COLOR_EMPTY
        rect = self.addRect(sx, sy, CELL_SIZE, CELL_SIZE,
                            QPen(QColor(180, 180, 180)), QBrush(color))
        rect.setZValue(0)

    # -- shelf ---------------------------------------------------------------

    def _draw_shelf(self, sx, sy, name):
        margin = 8
        pen = QPen(QColor(100, 60, 20), 2)
        brush = QBrush(COLOR_SHELF)
        rect = self.addRect(sx + margin, sy + margin,
                            CELL_SIZE - 2 * margin, CELL_SIZE - 2 * margin,
                            pen, brush)
        rect.setZValue(1)

        idx = name.replace("shelf", "")
        label = self.addSimpleText("S" + idx, QFont("Monospace", 9, QFont.Weight.Bold))
        label.setBrush(QBrush(QColor(255, 255, 255)))
        label.setPos(sx + margin + 4, sy + margin + 4)
        label.setZValue(2)

    # -- goal (diamond) ------------------------------------------------------

    def _draw_goal(self, sx, sy, name):
        cx = sx + CELL_SIZE / 2
        cy = sy + CELL_SIZE / 2
        r = CELL_SIZE / 2 - 6
        poly = QPolygonF([
            QPointF(cx, cy - r),
            QPointF(cx + r, cy),
            QPointF(cx, cy + r),
            QPointF(cx - r, cy),
        ])
        item = self.addPolygon(poly, QPen(QColor(0, 100, 0), 2), QBrush(COLOR_GOAL))
        item.setZValue(1)

        idx = name.replace("goal", "")
        label = self.addSimpleText("G" + idx, QFont("Monospace", 9, QFont.Weight.Bold))
        label.setBrush(QBrush(QColor(255, 255, 255)))
        label.setPos(cx - 8, cy - 7)
        label.setZValue(2)

    # -- home (dashed outline) -----------------------------------------------

    def _draw_home(self, sx, sy, name):
        margin = 4
        pen = QPen(COLOR_HOME, 2, Qt.PenStyle.DashLine)
        rect = self.addRect(sx + margin, sy + margin,
                            CELL_SIZE - 2 * margin, CELL_SIZE - 2 * margin,
                            pen, QBrush(Qt.BrushStyle.NoBrush))
        rect.setZValue(0.5)

    # -- robot ---------------------------------------------------------------

    def _draw_robot(self, sx, sy, name, robot_obj, is_selected):
        cx = sx + CELL_SIZE / 2
        cy = sy + CELL_SIZE / 2
        radius = 22

        # Determine colour from fault state
        color = COLOR_ROBOT_HEALTHY
        fault_letter = ""
        if robot_obj.battery_faulted_critical:
            color = COLOR_ROBOT_BATTERY_CRITICAL
            fault_letter = "X"
        elif robot_obj.battery_faulted:
            color = COLOR_ROBOT_BATTERY_LOW
            fault_letter = "B"
        elif robot_obj.actuators_faulted:
            color = COLOR_ROBOT_ACTUATOR
            fault_letter = "A"
        elif robot_obj.sensors_faulted:
            color = COLOR_ROBOT_SENSOR
            fault_letter = "S"

        # Selection highlight ring
        if is_selected:
            highlight_pen = QPen(COLOR_SELECTED_HIGHLIGHT, 4)
            self.addEllipse(cx - radius - 4, cy - radius - 4,
                            2 * (radius + 4), 2 * (radius + 4),
                            highlight_pen, QBrush(Qt.BrushStyle.NoBrush)).setZValue(4)

        # Robot circle
        pen = QPen(QColor(30, 30, 30), 2)
        brush = QBrush(color)
        ellipse = self.addEllipse(cx - radius, cy - radius,
                                  2 * radius, 2 * radius,
                                  pen, brush)
        ellipse.setZValue(5)

        # Label (R0, R1, ...)
        idx = name.replace("robot", "")
        label_text = "R" + idx
        label = self.addSimpleText(label_text, QFont("Monospace", 8, QFont.Weight.Bold))
        label.setBrush(QBrush(QColor(255, 255, 255)))
        # Centre the label roughly
        label.setPos(cx - len(label_text) * 4, cy - 6)
        label.setZValue(6)

        # Fault letter overlay (small, upper-right of circle)
        if fault_letter:
            fault_label = self.addSimpleText(fault_letter, QFont("Monospace", 7, QFont.Weight.Bold))
            fault_label.setBrush(QBrush(QColor(255, 255, 255)))
            fault_label.setPos(cx + radius - 10, cy - radius)
            fault_label.setZValue(7)

        # Inventory count (lower-right)
        inv_count = robot_obj.get_inventory_usage()
        if inv_count > 0:
            inv_label = self.addSimpleText(str(inv_count), QFont("Monospace", 7))
            inv_label.setBrush(QBrush(QColor(255, 255, 200)))
            inv_label.setPos(cx + radius - 8, cy + radius - 14)
            inv_label.setZValue(7)

    # -- selected robot A* path overlay --------------------------------------

    def _draw_robot_path(self, robot_obj):
        path_deque = robot_obj.get_movement_path()
        if not path_deque:
            return

        pen = QPen(COLOR_PATH_LINE, 2, Qt.PenStyle.DashLine)
        points = [robot_obj.get_position()] + list(path_deque)
        for i in range(len(points) - 1):
            x1, y1 = self._scene_xy(*points[i])
            x2, y2 = self._scene_xy(*points[i + 1])
            line = self.addLine(
                x1 + CELL_SIZE / 2, y1 + CELL_SIZE / 2,
                x2 + CELL_SIZE / 2, y2 + CELL_SIZE / 2,
                pen,
            )
            line.setZValue(3)

    # -- selected robot target highlight -------------------------------------

    def _draw_target_highlight(self, robot_obj):
        target = robot_obj.get_target()
        if target is None:
            return
        tx, ty = target.get_position()
        sx, sy = self._scene_xy(tx, ty)
        pen = QPen(COLOR_TARGET_OUTLINE, 3, Qt.PenStyle.DashLine)
        rect = self.addRect(sx + 2, sy + 2, CELL_SIZE - 4, CELL_SIZE - 4,
                            pen, QBrush(Qt.BrushStyle.NoBrush))
        rect.setZValue(8)


# ---------------------------------------------------------------------------
# WarehouseView
# ---------------------------------------------------------------------------
class WarehouseView(QGraphicsView):
    """Scrollable / zoomable view of the warehouse grid.  Left-click to
    select a robot."""

    def __init__(self, scene, warehouse, on_robot_click=None, parent=None):
        super().__init__(scene, parent)
        self._warehouse = warehouse
        self._on_robot_click = on_robot_click
        self._zoom_factor = 1.0
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15
        if event.angleDelta().y() > 0:
            self.scale(factor, factor)
            self._zoom_factor *= factor
        else:
            self.scale(1 / factor, 1 / factor)
            self._zoom_factor /= factor

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._on_robot_click:
            scene_pos = self.mapToScene(event.pos())
            gx = int(scene_pos.x() // CELL_SIZE)
            gy_scene = int(scene_pos.y() // CELL_SIZE)
            # Convert scene row back to warehouse y
            gy = self._warehouse._height - 1 - gy_scene
            if 0 <= gx < self._warehouse._width and 0 <= gy < self._warehouse._height:
                robot_name = self._warehouse._position_to_robot.get((gx, gy))
                self._on_robot_click(robot_name)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# RobotInspectorPanel
# ---------------------------------------------------------------------------
class RobotInspectorPanel(QWidget):
    """Shows detailed information about the currently selected robot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        title = QLabel("Robot Inspector")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Property", "Value"])
        self._tree.setColumnWidth(0, 140)
        self._tree.setRootIsDecorated(True)
        layout.addWidget(self._tree)

    def update_robot(self, warehouse, robot_name):
        self._tree.clear()
        if robot_name is None:
            item = QTreeWidgetItem(["(no robot selected)", ""])
            self._tree.addTopLevelItem(item)
            return

        robot_obj = warehouse._robots.get(robot_name)
        if robot_obj is None:
            return

        scheduler = warehouse.get_scheduler()

        def _add(key, value):
            self._tree.addTopLevelItem(QTreeWidgetItem([str(key), str(value)]))

        _add("Name", robot_name)
        pos = robot_obj.get_position()
        _add("Position", f"({pos[0]}, {pos[1]})")

        target = robot_obj.get_target()
        if target is not None:
            tpos = target.get_position()
            _add("Target", f"{target.get_name()} ({tpos[0]},{tpos[1]})")
        else:
            _add("Target", "None")

        _add("Priority", robot_obj.get_prio())
        _add("Wait Steps", robot_obj.get_wait_steps())
        _add("Assigned Order", robot_obj.get_assigned_order())

        # Faults
        faults = []
        if robot_obj.battery_faulted_critical:
            faults.append("battery_critical")
        if robot_obj.battery_faulted:
            faults.append("battery_low")
        if robot_obj.actuators_faulted:
            faults.append("actuator")
        if robot_obj.sensors_faulted:
            faults.append("sensor")
        _add("Faults", ", ".join(faults) if faults else "None")

        # Inventory
        inv = robot_obj.report_inventory()
        inv_parent = QTreeWidgetItem(["Inventory", f"({len(inv)} items)"])
        for it in inv:
            QTreeWidgetItem(inv_parent, [it.get_name(), f"dep={it.get_dependency()}"])
        self._tree.addTopLevelItem(inv_parent)
        inv_parent.setExpanded(True)

        # Schedule queue (up to 10 entries)
        sched = scheduler._schedule.get(robot_name, deque())
        sched_list = list(sched)[:10]
        sched_parent = QTreeWidgetItem(["Schedule", f"({len(sched)} entries)"])
        for i, entry in enumerate(sched_list):
            QTreeWidgetItem(sched_parent, [f"[{i}]", str(entry)])
        if len(sched) > 10:
            QTreeWidgetItem(sched_parent, ["...", f"{len(sched) - 10} more"])
        self._tree.addTopLevelItem(sched_parent)
        sched_parent.setExpanded(True)

        # Movement path length
        path_len = len(robot_obj.get_movement_path())
        _add("Movement Path Length", str(path_len))


# ---------------------------------------------------------------------------
# OrderPanel
# ---------------------------------------------------------------------------
class OrderPanel(QWidget):
    """Shows orders grouped into Active, Backlog, and Completed categories."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        title = QLabel("Orders")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Order", "Details"])
        self._tree.setColumnWidth(0, 160)
        self._tree.setRootIsDecorated(True)
        layout.addWidget(self._tree)

    def update_orders(self, warehouse):
        self._tree.clear()
        scheduler = warehouse.get_scheduler()
        order_manager = warehouse.get_order_manager()

        # Active orders
        active_parent = QTreeWidgetItem(["Active", f"({len(scheduler._orders_active)})"])
        active_parent.setForeground(0, QBrush(QColor(0, 140, 0)))
        for order_obj in scheduler._orders_active:
            self._add_order_item(active_parent, order_obj, scheduler, "active")
        self._tree.addTopLevelItem(active_parent)
        active_parent.setExpanded(True)

        # Backlog orders
        backlog_parent = QTreeWidgetItem(["Backlog", f"({len(scheduler._orders_backlog)})"])
        backlog_parent.setForeground(0, QBrush(QColor(180, 160, 0)))
        for order_obj in scheduler._orders_backlog:
            self._add_order_item(backlog_parent, order_obj, scheduler, "backlog")
        self._tree.addTopLevelItem(backlog_parent)
        backlog_parent.setExpanded(True)

        # Completed orders
        completion_times = order_manager.get_order_finish_work_times()
        completed_parent = QTreeWidgetItem(["Completed", f"({len(completion_times)})"])
        completed_parent.setForeground(0, QBrush(QColor(120, 120, 120)))
        for order_id, step in completion_times.items():
            child = QTreeWidgetItem(completed_parent, [f"Order {order_id}", f"completed at step {step}"])
            child.setForeground(0, QBrush(QColor(120, 120, 120)))
            child.setForeground(1, QBrush(QColor(120, 120, 120)))
        self._tree.addTopLevelItem(completed_parent)
        completed_parent.setExpanded(True)

    def _add_order_item(self, parent, order_obj, scheduler, status):
        oid = order_obj.get_id()
        prio = order_obj.get_prio()
        child = QTreeWidgetItem(parent, [
            f"Order {oid} (prio {prio})",
            status,
        ])

        # Robots assigned
        robots = scheduler._order_robots_assignment.get(oid, [])
        QTreeWidgetItem(child, ["Robots", ", ".join(robots) if robots else "None"])

        # Goal assigned
        goal = scheduler._order_goal_assignment.get(oid, "None")
        QTreeWidgetItem(child, ["Goal", str(goal)])

        # Items
        items_parent = QTreeWidgetItem(child, ["Items", ""])
        for it in order_obj.get_items():
            QTreeWidgetItem(items_parent, [it.get_name(), f"dep={it.get_dependency()}"])


# ---------------------------------------------------------------------------
# SimulationGUI (main window)
# ---------------------------------------------------------------------------
class SimulationGUI(QMainWindow):
    """Main window that ties the scene, view, panels, and controls together."""

    def __init__(self, warehouse, parent=None):
        super().__init__(parent)
        self._warehouse = warehouse
        self._selected_robot = None
        self._sim_running = False
        self._sim_finished = False
        self._step_counter = 0
        self._timer_interval_ms = 200

        self.setWindowTitle("MRWS Debug GUI")
        self.resize(1200, 800)

        # -- Scene / View --
        self._scene = WarehouseScene(warehouse)
        self._view = WarehouseView(self._scene, warehouse,
                                    on_robot_click=self._on_robot_click)
        self.setCentralWidget(self._view)

        # -- Right dock: Robot Inspector --
        self._robot_panel = RobotInspectorPanel()
        dock_robot = QDockWidget("Robot Inspector", self)
        dock_robot.setWidget(self._robot_panel)
        dock_robot.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_robot)

        # -- Right dock (below): Order Panel --
        self._order_panel = OrderPanel()
        dock_orders = QDockWidget("Orders", self)
        dock_orders.setWidget(self._order_panel)
        dock_orders.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_orders)

        # -- Bottom toolbar --
        self._build_toolbar()

        # -- Timer --
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)

        # Initial draw
        self.refresh_display()

    # -- toolbar -------------------------------------------------------------

    def _build_toolbar(self):
        toolbar = QToolBar("Controls", self)
        toolbar.setMovable(False)
        self.addToolBar(Qt.ToolBarArea.BottomToolBarArea, toolbar)

        self._btn_play = QPushButton("Play")
        self._btn_play.clicked.connect(self._on_play)
        toolbar.addWidget(self._btn_play)

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.clicked.connect(self._on_pause)
        toolbar.addWidget(self._btn_pause)

        self._btn_step = QPushButton("Step")
        self._btn_step.clicked.connect(self._on_step)
        toolbar.addWidget(self._btn_step)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" Speed: "))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(10)
        self._speed_slider.setMaximum(1000)
        self._speed_slider.setValue(self._timer_interval_ms)
        self._speed_slider.setFixedWidth(150)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        toolbar.addWidget(self._speed_slider)

        self._speed_label = QLabel(f" {self._timer_interval_ms}ms ")
        toolbar.addWidget(self._speed_label)

        toolbar.addSeparator()

        self._step_label = QLabel(" Step: 0 ")
        self._step_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self._step_label)

        self._status_label = QLabel(" Status: Paused ")
        toolbar.addWidget(self._status_label)

    # -- callbacks -----------------------------------------------------------

    def _on_play(self):
        if self._sim_finished:
            return
        self._sim_running = True
        self._status_label.setText(" Status: Running ")
        self._timer.start(self._timer_interval_ms)

    def _on_pause(self):
        self._sim_running = False
        self._status_label.setText(" Status: Paused ")
        self._timer.stop()

    def _on_step(self):
        if self._sim_finished:
            return
        self._do_simulation_step()

    def _on_speed_changed(self, value):
        self._timer_interval_ms = value
        self._speed_label.setText(f" {value}ms ")
        if self._timer.isActive():
            self._timer.setInterval(value)

    def _on_timer_tick(self):
        if self._sim_finished:
            self._timer.stop()
            return
        self._do_simulation_step()

    def _on_robot_click(self, robot_name):
        """Called when the user clicks on the grid; robot_name may be None."""
        self._selected_robot = robot_name
        self.refresh_display()

    # -- simulation step -----------------------------------------------------

    def _do_simulation_step(self):
        try:
            done = self._warehouse.step()
        except Exception as exc:
            self._sim_finished = True
            self._timer.stop()
            self._status_label.setText(f" Status: ERROR - {exc} ")
            self.refresh_display()
            return

        self._step_counter = self._warehouse.get_total_steps()

        if done:
            self._sim_finished = True
            self._timer.stop()
            self._status_label.setText(" Status: Completed ")

        self.refresh_display()

    # -- display refresh -----------------------------------------------------

    def refresh_display(self):
        self._scene.rebuild(self._selected_robot)
        self._robot_panel.update_robot(self._warehouse, self._selected_robot)
        self._order_panel.update_orders(self._warehouse)
        self._step_label.setText(f" Step: {self._step_counter} ")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def launch_gui(warehouse):
    """Create a QApplication, show the SimulationGUI window, and run the
    event loop.  Call this from main.py when ``--gui`` is passed."""
    app = QApplication(sys.argv)
    window = SimulationGUI(warehouse)
    window.show()
    sys.exit(app.exec())
