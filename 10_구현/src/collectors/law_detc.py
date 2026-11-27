"""헌법재판소 결정례의 목록과 본문(주문·이유 전문)을 최신 종국일자순으로 받는다. target=detc

실행:  python law_detc.py              # 최신 100건
       python law_detc.py --pages 10   # 최신 1,000건
저장:  09_데이터/raw/law_go_kr/law_detc/<수집일>/list_page_NNN.json, bodies/<결정례일련번호>.xml
본문은 JSON을 요청하면 HTML이 와서 XML로 받는다. 이미 받은 결정례는 다시 받지 않는다.
"""
import argparse
import json

import law_go_kr  # config 경로 설정이 여기서 되므로 먼저 가져온다
import config  # noqa: E402

DATASET_ID = "law_detc"


def collect(pages=1):
    out = config.raw_dir("law_go_kr", DATASET_ID)
    done = config.collected_names("law_go_kr", DATASET_ID, "bodies/*.xml")

    # 1) 종국일자 내림차순 목록을 쪽마다 받는다
    cases = []
    for page in range(1, pages + 1):
        text = law_go_kr.get("lawSearch.do", target="detc", type="JSON", sort="ddes", display=100, page=page)
        (out / f"list_page_{page:03d}.json").write_text(text, encoding="utf-8")
        rows = json.loads(text)["DetcSearch"].get("Detc") or []
        cases += [rows] if isinstance(rows, dict) else rows
        if not rows:
            break

    # 2) 아직 없는 결정례만 본문을 받는다
    (out / "bodies").mkdir(exist_ok=True)
    new = 0
    for case in cases:
        cid = case["헌재결정례일련번호"]
        if cid in done:
            continue
        text = law_go_kr.get("lawService.do", target="detc", type="XML", ID=cid)
        (out / "bodies" / f"{cid}.xml").write_text(text, encoding="utf-8")
        done.add(cid)
        new += 1
    print(f"[{DATASET_ID}] 목록 {len(cases)}건, 새 본문 {new}건 → {out}")
    return new


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", type=int, default=1, help="받을 목록 쪽수 (한 쪽 100건, 최신순)")
    collect(ap.parse_args().pages)
