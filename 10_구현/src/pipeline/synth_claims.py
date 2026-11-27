"""국회 표결·의안 기록으로 라벨이 붙은 주장 문장을 자동으로 만든다 (학습·개발용 정답셋).

실행:  python synth_claims.py                 # 유형마다 기록 400개씩
       python synth_claims.py --per-type 1000
결과:  09_데이터/processed/synthetic__claims.csv

기록 하나로 '사실' 주장 1개와, 내용을 바꾼 주장 1개(거짓 또는 일부사실)를 만든다.
라벨 규칙은 12_기준/docs/02_judgment_criteria.md 를 따른다:
  결과 뒤집기·대상 바꾸기 → 거짓 / 표수·날짜 바꾸기 → 일부사실 / 계류 중인 법안을 '통과'로 → 거짓
템플릿 문장은 실제 기사 문장과 다르므로 최종 평가에는 사람이 검수한 기사 문장(gold__claims_evidence.csv)을 쓴다.
"""
import argparse
import csv
import random
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bill_match  # noqa: E402
from bill_match import clean_name, config  # noqa: E402

FIELDS = ["claim_id", "claim_type", "claim", "label", "perturbation", "evidence_dataset", "evidence_id",
          "evidence_summary", "made_by"]

# 같은 사실을 여러 말투로 쓴다 (모델이 한 문장 틀만 외우지 않게)
VOTE_TEMPLATES = [
    "{name}{i} {date} 국회 본회의에서 재석 {vote}명 중 찬성 {yes}명, 반대 {no}명, 기권 {blank}명으로 {result}됐다.",
    "국회는 {date} 본회의를 열어 {name}{eul} 찬성 {yes}표, 반대 {no}표, 기권 {blank}표로 {result}했다.",
    "{date} 본회의 표결에서 {name}{i} 찬성 {yes}표로 {result}됐다.",
]
PASS_TEMPLATES = [
    "{name}{i} {date} 국회 본회의를 통과했다.",
    "국회는 {date} 본회의에서 {name}{eul} {result}했다.",
]
PROPOSE_TEMPLATES = [
    "{who} 의원이 {date} {name}{eul} 대표발의했다.",
    "{who} 의원은 {date} {name}{eul} 대표발의했다고 밝혔다.",
]


def josa(word, with_final, without_final):
    """앞말의 마지막 한글 글자에 받침이 있으면 with_final(이/을), 없으면 without_final(가/를). '(대안)'처럼 괄호로 끝나도 '안'을 본다."""
    hangul = [c for c in word if "가" <= c <= "힣"]
    last = hangul[-1] if hangul else "가"
    has_final = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0
    return with_final if has_final else without_final


def korean_date(iso):
    """2026-11-20 → 2026년 11월 20일"""
    y, m, d = iso.split("-")
    return f"{int(y)}년 {int(m)}월 {int(d)}일"


def shift_date(iso, rng):
    """날짜를 1~6주 앞뒤로 옮긴다."""
    day = date.fromisoformat(iso) + timedelta(days=rng.choice([-1, 1]) * rng.randint(7, 45))
    return day.isoformat()


def fill(template, name, **values):
    return template.format(name=name, i=josa(name, "이", "가"), eul=josa(name, "을", "를"), **values)


def vote_claims(votes, rng, per_type):
    """표결 기록 → 표결 주장. 바꾸기: 결과 뒤집기(거짓), 찬성 표수(일부사실), 날짜(일부사실)."""
    rows = []
    laws = [v for v in votes if v["BILL_KIND_CD"] == "법률안" and v["YES_TCNT"] is not None]
    for v in rng.sample(laws, min(per_type, len(laws))):
        name, result = clean_name(v["BILL_NAME"]), "부결" if v["PROC_RESULT_CD"] == "부결" else "가결"
        facts = {"date": v["PROC_DT"], "vote": v["VOTE_TCNT"], "yes": v["YES_TCNT"], "no": v["NO_TCNT"],
                 "blank": v["BLANK_TCNT"], "result": result}
        summary = (f"{name} | {v['PROC_DT']} 본회의 {v['PROC_RESULT_CD']} | 재적 {v['MEMBER_TCNT']}, 재석 {v['VOTE_TCNT']}, "
                   f"찬성 {v['YES_TCNT']}, 반대 {v['NO_TCNT']}, 기권 {v['BLANK_TCNT']}")
        base = {"claim_type": "표결", "evidence_dataset": "assembly_votes", "evidence_id": v["BILL_ID"], "evidence_summary": summary}

        template = rng.choice(VOTE_TEMPLATES)
        rows.append({**base, "label": "사실", "perturbation": "없음",
                     "claim": fill(template, name, **{**facts, "date": korean_date(facts["date"])})})
        kind = rng.choice(["결과", "표수", "날짜"])
        wrong = dict(facts)
        if kind == "결과":
            wrong["result"] = "부결" if result == "가결" else "가결"
            label = "거짓"
        elif kind == "표수":
            wrong["yes"] = max(0, facts["yes"] + rng.choice([-1, 1]) * rng.randint(15, 80))
            if wrong["yes"] == facts["yes"]:
                wrong["yes"] += 20
            label = "일부사실"
        else:
            wrong["date"] = shift_date(facts["date"], rng)
            label = "일부사실"
        rows.append({**base, "label": label, "perturbation": kind,
                     "claim": fill(template, name, **{**wrong, "date": korean_date(wrong["date"])})})
    return rows


def pass_claims(votes, bills, rng, per_type):
    """가결 기록 → '통과했다' 주장(사실), 계류 중인 의원 발의안 → '통과했다' 주장(거짓)."""
    rows = []
    passed = [v for v in votes if v["BILL_KIND_CD"] == "법률안" and v["PROC_RESULT_CD"] in ("원안가결", "수정가결")]
    pending = [b for b in bills if not b["PROC_RESULT"]]
    for v in rng.sample(passed, min(per_type, len(passed))):
        name = clean_name(v["BILL_NAME"])
        rows.append({"claim_type": "의결", "label": "사실", "perturbation": "없음",
                     "claim": fill(rng.choice(PASS_TEMPLATES), name, date=korean_date(v["PROC_DT"]), result=v["PROC_RESULT_CD"]),
                     "evidence_dataset": "assembly_votes", "evidence_id": v["BILL_ID"],
                     "evidence_summary": f"{name} | {v['PROC_DT']} 본회의 {v['PROC_RESULT_CD']}"})
    for b in rng.sample(pending, min(per_type, len(pending))):
        name = b["BILL_NAME"]
        fake_day = (date.fromisoformat(b["PROPOSE_DT"]) + timedelta(days=rng.randint(30, 150))).isoformat()
        rows.append({"claim_type": "의결", "label": "거짓", "perturbation": "계류안 통과",
                     "claim": fill(PASS_TEMPLATES[0], name, date=korean_date(fake_day), result="가결"),
                     "evidence_dataset": "assembly_bills", "evidence_id": b["BILL_ID"],
                     "evidence_summary": f"{name} | {b['PROPOSE_DT']} 발의 ({b['PROPOSER']}) | 처리결과 없음(계류)"})
    return rows


def propose_claims(bills, rng, per_type):
    """발의 기록 → 대표발의 주장. 바꾸기: 대표발의자(거짓), 발의 날짜(일부사실)."""
    rows = []
    proposers = sorted({b["RST_PROPOSER"] for b in bills if b["RST_PROPOSER"]})
    for b in rng.sample(bills, min(per_type, len(bills))):
        name, who = b["BILL_NAME"], b["RST_PROPOSER"]
        summary = f"{name} | {b['PROPOSE_DT']} 발의 | 대표발의 {who} ({b['PROPOSER']})"
        base = {"claim_type": "발의", "evidence_dataset": "assembly_bills", "evidence_id": b["BILL_ID"], "evidence_summary": summary}
        template = rng.choice(PROPOSE_TEMPLATES)
        rows.append({**base, "label": "사실", "perturbation": "없음",
                     "claim": fill(template, name, who=who, date=korean_date(b["PROPOSE_DT"]))})
        if rng.random() < 0.5:
            other = rng.choice([p for p in proposers if p != who])
            rows.append({**base, "label": "거짓", "perturbation": "대표발의자",
                         "claim": fill(template, name, who=other, date=korean_date(b["PROPOSE_DT"]))})
        else:
            rows.append({**base, "label": "일부사실", "perturbation": "날짜",
                         "claim": fill(template, name, who=who, date=korean_date(shift_date(b["PROPOSE_DT"], rng)))})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--per-type", type=int, default=400, help="유형마다 쓸 기록 수 (기록 하나에 주장 2개)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    votes = list(bill_match.load_latest("assembly_votes").values())
    bills = list(bill_match.load_latest("assembly_bills").values())
    rows = vote_claims(votes, rng, args.per_type) + pass_claims(votes, bills, rng, args.per_type // 2) + propose_claims(bills, rng, args.per_type)
    for n, row in enumerate(rows, 1):
        row.update(claim_id=f"S{n:05d}", made_by="템플릿")

    out = config.DATA / "processed" / "synthetic__claims.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig: 엑셀에서 한글이 깨지지 않게
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"표결 기록 {len(votes):,}건, 의안 {len(bills):,}건 → 주장 {len(rows):,}개 → {out}")
    print("  유형별:", dict(Counter(r["claim_type"] for r in rows)))
    print("  라벨별:", dict(Counter(r["label"] for r in rows)))


if __name__ == "__main__":
    main()
