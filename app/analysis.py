from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from .models import Batch, ClimateRecord, BehaviorRecord

def get_batch_summary(db):
    batches = db.query(Batch).order_by(Batch.upload_time.desc()).all()
    result = []
    for b in batches:
        cc = db.query(sqlfunc.count(ClimateRecord.id)).filter(ClimateRecord.batch_id == b.id).scalar()
        bc = db.query(sqlfunc.count(BehaviorRecord.id)).filter(BehaviorRecord.batch_id == b.id).scalar()
        result.append({
            "id": b.id, "date_label": b.date_label, "time_period": b.time_period,
            "upload_time": b.upload_time.isoformat() if b.upload_time else None,
            "climate_records": cc, "behavior_records": bc,
        })
    return result

def get_climate_timeseries(db, batch_ids=None):
    q = db.query(ClimateRecord.batch_id, ClimateRecord.timestamp,
        ClimateRecord.temperature, ClimateRecord.wbgt, ClimateRecord.relative_humidity,
        ClimateRecord.globe_temperature, ClimateRecord.wet_bulb_temp, ClimateRecord.wind_speed,
        ClimateRecord.heat_index, ClimateRecord.dew_point, ClimateRecord.thermal_work_limit)
    if batch_ids:
        q = q.filter(ClimateRecord.batch_id.in_(batch_ids))
    q = q.order_by(ClimateRecord.batch_id, ClimateRecord.timestamp)
    records = q.all()
    series = {}
    for r in records:
        bid = r.batch_id
        if bid not in series:
            series[bid] = []
        series[bid].append({
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "temperature": r.temperature, "wbgt": r.wbgt,
            "humidity": r.relative_humidity, "globe_temp": r.globe_temperature,
            "wet_bulb": r.wet_bulb_temp, "wind_speed": r.wind_speed,
            "heat_index": r.heat_index, "dew_point": r.dew_point,
            "thermal_work_limit": r.thermal_work_limit,
        })
    batches = {b.id: {"date": b.date_label, "period": b.time_period} for b in db.query(Batch).all()}
    labeled = {}
    for bid, data in series.items():
        label = batches.get(bid, {})
        key = f"{label.get('date', '')} {label.get('period', '')}" if label else f"Batch{bid}"
        labeled[key] = data
    return labeled

def get_behavior_distribution(db, batch_ids=None):
    q = db.query(BehaviorRecord.batch_id, BehaviorRecord.behavior_category,
        sqlfunc.count(BehaviorRecord.id).label("count"))
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    q = q.group_by(BehaviorRecord.batch_id, BehaviorRecord.behavior_category)
    q = q.order_by(BehaviorRecord.batch_id)
    records = q.all()
    batches = {b.id: {"date": b.date_label, "period": b.time_period} for b in db.query(Batch).all()}
    result = {}
    for r in records:
        label = batches.get(r.batch_id, {})
        key = f"{label.get('date', '')} {label.get('period', '')}" if label else f"Batch{r.batch_id}"
        if key not in result:
            result[key] = {}
        result[key][r.behavior_category or "Unknown"] = r.count
    return result

def get_temperature_vs_behavior(db, batch_ids=None):
    q = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    behaviors = q.all()
    batches = {b.id: {"date": b.date_label, "period": b.time_period} for b in db.query(Batch).all()}
    scatter = []
    for b in behaviors:
        if not b.start_time or not b.behavior_category:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.temperature), sqlfunc.avg(ClimateRecord.wbgt))             .filter(ClimateRecord.batch_id == b.batch_id)             .filter(ClimateRecord.timestamp >= b.start_time)             .filter(ClimateRecord.timestamp <= end).first()
        avg_temp = row[0] if row and row[0] else None
        avg_wbgt = row[1] if row and row[1] else None
        label = batches.get(b.batch_id, {})
        batch_key = f"{label.get('date', '')} {label.get('period', '')}" if label else f"Batch{b.batch_id}"
        scatter.append({
            "batch": batch_key, "behavior": b.behavior_category,
            "detail": b.behavior_detail or "",
            "avg_temp": round(avg_temp, 1) if avg_temp else None,
            "avg_wbgt": round(avg_wbgt, 1) if avg_wbgt else None,
            "chair_env": b.chair_environment or "",
            "orientation": b.orientation or "",
            "num_people": b.num_people or "",
        })
    return scatter

def get_shade_vs_temperature(db, batch_ids=None):
    q = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    behaviors = q.all()
    batches = {b.id: {"date": b.date_label, "period": b.time_period} for b in db.query(Batch).all()}
    data = []
    for b in behaviors:
        if not b.start_time or not b.chair_environment:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.temperature), sqlfunc.avg(ClimateRecord.wbgt))             .filter(ClimateRecord.batch_id == b.batch_id)             .filter(ClimateRecord.timestamp >= b.start_time)             .filter(ClimateRecord.timestamp <= end).first()
        avg_temp = row[0] if row and row[0] else None
        avg_wbgt = row[1] if row and row[1] else None
        label = batches.get(b.batch_id, {})
        batch_key = f"{label.get('date', '')} {label.get('period', '')}" if label else f"Batch{b.batch_id}"
        data.append({
            "batch": batch_key, "chair_env": b.chair_environment,
            "avg_temp": round(avg_temp, 1) if avg_temp else None,
            "avg_wbgt": round(avg_wbgt, 1) if avg_wbgt else None,
            "behavior": b.behavior_category or "",
        })
    return data

def get_chair_heatmap(db, batch_ids=None):
    q = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    behaviors = q.all()
    batches = {b.id: {"date": b.date_label, "period": b.time_period} for b in db.query(Batch).all()}
    heat_data = []
    for b in behaviors:
        if not b.start_time or b.chair_number is None:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.wbgt))             .filter(ClimateRecord.batch_id == b.batch_id)             .filter(ClimateRecord.timestamp >= b.start_time)             .filter(ClimateRecord.timestamp <= end).first()
        avg_wbgt = round(row[0], 1) if row and row[0] else None
        label = batches.get(b.batch_id, {})
        batch_key = f"{label.get('date', '')} {label.get('period', '')}" if label else f"Batch{b.batch_id}"
        heat_data.append({
            "batch": batch_key, "chair": b.chair_number,
            "start": b.start_time.strftime("%H:%M") if hasattr(b.start_time, "strftime") else str(b.start_time),
            "end": b.end_time.strftime("%H:%M") if hasattr(b.end_time, "strftime") else str(b.end_time),
            "wbgt": avg_wbgt, "behavior": b.behavior_category or "", "env": b.chair_environment or "",
        })
    return heat_data

def get_global_stats(db, batch_ids=None):
    q = db.query(ClimateRecord)
    if batch_ids:
        q = q.filter(ClimateRecord.batch_id.in_(batch_ids))
    stats = {}
    temp_stats = q.with_entities(
        sqlfunc.min(ClimateRecord.temperature), sqlfunc.max(ClimateRecord.temperature),
        sqlfunc.avg(ClimateRecord.temperature),
        sqlfunc.min(ClimateRecord.wbgt), sqlfunc.max(ClimateRecord.wbgt), sqlfunc.avg(ClimateRecord.wbgt),
    ).first()
    if temp_stats:
        stats["temp_min"] = round(temp_stats[0], 1) if temp_stats[0] else 0
        stats["temp_max"] = round(temp_stats[1], 1) if temp_stats[1] else 0
        stats["temp_avg"] = round(temp_stats[2], 1) if temp_stats[2] else 0
        stats["wbgt_min"] = round(temp_stats[3], 1) if temp_stats[3] else 0
        stats["wbgt_max"] = round(temp_stats[4], 1) if temp_stats[4] else 0
        stats["wbgt_avg"] = round(temp_stats[5], 1) if temp_stats[5] else 0
    bq = db.query(sqlfunc.count(BehaviorRecord.id))
    if batch_ids:
        bq = bq.filter(BehaviorRecord.batch_id.in_(batch_ids))
    stats["total_behaviors"] = bq.scalar()
    wbgt_records = db.query(ClimateRecord.wbgt)
    if batch_ids:
        wbgt_records = wbgt_records.filter(ClimateRecord.batch_id.in_(batch_ids))
    wbgt_values = [r[0] for r in wbgt_records.all() if r[0] is not None]
    stats["wbgt_distribution"] = {
        "safe": sum(1 for v in wbgt_values if v < 28),
        "caution": sum(1 for v in wbgt_values if 28 <= v < 30),
        "danger": sum(1 for v in wbgt_values if 30 <= v < 32),
        "extreme": sum(1 for v in wbgt_values if v >= 32),
    }
    return stats

def get_wbgt_heat_stress_zones():
    return [
        {"label": "Safe <28", "from": 0, "to": 28, "color": "rgba(34,197,94,0.15)"},
        {"label": "Caution 28-30", "from": 28, "to": 30, "color": "rgba(234,179,8,0.15)"},
        {"label": "Danger 30-32", "from": 30, "to": 32, "color": "rgba(239,68,68,0.15)"},
        {"label": "Extreme >=32", "from": 32, "to": 50, "color": "rgba(180,0,0,0.15)"},
    ]


import statistics as _stats

def get_boxplot_data(db, batch_ids=None):
    q = db.query(ClimateRecord.batch_id, ClimateRecord.temperature, ClimateRecord.timestamp)
    if batch_ids:
        q = q.filter(ClimateRecord.batch_id.in_(batch_ids))
    all_climate = q.all()
    bq = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        bq = bq.filter(BehaviorRecord.batch_id.in_(batch_ids))
    all_behaviors = bq.all()
    temp_by_behavior = {}
    for b in all_behaviors:
        if not b.behavior_category or not b.start_time:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        temps = [c.temperature for c in all_climate
                 if c.batch_id == b.batch_id and c.timestamp and b.start_time
                 and c.timestamp >= b.start_time and c.timestamp <= end and c.temperature is not None]
        if b.behavior_category not in temp_by_behavior:
            temp_by_behavior[b.behavior_category] = []
        temp_by_behavior[b.behavior_category].extend(temps)
    result = []
    for behav, temps in temp_by_behavior.items():
        if len(temps) < 2:
            continue
        temps.sort()
        n = len(temps)
        result.append({
            "behavior": behav, "min": round(temps[0], 1),
            "q1": round(temps[n//4] if n >= 4 else temps[0], 1),
            "median": round(temps[n//2], 1),
            "q3": round(temps[3*n//4] if n >= 4 else temps[-1], 1),
            "max": round(temps[-1], 1), "count": n,
        })
    return result

def get_shade_stacked(db, batch_ids=None):
    bins = ["<=24", "24-26", "26-28", "28-30", ">30"]
    envs = ["全遮阴", "全遮荫", "半遮阴", "半遮荫", "曝晒", "无遮荫"]
    data = {b: {e: 0 for e in envs} for b in bins}
    q = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    for b in q.all():
        if not b.chair_environment or not b.start_time:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.temperature)).filter(
            ClimateRecord.batch_id == b.batch_id, ClimateRecord.timestamp >= b.start_time,
            ClimateRecord.timestamp <= end).first()
        avg_t = row[0] if row and row[0] else None
        if avg_t is None:
            continue
        bk = "<=24" if avg_t <= 24 else "24-26" if avg_t <= 26 else "26-28" if avg_t <= 28 else "28-30" if avg_t <= 30 else ">30"
        if b.chair_environment in data[bk]:
            data[bk][b.chair_environment] += 1
    return {"bins": bins, "data": data}

def get_matrix_heatmap(db, batch_ids=None):
    bq = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        bq = bq.filter(BehaviorRecord.batch_id.in_(batch_ids))
    cells = []
    for b in bq.all():
        if b.chair_number is None or not b.start_time:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.wbgt)).filter(
            ClimateRecord.batch_id == b.batch_id, ClimateRecord.timestamp >= b.start_time,
            ClimateRecord.timestamp <= end).first()
        wbgt = round(row[0], 1) if row and row[0] else None
        st = b.start_time.strftime("%H:%M") if hasattr(b.start_time, "strftime") else str(b.start_time)[:5]
        cells.append({"x": str(b.chair_number), "y": st, "v": wbgt, "behav": b.behavior_category or ""})
    chairs = sorted(set(c["x"] for c in cells))
    return {"chairs": chairs, "cells": cells}


def get_behavior_by_temp(db, batch_ids=None):
    bins = ["<=24","24-26","26-28","28-30",">30"]
    bq = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        bq = bq.filter(BehaviorRecord.batch_id.in_(batch_ids))
    data = {}
    for b in bq.all():
        if not b.behavior_category or not b.start_time:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.temperature)).filter(
            ClimateRecord.batch_id == b.batch_id,
            ClimateRecord.timestamp >= b.start_time,
            ClimateRecord.timestamp <= end).first()
        avg_t = row[0] if row and row[0] else None
        if avg_t is None:
            continue
        bk = "<=24" if avg_t <= 24 else "24-26" if avg_t <= 26 else "26-28" if avg_t <= 28 else "28-30" if avg_t <= 30 else ">30"
        if bk not in data:
            data[bk] = {}
        cat = b.behavior_category
        data[bk][cat] = data[bk].get(cat, 0) + 1
    return {"bins": bins, "data": data}


def get_shade_by_age(db, batch_ids=None):
    q = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        q = q.filter(BehaviorRecord.batch_id.in_(batch_ids))
    ages = {}
    for b in q.all():
        if not b.chair_environment or not b.age:
            continue
        age = b.age.strip()
        if age not in ages:
            ages[age] = {}
        env = b.chair_environment
        ages[age][env] = ages[age].get(env, 0) + 1
    return {"ages": list(ages.keys()), "data": ages}


def get_wbgt_age_behavior(db, batch_ids=None):
    """WBGT-年龄-行为三重分析"""
    bq = db.query(BehaviorRecord).order_by(BehaviorRecord.batch_id)
    if batch_ids:
        bq = bq.filter(BehaviorRecord.batch_id.in_(batch_ids))
    rows = []
    for b in bq.all():
        if not b.behavior_category or not b.start_time or not b.age:
            continue
        end = b.end_time if b.end_time else b.start_time
        if isinstance(b.start_time, str) or isinstance(end, str):
            continue
        row = db.query(sqlfunc.avg(ClimateRecord.wbgt)).filter(
            ClimateRecord.batch_id == b.batch_id,
            ClimateRecord.timestamp >= b.start_time,
            ClimateRecord.timestamp <= end).first()
        wbgt = row[0] if row and row[0] else None
        if wbgt is None:
            continue
        if wbgt < 28:
            zone = 'Safe<28'
        elif wbgt < 30:
            zone = 'Caution28-30'
        elif wbgt < 32:
            zone = 'Danger30-32'
        else:
            zone = 'Extreme>=32'
        ages = [a.strip() for a in b.age.split('+')] if '+' in b.age else [b.age.strip()]
        for age in ages:
            if not age:
                continue
            rows.append({'age': age, 'zone': zone, 'behavior': b.behavior_category, 'wbgt': round(wbgt, 1)})
    groups = {}
    for r in rows:
        key = r['age'] + '|' + r['zone']
        if key not in groups:
            groups[key] = {'age': r['age'], 'zone': r['zone'], 'behaviors': {}}
        groups[key]['behaviors'][r['behavior']] = groups[key]['behaviors'].get(r['behavior'], 0) + 1
    order = ['青年', '中年', '老年']
    zone_order = ['Safe<28', 'Caution28-30', 'Danger30-32', 'Extreme>=32']
    sorted_keys = sorted(groups.keys(), key=lambda k: (order.index(groups[k]['age']) if groups[k]['age'] in order else 99, zone_order.index(groups[k]['zone']) if groups[k]['zone'] in zone_order else 99))
    return [groups[k] for k in sorted_keys]
