"""AI Hub 「낚시성 기사 탐지 데이터」에서 한 분야(기본: 정치) 기사를 뽑아 정제한 뒤 JSONL로 저장한다.

실행 예:
    python build_dataset.py                  # 정치 기사 전체
    python build_dataset.py --limit 200      # 폴더마다 200건만 (빠른 확인용)
    python build_dataset.py --category EC    # 경제 기사

원자료: 트라이톤 공모전 폴더의 AI Hub 원본 (용량이 커서 09_데이터/raw 로 복사하지 않고 그 자리에서 읽는다)
결과: 09_데이터/interim/aihub_clickbait__<분야>_train.jsonl, ..._valid.jsonl (한 줄에 기사 1건)
"""
import argparse
import json
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[3]  # 프로젝트 최상위 폴더
DEFAULT_DATA = HERE.parent / "트라이톤 공모전" / "data" / "146.낚시성 기사 탐지 데이터" / "01-1.정식개방데이터"
SPLITS = {"train": "Training", "valid": "Validation"}


def clean(text):
    """원본에 남아 있는 \\" 같은 이스케이프와 불필요한 공백을 정리한다."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace('\\"', '"').replace("\\'", "'")
    text = re.sub(r"[ \t ]+", " ", text)
    return text.strip()


def parse(path, folder):
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    src, lab = raw["sourceDataInfo"], raw["labeledDataInfo"]

    # 폴더 이름 예: TL_Part1_Clickbait_Direct_PO
    _, part, kind, method, _ = folder.split("_")
    is_clickbait = kind == "Clickbait"

    title = clean(src["newsTitle"])
    sentences = [clean(s["sentenceContent"]) for s in src["sentenceInfo"]]
    original_title = None
    inconsistent = []

    if part == "Part1":
        # Part1: 제목과 본문이 어긋나는 유형. 낚시성이면 newTitle이 바꿔 넣은 제목이다.
        if is_clickbait:
            original_title, title = title, clean(lab["newTitle"])
    else:
        # Part2: 본문 안에 주제와 어긋나는 문장이 섞인 유형. 가공된 본문은 processSentenceInfo에 있다.
        processed = lab["processSentenceInfo"]
        sentences = [clean(s["sentenceContent"]) for s in processed]
        inconsistent = [s["sentenceNo"] for s in processed if s.get("subjectConsistencyYn") == "N"]

    return {
        "id": src["newsID"],
        "media": src["newsID"].split("_")[1],
        "category": src["newsCategory"],
        "subcategory": src["newsSubcategory"],
        "title": title,
        "subtitle": clean(src.get("newsSubTitle")),
        "content": "\n".join(sentences),
        "sentences": sentences,
        "is_clickbait": is_clickbait,
        "part": part,                      # Part1=제목-본문 불일치, Part2=본문 내 불일치
        "made_by": method,                 # Auto=자동 생성, Direct=사람이 직접 작성
        "pattern": src.get("processPattern"),
        "original_title": original_title,  # Part1 낚시성 기사의 원래 제목
        "inconsistent_sentences": inconsistent,  # Part2에서 주제와 어긋나는 문장 번호
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA, help="01-1.정식개방데이터 폴더 경로")
    ap.add_argument("--out-dir", type=Path, default=HERE / "09_데이터" / "interim")
    ap.add_argument("--category", default="PO", help="PO 정치, EC 경제, SO 사회, LC 생활문화, IS 세계, GB IT과학, ET 연예")
    ap.add_argument("--limit", type=int, default=0, help="폴더마다 읽을 최대 건수 (0이면 전체)")
    args = ap.parse_args()

    if not args.data_dir.is_dir():
        raise SystemExit(f"데이터 폴더가 없습니다: {args.data_dir}\n--data-dir 로 경로를 지정하세요.")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for split, split_dir in SPLITS.items():
        label_dir = args.data_dir / split_dir / "02.라벨링데이터"
        folders = sorted(d.name for d in os.scandir(label_dir) if d.is_dir() and d.name.endswith("_" + args.category))
        if not folders:
            raise SystemExit(f"'{args.category}' 분야 폴더가 없습니다: {label_dir}")

        out_path = args.out_dir / f"aihub_clickbait__{args.category}_{split}.jsonl"
        seen, stats, failed = set(), Counter(), 0
        with open(out_path, "w", encoding="utf-8") as out:
            for folder in folders:
                for i, entry in enumerate(os.scandir(label_dir / folder)):
                    if args.limit and i >= args.limit:
                        break
                    if not entry.name.endswith(".json"):
                        continue
                    try:
                        row = parse(entry.path, folder)
                    except (ValueError, KeyError) as e:
                        failed += 1
                        print(f"  건너뜀 {entry.name}: {type(e).__name__} {e}")
                        continue
                    if not row["title"] or not row["sentences"]:
                        stats["빈 기사 제외"] += 1
                        continue
                    key = (row["id"], row["part"], row["is_clickbait"])
                    if key in seen:
                        stats["중복 제외"] += 1
                        continue
                    seen.add(key)
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stats["낚시성" if row["is_clickbait"] else "정상"] += 1
                    stats[row["part"]] += 1
                print(f"  {split} {folder} 완료 (누적 {len(seen):,}건)", flush=True)

        print(f"[{split}] {len(seen):,}건 저장 → {out_path}")
        print("   " + ", ".join(f"{k} {v:,}" for k, v in sorted(stats.items())) + f", 읽기 실패 {failed}")


if __name__ == "__main__":
    main()
