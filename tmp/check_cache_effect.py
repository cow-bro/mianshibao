import json, time
import requests

BASE = "http://localhost:8000/api/v1"
login = requests.post(f"{BASE}/auth/login", json={"username":"demo","password":"demo123"}, timeout=20)
login.raise_for_status()
token = login.json().get("data", {}).get("access_token")
headers = {"Authorization": f"Bearer {token}"}
payload = {"query": "FastAPI 依赖注入与异步数据库会话", "top_k": 10, "visibility": "PUBLIC"}

times = []
for i in range(10):
    t0 = time.perf_counter()
    r = requests.post(f"{BASE}/knowledge/search", headers=headers, json=payload, timeout=30)
    ms = (time.perf_counter() - t0) * 1000
    times.append(round(ms,2))
    print(f"req{i+1} status={r.status_code} ms={ms:.2f}")

print("TIMES_JSON=" + json.dumps(times, ensure_ascii=False))
