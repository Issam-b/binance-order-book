#!/usr/bin/env python3

import requests
import argparse
import sys
import math
from collections import defaultdict

def parse_group_size(gs_str: str) -> (float, int):
    """
    Convert the user-supplied group_size string to:
      1) a float value
      2) a decimal precision (number of decimals) based on the input

    Examples:
      "1"       -> (1.0, 0)   # integer => no decimals
      "1.0"     -> (1.0, 0)   # trailing zero => effectively integer
      "0.1"     -> (0.1, 1)
      "2.50"    -> (2.5, 1)
      "0.25"    -> (0.25, 2)
      "0.0010"  -> (0.001, 3)
    """
    val = float(gs_str)
    s = gs_str.rstrip('0').rstrip('.')
    if '.' in s:
        decimals_count = len(s.split('.')[1])
    else:
        decimals_count = 0
    return val, decimals_count

def group_price(price_str, group_size_float):
    """
    Group a floating price into buckets of size group_size_float (which may be float).

    e.g., if group_size=0.1,  price=3.14 => floor(3.14/0.1)=31 => 31*0.1=3.1
    """
    price = float(price_str)
    return math.floor(price / group_size_float) * group_size_float

def format_quantity(q):
    """
    Convert a numeric quantity into a string with k, M, or B suffixes.
    Otherwise, up to 2 decimals, removing trailing zeros.
    """
    if q >= 1_000_000_000:
        return f"{q/1_000_000_000:.2f}B"
    elif q >= 1_000_000:
        return f"{q/1_000_000:.2f}M"
    elif q >= 1_000:
        return f"{q/1_000:.2f}k"
    else:
        return f"{q:.2f}".rstrip("0").rstrip(".")

def print_side_by_side(title, sorted_by_price, sorted_by_qty, group_size_decimals):
    """
    Print two tables side by side:
      Left table: Sorted by price.
      Right table: Sorted by quantity.
    """
    # Define column widths.
    col_width_price = 8
    col_width_qty = 10
    inner_sep = "    "  # 4 spaces between Price and Quantity in each table
    # Total width for one table (Price + inner_sep + Quantity)
    col_total = col_width_price + len(inner_sep) + col_width_qty
    # Define a separator between the two tables.
    table_sep = "    |    "  # 4 spaces on each side of the vertical bar

    # Print header lines.
    print(title)
    print(f"{'Sort by price':<{col_total}}{table_sep}{'Sort by quantity':<{col_total}}")
    print(f"{'Price':>{col_width_price}}{inner_sep}{'Quantity':>{col_width_qty}}"
          f"{table_sep}"
          f"{'Price':>{col_width_price}}{inner_sep}{'Quantity':>{col_width_qty}}")

    # Determine how many rows to print.
    n = max(len(sorted_by_price), len(sorted_by_qty))
    for i in range(n):
        # Left table: Sorted by price.
        if i < len(sorted_by_price):
            price_left, qty_left = sorted_by_price[i]
            if group_size_decimals > 0:
                price_str_left = f"{price_left:.{group_size_decimals}f}"
            else:
                price_str_left = f"{int(price_left)}"
            qty_str_left = format_quantity(qty_left)
            left_line = f"{price_str_left:>{col_width_price}}{inner_sep}{qty_str_left:>{col_width_qty}}"
        else:
            left_line = " " * col_total

        # Right table: Sorted by quantity.
        if i < len(sorted_by_qty):
            price_right, qty_right = sorted_by_qty[i]
            if group_size_decimals > 0:
                price_str_right = f"{price_right:.{group_size_decimals}f}"
            else:
                price_str_right = f"{int(price_right)}"
            qty_str_right = format_quantity(qty_right)
            right_line = f"{price_str_right:>{col_width_price}}{inner_sep}{qty_str_right:>{col_width_qty}}"
        else:
            right_line = ""

        print(f"{left_line}{table_sep}{right_line}")
    print()  # Blank line after the table

def main():
    parser = argparse.ArgumentParser(
        description="Fetch and aggregate Binance order book data by decimal bucket size, "
                    "and display two orderings side by side: sorted by price and sorted by quantity."
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="SOLUSDT",
        help="Trading pair symbol on Binance (default: SOLUSDT)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Number of order book levels to fetch (default: 1000)."
    )
    # Parse group-size as a string to capture its formatting.
    parser.add_argument(
        "--group-size",
        type=str,
        default="1",
        help="Decimal bucket size for prices (default: 1). E.g., '0.1', '1', '2.5'."
    )
    # The sort direction will affect the quantity-sorted table.
    parser.add_argument(
        "--sort-dir",
        choices=["asc", "desc"],
        default="desc",
        help="Sort direction for the quantity column (default: desc)."
    )

    args = parser.parse_args()
    group_size_float, group_size_decimals = parse_group_size(args.group_size)

    endpoint = "https://api.binance.com/api/v3/depth"
    params = {"symbol": args.symbol.upper(), "limit": args.limit}

    try:
        resp = requests.get(endpoint, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching data from Binance: {e}")
        sys.exit(1)

    # Aggregate bids and asks into price buckets.
    bids_agg = defaultdict(float)
    for price_str, qty_str, *_ in data.get("bids", []):
        bucket = group_price(price_str, group_size_float)
        bids_agg[bucket] += float(qty_str)

    asks_agg = defaultdict(float)
    for price_str, qty_str, *_ in data.get("asks", []):
        bucket = group_price(price_str, group_size_float)
        asks_agg[bucket] += float(qty_str)

    # Create two orderings for each side.
    # For bids: price ordering is descending (highest price first).
    bids_by_price = sorted(bids_agg.items(), key=lambda x: x[0], reverse=True)
    bids_by_qty = sorted(bids_agg.items(), key=lambda x: x[1], reverse=(args.sort_dir == "desc"))

    # For asks: price ordering is ascending (lowest ask first).
    asks_by_price = sorted(asks_agg.items(), key=lambda x: x[0], reverse=False)
    asks_by_qty = sorted(asks_agg.items(), key=lambda x: x[1], reverse=(args.sort_dir == "desc"))

    # Print Bids.
    header_bids = (f"### Bids (symbol={args.symbol.upper()}, group_size={args.group_size}, "
                   f"price sort: bids descending, quantity sort: {args.sort_dir}):")
    # Note: first column is sorted by price, second by quantity.
    print_side_by_side(header_bids, bids_by_price, bids_by_qty, group_size_decimals)

    # Print Asks.
    header_asks = (f"### Asks (symbol={args.symbol.upper()}, group_size={args.group_size}, "
                   f"price sort: asks ascending, quantity sort: {args.sort_dir}):")
    print_side_by_side(header_asks, asks_by_price, asks_by_qty, group_size_decimals)

if __name__ == "__main__":
    main()
