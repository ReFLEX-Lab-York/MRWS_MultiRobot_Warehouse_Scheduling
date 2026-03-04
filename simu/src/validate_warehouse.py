"""Structural validator for MRWS warehouse files.

Usage:
    python validate_warehouse.py path/to/warehouse.txt [--items N]
    python validate_warehouse.py --scan-all [--sim]

Checks:
    - File exists and is readable
    - Grid is rectangular (all rows same width)
    - All characters are valid (R, S, G, X, W)
    - At least 1 robot, 1 goal, 1 shelf present
    - If --items given, shelf count matches

Exit codes: 0 = valid, 1 = invalid
"""

import argparse
import glob
import os
import sys

VALID_CHARS = {'R', 'S', 'G', 'X', 'W'}


def validate_warehouse(filepath, expected_items=None):
    """Validate a warehouse file and return (errors, stats).

    Args:
        filepath: Path to the warehouse text file.
        expected_items: If set, shelf count must equal this number.

    Returns:
        Tuple of (list of error strings, dict of stats).
    """
    errors = []
    stats = {'robots': 0, 'shelves': 0, 'goals': 0, 'walls': 0, 'width': 0, 'height': 0}

    try:
        with open(filepath) as f:
            lines = [line.rstrip('\n') for line in f.readlines()]
    except FileNotFoundError:
        return [f"File not found: {filepath}"], stats
    except OSError as e:
        return [f"Cannot read file: {e}"], stats

    lines = [l for l in lines if l]  # drop blank lines
    if not lines:
        return ["File is empty"], stats

    stats['height'] = len(lines)
    stats['width'] = len(lines[0])

    for row_idx, line in enumerate(lines):
        if len(line) != stats['width']:
            errors.append(
                f"Row {row_idx} has width {len(line)}, expected {stats['width']}"
            )
        for col_idx, ch in enumerate(line):
            if ch not in VALID_CHARS:
                errors.append(
                    f"Invalid character '{ch}' at row {row_idx}, col {col_idx}"
                )
            elif ch == 'R':
                stats['robots'] += 1
            elif ch == 'S':
                stats['shelves'] += 1
            elif ch == 'G':
                stats['goals'] += 1
            elif ch == 'W':
                stats['walls'] += 1

    if stats['robots'] == 0:
        errors.append("No robots (R) found")
    if stats['goals'] == 0:
        errors.append("No goals (G) found")
    if stats['shelves'] == 0:
        errors.append("No shelves (S) found")

    if expected_items is not None and stats['shelves'] != expected_items:
        errors.append(
            f"Shelf count ({stats['shelves']}) does not match --items ({expected_items})"
        )

    return errors, stats


def print_report(filepath, errors, stats):
    """Print a human-readable validation report."""
    print(f"Warehouse: {filepath}")
    print(f"Size:      {stats['width']} x {stats['height']}")
    print(f"Robots:    {stats['robots']}")
    print(f"Shelves:   {stats['shelves']}")
    print(f"Goals:     {stats['goals']}")
    print(f"Walls:     {stats['walls']}")

    if errors:
        print(f"Status:    INVALID")
        for err in errors:
            print(f"  FAIL: {err}")
    else:
        print(f"Status:    VALID")


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def scan_all_warehouses(data_dir=None, run_sim=False, schedule_mode="multi-robot",
                        step_limit=5000):
    """Scan all warehouse .txt files in data_dir and print a summary table.

    Args:
        data_dir: Directory to scan. Defaults to simu/data/.
        run_sim: If True, run a quick simulation on each file and report steps.
        schedule_mode: Scheduling mode for simulations.
        step_limit: Max steps before considering the sim failed.
    """
    if data_dir is None:
        data_dir = DATA_DIR

    files = sorted(glob.glob(os.path.join(data_dir, "*.txt")))
    if not files:
        print(f"No .txt files found in {data_dir}")
        return

    rows = []
    for filepath in files:
        errors, stats = validate_warehouse(filepath)
        name = os.path.basename(filepath)
        size = f"{stats['width']}x{stats['height']}"
        sim_steps = ""

        if run_sim and not errors:
            sim_steps = _run_quick_sim(filepath, stats['shelves'], schedule_mode,
                                       step_limit)

        rows.append({
            'file': name,
            'size': size,
            'robots': stats['robots'],
            'shelves': stats['shelves'],
            'goals': stats['goals'],
            'valid': len(errors) == 0,
            'sim_steps': sim_steps,
        })

    _print_table(rows, run_sim)


def _run_quick_sim(filepath, num_items, schedule_mode, step_limit):
    """Run a single simulation and return the step count or error string."""
    os.environ.setdefault("ROBOTSIM_TRANSMIT", "False")
    # Import here to avoid circular dependency at module level
    from main import Simulation
    try:
        sim = Simulation(1, filepath, num_items, 3, schedule_mode,
                         [0, 0, 0, 0], True, step_limit)
        sim.run_simulation(True, False)
        if sim.step_amounts:
            return str(sim.step_amounts[0])
        return "ERR"
    except Exception as e:
        return "ERR"


def _print_table(rows, show_sim):
    """Print a formatted table of warehouse info."""
    # Column definitions: (header, key, min_width)
    cols = [
        ("File", "file", 4),
        ("Size", "size", 4),
        ("Robots", "robots", 6),
        ("Shelves", "shelves", 7),
        ("Goals", "goals", 5),
        ("Valid", "valid", 5),
    ]
    if show_sim:
        cols.append(("Sim Steps", "sim_steps", 9))

    # Compute column widths
    widths = []
    for header, key, min_w in cols:
        w = max(min_w, len(header))
        for row in rows:
            val = row[key]
            w = max(w, len(str(val)))
        widths.append(w)

    def hline(left, mid, right, fill="─"):
        parts = [fill * (w + 2) for w in widths]
        return left + mid.join(parts) + right

    def data_line(values):
        cells = []
        for val, w in zip(values, widths):
            cells.append(f" {str(val):<{w}} ")
        return "│" + "│".join(cells) + "│"

    # Print table
    print(hline("┌", "┬", "┐"))
    headers = [h for h, _, _ in cols]
    print(data_line(headers))
    print(hline("├", "┼", "┤"))
    for i, row in enumerate(rows):
        values = []
        for _, key, _ in cols:
            val = row[key]
            if key == "valid":
                val = "YES" if val else "NO"
            values.append(val)
        print(data_line(values))
        if i < len(rows) - 1:
            print(hline("├", "┼", "┤"))
    print(hline("└", "┴", "┘"))


def main():
    parser = argparse.ArgumentParser(description="Validate an MRWS warehouse file.")
    parser.add_argument("warehouse", nargs="?", default=None,
                        help="Path to warehouse text file")
    parser.add_argument(
        "--items", type=int, default=None,
        help="Expected number of shelves/items (checks exact match)"
    )
    parser.add_argument(
        "--scan-all", action="store_true",
        help="Scan all warehouse files in data/ and print summary table"
    )
    parser.add_argument(
        "--sim", action="store_true",
        help="With --scan-all, run a quick simulation on each valid warehouse"
    )
    parser.add_argument(
        "--mode", type=str, default="multi-robot",
        choices=["simple", "simple-interrupt", "multi-robot", "multi-robot-genetic"],
        help="Scheduling mode for --sim (default: multi-robot)"
    )
    args = parser.parse_args()

    if args.scan_all:
        scan_all_warehouses(run_sim=args.sim, schedule_mode=args.mode)
    elif args.warehouse:
        errors, stats = validate_warehouse(args.warehouse, args.items)
        print_report(args.warehouse, errors, stats)
        sys.exit(1 if errors else 0)
    else:
        parser.error("Provide a warehouse file or use --scan-all")


if __name__ == "__main__":
    main()
