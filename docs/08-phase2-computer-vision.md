# GuardX — Phase 2: Computer Vision (YOLO person detection)

## What was built

| Component | File | Notes |
|-----------|------|-------|
| Frame source | `backend/app/vision/frame_source.py` | `FrameSource` interface; `OpenCVFrameSource` (file/webcam); `loop=True` rewinds file sources for continuous demo feeds; `create_frame_source()` factory for future sources |
| Detector | `backend/app/vision/detector.py` | Pretrained **YOLOv8n** (no custom training); lazy thread-safe load; person class (COCO 0) only; structured `Detection` (bbox xyxy, confidence, class, track_id, frame_index, timestamp) |
| Tracker | `backend/app/vision/tracker.py` | Centroid tracker: greedy nearest-neighbour match, `max_distance=60px`, `max_missed=10` frames; no DeepSORT/ByteTrack in MVP |
| Annotation | `backend/app/vision/annotate.py` | Boxes + `person #id conf` labels + FPS/persons HUD text; JPEG encoder |
| Worker | `backend/app/vision/camera_worker.py` | Background thread per camera: source → frame_skip → detect → track → annotate → latest JPEG; rolling FPS EMA; mirrors status to DB |
| Manager | `backend/app/vision/manager.py` | Process-wide singleton owning live workers |
| API | `backend/app/api/v1/routers/cameras.py` | CRUD + `POST /{id}/start?loop=true` + `POST /{id}/stop` + `GET /{id}/status` + `GET /{id}/stream` (MJPEG) |
| Dashboard | `frontend/components/CameraPanel.tsx` | Camera list/add, Start/Stop, live MJPEG, persons/FPS/inference/frame readouts, 2s status polling |

Model weights (`yolov8n.pt`, 6.2 MB) are downloaded once by ultralytics into the
working directory / cache — never committed (`*.pt` in `.gitignore`).

## Measured performance (this machine, 2026-10-07)

Environment: **AMD EPYC 9D25, 2 vCPUs, no GPU** · torch 2.14.1+cpu ·
ultralytics 8.4.174 · opencv 5.0.0 · YOLOv8n @ imgsz=640, conf=0.5

| Metric | Measured |
|--------|----------|
| Cold start (download + load + first inference) | ~7.3 s (one-time; weights cached after) |
| Steady-state inference latency (810×1080 image) | **mean 111 ms, p95 130 ms** |
| End-to-end pipeline (60-frame 640×480 clip, frame_skip=2) | **17.9 FPS** (3.3 s wall) |
| Detection accuracy (fixture `bus.jpg`) | 3 persons, confidences 0.87 / 0.85 / 0.83 |

Script: `scripts/measure_fps.py`. Numbers are real measurements, not estimates.

## Test summary

`pytest backend/tests/` — **35 passed**:
- `test_frame_source.py` (8): iteration, indices, timestamps, EOS, loop rewind, invalid source, idempotent close, FPS reporting
- `test_detector.py` (5): schema fields, person-only `classes=[0]` contract, confidence forwarding, empty results, lazy load (model stubbed)
- `test_tracker.py` (6): stable ID over 30 frames, new ID for far detection, ID persistence, drop after `max_missed`, fresh ID after drop, reset
- `test_camera_api.py` (7): CRUD, 404s, invalid-source start → 422, start/stop lifecycle, double-start → 409, stream 409-guard, MJPEG generator chunk format
- `test_vision_integration.py` (2): **real YOLOv8n** finds ≥1 person in fixture; full pipeline (source→detect→track) on generated clip finds persons with stable track IDs
- Phase 1 tests still green (health, config).

## Design decisions / fixes during Phase 2

1. **File sources loop by default** (`POST /start?loop=true`): a finite sample
   video used to kill the worker at EOS within a second, which broke the demo
   and raced the tests. Looping makes a file behave like a live feed.
2. **CPU-only torch**: PyPI's torch wheel bundles CUDA (~800 MB, useless here
   and too slow to download); torch+torchvision are installed from the
   PyTorch CPU index. `requirements.txt` documents this.
3. **torchvision version pinning matters**: mismatched torchvision (PyPI build
   vs CPU torch) crashes inference with `torchvision::nms does not exist`.
4. **MJPEG generator extracted** (`mjpeg_generator()`): the infinite stream
   deadlocks Starlette's TestClient, so it's unit-tested directly; live bytes
   are verified with curl against a running server.
5. **Egress proxy**: unchanged from Phase 1 — internal HTTP checks use
   `trust_env=False`.

## Known limitations (by design)

- Single active camera per worker; multi-camera orchestration is future work.
- No frame pacing — the worker processes as fast as the CPU allows.
- Webcam/RTSP paths are implemented but untested on this headless VM.
- Small/distant persons may be missed by the pretrained nano model (documented
  MVP limitation; no custom training yet).
