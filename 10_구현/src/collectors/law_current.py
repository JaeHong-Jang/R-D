"""최근 공포된 현행 법령의 목록과 본문(조문·부칙·제개정이유)을 받는다. target=law

실행:  python law_current.py             # 최근 7일 공포분
       python law_current.py --days 90   # 최근 90일 공포분
저장:  09_데이터/raw/law_go_kr/law_current/<수집일>/list_page_NNN.json, bodies/<법령일련번호>.json
이미 받은 법령 본문은 다시 받지 않는다.
"""
import argparse
import json
from datetime import date, timedelta

import law_go_kr  # config 경로 설정이 여기서 되므로 먼저 가져온다
import config  # noqa: E402

DATASET_ID = "law_current"


def collect(days=7):
    out = config.raw_dir("law_go_kr", DATASET_ID)
    done = config.collected_names("law_go_kr", DATASET_ID, "bodies/*.json")
    period = f"{(date.today() - timedelta(days=days)):%Y%m%d}~{date.today():%Y%m%d}"

    # 1) 공포일 범위로 목록을 쪽마다 받는다
    laws, page = [], 1
    while True:
        text = law_go_kr.get("lawSearch.do", target="law", type="JSON", ancYd=period, sort="ddes", display=100, page=page)
        (out / f"list_page_{page:03d}.json").write_text(text, encoding="utf-8")
        body = json.loads(text)["LawSearch"]
        rows = body.get("law") or []
        rows = [rows] if isinstance(rows, dict) else rows  # 1건이면 목록이 아니라 객체로 온다
        laws += rows
        if page * 100 >= int(body["totalCnt"]) or not rows:
            break
        page += 1

    # 2) 아직 없는 법령만 본문을 받는다
    (out / "bodies").mkdir(exist_ok=True)
    new = 0
    for law in laws:
        mst = law["법령일련번호"]
        if mst in done:
            continue
        text = law_go_kr.get("lawService.do", target="law", type="JSON", MST=mst)
        (out / "bodies" / f"{mst}.json").write_text(text, encoding="utf-8")
        done.add(mst)
        new += 1
    print(f"[{DATASET_ID}] 공포 {period} 목록 {len(laws)}건, 새 본문 {new}건 → {out}")
    return new


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=7, help="오늘부터 며칠 전 공포분까지 받을지")
    collect(ap.parse_args().days)
