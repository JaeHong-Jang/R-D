"""국회 원자료를 읽고, 문장 속 법안 이름(별칭 포함)과 공식 의안명을 맞춰 보는 공통 함수."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

# 법안 이름이 아닌 "~법" 낱말 (따옴표 없는 이름을 찾을 때 뺀다)
GENERIC_LAW_WORDS = ("입법", "헌법", "방법", "불법", "위법", "사법", "합법", "편법", "적법", "탈법", "문법", "수법", "어법", "해법", "현행법")


def load_latest(dataset_id):
    """모든 수집일의 국회 자료를 읽어 의안마다 가장 최근에 받은 상태만 남긴다."""
    latest = {}
    for page in sorted((config.DATA / "raw" / "open_assembly" / dataset_id).glob("*/page_*.json")):  # 날짜순
        for row in json.loads(page.read_text(encoding="utf-8")):
            latest[row["BILL_ID"]] = row
    return latest


def clean_name(name):
    """표결 자료의 의안명 끝에 붙은 '(OOO의원 등 N인)', '(정부)' 같은 제안자 표시를 뗀다."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", name or "").strip()


def bigrams(text):
    """띄어쓰기와 흔한 꼬리말을 지운 두 글자 묶음. 별칭과 공식 의안명의 겹침을 재는 데 쓴다."""
    text = re.sub(r"\s|일부개정법률안|법률안|\(.*?\)", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def law_names(sentence):
    """문장에서 법안 이름으로 보이는 말을 뽑는다 (따옴표 안 이름과 '~법' 낱말)."""
    quoted = re.findall(r"[‘'\"“「]([^’'\"”」]{2,40}?(?:법|법안|개정안|특별법|특검법))[’'\"”」]", sentence)
    bare = [m for m in re.findall(r"([가-힣·]{2,25}(?:특검법|특별법|기본법|법))(?:\s*(?:일부\s*)?(?:개정안|개정법률안|제정안|법률안|안))?", sentence)
            if not m.endswith(GENERIC_LAW_WORDS)]
    return list(dict.fromkeys(quoted + bare))


class Matcher:
    """의안 목록에 두 글자 묶음 색인을 만들어, 문장 속 법안 이름과 가장 많이 겹치는 의안을 찾는다."""

    def __init__(self, records):
        self.records = records
        self.index = {}
        for i, rec in enumerate(records):
            for gram in bigrams(clean_name(rec["BILL_NAME"])):
                self.index.setdefault(gram, []).append(i)

    def match(self, sentence, k=3, min_ratio=0.5):
        """(의안, 겹침 비율) 목록을 비율이 높은 순으로 돌려준다. 이름의 절반 이상이 겹쳐야 후보가 된다."""
        best = Counter()
        for name in law_names(sentence):
            query = bigrams(name)
            scores = Counter()
            for gram in query:
                for i in self.index.get(gram, ()):
                    scores[i] += 1
            for i, score in scores.items():
                ratio = score / len(query)
                if score >= 2 and ratio >= min_ratio:
                    best[i] = max(best[i], ratio)
        return [(self.records[i], ratio) for i, ratio in best.most_common(k)]
