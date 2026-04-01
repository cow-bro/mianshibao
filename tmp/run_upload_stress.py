import json, time, math, statistics, concurrent.futures
from pathlib import Path
import requests

BASE = "http://localhost:8000/api/v1"

login = requests.post(f"{BASE}/auth/login", json={"username":"demo","password":"demo123"}, timeout=20)
login.raise_for_status()
login_data = login.json()
token = login_data.get("data", {}).get("access_token")
if not token:
    raise RuntimeError(f"login failed: {login_data}")
headers = {"Authorization": f"Bearer {token}"}

files = [
    Path(r"D:/mianshibao/知识文档示例/Python 进阶核心知识解析.pdf"),
    Path(r"D:/mianshibao/知识文档示例/FastAPI：核心原理、代码实战.pdf"),
]

upload_results = []
for fp in files:
    t0 = time.perf_counter()
    with fp.open("rb") as f:
        resp = requests.post(
            f"{BASE}/knowledge/upload",
            headers=headers,
            files={"file": (fp.name, f, "application/pdf")},
            data={"subject": "Backend", "category": "Python", "difficulty": "MEDIUM"},
            timeout=600,
        )
    elapsed = (time.perf_counter() - t0) * 1000
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:1200]}
    upload_results.append({
        "file": fp.name,
        "status_code": resp.status_code,
        "elapsed_ms": round(elapsed, 2),
        "ok": 200 <= resp.status_code < 300,
        "response": body,
    })

# warmup
for _ in range(5):
    requests.post(
        f"{BASE}/knowledge/search",
        headers=headers,
        json={"query": "FastAPI 依赖注入", "top_k": 10, "visibility": "PUBLIC"},
        timeout=30,
    )

TOTAL = 120
CONCURRENCY = 12
payload = {"query": "FastAPI 依赖注入与异步数据库会话", "top_k": 10, "visibility": "PUBLIC"}

lat = []
status_counts = {}
errors = []

def one_req(i: int):
    t0 = time.perf_counter()
    try:
        r = requests.post(f"{BASE}/knowledge/search", headers=headers, json=payload, timeout=30)
        return r.status_code, (time.perf_counter() - t0) * 1000, None
    except Exception as e:
        return -1, (time.perf_counter() - t0) * 1000, str(e)

start = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
    futs = [ex.submit(one_req, i) for i in range(TOTAL)]
    for fu in concurrent.futures.as_completed(futs):
        code, ms, err = fu.result()
        lat.append(ms)
        status_counts[code] = status_counts.get(code, 0) + 1
        if err:
            errors.append(err)
wall = time.perf_counter() - start

lat_sorted = sorted(lat)

def pct(p):
    if not lat_sorted:
        return None
    idx = max(0, min(len(lat_sorted)-1, math.ceil(len(lat_sorted)*p)-1))
    return round(lat_sorted[idx], 2)

success = sum(v for k, v in status_counts.items() if 200 <= k < 300)
result = {
    "upload_results": upload_results,
    "stress": {
        "total_requests": TOTAL,
        "concurrency": CONCURRENCY,
        "wall_time_sec": round(wall, 3),
        "throughput_rps": round(TOTAL / wall, 2) if wall > 0 else None,
        "success_count": success,
        "success_rate": round(success / TOTAL, 4),
        "status_counts": status_counts,
        "latency_ms": {
            "min": round(min(lat_sorted), 2) if lat_sorted else None,
            "mean": round(statistics.mean(lat_sorted), 2) if lat_sorted else None,
            "p50": pct(0.5),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": round(max(lat_sorted), 2) if lat_sorted else None,
        },
        "sample_errors": errors[:5],
    },
}

out = Path(r"D:/mianshibao/tmp/knowledge_upload_stress_result.json")
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
print(f"RESULT_FILE={out}")
