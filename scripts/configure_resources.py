#!/usr/bin/env python3
"""
Auto-configure Docker Compose memory limits based on host hardware.

Usage:
    python scripts/configure_resources.py            # Apply changes
    python scripts/configure_resources.py --dry-run  # Preview only
"""

import argparse
import math
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

# Allocation ratios (fraction of AVAILABLE RAM, not total)
# Available RAM = total - (OS + running apps)
ALLOCATIONS = {
    "postgres": 0.18,
    "clickhouse": 0.30,
    "redis": 0.06,
    "airflow-webserver": 0.15,
    "airflow-scheduler": 0.12,
    "fastapi": 0.10,
    "frontend": 0.04,
}
# Total: ~95% of available RAM, remaining %5 headroom

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


def compute_limits(available_bytes: int) -> dict[str, int]:
    """Return memory limits in MB per service based on available RAM."""
    available_mb = available_bytes / (1024 ** 2)

    limits = {}
    for svc, ratio in ALLOCATIONS.items():
        mb = max(MINIMUMS[svc], int(available_mb * ratio))
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
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    mem = psutil.virtual_memory()
    total_gb = mem.total / (1024 ** 3)
    available_gb = mem.available / (1024 ** 3)
    used_gb = total_gb - available_gb

    print(f"Total RAM     : {total_gb:.1f} GB")
    print(f"Used (OS+apps): {used_gb:.1f} GB")
    print(f"Available     : {available_gb:.1f} GB")
    print()

    limits = compute_limits(mem.available)

    print(f"{'Service':<22} {'Limit':>8}")
    print("-" * 32)
    total_alloc = 0
    for svc, mb in limits.items():
        print(f"  {svc:<20} {format_memory(mb):>8}")
        total_alloc += mb
    print("-" * 32)
    print(f"  {'Docker total':<20} {format_memory(total_alloc):>8}  ({total_alloc / 1024:.1f} GB / {available_gb:.1f} GB available)")
    print()

    if total_alloc / 1024 > available_gb * 0.95:
        print("WARNING: Allocation exceeds available RAM. Some services may be OOM-killed.")
        print()

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
