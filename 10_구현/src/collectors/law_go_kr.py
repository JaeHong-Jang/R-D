"""국가법령정보 공동활용 Open API 공통 호출 함수. 데이터셋별 수집기(law_*.py)가 가져다 쓴다.

인증키: .env 의 LAW_OC (open.law.go.kr 에서 신청할 때 직접 정한 값)
신청할 때 등록한 IP에서만 호출된다. IP가 바뀌면 마이페이지에서 다시 등록한다.
"""
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

API = "https://www.law.go.kr/DRF/"  # http 주소는 봇 차단 페이지를 돌려주므로 https만 쓴다
DELAY = 1.0  # 요청 사이 간격(초). 과도한 호출은 이용 제한 대상이다


def oc():
    """인증값을 읽는다. 없으면 실행을 멈춘다."""
    value = config.env("LAW_OC")
    if not value:
        raise RuntimeError(".env 에 LAW_OC 가 없습니다")
    return value


def get(path, **params):
    """한 번 호출해 응답 본문(문자열)을 돌려준다. 인증 실패도 HTTP 200으로 오므로 본문으로 확인한다."""
    time.sleep(DELAY)
    r = requests.get(API + path, params={"OC": oc(), **params},
                     headers={"User-Agent": config.USER_AGENT}, timeout=60)
    r.raise_for_status()
    if "사용자 정보 검증에 실패" in r.text:
        raise RuntimeError("법제처 인증 실패: 등록한 IP와 지금 IP가 다른지 확인하세요 (open.law.go.kr 마이페이지)")
    return r.text
