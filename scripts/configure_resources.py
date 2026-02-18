#!/usr/bin/env python3
"""
Auto-configure Docker Compose memory limits based on host hardware.

Usage:
    python scripts/configure_resources.py                    # Auto-detect available RAM
    python scripts/configure_resources.py --ram 8g        # Allocate from 8 GB ram
    python scripts/configure_resources.py --ram 70%       # Use 70% of total RAM
    python scripts/configure_resources.py --dry-run          # Preview only
"""

import argparse
import math
import re
import sys
from pathlib import Path

try:
    import psutil
except ImportError:
    sys.exit("psutil required: pip install psutil")

try:
    from ruamel.yaml import YAML
except ImportError:
    sys.exit("ruamel.yaml required: pip install ruamel.yaml")

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "docker-compose.yml"

# Allocation ratios (fraction of ram)
ALLOCATIONS = {
    "postgres": 0.18,
    "clickhouse": 0.30,
    "redis": 0.06,
    "airflow-webserver": 0.15,
    "airflow-scheduler": 0.12,
    "fastapi": 0.10,
    "frontend": 0.04,
}
# Total: ~95% of ram, remaining %5 headroom

# Minimum limits per service (MB)
MINIMUMS = {
    "postgres": 256,
    "clickhouse": 1536,
    "redis": 64,
    "airflow-webserver": 512,
    "airflow-scheduler": 384,
    "fastapi": 256,
    "frontend": 64,
}


def parse_ram(ram_str: str, total_bytes: int) -> int:
    """Parse ram string like '8g', '4096m', '70%' into bytes."""
    ram_str = ram_str.strip().lower()

    # Percentage of total RAM
    if ram_str.endswith("%"):
        pct = float(ram_str[:-1])
        if not 0 < pct <= 100:
            sys.exit(f"Invalid percentage: {ram_str} (must be 1-100)")
        return int(total_bytes * pct / 100)

    # Absolute value with unit
    match = re.match(r"^(\d+(?:\.\d+)?)\s*(g|gb|m|mb)$", ram_str)
    if not match:
        sys.exit(f"Invalid ram format: '{ram_str}'. Examples: 8g, 4096m, 70%")

    value = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("g"):
        return int(value * 1024 ** 3)
    return int(value * 1024 ** 2)


def compute_limits(ram_bytes: int) -> dict[str, int]:
    """Return memory limits in MB per service based on ram."""
    ram_mb = ram_bytes / (1024 ** 2)

    limits = {}
    for svc, ratio in ALLOCATIONS.items():
        mb = max(MINIMUMS[svc], int(ram_mb * ratio))
        # Round to nearest 64MB for cleaner values
        mb = int(math.ceil(mb / 64) * 64)
        limits[svc] = mb

    return limits


def format_memory(mb: int) -> str:
    if mb >= 1024 and mb % 1024 == 0:
        return f"{mb // 1024}g"
    return f"{mb}m"


def apply_limits(compose: dict, limits: dict[str, int]) -> None:
    services = compose["services"]

    for svc_name, mb in limits.items():
        if svc_name not in services:
            continue

        svc = services[svc_name]

        # Set deploy.resources.limits.memory
        if "deploy" not in svc:
            svc["deploy"] = {}
        if "resources" not in svc["deploy"]:
            svc["deploy"]["resources"] = {}
        if "limits" not in svc["deploy"]["resources"]:
            svc["deploy"]["resources"]["limits"] = {}

        svc["deploy"]["resources"]["limits"]["memory"] = format_memory(mb)

    # Configure Redis maxmemory (90% of container limit)
    if "redis" in services and "redis" in limits:
        redis_max = int(limits["redis"] * 0.9)
        services["redis"]["command"] = [
            "redis-server",
            "--maxmemory", f"{redis_max}mb",
            "--maxmemory-policy", "allkeys-lru",
        ]

    # Configure PostgreSQL shared_buffers (25% of container limit)
    if "postgres" in services and "postgres" in limits:
        shared_buf = int(limits["postgres"] * 0.25)
        services["postgres"]["command"] = [
            "postgres",
            "-c", "checkpoint_timeout=30min",
            "-c", f"shared_buffers={shared_buf}MB",
        ]


def main():
    parser = argparse.ArgumentParser(description="Auto-configure Docker Compose memory limits")
    parser.add_argument("--ram", type=str, default=None,
                        help="RAM ram for Docker: absolute (8g, 4096m) or percentage (70%%)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)

    if args.ram:
        ram_bytes = parse_ram(args.ram, mem.total)
        ram_gb = ram_bytes / (1024 ** 3)
        print(f"Total RAM : {total_gb:.1f} GB")
        print(f"RAM       : {ram_gb:.1f} GB ({args.ram})")
    else:
        ram_bytes = mem.available
        ram_gb = ram_bytes / (1024 ** 3)
        used_gb = total_gb - ram_gb
        print(f"Total RAM     : {total_gb:.1f} GB")
        print(f"Used (OS+apps): {used_gb:.1f} GB")
        print(f"Available     : {ram_gb:.1f} GB (auto-detected)")
        print()
        print("Tip: Use --ram to set a fixed ram (e.g., --ram 8g, --ram 70%)")

    print()

    limits = compute_limits(ram_bytes)

    print(f"{'Service':<22} {'Limit':>8}")
    print("-" * 32)
    total_alloc = 0
    for svc, mb in limits.items():
        print(f"  {svc:<20} {format_memory(mb):>8}")
        total_alloc += mb
    print("-" * 32)
    print(f"  {'Docker total':<20} {format_memory(total_alloc):>8}  ({total_alloc / 1024:.1f} GB / {ram_gb:.1f} GB ram)")
    print()

    if total_alloc / 1024 > total_gb:
        print("ERROR: Allocation exceeds total system RAM!")
        print()
        if not args.dry_run:
            sys.exit(1)

    if args.dry_run:
        print("[dry-run] No changes written.")
        return

    yaml = YAML()
    yaml.preserve_quotes = True

    with open(COMPOSE_FILE) as f:
        compose = yaml.load(f)

    apply_limits(compose, limits)

    with open(COMPOSE_FILE, "w") as f:
        yaml.dump(compose, f)

    print(f"Updated: {COMPOSE_FILE}")
    print("Run 'docker compose up -d' to apply.")


if __name__ == "__main__":
    main()
