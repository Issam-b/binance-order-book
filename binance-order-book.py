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

    # Strip trailing zeros and '.' to detect how many decimals remain
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
        # Show up to 2 decimals, strip trailing zeros
        return f"{q:.2f}".rstrip("0").rstrip(".")

def main():
    parser = argparse.ArgumentParser(
        description="Fetch and aggregate Binance order book data by decimal bucket size."
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
    # We'll parse as string to determine decimal precision
    parser.add_argument(
        "--group-size",
        type=str,
        default="1",
        help="Decimal bucket size for prices (default: 1). E.g., '0.1', '1', '2.5'."
    )
    parser.add_argument(
        "--sort-by",
        choices=["price", "quantity"],
        default="quantity",
        help="Sort results by 'price' or 'quantity' (default: quantity)."
    )
    parser.add_argument(
        "--sort-dir",
        choices=["asc", "desc"],
        default="desc",
        help="Sort direction (default: desc)."
    )

    args = parser.parse_args()

    group_size_float, group_size_decimals = parse_group_size(args.group_size)

    endpoint = "https://api.binance.com/api/v3/depth"
    params = {
        "symbol": args.symbol.upper(),
        "limit": args.limit
    }

    try:
        resp = requests.get(endpoint, params=params)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching data from Binance: {e}")
        sys.exit(1)

    bids_agg = defaultdict(float)
    for price_str, qty_str, *_ in data.get("bids", []):
        bucket = group_price(price_str, group_size_float)
        bids_agg[bucket] += float(qty_str)

    asks_agg = defaultdict(float)
    for price_str, qty_str, *_ in data.get("asks", []):
        bucket = group_price(price_str, group_size_float)
        asks_agg[bucket] += float(qty_str)

    # Determine sorting key
    if args.sort_by == "quantity":
        sort_key = lambda x: x[1]
    else:  # args.sort_by == "price"
        sort_key = lambda x: x[0]

    # If sorting by quantity, use the same order for both bids and asks.
    if args.sort_by == "quantity":
        reverse_order = args.sort_dir == "desc"
        bids_sorted = sorted(bids_agg.items(), key=sort_key, reverse=reverse_order)
        asks_sorted = sorted(asks_agg.items(), key=sort_key, reverse=reverse_order)
    else:
        # For price sorting, use opposite sort directions:
        # bids descending (for higher bid prices first) and asks ascending (for lower ask prices first)
        if args.sort_dir == "desc":
            bids_sorted = sorted(bids_agg.items(), key=sort_key, reverse=True)
            asks_sorted = sorted(asks_agg.items(), key=sort_key, reverse=False)
        else:
            bids_sorted = sorted(bids_agg.items(), key=sort_key, reverse=False)
            asks_sorted = sorted(asks_agg.items(), key=sort_key, reverse=True)

    # Print header with smaller widths
    print(f"### Bids (symbol={args.symbol}, group_size={args.group_size}, "
          f"sort_by={args.sort_by}, sort_dir={args.sort_dir}):")
    print(f"{'Price':>8}  {'Quantity':>10}")

    for price_bucket, qty_sum in bids_sorted:
        # If group_size_decimals > 0, format that many decimals; else integer
        if group_size_decimals > 0:
            price_str = f"{price_bucket:.{group_size_decimals}f}"
        else:
            price_str = f"{int(price_bucket)}"
        qty_str = format_quantity(qty_sum)
        print(f"{price_str:>8}  {qty_str:>10}")

    print(f"\n### Asks (symbol={args.symbol}, group_size={args.group_size}, "
          f"sort_by={args.sort_by}, sort_dir={args.sort_dir}):")
    print(f"{'Price':>8}  {'Quantity':>10}")

    for price_bucket, qty_sum in asks_sorted:
        if group_size_decimals > 0:
            price_str = f"{price_bucket:.{group_size_decimals}f}"
        else:
            price_str = f"{int(price_bucket)}"
        qty_str = format_quantity(qty_sum)
        print(f"{price_str:>8}  {qty_str:>10}")

if __name__ == "__main__":
    main()
