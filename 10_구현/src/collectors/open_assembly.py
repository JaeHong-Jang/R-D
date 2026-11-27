"""열린국회정보 Open API 공통 호출 함수. 데이터셋별 수집기(assembly_*.py)가 가져다 쓴다.

인증키: .env 의 ASSEMBLY_KEY (발급: open.assembly.go.kr 로그인 → 마이페이지 → 인증키 발급)
키가 없으면 API마다 5건만 내려오는 시험 모드로 동작한다.
"""
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

API = "https://open.assembly.go.kr/portal/openapi/"
PAGE_SIZE = 1000  # API 최대값


def fetch(code, age, page, key):
    """한 쪽을 받아 행 목록을 돌려준다. 데이터가 더 없으면 빈 목록."""
    params = {"Type": "json", "AGE": age, "pIndex": page, "pSize": PAGE_SIZE}
    if key:
        params["KEY"] = key
    r = requests.get(API + code, params=params, headers={"User-Agent": config.USER_AGENT}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if code not in data:  # 오류와 '데이터 없음'은 HTTP 200에 RESULT만 담겨 온다
        result = data["RESULT"]
        if result["CODE"] == "INFO-200":
            return []
        raise RuntimeError(f"국회 API 오류 {result['CODE']}: {result['MESSAGE']}")
    return data[code][1]["row"]


def collect(dataset_id, code, pages=1, age="22"):
    """최신순으로 pages 쪽을 받아 오늘 수집일 폴더에 쪽마다 JSON으로 저장한다."""
    key = config.env("ASSEMBLY_KEY")
    if not key:
        print(f"[{dataset_id}] .env 에 ASSEMBLY_KEY 가 없어 시험 모드로 받습니다 (5건)")
        pages = 1  # 시험 모드는 1쪽만 내려온다
    out = config.raw_dir("open_assembly", dataset_id)
    total = 0
    for page in range(1, pages + 1):
        rows = fetch(code, age, page, key)
        if not rows:
            break
        (out / f"page_{page:03d}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        total += len(rows)
        if len(rows) < PAGE_SIZE:
            break
        time.sleep(1)
    print(f"[{dataset_id}] {total:,}건 저장 → {out}")
    return total
