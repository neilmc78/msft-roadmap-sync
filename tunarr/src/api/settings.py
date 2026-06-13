import shutil
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import RootFolder, QualityProfile, AppConfig
from ..schemas import RootFolderIn, RootFolderOut, QualityProfileIn, QualityProfileOut, QUALITY_DEFINITIONS

router = APIRouter(prefix="/api/v3", tags=["settings"])


# ─── Root Folders ──────────────────────────────────────────────────────────────

def _folder_stats(path: str) -> dict:
    try:
        usage = shutil.disk_usage(path)
        return {"freeSpace": usage.free, "totalSpace": usage.total}
    except OSError:
        return {"freeSpace": 0, "totalSpace": 0}


@router.get("/rootfolder", response_model=list[RootFolderOut])
def list_root_folders(db: Session = Depends(get_db)):
    folders = db.query(RootFolder).all()
    result = []
    for f in folders:
        stats = _folder_stats(f.path)
        result.append(RootFolderOut(id=f.id, path=f.path, **stats))
    return result


@router.post("/rootfolder", response_model=RootFolderOut, status_code=201)
def add_root_folder(body: RootFolderIn, db: Session = Depends(get_db)):
    import os
    os.makedirs(body.path, exist_ok=True)
    existing = db.query(RootFolder).filter(RootFolder.path == body.path).first()
    if existing:
        raise HTTPException(400, "Root folder already exists")
    rf = RootFolder(path=body.path)
    db.add(rf)
    db.commit()
    db.refresh(rf)
    stats = _folder_stats(rf.path)
    return RootFolderOut(id=rf.id, path=rf.path, **stats)


@router.delete("/rootfolder/{folder_id}", status_code=200)
def delete_root_folder(folder_id: int, db: Session = Depends(get_db)):
    rf = db.get(RootFolder, folder_id)
    if not rf:
        raise HTTPException(404, "Root folder not found")
    db.delete(rf)
    db.commit()
    return {}


# ─── Quality Profiles ──────────────────────────────────────────────────────────

@router.get("/qualityprofile", response_model=list[QualityProfileOut])
def list_quality_profiles(db: Session = Depends(get_db)):
    return db.query(QualityProfile).all()


@router.post("/qualityprofile", response_model=QualityProfileOut, status_code=201)
def create_quality_profile(body: QualityProfileIn, db: Session = Depends(get_db)):
    import json
    qp = QualityProfile(
        name=body.name,
        upgrade_allowed=body.upgradeAllowed,
        cutoff=body.cutoff,
        items=json.dumps(body.items or QUALITY_DEFINITIONS),
    )
    db.add(qp)
    db.commit()
    db.refresh(qp)
    return qp


@router.put("/qualityprofile/{profile_id}", response_model=QualityProfileOut)
def update_quality_profile(profile_id: int, body: QualityProfileIn, db: Session = Depends(get_db)):
    import json
    qp = db.get(QualityProfile, profile_id)
    if not qp:
        raise HTTPException(404, "Quality profile not found")
    qp.name = body.name
    qp.upgrade_allowed = body.upgradeAllowed
    qp.cutoff = body.cutoff
    qp.items = json.dumps(body.items)
    db.commit()
    db.refresh(qp)
    return qp


@router.delete("/qualityprofile/{profile_id}", status_code=200)
def delete_quality_profile(profile_id: int, db: Session = Depends(get_db)):
    qp = db.get(QualityProfile, profile_id)
    if not qp:
        raise HTTPException(404, "Quality profile not found")
    db.delete(qp)
    db.commit()
    return {}


# ─── Quality Definitions (read-only reference) ─────────────────────────────────

@router.get("/qualitydefinition")
def quality_definitions():
    return QUALITY_DEFINITIONS


# ─── App Config (key/value store) ──────────────────────────────────────────────

@router.get("/config/host")
def get_host_config(db: Session = Depends(get_db)):
    def _cfg(key, default=""):
        row = db.query(AppConfig).filter(AppConfig.key == key).first()
        return row.value if row else default

    return {
        "port": int(_cfg("port", "8686")),
        "urlBase": _cfg("urlBase", ""),
        "bindAddress": _cfg("bindAddress", "*"),
        "instanceName": _cfg("instanceName", "Tunarr"),
        "applicationUrl": _cfg("applicationUrl", ""),
    }


@router.put("/config/host")
def update_host_config(body: dict, db: Session = Depends(get_db)):
    for key, value in body.items():
        row = db.query(AppConfig).filter(AppConfig.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(AppConfig(key=key, value=str(value)))
    db.commit()
    return body


@router.get("/config/naming")
def get_naming_config(db: Session = Depends(get_db)):
    def _cfg(key, default=""):
        row = db.query(AppConfig).filter(AppConfig.key == key).first()
        return row.value if row else default

    return {
        "standardTrackFormat": _cfg(
            "standardTrackFormat",
            "{Artist Name}/{Album Title} ({Release Year})/{track:00} - {Track Title}"
        ),
        "artistFolderFormat": _cfg("artistFolderFormat", "{Artist Name}"),
        "albumFolderFormat": _cfg("albumFolderFormat", "{Album Title} ({Release Year})"),
        "renameTracks": _cfg("renameTracks", "true") == "true",
        "replaceIllegalCharacters": _cfg("replaceIllegalCharacters", "true") == "true",
    }


@router.put("/config/naming")
def update_naming_config(body: dict, db: Session = Depends(get_db)):
    for key, value in body.items():
        row = db.query(AppConfig).filter(AppConfig.key == key).first()
        if row:
            row.value = str(value)
        else:
            db.add(AppConfig(key=key, value=str(value)))
    db.commit()
    return body
