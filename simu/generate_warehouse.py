"""Generate MRWS warehouse files with zone-based layouts.

Usage:
    python generate_warehouse.py --size 50 --robots 20 [--items 30] [--goals 5] [-o path]

Layout zones (left to right):
    - Col 0:     Border (X)
    - Col 1:     Goals, spread vertically
    - Col 2:     Robot homes, spread vertically
    - Cols 3-4:  Main vertical aisle
    - Cols 5+:   Shelf pairs (SS) separated by aisle columns (X)
    - Last col:  Border (X)

Horizontal cross-aisles are inserted at scaled intervals.
Row 0 and row N-1 are all-X borders.
"""

import argparse
import os
import sys

from validate_warehouse import validate_warehouse, print_report

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def generate_warehouse(side_len, robot_num, num_items=None, num_goals=None, output=None):
    """Generate an NxN warehouse file with the given parameters.

    Args:
        side_len: Width and height of the square grid.
        robot_num: Number of robots to place.
        num_items: Number of shelves. Defaults to ~70% of shelf capacity.
        num_goals: Number of goal/order stations. Defaults to robot_num (1 per robot).
        output: Output file path. Defaults to DATA_DIR/wt{N}x{N}r{R}.txt.

    Returns:
        The output file path.

    Raises:
        ValueError: If the warehouse is too small for the requested entities.
    """
    if num_goals is None:
        num_goals = max(robot_num, 1)

    if output is None:
        output = os.path.join(DATA_DIR, f"wt{side_len}x{side_len}r{robot_num}.txt")

    if side_len < 7:
        raise ValueError("Minimum warehouse size is 7x7")

    # Interior rows available (exclude top/bottom border rows)
    interior_rows = side_len - 2  # rows 1 .. side_len-2

    if robot_num > interior_rows:
        raise ValueError(
            f"Cannot fit {robot_num} robots in {interior_rows} interior rows "
            f"(max 1 per row in staging column)"
        )
    if num_goals > interior_rows:
        raise ValueError(
            f"Cannot fit {num_goals} goals in {interior_rows} interior rows"
        )

    # --- Build the grid ---
    grid = [['X'] * side_len for _ in range(side_len)]

    # Cross-aisle interval scales with warehouse size
    cross_aisle_interval = min(12, max(6, side_len // 6))
    cross_aisle_rows = {0, side_len - 1}
    row = cross_aisle_interval
    while row < side_len - 1:
        cross_aisle_rows.add(row)
        row += cross_aisle_interval

    # Placeable rows (interior, non-cross-aisle)
    placeable_rows = [r for r in range(1, side_len - 1) if r not in cross_aisle_rows]

    # --- Place goals in col 1 ---
    goal_positions = _spread_positions(placeable_rows, num_goals)
    for r in goal_positions:
        grid[r][1] = 'G'

    # --- Place robots in col 2 ---
    robot_positions = _spread_positions(placeable_rows, robot_num)
    for r in robot_positions:
        grid[r][2] = 'R'

    # --- Determine shelf columns (SS|X pattern from col 5+) ---
    shelf_col_pairs = []
    c = 5
    while c + 1 < side_len - 1:
        shelf_col_pairs.append((c, c + 1))
        c += 3  # 2 shelf cols + 1 aisle col

    # Shelf rows: interior rows that aren't cross-aisles
    shelf_rows = [r for r in range(1, side_len - 1) if r not in cross_aisle_rows]
    max_shelf_capacity = len(shelf_rows) * len(shelf_col_pairs) * 2

    if max_shelf_capacity == 0:
        raise ValueError(f"No shelf positions available in a {side_len}x{side_len} warehouse")

    # Default num_items: ~70% of shelf capacity
    if num_items is None:
        num_items = max(int(max_shelf_capacity * 0.7), 1)

    if max_shelf_capacity < num_items:
        raise ValueError(
            f"Cannot fit {num_items} shelves in a {side_len}x{side_len} warehouse "
            f"(only {max_shelf_capacity} shelf positions available)"
        )

    # --- Place shelves densely: fill column pairs top-to-bottom ---
    placed = 0
    for c1, c2 in shelf_col_pairs:
        for r in shelf_rows:
            if placed >= num_items:
                break
            grid[r][c1] = 'S'
            placed += 1
            if placed >= num_items:
                break
            grid[r][c2] = 'S'
            placed += 1
        if placed >= num_items:
            break

    # --- Write the file ---
    # File format: first line = highest y (row side_len-1), last line = y=0
    with open(output, 'w') as f:
        for r in range(side_len - 1, -1, -1):
            f.write(''.join(grid[r]))
            if r > 0:
                f.write('\n')
        f.write('\n')

    # --- Validate output ---
    errors, stats = validate_warehouse(output, expected_items=num_items)
    if errors:
        print_report(output, errors, stats)
        os.remove(output)
        raise RuntimeError(f"Generated warehouse failed validation: {errors}")

    print_report(output, errors, stats)
    return output


def _spread_positions(positions, count):
    """Select `count` items from `positions`, spread as evenly as possible.

    Returns a list of selected items from `positions`.
    """
    n = len(positions)
    if count > n:
        raise ValueError(f"Cannot select {count} from {n} available positions")
    if count == n:
        return list(positions)
    if count == 1:
        return [positions[n // 2]]
    # Evenly spaced indices
    return [positions[round(i * (n - 1) / (count - 1))] for i in range(count)]


def main():
    parser = argparse.ArgumentParser(
        description="Generate an MRWS warehouse file with zone-based layout."
    )
    parser.add_argument("--size", type=int, required=True, help="Side length (NxN)")
    parser.add_argument("--robots", type=int, required=True, help="Number of robots")
    parser.add_argument(
        "--items", type=int, default=None,
        help="Number of shelves/items (default: ~70%% of shelf capacity)"
    )
    parser.add_argument(
        "--goals", type=int, default=None,
        help="Number of goal stations (default: robots // 4, min 1)"
    )
    parser.add_argument("-o", "--output", default=None, help="Output file path")
    args = parser.parse_args()

    generate_warehouse(args.size, args.robots, args.items, args.goals, args.output)


if __name__ == "__main__":
    main()
