"""Generate a small deterministic test clip from bus.jpg (pan across the image).

Output: assets/test_videos/person_pan_test.mp4 — 60 frames, 640x480, 10 fps.
No copyrighted video footage needed; bus.jpg contains real people.
"""
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "assets", "test_videos", "bus.jpg")
DST = os.path.join(HERE, "..", "assets", "test_videos", "person_pan_test.mp4")

W, H, FPS, N = 640, 480, 10, 60


def main() -> None:
    img = cv2.imread(SRC)
    assert img is not None, f"fixture missing: {SRC}"
    ih, iw = img.shape[:2]
    writer = cv2.VideoWriter(DST, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    assert writer.isOpened(), "VideoWriter failed"
    for i in range(N):
        # horizontal pan: crop window slides across the image
        x0 = int((iw - W) * (i / max(1, N - 1)))
        crop = img[0:H, x0 : x0 + W]
        if crop.shape[1] < W:  # pad if image narrower than window
            pad = np.zeros((H, W - crop.shape[1], 3), dtype=np.uint8)
            crop = np.hstack([crop, pad])
        writer.write(crop)
    writer.release()
    size = os.path.getsize(DST)
    print(f"wrote {DST} ({N} frames, {size // 1024} KB)")


if __name__ == "__main__":
    main()
