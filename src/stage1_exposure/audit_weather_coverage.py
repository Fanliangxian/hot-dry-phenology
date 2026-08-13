from pathlib import Path
import json
import numpy as np
import pyarrow.dataset as pads
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results" / "fixed_window_runs" / "fixed_window_v01"
ZARR = ROOT.parent / "Pixel_level_results" / "ERA5_daily_cells.zarr"

windows = pads.dataset(RUN / "windows_by_bucket", format="parquet", partitioning="hive")
used = set()
for batch in windows.to_batches(columns=["cell_index"], batch_size=500_000):
    used.update(np.unique(batch.column(0).to_numpy(zero_copy_only=False)).tolist())
ds = xr.open_zarr(ZARR, consolidated=False)
allnan_t, allnan_v, allnan_either, used_bad = 0, 0, 0, []
for start in range(0, ds.sizes["cell"], 2000):
    stop = min(start + 2000, ds.sizes["cell"])
    t = ds["Tmax"].isel(cell=slice(start, stop)).values
    v = ds["VPD"].isel(cell=slice(start, stop)).values
    bt = np.isnan(t).all(axis=0)
    bv = np.isnan(v).all(axis=0)
    bad = bt | bv
    allnan_t += int(bt.sum()); allnan_v += int(bv.sum()); allnan_either += int(bad.sum())
    used_bad.extend([int(start + i) for i in np.flatnonzero(bad) if start + i in used])
result = {"total_cells": int(ds.sizes["cell"]), "used_cells": len(used), "all_nan_tmax_cells": allnan_t,
          "all_nan_vpd_cells": allnan_v, "all_nan_either_cells": allnan_either,
          "used_all_nan_either_cells": len(used_bad), "used_bad_cell_indices": used_bad}
(RUN / "weather_coverage_qc.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result))

