"""본회의 의안별 표결 결과(재적·찬성·반대·기권 수)를 받는다. 서비스: ncocpgfiaoituanbr

실행:  python assembly_votes.py            # 최신 1,000건
       python assembly_votes.py --pages 5  # 22대 국회 전체 (처음 한 번)
"""
import argparse

import open_assembly

DATASET_ID = "assembly_votes"
SERVICE = "ncocpgfiaoituanbr"


def collect(pages=1):
    return open_assembly.collect(DATASET_ID, SERVICE, pages)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", type=int, default=1, help="받을 쪽수 (한 쪽 1,000건, 최신순)")
    collect(ap.parse_args().pages)
