# Warehouse Generation & Validation Tools Design

## Problem

The existing `gen_nxn_warehouse()` in `main.py` produces poor layouts (robots packed in top rows, goals = robot count, no cross-aisles, no validation). There is no standalone verification tool.

## Decision

Two new standalone scripts in `simu/src/`:

### `generate_warehouse.py`

CLI: `python generate_warehouse.py --size 50 --robots 20 --items 30 --goals 5 -o ../data/out.txt`

Zone-based layout algorithm:
- **Left staging zone (cols 1-2):** Goals in col 1, robot homes in col 2, spread vertically
- **Main aisle (cols 3-4):** Open vertical corridor
- **Shelf zone (cols 5+):** Repeating `SS|` pattern (2 shelf cols + 1 aisle col). Shelves distributed evenly until `num_items` reached
- **Horizontal cross-aisles:** Every ~12 rows, full row of `X`
- **Border:** Row 0 and row N-1 all `X`

Runs structural validation on output before writing.

### `validate_warehouse.py`

CLI: `python validate_warehouse.py path/to/file.txt [--items N]`

Structural checks:
1. File exists and is readable
2. Grid is rectangular
3. All characters valid (R, S, G, X, W)
4. At least 1 robot, 1 goal, 1 shelf
5. If `--items` given, shelf count == items

Prints summary table, exits 0 (valid) or 1 (invalid).

## Primary use case

Batch performance testing — fast deterministic generation of valid warehouses.
