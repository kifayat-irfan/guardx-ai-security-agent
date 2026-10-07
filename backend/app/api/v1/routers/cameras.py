"""Camera CRUD + vision-loop control + MJPEG stream."""
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraRead
from app.schemas.camera_status import CameraStatus, CameraUpdate
from app.vision.manager import CameraAlreadyRunning, manager

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _get_camera(camera_id: uuid.UUID, db: Session) -> Camera:
    cam = db.get(Camera, camera_id)
    if cam is None:
        raise HTTPException(status_code=404, detail="camera not found")
    return cam


# -- CRUD ---------------------------------------------------------------
@router.post("", response_model=CameraRead, status_code=201)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    cam = Camera(
        name=payload.name,
        source_type=payload.source_type,
        source_url=payload.source_url,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.get("", response_model=list[CameraRead])
def list_cameras(db: Session = Depends(get_db)):
    return db.query(Camera).order_by(Camera.created_at).all()


@router.get("/{camera_id}", response_model=CameraRead)
def get_camera(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_camera(camera_id, db)


@router.patch("/{camera_id}", response_model=CameraRead)
def update_camera(
    camera_id: uuid.UUID, payload: CameraUpdate, db: Session = Depends(get_db)
):
    cam = _get_camera(camera_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cam, field, value)
    db.commit()
    db.refresh(cam)
    return cam


@router.delete("/{camera_id}", status_code=204)
def delete_camera(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    cam = _get_camera(camera_id, db)
    manager.stop(camera_id)  # stop the worker if running
    db.delete(cam)
    db.commit()
    return None


# -- vision loop control --------------------------------------------------
@router.post("/{camera_id}/start", response_model=CameraStatus, status_code=202)
def start_camera(
    camera_id: uuid.UUID, loop: bool = True, db: Session = Depends(get_db)
):
    cam = _get_camera(camera_id, db)
    settings = get_settings()
    frame_skip = int(getattr(settings, "frame_skip", 2))
    try:
        worker = manager.start(cam, frame_skip=frame_skip, loop=loop)
    except CameraAlreadyRunning:
        raise HTTPException(status_code=409, detail="camera already streaming")
    time.sleep(0.3)  # let the worker open the source / surface errors
    snap = worker.snapshot()
    if snap["error"]:
        raise HTTPException(status_code=422, detail=snap["error"])
    return CameraStatus(**snap)


@router.post("/{camera_id}/stop", response_model=CameraStatus)
def stop_camera(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    cam = _get_camera(camera_id, db)
    manager.stop(camera_id)
    db.refresh(cam)
    worker = manager.get_worker(camera_id)
    snap = (
        worker.snapshot()
        if worker
        else {
            "camera_id": str(camera_id),
            "status": cam.status,
            "fps": 0.0,
            "person_count": 0,
            "frame_index": 0,
            "inference_ms": 0.0,
            "error": None,
            "detections": [],
        }
    )
    return CameraStatus(**snap)


@router.get("/{camera_id}/status", response_model=CameraStatus)
def camera_status(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    cam = _get_camera(camera_id, db)
    worker = manager.get_worker(camera_id)
    if worker is None:
        return CameraStatus(
            camera_id=camera_id,
            status=cam.status,
            fps=0.0,
            person_count=0,
            frame_index=0,
            inference_ms=0.0,
            error=None,
            detections=[],
        )
    return CameraStatus(**worker.snapshot())


# -- MJPEG stream ---------------------------------------------------------
def mjpeg_generator(worker, interval: float = 0.1):
    """Yield multipart MJPEG chunks from a running worker (unit-testable)."""
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    while worker.is_running:
        jpeg = worker.latest_jpeg()
        if jpeg:
            yield boundary + jpeg + b"\r\n"
        time.sleep(interval)


@router.get("/{camera_id}/stream")
def camera_stream(camera_id: uuid.UUID, db: Session = Depends(get_db)):
    _get_camera(camera_id, db)
    worker = manager.get_worker(camera_id)
    if worker is None or not worker.is_running:
        raise HTTPException(
            status_code=409, detail="camera is not streaming — POST /start first"
        )
    return StreamingResponse(
        mjpeg_generator(worker),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
