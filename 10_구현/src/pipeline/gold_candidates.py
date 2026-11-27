"""수집한 기사에서 정답셋 후보 문장을 규칙으로 뽑고, 근거 후보(국회 의안)를 붙여 라벨 작업용 CSV를 만든다.

실행:  python gold_candidates.py              # 전체 후보
       python gold_candidates.py --max 200    # 유형별로 고르게 200개만
결과:  09_데이터/processed/gold__candidates.csv (엑셀로 열어 label_a·label_b를 채운다)
판정 기준과 라벨 다는 법: 12_기준/docs/02_judgment_criteria.md

이 규칙 추출은 제안서가 요구하는 '키워드·규칙 기반 방식'의 기준선이기도 하다. 놓치거나 잘못 잡는 문장이 그 한계다.
"""
import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402

# 주장 유형별 문장 규칙. 앞에 있는 유형이 먼저 잡힌다.
CLAIM_TYPES = {
    "표결": r"찬성\s*\d+\s*(표|명)|재석\s*\d+",
    "의결": r"(본회의|법사위|상임위|국회|위원회|소위).{0,40}(통과|가결|부결|의결)|(통과|가결|부결)(됐|되었|시켰|했|된)",
    "발의": r"대표\s*발의|발의(했|한)|(개정안|법안|특별법)을? (냈|제출)",
    "헌재": r"헌법재판소|헌재.{0,20}(위헌|합헌|각하|기각|헌법불합치|인용)",
    "법령내용": r"(법|법률|시행령|헌법)\s*제\d+조",
}
# 판정 범위 밖으로 미리 표시할 문장 (지방의회, 여론조사)
OUT_OF_SCOPE = r"(시|도|구|군)의회|찬성\s*\d+(\.\d+)?\s*%|반대\s*\d+(\.\d+)?\s*%|여론조사|응답"
# 법안 이름이 아닌 "~법" 낱말 (따옴표 없는 이름을 찾을 때 뺀다)
GENERIC_LAW_WORDS = ("입법", "헌법", "방법", "불법", "위법", "사법", "합법", "편법", "적법", "탈법", "문법", "수법", "어법", "해법", "현행법")
SENTENCE_SPLIT = re.compile(r"(?<=[다요])\.\s+|\n")
FIELDS = ["claim_id", "claim_type", "out_of_scope_hint", "media", "article_date", "sentence", "article_title", "article_url",
          "evidence_candidates", "label_a", "label_b", "label_final", "evidence_dataset", "evidence_id",
          "made_by", "annotator_a", "annotator_b", "note"]


def load_articles():
    """모든 수집일의 뉴스 원자료를 읽는다."""
    rows = []
    for path in sorted((config.DATA / "raw" / "collected" / "news_press").glob("*/articles.csv")):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows += list(csv.DictReader(f))
    return rows


def load_bills():
    """모든 수집일의 국회 의안을 읽어 의안마다 가장 최근에 받은 상태만 남긴다."""
    latest = {}
    for page in sorted((config.DATA / "raw" / "open_assembly" / "assembly_bills").glob("*/page_*.json")):  # 날짜순
        for row in json.loads(page.read_text(encoding="utf-8")):
            latest[row["BILL_ID"]] = row
    return list(latest.values())


def bigrams(text):
    """띄어쓰기를 지운 두 글자 묶음. 별칭과 공식 의안명의 겹침을 재는 데 쓴다."""
    text = re.sub(r"\s|일부개정법률안|법률안|\(.*?\)", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def evidence_candidates(sentence, bills, index, k=3):
    """문장의 따옴표 속 법안 이름과 가장 많이 겹치는 의안 k개를 'BILL_ID 의안명(처리결과)'로 돌려준다."""
    quoted = re.findall(r"[‘'\"“「]([^’'\"”」]{2,40}?(?:법|법안|개정안|특별법|특검법))[’'\"”」]", sentence)
    bare = [m for m in re.findall(r"([가-힣·]{2,25}(?:특검법|특별법|기본법|법))(?:\s*(?:일부\s*)?(?:개정안|개정법률안|제정안|법률안|안))?", sentence)
            if not m.endswith(GENERIC_LAW_WORDS)]
    best_score = Counter()
    for name in dict.fromkeys(quoted + bare):  # 이름마다 따로 비교해 가장 잘 맞는 점수를 남긴다
        query = bigrams(name)
        scores = Counter()
        for gram in query:
            for i in index.get(gram, ()):
                scores[i] += 1
        for i, score in scores.items():
            ratio = score / len(query)
            if score >= 2 and ratio >= 0.5:  # 이름의 절반 이상이 의안명에 들어 있어야 후보로 둔다
                best_score[i] = max(best_score[i], ratio)
    best = [bills[i] for i, _ in best_score.most_common(k)]
    return " | ".join(f"{b['BILL_ID']} {b['BILL_NAME']}({b['PROC_RESULT'] or '계류'})" for b in best)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max", type=int, default=0, help="유형별로 고르게 뽑을 최대 개수 (0이면 전체)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    articles, bills = load_articles(), load_bills()
    index = {}  # 두 글자 묶음 → 의안 번호들 (빠른 검색용)
    for i, bill in enumerate(bills):
        for gram in bigrams(bill["BILL_NAME"]):
            index.setdefault(gram, []).append(i)

    # 1) 기사마다 문장을 나눠 규칙에 걸리는 문장을 모은다
    rows, seen = [], set()
    for art in articles:
        for sent in SENTENCE_SPLIT.split(art["content"]):
            sent = sent.strip()
            if not 15 < len(sent) < 400 or sent in seen:
                continue
            ctype = next((t for t, p in CLAIM_TYPES.items() if re.search(p, sent)), None)
            if not ctype:
                continue
            seen.add(sent)
            rows.append({"claim_type": ctype, "out_of_scope_hint": "Y" if re.search(OUT_OF_SCOPE, sent) else "",
                         "media": art["media"], "article_date": (art["date"] or "")[:10], "sentence": sent,
                         "article_title": art["title"], "article_url": art["url"],
                         "evidence_candidates": evidence_candidates(sent, bills, index), "made_by": "원문"})

    # 2) 필요하면 유형별로 고르게 줄인다
    if args.max:
        random.seed(args.seed)
        by_type = {}
        for row in rows:
            by_type.setdefault(row["claim_type"], []).append(row)
        per = max(1, args.max // len(by_type))
        rows = [r for group in by_type.values() for r in random.sample(group, min(per, len(group)))]

    # 3) 번호를 매겨 저장한다. 이미 라벨을 단 파일은 덮어쓰지 않는다
    out = config.DATA / "processed" / "gold__candidates.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        with open(out, encoding="utf-8-sig", newline="") as f:
            if any(r.get("label_a") or r.get("label_b") for r in csv.DictReader(f)):
                raise SystemExit(f"{out} 에 이미 라벨이 있어 덮어쓰지 않습니다. 파일 이름을 바꾼 뒤 다시 실행하세요.")
    for n, row in enumerate(rows, 1):
        row["claim_id"] = f"C{n:04d}"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: 엑셀에서 한글이 깨지지 않게
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(r["claim_type"] for r in rows)
    print(f"기사 {len(articles):,}건 → 후보 {len(rows)}개 {dict(counts)}")
    print(f"범위 밖 표시 {sum(r['out_of_scope_hint'] == 'Y' for r in rows)}개, 근거 후보가 붙은 문장 {sum(bool(r['evidence_candidates']) for r in rows)}개 → {out}")


if __name__ == "__main__":
    main()
