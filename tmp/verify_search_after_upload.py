import requests, json
BASE = "http://localhost:8000/api/v1"
login = requests.post(f"{BASE}/auth/login", json={"username":"demo","password":"demo123"}, timeout=20)
login.raise_for_status()
token = login.json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}
q = {"query":"FastAPI 核心原理 异步 依赖注入", "top_k":5, "visibility":"PUBLIC"}
r = requests.post(f"{BASE}/knowledge/search", headers=headers, json=q, timeout=30)
print(r.status_code)
js = r.json()
items = js.get("data",{}).get("results",[])
print(json.dumps(items[:5], ensure_ascii=False))
