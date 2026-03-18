#!/usr/bin/env python3
"""
Download USGS pesticide data from ScienceBase to data/ for offline use.
Run when ScienceBase is reachable; the build notebook will use these files
if the URL fetch times out (e.g. behind firewall/VPN).

Usage:
    python scripts/download_pesticide_data.py

Output: data/pesticide_2016_17.tsv, data/pesticide_2018.tsv, data/pesticide_2019.tsv
"""
import os
import sys

try:
    import requests  # type: ignore
    from requests.adapters import HTTPAdapter  # type: ignore
    from urllib3.util.retry import Retry  # type: ignore
    HAS_REQUESTS = True
except Exception:
    # Fallback: keep script runnable in minimal environments (no requests installed).
    HAS_REQUESTS = False
    requests = None  # type: ignore
    HTTPAdapter = None  # type: ignore
    Retry = None  # type: ignore

import time
import urllib.request
import urllib.error

# URLs from EDA/build_joint_dataset.ipynb
URLS = {
    "pesticide_2016_17.tsv": "https://www.sciencebase.gov/catalog/file/get/5e95c12282ce172707f2524e?f=__disk__62%2F83%2Fd3%2F6283d3501f1028b1ccc3976ea2e6de848bc2fef8&allowOpen=true",
    "pesticide_2018.tsv": "https://www.sciencebase.gov/catalog/file/get/6081a706d34e8564d686618e?f=__disk__58%2F6a%2Fed%2F586aed9a844eac0174a0600c8a7293ec4cda0265&allowOpen=true",
    "pesticide_2019.tsv": "https://www.sciencebase.gov/catalog/file/get/6081a924d34e8564d68661a1?f=__disk__08%2F42%2Fcd%2F0842cdac3a7d8b5056645a4dc08d1da96ad4e0b7&allowOpen=true",
}

CONNECT_TIMEOUT = 30  # seconds
READ_TIMEOUT = 300  # seconds per file


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "..", "data")
    os.makedirs(data_dir, exist_ok=True)

    session = None
    if HAS_REQUESTS:
        session = requests.Session()
        retry = Retry(
            total=6,
            connect=6,
            read=6,
            status=6,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

    for filename, url in URLS.items():
        path = os.path.join(data_dir, filename)
        print(f"Downloading {filename}...", end=" ", flush=True)
        try:
            if HAS_REQUESTS and session is not None:
                r = session.get(
                    url,
                    timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                    headers={"User-Agent": "spring-2026-pesticide-exposure/1.0 (+requests)"},
                )
                r.raise_for_status()
                text = r.text
            else:
                # urllib fallback with basic retries/backoff
                last_err = None
                text = None
                for attempt in range(1, 7):
                    try:
                        req = urllib.request.Request(
                            url,
                            headers={"User-Agent": "spring-2026-pesticide-exposure/1.0 (+urllib)"},
                            method="GET",
                        )
                        with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as resp:
                            raw = resp.read()
                        text = raw.decode("utf-8", errors="replace")
                        break
                    except (urllib.error.URLError, TimeoutError, OSError) as e:
                        last_err = e
                        time.sleep(min(30, 2 ** (attempt - 1)))
                if text is None:
                    raise RuntimeError(last_err)

            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"OK ({len(text):,} chars)")
        except Exception as e:
            print(f"FAILED: {e}")
            if os.path.isfile(path):
                print(f"Keeping existing local file: {path}")
                continue
            sys.exit(1)

    print("Done. Pesticide data saved to data/")


if __name__ == "__main__":
    main()
