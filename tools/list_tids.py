#!/usr/bin/env python3
"""
List track IDs (tid) contained in a PHALP/4D-Humans results .pkl file,
with basic statistics like number of frames containing that tid.

Usage:
  python tools/list_tids.py --pkl /path/to/outputs/results/demo_7111.pkl [--top 20]

Outputs a sorted table by frame_count desc and a JSON summary line.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from typing import Dict, Any, List


def load_pkl(pkl_path: str) -> Dict[str, Any]:
    try:
        import joblib
    except ImportError as exc:
        raise SystemExit("joblib is required: pip install joblib") from exc

    data = joblib.load(pkl_path)
    if not isinstance(data, dict):
        raise SystemExit("Unexpected PKL format: expected dict keyed by frame identifiers")
    return data


def enumerate_tids(data: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    tid_to_stats: Dict[int, Dict[str, Any]] = defaultdict(lambda: {
        "frame_count": 0,
        "frames": [],
    })

    # Sort frame keys in natural order if they are numeric-like; otherwise preserve insertion
    frame_keys: List[str] = list(data.keys())

    for frame_key in frame_keys:
        frame = data[frame_key]
        # Prefer 'tracked_ids' (detections + ghosts). Fall back to 'tid' if present.
        tids: List[int] = []
        if isinstance(frame, dict):
            if "tracked_ids" in frame and isinstance(frame["tracked_ids"], (list, tuple)):
                tids = [int(x) for x in frame["tracked_ids"] if x is not None]
            elif "tid" in frame and isinstance(frame["tid"], (list, tuple)):
                tids = [int(x) for x in frame["tid"] if x is not None]

        # Count unique tids in this frame (avoid double counting if repeated)
        for tid in set(tids):
            stats = tid_to_stats[int(tid)]
            stats["frame_count"] += 1
            stats["frames"].append(frame_key)

    return tid_to_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="List TIDs inside a PHALP/4D-Humans PKL with basic stats")
    parser.add_argument("--pkl", required=True, help="Path to results .pkl (e.g., outputs/results/demo_7111.pkl)")
    parser.add_argument("--top", type=int, default=50, help="Show top-N tids by frame count")
    args = parser.parse_args()

    data = load_pkl(args.pkl)
    tid_stats = enumerate_tids(data)

    if not tid_stats:
        print("No tids found.")
        return

    rows = sorted(((tid, st["frame_count"]) for tid, st in tid_stats.items()), key=lambda x: (-x[1], x[0]))
    print("tid,frame_count")
    for tid, cnt in rows[: args.top]:
        print(f"{tid},{cnt}")

    summary = {
        "total_tids": len(tid_stats),
        "top": [{"tid": tid, "frame_count": cnt} for tid, cnt in rows[: args.top]],
    }
    print("---")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)



