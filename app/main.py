import os
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.requests import Request
from sqlalchemy.orm import Session

import traceback
from .database import init_db, get_db
from .models import Batch, ClimateRecord, BehaviorRecord
from app.parsers import parse_climate_csv, parse_observation_xlsx, infer_batch_meta_from_filenames
from .analysis import (
    get_batch_summary, get_climate_timeseries, get_behavior_distribution,
    get_temperature_vs_behavior, get_shade_vs_temperature, get_chair_heatmap,
    get_global_stats, get_wbgt_heat_stress_zones,
    get_boxplot_data, get_shade_stacked, get_matrix_heatmap,
    get_behavior_by_temp, get_shade_by_age, get_wbgt_age_behavior,
)

PROJ_ROOT = Path(__file__).resolve().parent.parent
IS_VERCEL = os.environ.get("VERCEL") == "1"

def serve_html(name):
    """Serve HTML template as static file"""
    from fastapi.responses import HTMLResponse
    path = PROJ_ROOT / "app" / "templates" / name
    return HTMLResponse(content=path.read_text(encoding="utf-8"))

default_upload_dir = "/tmp/uploads" if IS_VERCEL else str(PROJ_ROOT / "uploads")
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", default_upload_dir))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="微气候观测数据分析平台")

app.mount("/static", StaticFiles(directory=str(PROJ_ROOT / "app" / "templates")), name="static")

# Vercel 的 ASGI 包装不一定触发 FastAPI startup 事件，导入时初始化保证表已存在
init_db()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return serve_html("index.html")


@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return serve_html("upload.html")


@app.get("/analysis", response_class=HTMLResponse)
def analysis_page(request: Request, batch_ids: str = Query("", description="comma-separated batch IDs")):
     return serve_html("analysis_full.html")


@app.get("/api/batches")
def api_batches(db: Session = Depends(get_db)):
    return JSONResponse(get_batch_summary(db))


@app.get("/api/batches/{batch_id}")
def api_batch_detail(batch_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "batch not found")
    return JSONResponse({
        "id": batch.id, "date_label": batch.date_label, "time_period": batch.time_period,
        "upload_time": batch.upload_time.isoformat() if batch.upload_time else None,
        "device_name": batch.device_name, "device_model": batch.device_model,
        "serial_number": batch.serial_number, "location": batch.location,
        "notes": batch.notes, "original_csv": batch.original_csv, "original_xlsx": batch.original_xlsx,
    })


@app.delete("/api/batches/{batch_id}")
def api_delete_batch(batch_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "batch not found")
    from .models import ClimateRecord, BehaviorRecord
    db.query(ClimateRecord).filter(ClimateRecord.batch_id == batch_id).delete()
    db.query(BehaviorRecord).filter(BehaviorRecord.batch_id == batch_id).delete()
    db.delete(batch)
    db.commit()
    return JSONResponse({"success": True, "deleted_batch_id": batch_id})


@app.post("/api/upload")
async def api_upload(climate_file: UploadFile = File(...), observation_file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        if not climate_file.filename or not observation_file.filename:
            raise HTTPException(400, "please select two files")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = str(UPLOAD_DIR / f"{ts}_{climate_file.filename}")
        xlsx_path = str(UPLOAD_DIR / f"{ts}_{observation_file.filename}")
        
        climate_file.file.seek(0)
        with open(csv_path, "wb") as f:
            shutil.copyfileobj(climate_file.file, f)
        
        observation_file.file.seek(0)
        with open(xlsx_path, "wb") as f:
            shutil.copyfileobj(observation_file.file, f)
        
        climate_data, meta = parse_climate_csv(csv_path)
        # Extract date from climate data for behavior record alignment
        date_hint_value = climate_data[0].get('timestamp').date() if climate_data and climate_data[0].get('timestamp') else None
        behavior_data = parse_observation_xlsx(xlsx_path, date_hint=date_hint_value)
        
        file_meta = infer_batch_meta_from_filenames(climate_file.filename, observation_file.filename)
        dl = file_meta.get("date_label","")
        tp = file_meta.get("time_period","")
        if dl and tp:
            dup = db.query(Batch).filter(Batch.date_label == dl, Batch.time_period == tp).first()
            if dup:
                db.delete(dup)
                db.commit()
        if not climate_data and not behavior_data:
            raise HTTPException(400, "cannot parse files")
        batch = Batch(
            date_label=file_meta.get("date_label", ""), time_period=file_meta.get("time_period", ""),
            upload_time=datetime.now(), original_csv=climate_file.filename,
            original_xlsx=observation_file.filename, device_name=meta.get("device_name", ""),
            device_model=meta.get("device_model", ""), serial_number=meta.get("serial_number", ""),
        )
        db.add(batch)
        db.flush()
        for row in climate_data:
            rec = ClimateRecord(batch_id=batch.id, timestamp=row.get("timestamp"),
                temperature=row.get("temperature"), wet_bulb_temp=row.get("wet_bulb_temp"),
                globe_temperature=row.get("globe_temperature"), relative_humidity=row.get("relative_humidity"),
                barometric_pressure=row.get("barometric_pressure"), altitude=row.get("altitude"),
                station_pressure=row.get("station_pressure"), wind_speed=row.get("wind_speed"),
                heat_index=row.get("heat_index"), dew_point=row.get("dew_point"),
                density_altitude=row.get("density_altitude"), crosswind=row.get("crosswind"),
                headwind=row.get("headwind"), compass_magnetic=row.get("compass_magnetic"),
                nwb_temp=row.get("nwb_temp"), compass_true=row.get("compass_true"),
                thermal_work_limit=row.get("thermal_work_limit"), wbgt=row.get("wbgt"),
                wind_chill=row.get("wind_chill"))
            db.add(rec)
        for row in behavior_data:
            rec = BehaviorRecord(batch_id=batch.id, start_time=row.get("start_time"),
                end_time=row.get("end_time"), gender=row.get("gender"), age=row.get("age"),
                clothing_color=row.get("clothing_color"), clothing_thickness=row.get("clothing_thickness"),
                clothing_coverage=row.get("clothing_coverage"), chair_environment=row.get("chair_environment"),
                chair_number=row.get("chair_number"), behavior_category=row.get("behavior_category"),
                behavior_detail=row.get("behavior_detail"), weather_change_from=row.get("weather_change_from"),
                weather_change_time=row.get("weather_change_time"), active_adjustments=row.get("active_adjustments"),
                orientation=row.get("orientation"), num_people=row.get("num_people"))
            db.add(rec)
        db.commit()
        return JSONResponse({"success": True, "batch_id": batch.id, "climate_count": len(climate_data),
            "behavior_count": len(behavior_data), "date_label": batch.date_label, "time_period": batch.time_period})
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        return JSONResponse({"success": False, "error": str(e), "detail": traceback.format_exc()}, status_code=500)
def _parse_batch_ids(batch_ids_str: str):
    if not batch_ids_str:
        return None
    try:
        ids = [int(x.strip()) for x in batch_ids_str.split(",") if x.strip()]
        return ids if ids else None
    except ValueError:
        return None


@app.get("/api/analysis/timeseries")
def api_timeseries(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_climate_timeseries(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/behavior-distribution")
def api_behavior_distribution(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_behavior_distribution(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/temp-vs-behavior")
def api_temp_vs_behavior(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_temperature_vs_behavior(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/shade-vs-temp")
def api_shade_vs_temp(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_shade_vs_temperature(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/chair-heatmap")
def api_chair_heatmap(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_chair_heatmap(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/stats")
def api_stats(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    ids = _parse_batch_ids(batch_ids)
    stats = get_global_stats(db, ids)
    stats["wbgt_zones"] = get_wbgt_heat_stress_zones()
    return JSONResponse(stats)



@app.get("/api/analysis/boxplot")
def api_boxplot(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_boxplot_data(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/shade-stacked")
def api_shade_stacked(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_shade_stacked(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/matrix-heatmap")
def api_matrix_heatmap(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_matrix_heatmap(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/behavior-by-temp")
def api_behavior_by_temp(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_behavior_by_temp(db, _parse_batch_ids(batch_ids)))


@app.get("/api/analysis/shade-by-age")
def api_shade_by_age(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_shade_by_age(db, _parse_batch_ids(batch_ids)))

@app.get("/api/analysis/wbgt-age-behavior")
def api_wbgt_age_behavior(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    return JSONResponse(get_wbgt_age_behavior(db, _parse_batch_ids(batch_ids)))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

def get_raw_behaviors(db, batch_ids=None):
    from app.models import BehaviorRecord
    q = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    return [{"age": b.age, "behavior": b.behavior_category, "chair_env": b.chair_environment} for b in q.all()]

@app.get("/api/analysis/raw-behaviors")
def api_raw_behaviors(batch_ids: str = Query(""), db: Session = Depends(get_db)):
    from fastapi.responses import JSONResponse
    return JSONResponse(get_raw_behaviors(db, _parse_batch_ids(batch_ids)))
