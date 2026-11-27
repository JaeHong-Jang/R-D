"""국회의원 발의 법률안과 처리 상태(가결·폐기 등)를 받는다. 서비스: nzmimeepazxkubdpn

실행:  python assembly_bills.py            # 최신 1,000건
       python assembly_bills.py --pages 30 # 22대 국회 전체 (처음 한 번)
"""
import argparse

import open_assembly

DATASET_ID = "assembly_bills"
SERVICE = "nzmimeepazxkubdpn"


def collect(pages=1):
    return open_assembly.collect(DATASET_ID, SERVICE, pages)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", type=int, default=1, help="받을 쪽수 (한 쪽 1,000건, 최신순)")
    collect(ap.parse_args().pages)
