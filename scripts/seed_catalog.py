"""CLI wrapper — see core/collect/seed.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.collect.seed import build_seed  # noqa: E402

if __name__ == "__main__":
    build_seed()
