"""매일 돌리는 수집 진입점. 뉴스 → 국회 → 법제처 순서로 수집기를 실행하고 결과를 로그에 남긴다.

실행:  python 10_구현/scripts/collect_daily.py
로그:  09_데이터/raw/collect_log.txt (실행 시각과 수집기별 결과·오류)
한 수집기가 실패해도 나머지는 계속 돌린다.
"""
import sys
import traceback
from datetime import datetime
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path[:0] = [str(SRC), str(SRC / "collectors")]

import assembly_bills  # noqa: E402
import assembly_votes  # noqa: E402
import config  # noqa: E402
import law_current  # noqa: E402
import law_detc  # noqa: E402
import news_press  # noqa: E402

# 수집기 이름과 실행 함수. 뉴스는 명령줄 인자를 쓰므로 기본값으로 실행한다.
JOBS = [
    ("news_press", lambda: news_press.main()),
    ("assembly_bills", lambda: assembly_bills.collect()),
    ("assembly_votes", lambda: assembly_votes.collect()),
    ("law_current", lambda: law_current.collect()),
    ("law_detc", lambda: law_detc.collect()),
]


def main():
    sys.argv = sys.argv[:1]  # 뉴스 수집기가 이 스크립트의 인자를 읽지 않게 비운다
    log = config.DATA / "raw" / "collect_log.txt"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        for name, job in JOBS:
            started = datetime.now().isoformat(timespec="seconds")
            try:
                result = job()
                f.write(f"{started}\t{name}\t성공\t{result}\n")
            except Exception as e:  # 한 곳이 실패해도 다음 수집기를 돌린다
                traceback.print_exc()
                f.write(f"{started}\t{name}\t실패\t{type(e).__name__}: {e}\n")
            f.flush()
    print(f"로그 → {log}")


if __name__ == "__main__":
    main()
