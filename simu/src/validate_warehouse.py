"""Structural validator for MRWS warehouse files.

Usage:
    python validate_warehouse.py path/to/warehouse.txt [--items N]

Checks:
    - File exists and is readable
    - Grid is rectangular (all rows same width)
    - All characters are valid (R, S, G, X, W)
    - At least 1 robot, 1 goal, 1 shelf present
    - If --items given, shelf count matches

Exit codes: 0 = valid, 1 = invalid
"""

import argparse
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


def main():
    parser = argparse.ArgumentParser(description="Validate an MRWS warehouse file.")
    parser.add_argument("warehouse", help="Path to warehouse text file")
    parser.add_argument(
        "--items", type=int, default=None,
        help="Expected number of shelves/items (checks exact match)"
    )
    args = parser.parse_args()

    errors, stats = validate_warehouse(args.warehouse, args.items)
    print_report(args.warehouse, errors, stats)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
