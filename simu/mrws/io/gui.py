"""
PyQt6 Debug GUI for the MRWS Warehouse Simulator.

Provides a real-time visual debugger for the warehouse simulation, including
a grid display, robot inspector, and order panel.
"""

import sys
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
    QLabel,
    QDockWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QCheckBox,
    QSlider,
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
    QKeyEvent,
    QPaintEvent,
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

    def keyPressEvent(self, event: QKeyEvent):
        """Forward shortcut keys to the main window."""
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_S, Qt.Key.Key_R):
            self.window().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

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
# StatsChartWidget  (used inside the Stats dock panel)
# ---------------------------------------------------------------------------
class StatsChartWidget(QWidget):
    """Draws a line chart of simulation metrics over steps."""

    _PADDING = 6
    _Y_AXIS_W = 36   # width reserved for y-axis labels
    _X_AXIS_H = 18   # height reserved for x-axis labels

    _COLOR_ACTIVE = QColor(50, 180, 50)
    _COLOR_BACKLOG = QColor(200, 170, 30)
    _COLOR_COMPLETED = QColor(130, 130, 130)
    _COLOR_IDLE = QColor(50, 120, 220)
    _COLOR_FAULTED = QColor(220, 50, 50)
    _COLOR_CARRYING = QColor(0, 190, 190)

    _SERIES_INFO = [
        ("_history_active", _COLOR_ACTIVE, "Active"),
        ("_history_backlog", _COLOR_BACKLOG, "Backlog"),
        ("_history_completed", _COLOR_COMPLETED, "Done"),
        ("_history_idle", _COLOR_IDLE, "Idle"),
        ("_history_faulted", _COLOR_FAULTED, "Faulted"),
        ("_history_carrying", _COLOR_CARRYING, "Carrying"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history_active = []
        self._history_backlog = []
        self._history_completed = []
        self._history_idle = []
        self._history_faulted = []
        self._history_carrying = []
        # All series visible by default
        self._visible = {attr for attr, _, _ in self._SERIES_INFO}
        self.setMinimumHeight(100)

    def set_visible(self, attr, on):
        """Toggle visibility of a series by its attribute name."""
        if on:
            self._visible.add(attr)
        else:
            self._visible.discard(attr)
        self.update()

    def reset(self):
        for attr, _, _ in self._SERIES_INFO:
            getattr(self, attr).clear()
        self.update()

    def record(self, warehouse):
        scheduler = warehouse.get_scheduler()
        order_manager = warehouse.get_order_manager()
        robots = warehouse._robots
        num_robots = len(robots)
        assigned = len(scheduler._assigned_robots)

        # Count faulted robots and total items being carried
        faulted = 0
        carrying = 0
        for robot_obj in robots.values():
            if (robot_obj.battery_faulted_critical or robot_obj.battery_faulted
                    or robot_obj.actuators_faulted or robot_obj.sensors_faulted):
                faulted += 1
            carrying += robot_obj.get_inventory_usage()

        self._history_active.append(len(scheduler._orders_active))
        self._history_backlog.append(len(scheduler._orders_backlog))
        self._history_completed.append(len(order_manager.get_order_finish_work_times()))
        self._history_idle.append(num_robots - assigned)
        self._history_faulted.append(faulted)
        self._history_carrying.append(carrying)
        self.update()

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        pad = self._PADDING

        # Chart area bounds
        cx = pad + self._Y_AXIS_W
        cy = pad
        cw = w - cx - pad
        ch = h - cy - pad - self._X_AXIS_H

        if cw < 30 or ch < 30:
            p.end()
            return

        # Background
        p.setBrush(QBrush(QColor(250, 250, 250)))
        p.setPen(QPen(QColor(200, 200, 200), 1))
        p.drawRect(cx, cy, cw, ch)

        n = len(self._history_active)
        if n == 0:
            p.setPen(QPen(QColor(150, 150, 150)))
            p.setFont(QFont("Monospace", 8))
            p.drawText(cx + 8, cy + ch // 2, "No data yet")
            p.end()
            return

        # Y-axis max (only from visible series)
        visible_maxes = [
            max(getattr(self, attr))
            for attr, _, _ in self._SERIES_INFO
            if attr in self._visible and getattr(self, attr)
        ]
        raw_max = max(max(visible_maxes) if visible_maxes else 0, 1)
        y_max = self._nice_ceil(raw_max)

        # Horizontal grid lines + y-axis labels
        font_small = QFont("Monospace", 7)
        p.setFont(font_small)
        num_y_ticks = 4
        for i in range(num_y_ticks + 1):
            frac = i / num_y_ticks
            gy = cy + ch - int(ch * frac)
            if 0 < i < num_y_ticks + 1:
                p.setPen(QPen(QColor(220, 220, 220), 1, Qt.PenStyle.DotLine))
                p.drawLine(cx, gy, cx + cw, gy)
            val = int(y_max * frac)
            p.setPen(QPen(QColor(100, 100, 100)))
            p.drawText(pad, gy + 4, str(val))

        # X-axis: step labels
        x_denom = max(n - 1, 1)
        num_ticks = min(5, n)
        if num_ticks >= 2:
            for i in range(num_ticks):
                step_idx = int(i * (n - 1) / (num_ticks - 1))
                lx = cx + int(step_idx / x_denom * cw)
                # Vertical grid line
                p.setPen(QPen(QColor(220, 220, 220), 1, Qt.PenStyle.DotLine))
                p.drawLine(lx, cy, lx, cy + ch)
                # Label
                p.setPen(QPen(QColor(100, 100, 100)))
                p.setFont(font_small)
                label = str(step_idx + 1)
                p.drawText(max(lx - 10, cx), cy + ch + 12, label)

        # Downsample: keep at most `max_pts` points per series.
        # For each bucket, keep the min and max to preserve spikes.
        max_pts = max(int(cw // 2), 40)
        if n > max_pts:
            bucket_size = n / max_pts
            buckets = []
            for b in range(max_pts):
                lo = int(b * bucket_size)
                hi = min(int((b + 1) * bucket_size), n)
                buckets.append((lo, hi))
        else:
            buckets = None

        # Draw series using individual line segments (avoids QPainterPath
        # anti-aliasing artifacts that can produce visual gaps).
        for attr, color, _label in self._SERIES_INFO:
            if attr not in self._visible:
                continue
            data = getattr(self, attr)
            if not data:
                continue
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)

            # Build the list of (index, value) to plot
            if buckets is not None:
                points = []
                for lo, hi in buckets:
                    chunk = data[lo:hi]
                    min_val = min(chunk)
                    max_val = max(chunk)
                    min_idx = lo + chunk.index(min_val)
                    max_idx = lo + chunk.index(max_val)
                    if min_idx <= max_idx:
                        points.append((min_idx, min_val))
                        if min_idx != max_idx:
                            points.append((max_idx, max_val))
                    else:
                        points.append((max_idx, max_val))
                        points.append((min_idx, min_val))
                # Always include last point
                points.append((n - 1, data[-1]))
            else:
                points = [(i, data[i]) for i in range(n)]

            # Draw connected line segments
            prev_x = prev_y = None
            for idx, val in points:
                x = cx + (idx / x_denom) * cw
                y = cy + ch - (val / y_max) * ch
                if prev_x is not None:
                    p.drawLine(QPointF(prev_x, prev_y), QPointF(x, y))
                prev_x, prev_y = x, y

        # Legend (top-left inside chart, with background) — only visible series
        visible_series = [(a, c, l) for a, c, l in self._SERIES_INFO if a in self._visible]
        if visible_series:
            row_h = 12
            lx = cx + 4
            ly = cy + 4
            lw = 80
            lh = len(visible_series) * row_h + 6
            p.setPen(QPen(QColor(200, 200, 200)))
            p.setBrush(QBrush(QColor(255, 255, 255, 220)))
            p.drawRect(lx, ly, lw, lh)
            p.setFont(font_small)
            for i, (_attr, color, label) in enumerate(visible_series):
                row_y = ly + 3 + i * row_h
                p.setPen(QPen(color, 2))
                p.drawLine(lx + 3, row_y + 5, lx + 14, row_y + 5)
                p.setPen(QPen(QColor(40, 40, 40)))
                p.drawText(lx + 18, row_y + 9, label)

        p.end()

    @staticmethod
    def _nice_ceil(value):
        """Round up to a 'nice' number for axis ticks."""
        if value <= 0:
            return 1
        import math
        mag = 10 ** math.floor(math.log10(value))
        residual = value / mag
        if residual <= 1:
            nice = 1
        elif residual <= 2:
            nice = 2
        elif residual <= 5:
            nice = 5
        else:
            nice = 10
        return int(nice * mag)


# ---------------------------------------------------------------------------
# StatsPanel  (dock panel wrapping the chart)
# ---------------------------------------------------------------------------
class StatsPanel(QWidget):
    """Dock panel containing toggles, chart, and a summary row."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # Toggle checkboxes for each series
        toggles_layout = QHBoxLayout()
        toggles_layout.setContentsMargins(2, 0, 2, 0)
        toggles_layout.setSpacing(6)
        self._chart = StatsChartWidget()
        for attr, color, label in StatsChartWidget._SERIES_INFO:
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            cb.setStyleSheet(f"color: {color.name()}; font-size: 10px;")
            cb.toggled.connect(lambda on, a=attr: self._chart.set_visible(a, on))
            toggles_layout.addWidget(cb)
        toggles_layout.addStretch()
        layout.addLayout(toggles_layout)

        layout.addWidget(self._chart, stretch=1)

        self._summary = QLabel("")
        self._summary.setStyleSheet(
            "font-size: 10px; color: #444; padding: 2px 4px;"
            "background: #f6f6f6; border-top: 1px solid #ddd;"
        )
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

    def record(self, warehouse):
        self._chart.record(warehouse)
        self._update_summary(warehouse)

    def reset(self):
        self._chart.reset()
        self._summary.setText("")

    def _update_summary(self, warehouse):
        scheduler = warehouse.get_scheduler()
        order_manager = warehouse.get_order_manager()
        robots = warehouse._robots
        num_robots = len(robots)
        step = warehouse.get_total_steps()

        # Utilization: fraction of robots currently assigned
        assigned = len(scheduler._assigned_robots)
        util_pct = int(100 * assigned / num_robots) if num_robots else 0

        # Completed count
        completed = order_manager.get_order_finish_work_times()
        n_done = len(completed)

        # Throughput: orders completed per 100 steps
        throughput = (n_done / step * 100) if step > 0 else 0

        # Average completion time
        if completed:
            intro = order_manager._order_intro_times
            avg_time = sum(
                ct - intro.get(oid, 0) for oid, ct in completed.items()
            ) / n_done
        else:
            avg_time = 0

        # Faults
        faults = sum(
            1 for r in robots.values()
            if r.battery_faulted_critical or r.battery_faulted
            or r.actuators_faulted or r.sensors_faulted
        )

        # Total items in transit
        carrying = sum(r.get_inventory_usage() for r in robots.values())

        parts = [
            f"Util: {util_pct}%",
            f"Done: {n_done}",
            f"Thru: {throughput:.1f}/100s",
            f"Avg: {avg_time:.0f}s",
            f"Faults: {faults}",
            f"Carry: {carrying}",
        ]
        self._summary.setText("  |  ".join(parts))


# ---------------------------------------------------------------------------
# SimulationGUI (main window)
# ---------------------------------------------------------------------------
class SimulationGUI(QMainWindow):
    """Main window that ties the scene, view, panels, and controls together."""

    def __init__(self, warehouse, warehouse_factory=None, parent=None):
        super().__init__(parent)
        self._warehouse = warehouse
        self._warehouse_factory = warehouse_factory
        self._selected_robot = None
        self._sim_running = False
        self._sim_finished = False
        self._step_counter = 0

        # Speed presets: (label, timer interval in ms)
        # 1.0x = 200ms base interval
        self._speed_presets = [
            ("0.1x", 2000),
            ("0.2x", 1000),
            ("0.5x", 400),
            ("1.0x", 200),
            ("2.0x", 100),
            ("5.0x", 40),
            ("10.0x", 20),
        ]
        self._speed_index = 3  # default 1.0x
        self._timer_interval_ms = self._speed_presets[self._speed_index][1]

        self.setWindowTitle("MRWS GUI")
        self.showMaximized()

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

        # -- Right dock (bottom): Stats Panel --
        self._stats_panel = StatsPanel()
        dock_stats = QDockWidget("Stats", self)
        dock_stats.setWidget(self._stats_panel)
        dock_stats.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_stats)

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
        self._btn_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_play.clicked.connect(self._on_play)
        toolbar.addWidget(self._btn_play)

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_pause.clicked.connect(self._on_pause)
        toolbar.addWidget(self._btn_pause)

        self._btn_step = QPushButton("Step")
        self._btn_step.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_step.clicked.connect(self._on_step)
        toolbar.addWidget(self._btn_step)

        self._btn_reset = QPushButton("Reset")
        self._btn_reset.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._btn_reset.clicked.connect(self._on_reset)
        self._btn_reset.setEnabled(self._warehouse_factory is not None)
        toolbar.addWidget(self._btn_reset)

        toolbar.addSeparator()

        toolbar.addWidget(QLabel(" Speed: "))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._speed_slider.setMinimum(0)
        self._speed_slider.setMaximum(len(self._speed_presets) - 1)
        self._speed_slider.setValue(self._speed_index)
        self._speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._speed_slider.setTickInterval(1)
        self._speed_slider.setFixedWidth(150)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        toolbar.addWidget(self._speed_slider)

        self._speed_label = QLabel(f" {self._speed_presets[self._speed_index][0]} ")
        self._speed_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self._speed_label)

        toolbar.addSeparator()

        self._step_label = QLabel(" Step: 0 ")
        self._step_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self._step_label)

        self._status_label = QLabel(" Status: Paused ")
        toolbar.addWidget(self._status_label)

        # Initial button highlight
        self._update_button_styles()

    # -- button styling ------------------------------------------------------

    _STYLE_PLAYING = "background-color: #2eaa2e; color: white; font-weight: bold;"
    _STYLE_PAUSED = "background-color: #ccaa00; color: white; font-weight: bold;"
    _STYLE_NORMAL = ""

    def _update_button_styles(self):
        """Highlight only the active state button."""
        if self._sim_running:
            self._btn_play.setStyleSheet(self._STYLE_PLAYING)
            self._btn_pause.setStyleSheet(self._STYLE_NORMAL)
            self._status_label.setText(" Status: Running ")
        else:
            self._btn_play.setStyleSheet(self._STYLE_NORMAL)
            self._btn_pause.setStyleSheet(self._STYLE_PAUSED)
            self._status_label.setText(" Status: Paused ")

    # -- keyboard shortcuts --------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Space:
            if self._sim_running:
                self._on_pause()
            else:
                self._on_play()
        elif key == Qt.Key.Key_S:
            self._on_step()
        elif key == Qt.Key.Key_R:
            self._on_reset()
        else:
            super().keyPressEvent(event)

    # -- callbacks -----------------------------------------------------------

    def _on_play(self):
        if self._sim_finished:
            return
        self._sim_running = True
        self._timer.start(self._timer_interval_ms)
        self._update_button_styles()

    def _on_pause(self):
        self._sim_running = False
        self._timer.stop()
        self._update_button_styles()

    def _on_step(self):
        if self._sim_finished:
            return
        self._do_simulation_step()

    def _on_reset(self):
        if self._warehouse_factory is None:
            return
        self._timer.stop()
        self._sim_running = False
        self._sim_finished = False
        self._step_counter = 0
        self._selected_robot = None
        self._warehouse = self._warehouse_factory()
        self._scene._warehouse = self._warehouse
        self._scene._width = self._warehouse._width
        self._scene._height = self._warehouse._height
        self._view._warehouse = self._warehouse
        self._stats_panel.reset()
        self._update_button_styles()
        self.refresh_display()

    def _on_speed_changed(self, index):
        self._speed_index = index
        self._timer_interval_ms = self._speed_presets[index][1]
        self._speed_label.setText(f" {self._speed_presets[index][0]} ")
        if self._timer.isActive():
            self._timer.setInterval(self._timer_interval_ms)

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
        self._stats_panel.record(self._warehouse)

        if done:
            self._sim_finished = True
            self._sim_running = False
            self._timer.stop()
            self._status_label.setText(" Status: Completed ")
            self._btn_play.setStyleSheet(self._STYLE_NORMAL)
            self._btn_pause.setStyleSheet(self._STYLE_NORMAL)

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
def launch_gui(warehouse, warehouse_factory=None):
    """Create a QApplication, show the SimulationGUI window, and run the
    event loop.  Call this from main.py when ``--gui`` is passed.

    *warehouse_factory*, if provided, is a callable that returns a fresh
    ``Warehouse`` instance with the same parameters.  This enables the
    Reset button.
    """
    app = QApplication(sys.argv)
    window = SimulationGUI(warehouse, warehouse_factory=warehouse_factory)
    window.show()
    sys.exit(app.exec())
