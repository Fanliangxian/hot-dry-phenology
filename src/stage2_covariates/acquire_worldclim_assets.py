from __future__ import annotations

import csv
import hashlib
import ssl
import urllib.request
import zipfile
from pathlib import Path
import os

ROOT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd())) / "stage2_covariate_inventory/stage2b_results"
ASSETS = ROOT / "assets"
SOURCES = {
    "worldclim21_prec_10m": (
        "http://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_prec.zip",
        "WorldClim 2.1 monthly precipitation climatology, 1970-2000, 10 arc-min, mm",
    ),
    "worldclim21_elev_10m": (
        "http://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_elev.zip",
        "WorldClim 2.1 elevation, 10 arc-min, m above sea level",
    ),
}


def download_in_ranges(url: str, target: Path, context: ssl.SSLContext, chunk_size: int = 262_144) -> None:
    head = urllib.request.Request(url.replace("http://", "https://"), method="HEAD")
    with urllib.request.urlopen(head, context=context, timeout=60) as response:
        total = int(response.headers["Content-Length"])
    with target.open("wb") as handle:
        for start in range(0, total, chunk_size):
            stop = min(start + chunk_size - 1, total - 1)
            request = urllib.request.Request(
                url.replace("http://", "https://"), headers={"Range": f"bytes={start}-{stop}"}
            )
            with urllib.request.urlopen(request, context=context, timeout=60) as response:
                payload = response.read()
            if len(payload) != stop - start + 1:
                raise IOError(f"Short range download for {url}: {start}-{stop}")
            handle.write(payload)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    rows = []
    context = ssl._create_unverified_context()
    for name, (url, description) in SOURCES.items():
        archive = ASSETS / f"{name}.zip"
        if not archive.exists() or not zipfile.is_zipfile(archive):
            download_in_ranges(url, archive, context)
        extract_dir = ASSETS / name
        extract_dir.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            bundle.testzip()
            bundle.extractall(extract_dir)
        members = sorted(str(p.relative_to(ROOT)) for p in extract_dir.rglob("*") if p.is_file())
        rows.append({
            "asset": name,
            "source_url": url,
            "description": description,
            "archive_bytes": archive.stat().st_size,
            "sha256": sha256(archive),
            "files": "|".join(members),
            "status": "ready",
        })
    with (ASSETS / "asset_manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()


