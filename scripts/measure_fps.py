"""Phase 2 performance measurement — real numbers, no estimates.

Measures on this machine:
  1. single-image YOLOv8n inference latency (warmup + steady state)
  2. end-to-end pipeline FPS on the generated test clip
Prints a markdown-ready summary.
"""
import os
import platform
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.vision.detector import PersonDetector  # noqa: E402
from app.vision.frame_source import create_frame_source  # noqa: E402
from app.vision.tracker import CentroidTracker  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(REPO, "assets", "test_videos", "bus.jpg")
CLIP = os.path.join(REPO, "assets", "test_videos", "person_pan_test.mp4")


def cpu_info() -> str:
    try:
        out = subprocess.check_output(
            ["lscpu"], text=True, stderr=subprocess.DEVNULL
        )
        model = [l for l in out.splitlines() if "Model name" in l]
        cpus = [l for l in out.splitlines() if l.startswith("CPU(s):")]
        return f"{model[0].split(':')[1].strip()} | {cpus[0].strip()}"
    except Exception:
        return platform.processor() or platform.machine()


def main() -> None:
    import torch

    print("## Environment")
    print(f"- CPU: {cpu_info()}")
    print(f"- GPU: {'cuda' if torch.cuda.is_available() else 'none (CPU-only)'}")
    print(f"- torch: {torch.__version__}, threads: {torch.get_num_threads()}")

    img = cv2.imread(FIXTURE)
    assert img is not None, f"missing fixture {FIXTURE}"
    print(f"- fixture: bus.jpg {img.shape[1]}x{img.shape[0]}")

    det = PersonDetector(confidence=0.5, imgsz=640)
    print("\n## Single-image inference (YOLOv8n, imgsz=640, person-only)")
    lat = []
    for i in range(12):
        t0 = time.perf_counter()
        dets = det.detect(img)
        dt = (time.perf_counter() - t0) * 1000
        lat.append(dt)
        if i == 0:
            print(f"- warmup (incl. model load): {dt:.0f} ms, persons: {len(dets)}")
    steady = lat[2:]
    print(f"- steady-state mean: {np.mean(steady):.0f} ms")
    print(f"- steady-state p95: {np.percentile(steady, 95):.0f} ms")

    print("\n## End-to-end pipeline (clip: 60 frames, 640x480)")
    tracker = CentroidTracker()
    n, persons_max = 0, 0
    t0 = time.perf_counter()
    with create_frame_source("file", CLIP) as src:
        while True:
            frame = src.read()
            if frame is None:
                break
            if frame.index % 2 == 0:  # FRAME_SKIP=2 like the worker
                dets = tracker.update(det.detect(frame.image, frame.index))
                persons_max = max(persons_max, len(dets))
            n += 1
    dt = time.perf_counter() - t0
    print(f"- frames: {n}, wall time: {dt:.1f} s")
    print(f"- pipeline FPS: {n / dt:.1f}")
    print(f"- max persons in a frame: {persons_max}")


if __name__ == "__main__":
    main()
