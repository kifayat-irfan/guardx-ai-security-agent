"""Zone CRUD — restricted polygons per camera (Phase 3)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.camera import Camera
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneRead, ZoneUpdate
from app.vision.manager import manager

router = APIRouter(prefix="/zones", tags=["zones"])


def _get_zone(zone_id: uuid.UUID, db: Session) -> Zone:
    zone = db.get(Zone, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="zone not found")
    return zone


def _refresh_worker(camera_id: uuid.UUID, db: Session) -> None:
    """Push the latest active zones into a running worker, if any."""
    worker = manager.get_worker(camera_id)
    if worker is not None:
        worker.reload_zones(db)


@router.post("", response_model=ZoneRead, status_code=201)
def create_zone(payload: ZoneCreate, db: Session = Depends(get_db)):
    if db.get(Camera, payload.camera_id) is None:
        raise HTTPException(status_code=404, detail="camera not found")
    zone = Zone(
        camera_id=payload.camera_id,
        name=payload.name,
        polygon=payload.polygon,
        dwell_seconds=payload.dwell_seconds,
        cooldown_seconds=payload.cooldown_seconds,
        active=payload.active,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    _refresh_worker(zone.camera_id, db)
    return zone


@router.get("", response_model=list[ZoneRead])
def list_zones(
    camera_id: uuid.UUID | None = Query(default=None),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Zone).order_by(Zone.created_at)
    if camera_id is not None:
        q = q.filter(Zone.camera_id == camera_id)
    if active is not None:
        q = q.filter(Zone.active == active)
    return q.all()


@router.get("/{zone_id}", response_model=ZoneRead)
def get_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    return _get_zone(zone_id, db)


@router.patch("/{zone_id}", response_model=ZoneRead)
def update_zone(
    zone_id: uuid.UUID, payload: ZoneUpdate, db: Session = Depends(get_db)
):
    zone = _get_zone(zone_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    db.commit()
    db.refresh(zone)
    _refresh_worker(zone.camera_id, db)
    return zone


@router.delete("/{zone_id}", status_code=204)
def delete_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    zone = _get_zone(zone_id, db)
    camera_id = zone.camera_id
    db.delete(zone)
    db.commit()
    _refresh_worker(camera_id, db)
    return None
