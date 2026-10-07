"""Frame source tests — lifecycle, iteration, error handling."""
import cv2
import numpy as np
import pytest

from app.vision.frame_source import (
    FrameSourceError,
    OpenCVFrameSource,
    create_frame_source,
)


def _make_video(path, n_frames=10, size=(320, 240)):
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, size
    )
    assert writer.isOpened()
    for i in range(n_frames):
        img = np.full((size[1], size[0], 3), i * 20 % 255, dtype=np.uint8)
        writer.write(img)
    writer.release()


def test_unsupported_source_type_raises():
    with pytest.raises(FrameSourceError):
        create_frame_source("rtsp", "whatever")


def test_missing_file_raises_on_open(tmp_path):
    src = create_frame_source("file", str(tmp_path / "nope.mp4"))
    with pytest.raises(FrameSourceError):
        src.open()


def test_iterate_video_frames(tmp_path):
    path = tmp_path / "clip.mp4"
    _make_video(path, n_frames=10)
    src = create_frame_source("file", str(path))
    with src:
        frames = []
        while True:
            f = src.read()
            if f is None:
                break
            frames.append(f)
    assert len(frames) == 10
    assert [f.index for f in frames] == list(range(10))
    assert frames[0].timestamp <= frames[-1].timestamp
    assert all(f.image.shape == (240, 320, 3) for f in frames)


def test_read_before_open_raises(tmp_path):
    src = OpenCVFrameSource("file", str(tmp_path / "x.mp4"))
    with pytest.raises(FrameSourceError):
        src.read()


def test_close_is_idempotent(tmp_path):
    path = tmp_path / "clip.mp4"
    _make_video(path, n_frames=2)
    src = create_frame_source("file", str(path))
    src.open()
    src.close()
    src.close()  # must not raise
    assert not src.is_open


def test_source_fps_reported(tmp_path):
    path = tmp_path / "clip.mp4"
    _make_video(path, n_frames=5)
    with create_frame_source("file", str(path)) as src:
        assert src.source_fps == pytest.approx(10.0, abs=0.5)


def test_loop_rewinds_file_source(tmp_path):
    path = tmp_path / "clip.mp4"
    _make_video(path, n_frames=4)
    src = OpenCVFrameSource("file", str(path), loop=True)
    with src:
        frames = [src.read() for _ in range(10)]
    assert all(f is not None for f in frames)  # never hits EOS
    assert src.loops_completed >= 2
    # indices restart on each loop
    assert frames[4].index == 0


def test_no_loop_hits_eos(tmp_path):
    path = tmp_path / "clip.mp4"
    _make_video(path, n_frames=4)
    with create_frame_source("file", str(path), loop=False) as src:
        for _ in range(4):
            assert src.read() is not None
        assert src.read() is None
