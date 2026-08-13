from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as pads
import pyarrow.parquet as pq
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stage1.events import get_run_intervals
from stage1.io import atomic_write_json, load_config


WINDOW_COLUMNS = [
    "pixel_id", "year", "pheno_type", "landscape_type", "lat_band", "era_cell_id",
    "pheno_value", "anomaly", "abs_anomaly", "anomaly_crossfit", "abs_anomaly_crossfit",
]


def noleap_doy(index: pd.DatetimeIndex) -> np.ndarray:
    doy = np.asarray(index.dayofyear)
    return np.where(np.asarray(index.is_leap_year) & (np.asarray(index.month) > 2), doy - 1, doy).astype(np.int16)


def circular_masks(doys: np.ndarray) -> list[np.ndarray]:
    masks = []
    for target in range(1, 366):
        distance = np.abs(doys - target)
        masks.append(np.minimum(distance, 365 - distance) <= 15)
    return masks


def build_pixel_stats(parquet_path: Path) -> pd.DataFrame:
    parts = []
    parquet = pq.ParquetFile(parquet_path)
    for batch in parquet.iter_batches(batch_size=400000, columns=["pixel_id", "pheno_value"]):
        frame = batch.to_pandas()
        frame["valid_n"] = frame["pheno_value"].notna().astype("int16")
        frame["pheno_sum"] = frame["pheno_value"].fillna(0.0)
        parts.append(frame.groupby("pixel_id", sort=False, observed=True)[["valid_n", "pheno_sum"]].sum().reset_index())
    return pd.concat(parts, ignore_index=True).groupby("pixel_id", sort=False, observed=True)[["valid_n", "pheno_sum"]].sum().reset_index()


def prepare_window_dataset(parquet_paths: list[Path], cell_lookup: pd.DataFrame, output: Path) -> list[dict]:
    if output.exists():
        raise FileExistsError(f"Window dataset already exists; use a new run directory: {output}")
    output.mkdir(parents=True)
    summaries = []
    for source_id, path in enumerate(parquet_paths):
        stats = build_pixel_stats(path)
        writer_index = 0
        row_count = 0
        missing_cell = 0
        missing_anchor = 0
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=300000, columns=WINDOW_COLUMNS):
            frame = batch.to_pandas().merge(stats, on="pixel_id", how="left", validate="many_to_one")
            frame = frame.merge(cell_lookup, on="era_cell_id", how="left", validate="many_to_one")
            denom = frame["valid_n"] - frame["pheno_value"].notna().astype("int16")
            frame["climatology_doy_loo"] = (frame["pheno_sum"] - frame["pheno_value"]) / denom.replace(0, np.nan)
            frame["source_id"] = np.int8(source_id)
            frame["cell_bucket"] = (frame["cell_index"] // 2000).astype("Int16")
            missing_cell += int(frame["cell_index"].isna().sum())
            missing_anchor += int(frame["climatology_doy_loo"].isna().sum())
            frame = frame.dropna(subset=["cell_index", "climatology_doy_loo"]).copy()
            frame["cell_index"] = frame["cell_index"].astype("int32")
            frame["cell_bucket"] = frame["cell_bucket"].astype("int16")
            keep = WINDOW_COLUMNS + ["climatology_doy_loo", "source_id", "cell_bucket", "cell_index"]
            table = pa.Table.from_pandas(frame[keep], preserve_index=False)
            pq.write_to_dataset(
                table, root_path=output, partition_cols=["source_id", "cell_bucket"],
                basename_template=f"batch-{writer_index}-{{i}}.parquet", compression="zstd",
                existing_data_behavior="overwrite_or_ignore",
            )
            writer_index += 1
            row_count += len(frame)
        summaries.append({
            "source_id": source_id, "source": str(path), "prepared_rows": row_count,
            "unique_pixels": int(len(stats)), "missing_cell_rows": missing_cell,
            "missing_climatology_rows": missing_anchor,
        })
    return summaries


def anchor_dates(year: np.ndarray, doy: np.ndarray) -> np.ndarray:
    rounded = np.clip(np.rint(doy), 1, 365).astype(int)
    years = year.astype(int)
    leap = (years % 4 == 0) & ((years % 100 != 0) | (years % 400 == 0))
    extra = (leap & (rounded >= 60)).astype(int)
    starts = pd.to_datetime(years.astype(str), format="%Y").to_numpy(dtype="datetime64[D]")
    return starts + (rounded - 1 + extra).astype("timedelta64[D]")


def interval_metrics_vectorized(intervals: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> tuple[np.ndarray, ...]:
    n = len(starts)
    if intervals.size == 0:
        zeros = np.zeros(n, dtype=np.int16)
        return zeros.astype(np.int8), zeros, zeros, zeros
    overlap_start = np.maximum(starts[:, None], intervals[None, :, 0])
    overlap_end = np.minimum(ends[:, None], intervals[None, :, 1])
    lengths = np.maximum(overlap_end - overlap_start + 1, 0)
    occurrence = (lengths.max(axis=1) > 0).astype(np.int8)
    n_events = (lengths > 0).sum(axis=1).astype(np.int16)
    cumulative = lengths.sum(axis=1).astype(np.int16)
    maximum = lengths.max(axis=1).astype(np.int16)
    return occurrence, n_events, cumulative, maximum


def calculate_thresholds(tmax: np.ndarray, vpd: np.ndarray, masks: list[np.ndarray], doys: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_cells = tmax.shape[1]
    t_threshold = np.empty((365, n_cells), dtype=np.float32)
    v_threshold = np.empty((365, n_cells), dtype=np.float32)
    for day, mask in enumerate(masks):
        t_threshold[day] = np.nanpercentile(tmax[mask], 90, axis=0)
        v_threshold[day] = np.nanpercentile(vpd[mask], 90, axis=0)
    idx = doys - 1
    valid = np.isfinite(tmax) & np.isfinite(vpd)
    compound = valid & (tmax > t_threshold[idx]) & (vpd > v_threshold[idx])
    return compound, t_threshold, v_threshold


def process_bucket(
    ds: xr.Dataset, windows: pads.Dataset, source_ids: list[int], bucket: int,
    time_index: pd.DatetimeIndex, doys: np.ndarray, masks: list[np.ndarray],
    gap_days: list[int], output: Path,
) -> dict:
    cell_start = bucket * 2000
    cell_end = min((bucket + 1) * 2000, ds.sizes["cell"])
    tmax = ds["Tmax"].isel(cell=slice(cell_start, cell_end)).load().values
    vpd = ds["VPD"].isel(cell=slice(cell_start, cell_end)).load().values
    compound, t_threshold, v_threshold = calculate_thresholds(tmax, vpd, masks, doys)
    bucket_rows = 0
    output_rows = 0
    time_values = time_index.to_numpy(dtype="datetime64[D]")
    min_date, max_date = time_values[0], time_values[-1]
    for source_id in source_ids:
        filt = (pads.field("source_id") == source_id) & (pads.field("cell_bucket") == bucket)
        table = windows.to_table(filter=filt)
        if table.num_rows == 0:
            continue
        frame = table.to_pandas()
        bucket_rows += len(frame)
        anchor = anchor_dates(frame["year"].to_numpy(), frame["climatology_doy_loo"].to_numpy())
        parts = []
        for gap in gap_days:
            end_dates = anchor - np.timedelta64(1 + gap, "D")
            start_dates = end_dates - np.timedelta64(89, "D")
            start_idx = np.searchsorted(time_values, start_dates, side="left")
            end_idx = np.searchsorted(time_values, end_dates, side="right") - 1
            complete = (start_dates >= min_date) & (end_dates <= max_date) & (start_idx <= end_idx)
            part = frame.copy()
            part["gap_days"] = np.int8(gap)
            part["fixed_window_start"] = start_dates
            part["fixed_window_end"] = end_dates
            part["window_complete"] = complete
            for suffix in ["3d", "5d"]:
                for metric in ["occurrence", "n_events", "cumulative_days", "max_duration"]:
                    part[f"event_{suffix}_{metric}"] = 0
            for cell_index, indices in part.groupby("cell_index", sort=False).groups.items():
                pos = np.asarray(list(indices), dtype=int)
                local = int(cell_index) - cell_start
                if local < 0 or local >= compound.shape[1]:
                    raise ValueError(f"Cell {cell_index} outside bucket {bucket}")
                for min_length, suffix in [(3, "3d"), (5, "5d")]:
                    intervals = get_run_intervals(compound[:, local], min_length=min_length)
                    metrics = interval_metrics_vectorized(intervals, start_idx[pos], end_idx[pos])
                    for name, values in zip(["occurrence", "n_events", "cumulative_days", "max_duration"], metrics):
                        values = values.copy(); values[~complete[pos]] = 0
                        part.loc[pos, f"event_{suffix}_{name}"] = values
            parts.append(part)
        result = pd.concat(parts, ignore_index=True)
        result["source_id"] = np.int8(source_id)
        result["cell_bucket"] = np.int16(bucket)
        target = output / f"source_id={source_id}" / f"cell_bucket={bucket}"
        target.mkdir(parents=True, exist_ok=True)
        file_result = result.drop(columns=["source_id", "cell_bucket"], errors="ignore")
        pq.write_table(pa.Table.from_pandas(file_result, preserve_index=False), target / "part.parquet", compression="zstd")
        output_rows += len(result)
    return {
        "bucket": bucket, "cell_start": cell_start, "cell_end": cell_end,
        "window_rows": bucket_rows, "output_rows": output_rows,
        "tmax_min": float(np.nanmin(tmax)), "tmax_max": float(np.nanmax(tmax)),
        "vpd_min": float(np.nanmin(vpd)), "vpd_max": float(np.nanmax(vpd)),
        "tmax_threshold_min": float(np.nanmin(t_threshold)), "tmax_threshold_max": float(np.nanmax(t_threshold)),
        "vpd_threshold_min": float(np.nanmin(v_threshold)), "vpd_threshold_max": float(np.nanmax(v_threshold)),
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-buckets", type=int, default=None, help="Process only the first N buckets for validation")
    parser.add_argument("--run-id", default="fixed_window_v01")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(ROOT / "config" / "stage1_config.json")
    zarr_path = Path(config["daily_era5_zarr"])
    run_root = ROOT / "results" / "fixed_window_runs" / args.run_id
    status_path = run_root / "run_status.json"
    if not zarr_path.exists():
        atomic_write_json({"status": "blocked_missing_daily_era5", "required_path": str(zarr_path)}, status_path)
        return 3
    ds = xr.open_zarr(zarr_path, consolidated=False)
    required = {"Tmax", "VPD", "era_row", "era_col", "time"}
    missing = sorted(required - set(ds.variables))
    if missing:
        atomic_write_json({"status": "invalid_zarr_schema", "missing": missing}, status_path)
        return 4
    time_index = pd.to_datetime(ds["time"].values)
    doys = noleap_doy(time_index)
    masks = circular_masks(doys)
    era_rows = ds["era_row"].values.astype(int)
    era_cols = ds["era_col"].values.astype(int)
    cell_lookup = pd.DataFrame({
        "era_cell_id": [f"{r}_{c}" for r, c in zip(era_rows, era_cols)],
        "cell_index": np.arange(ds.sizes["cell"], dtype=np.int32),
    })
    baseline_paths = sorted((ROOT / "results" / "baseline").glob("crossfit_*.parquet"))
    if len(baseline_paths) != 4:
        raise ValueError(f"Expected four crossfit parquet files, found {len(baseline_paths)}")
    windows_path = run_root / "windows_by_bucket"
    events_path = run_root / "events_by_bucket"
    run_root.mkdir(parents=True, exist_ok=True)
    window_summary = prepare_window_dataset(baseline_paths, cell_lookup, windows_path)
    pd.DataFrame(window_summary).to_csv(run_root / "window_preparation_qc.csv", index=False, encoding="utf-8-sig")
    windows = pads.dataset(windows_path, format="parquet", partitioning="hive")
    n_buckets = math.ceil(ds.sizes["cell"] / 2000)
    buckets = list(range(n_buckets))
    if args.max_buckets is not None:
        buckets = buckets[: args.max_buckets]
    bucket_qc = []
    for bucket in buckets:
        info = process_bucket(
            ds, windows, list(range(4)), bucket, time_index, doys, masks,
            config["windows"]["gap_days"], events_path,
        )
        bucket_qc.append(info)
        pd.DataFrame(bucket_qc).to_csv(run_root / "bucket_qc.csv", index=False, encoding="utf-8-sig")
        print(json.dumps(info), flush=True)
    status = {
        "status": "validation_partial" if args.max_buckets is not None and len(buckets) < n_buckets else "complete",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "zarr": str(zarr_path), "zarr_shape": {"time": ds.sizes["time"], "cell": ds.sizes["cell"]},
        "time_start": str(time_index.min().date()), "time_end": str(time_index.max().date()),
        "threshold_percentile": 90, "threshold_window_days": 31,
        "event_min_lengths": [3, 5], "gap_days": config["windows"]["gap_days"],
        "processed_buckets": buckets, "total_buckets": n_buckets,
        "tmax_metadata_units": ds["Tmax"].attrs.get("units"),
        "tmax_observed_unit_warning": "Metadata says K but observed values are Celsius-like; percentile exceedance is unit-invariant.",
    }
    atomic_write_json(status, status_path)
    print(json.dumps(status, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

