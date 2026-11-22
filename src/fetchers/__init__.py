"""
Problem fetchers for multiple DSA sources.
Each fetcher returns a list of Problem dicts with a unified schema.
"""

from src.fetchers.a2z_fetcher import fetch_a2z_problems
from src.fetchers.leetcode_fetcher import fetch_leetcode_problems
from src.fetchers.codeforces_fetcher import fetch_codeforces_problems
from src.fetchers.gfg_fetcher import fetch_gfg_problems

__all__ = [
    "fetch_a2z_problems",
    "fetch_leetcode_problems",
    "fetch_codeforces_problems",
    "fetch_gfg_problems",
]
