"""수집기와 변환 코드가 함께 쓰는 경로, 인증키, 요청 설정."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 프로젝트 최상위 폴더
DATA = ROOT / "09_데이터"
USER_AGENT = "student-research-crawler/0.1 (university R&D project; politics news analysis)"


def env(name):
    """프로젝트 최상위 .env 에서 인증키를 읽는다. 없으면 None."""
    path = ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, _, value = line.partition("=")
        if key.strip() == name and value.strip():
            return value.strip()
    return None


def raw_dir(source, dataset_id, day=None):
    """원자료 폴더 09_데이터/raw/<출처>/<데이터셋ID>/<수집일>/ 을 만들어 돌려준다."""
    path = DATA / "raw" / source / dataset_id / (day or date.today().isoformat())
    path.mkdir(parents=True, exist_ok=True)
    return path


def collected_names(source, dataset_id, pattern):
    """이전 수집일 폴더들에 이미 저장된 파일 이름(확장자 제외)을 모아 중복 수집을 막는다."""
    base = DATA / "raw" / source / dataset_id
    return {p.stem for p in base.glob(f"*/{pattern}")} if base.exists() else set()
