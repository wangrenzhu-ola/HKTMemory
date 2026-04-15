import json
import sys
import urllib.request
from pathlib import Path


BASE = "http://127.0.0.1:8765"
ID_FILE = Path("/tmp/hktmemory_acceptance_http_id.txt")


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read().decode())


def main() -> None:
    action = sys.argv[1]
    if action == "store-check":
        store_payload = {
            "content": "张三是工程师，负责平台架构设计。该事实有效期至 2024-01-01。",
            "title": "张三职业信息",
            "topic": "people",
        }
        store_resp = post("/store", store_payload)
        memory_id = store_resp["result"]["memory_ids"]["L2"]
        ID_FILE.write_text(memory_id, encoding="utf-8")
        print("STORE=", json.dumps(store_resp, ensure_ascii=False))

        recall_resp = post("/recall", {"query": "张三 工程师", "layer": "all", "limit": 5})
        print("RECALL=", json.dumps(recall_resp, ensure_ascii=False))

        stats_resp = json.loads(urllib.request.urlopen(BASE + "/stats").read().decode())
        summary = {
            "success": stats_resp["success"],
            "filter_count": stats_resp["result"]["layers"]["lifecycle"]["filter_count"],
        }
        print("STATS=", json.dumps(summary, ensure_ascii=False))
    elif action == "forget":
        memory_id = ID_FILE.read_text(encoding="utf-8").strip()
        forget_resp = post("/forget", {"memory_id": memory_id})
        print("FORGET=", json.dumps(forget_resp, ensure_ascii=False))
    else:
        raise SystemExit(f"unknown action: {action}")


if __name__ == "__main__":
    main()
