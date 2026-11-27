"""수집한 기사에서 정답셋 후보 문장을 규칙으로 뽑고, 근거 후보와 자동 라벨 제안을 붙여 검수용 CSV를 만든다.

실행:  python gold_candidates.py              # 전체 후보
       python gold_candidates.py --max 200    # 유형별로 고르게 200개만
결과:  09_데이터/processed/gold__candidates.csv (엑셀로 열어 auto_label을 보고 label_a·label_b를 채운다)
판정 기준과 라벨 다는 법: 12_기준/docs/02_judgment_criteria.md

자동 라벨(auto_label)은 제안일 뿐이다. 사람이 확인한 label_final만 정답으로 쓴다.
이 규칙 추출은 제안서가 요구하는 '키워드·규칙 기반 방식'의 기준선이기도 하다. 놓치거나 잘못 잡는 문장이 그 한계다.
"""
import argparse
import csv
import random
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bill_match  # noqa: E402
from bill_match import clean_name, config  # noqa: E402

# 주장 유형별 문장 규칙. 앞에 있는 유형이 먼저 잡힌다.
CLAIM_TYPES = {
    "표결": r"찬성\s*\d+\s*(표|명)|재석\s*\d+",
    "의결": r"(본회의|법사위|상임위|국회|위원회|소위).{0,40}(통과|가결|부결|의결)|(통과|가결|부결)(됐|되었|시켰|했|된)",
    "발의": r"대표\s*발의|발의(했|한)|(개정안|법안|특별법)을? (냈|제출)",
    "헌재": r"헌법재판소|헌재.{0,20}(위헌|합헌|각하|기각|헌법불합치|인용)",
    "법령내용": r"(법|법률|시행령|헌법)\s*제\d+조",
}
# 판정 범위 밖으로 볼 문장 (지방의회, 여론조사)
OUT_OF_SCOPE = r"(시|도|구|군)의회|찬성\s*\d+(\.\d+)?\s*%|반대\s*\d+(\.\d+)?\s*%|여론조사|응답"
# 본회의 전 단계(소위·상임위·법사위)를 말하는 문장. 이 단계의 처리 기록은 수집하지 않았다
COMMITTEE_STAGE = r"소위|소위원회|상임위|위원회 전체회의|법사위|법제사법위원회"
PLENARY_PASS = r"본회의.{0,40}(통과|가결|처리|의결)|(통과|가결)(됐|되었|시켰|했|된).{0,20}본회의"
# 아직 일어나지 않은 일을 말하는 문장 (조건·전망·계획). 사실 주장이 아니다
FUTURE = r"통과하면|처리하면|가결되면|앞둔|앞두고|예정|계획|방침|전망|할 것으로|될 것으로|추진"
SENTENCE_SPLIT = re.compile(r"(?<=[다요])\.\s+|\n")
FIELDS = ["claim_id", "claim_type", "media", "article_date", "sentence", "article_title", "article_url",
          "evidence_candidates", "auto_label", "auto_evidence_id", "auto_reason",
          "label_a", "label_b", "label_final", "evidence_dataset", "evidence_id",
          "made_by", "annotator_a", "annotator_b", "note"]


def load_articles():
    """모든 수집일의 뉴스 원자료를 읽는다."""
    rows = []
    for path in sorted((config.DATA / "raw" / "collected" / "news_press").glob("*/articles.csv")):
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows += list(csv.DictReader(f))
    return rows


def days_between(a, b):
    """두 날짜(YYYY-MM-DD) 사이 일수. 하나라도 없으면 None."""
    try:
        return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days
    except (TypeError, ValueError):
        return None


def auto_label(sentence, ctype, article_date, matches):
    """규칙으로 라벨을 제안한다. 확신할 수 없으면 빈 칸으로 둔다. (라벨, 근거 ID, 이유)"""
    if re.search(OUT_OF_SCOPE, sentence):
        return "판정대상아님", "", "지방의회 또는 여론조사 문장"
    if ctype not in ("의결", "표결"):
        return "", "", ""
    if re.search(FUTURE, sentence):
        return "판정대상아님", "", "조건·전망·계획 문장 (아직 일어나지 않은 일)"
    plenary = re.search(PLENARY_PASS, sentence)
    if not plenary and re.search(COMMITTEE_STAGE, sentence):
        return "근거없음", "", "본회의 전 단계(소위·상임위·법사위)라 수집한 근거 자료에 기록이 없음"
    if not plenary or not matches:
        return "", "", ""
    rec, ratio = matches[0]
    gap = days_between(article_date, rec.get("PROC_DT"))
    if rec.get("PROC_RESULT_CD") in ("원안가결", "수정가결") and gap is not None and 0 <= gap <= 3:
        return "사실", rec["BILL_ID"], f"기사 {gap}일 전 본회의 {rec['PROC_RESULT_CD']} 기록과 일치 (이름 겹침 {ratio:.0%})"
    return "", rec["BILL_ID"], f"이름은 비슷하나 기사 날짜 전후 본회의 가결 기록이 없음. 검수 필요 (이름 겹침 {ratio:.0%})"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max", type=int, default=0, help="유형별로 고르게 뽑을 최대 개수 (0이면 전체)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    articles = load_articles()
    # 본회의 표결 기록(위원장 대안·정부안 포함)과 의원 발의안을 함께 색인한다. 같은 의안이면 표결 기록을 쓴다
    records = {**bill_match.load_latest("assembly_bills"), **bill_match.load_latest("assembly_votes")}
    matcher = bill_match.Matcher(list(records.values()))

    # 1) 기사마다 문장을 나눠 규칙에 걸리는 문장을 모으고 근거 후보와 자동 라벨을 붙인다
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
            matches = matcher.match(sent)
            label, evidence_id, reason = auto_label(sent, ctype, art["date"] or "", matches)
            rows.append({"claim_type": ctype, "media": art["media"], "article_date": (art["date"] or "")[:10],
                         "sentence": sent, "article_title": art["title"], "article_url": art["url"],
                         "evidence_candidates": " | ".join(
                             f"{r['BILL_ID']} {clean_name(r['BILL_NAME'])}({r.get('PROC_RESULT_CD') or r.get('PROC_RESULT') or '계류'}"
                             f"{' ' + r['PROC_DT'] if r.get('PROC_DT') else ''})" for r, _ in matches),
                         "auto_label": label, "auto_evidence_id": evidence_id, "auto_reason": reason, "made_by": "원문"})

    # 2) 필요하면 유형별로 고르게 줄인다
    if args.max:
        random.seed(args.seed)
        by_type = {}
        for row in rows:
            by_type.setdefault(row["claim_type"], []).append(row)
        per = max(1, args.max // len(by_type))
        rows = [r for group in by_type.values() for r in random.sample(group, min(per, len(group)))]

    # 3) 번호를 매겨 저장한다. 이미 사람이 라벨을 단 파일은 덮어쓰지 않는다
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
    print(f"기사 {len(articles):,}건 → 후보 {len(rows)}개 {dict(Counter(r['claim_type'] for r in rows))}")
    print(f"근거 후보가 붙은 문장 {sum(bool(r['evidence_candidates']) for r in rows)}개, "
          f"자동 라벨 {dict(Counter(r['auto_label'] or '(없음)' for r in rows))} → {out}")


if __name__ == "__main__":
    main()
