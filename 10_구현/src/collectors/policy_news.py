"""정책브리핑 정책뉴스(부처별 정책 기사, 본문 포함)를 하루 단위로 받는다. 공공데이터포털 policyNewsList2

실행:  python policy_news.py             # 최근 3일 (매일 실행용, 늦게 수정된 기사도 다시 받음)
       python policy_news.py --days 90   # 최근 90일 (처음 한 번)
저장:  09_데이터/raw/data_go_kr/policy_news/<수집일>/<기사일 YYYYMMDD>.xml
인증키: .env 의 DATA_GO_KR_KEY. 개발계정은 하루 1,000회까지.
조회 기간이 3일을 넘으면 오류(THREE_DAYS_OVER_ERROR)라 하루씩 나눠 부른다. 보도자료는 들어 있지 않다(GroupingCode=policy만 확인).
"""
import argparse
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

API = "https://apis.data.go.kr/1371000/policyNewsService2/policyNewsList2"
DATASET_ID = "policy_news"


def fetch(day, key):
    """하루치 응답 XML을 받는다. 오류도 HTTP 200으로 오므로 결과 코드를 확인한다."""
    stamp = f"{day:%Y%m%d}"
    for attempt in range(3):  # 포털 서버가 가끔 연결을 끊어 세 번까지 다시 시도한다
        try:
            r = requests.get(API, params={"serviceKey": key, "startDate": stamp, "endDate": stamp},
                             headers={"User-Agent": config.USER_AGENT}, timeout=60)
            r.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt == 2:  # 원래 오류 메시지에는 인증키가 든 주소가 있어 이름만 남긴다
                raise RuntimeError(f"정책뉴스 API 연결 실패 ({stamp}): {type(e).__name__}") from None
            time.sleep(10)
    code = re.search(r"<(?:resultCode|returnReasonCode)>(.*?)<", r.text)
    if not code or code.group(1) not in ("0", "00"):
        msg = re.search(r"<(?:resultMsg|returnAuthMsg)>(.*?)<", r.text)
        raise RuntimeError(f"정책뉴스 API 오류 {code and code.group(1)}: {msg and msg.group(1)}")
    return r.text


def collect(days=3):
    key = config.env("DATA_GO_KR_KEY")
    if not key:
        raise RuntimeError(".env 에 DATA_GO_KR_KEY 가 없습니다")
    out = config.raw_dir("data_go_kr", DATASET_ID)
    total = 0
    for back in range(days):  # 오늘부터 하루씩 거슬러 올라간다
        day = date.today() - timedelta(days=back)
        text = fetch(day, key)
        (out / f"{day:%Y%m%d}.xml").write_text(text, encoding="utf-8")
        total += text.count("<NewsItem>")
        time.sleep(0.5)
    print(f"[{DATASET_ID}] 최근 {days}일 기사 {total}건 → {out}")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--days", type=int, default=3, help="오늘부터 며칠 전까지 받을지")
    collect(ap.parse_args().days)
