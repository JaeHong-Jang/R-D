# 인공지능 활용 온라인 정보 분석 및 검증 서비스 연구

생성형 AI로 정치 뉴스의 주장을 기관 자료(국회 의안·표결, 법령, 헌재 결정)와 대조해 신뢰성을 판정하고, 판단 근거와 출처를 함께 보여주는 서비스를 연구한다. 지엔소프트(주) 프로젝트형 일경험 과제(8주, 4인 팀).

## 먼저 볼 문서

- [하네스 계약](harness.yaml): 폴더 용도, 품질 게이트, 위험, 결정, 미해결 질문
- [데이터 폴더 규칙](09_데이터/README.md)과 [데이터셋 등록부](09_데이터/catalog/datasets.yaml)
- [데이터 규칙](12_기준/rules/data-rules.md), [수집 준수 규칙](12_기준/rules/collection-rules.md)
- [성능평가 기준](12_기준/evals/rubric.md)

## 시작하기

```bash
python3 -m venv ~/venvs/rnd
~/venvs/rnd/bin/pip install requests trafilatura
cp .env.example .env      # 인증키를 채운다
~/venvs/rnd/bin/python 10_구현/scripts/collect_daily.py
```

매일 9시·21시에 Windows 작업 스케줄러(`RnD_뉴스수집_0900`, `RnD_뉴스수집_2100`)가 `~/run_rnd_daily.sh`를 통해 `collect_daily.py`를 실행한다. PC가 켜져 있고 로그인돼 있어야 한다. 결과는 `09_데이터/raw/collect_log.txt`.

수집기를 하나씩 돌리려면 `10_구현/src/collectors/` 안의 파일을 직접 실행한다(각 파일 맨 위에 사용법).

## 폴더 구조

```text
.
├── 00_제출/            # 활동 계획서, 보고서
├── 01_전략/            # 주제·범위 결정, DDBM 캔버스
├── 02_제품/            # 서비스 정의, 화면 설계
├── 03_에이전트/        # 판정 프롬프트와 에이전트 설계
├── 04_아키텍처/        # 파이프라인, AutoRAG 구성
├── 05_리서치/
│   ├── research_notes/
│   └── reports/
├── 06_증빙/
│   ├── 수집_허용근거/   # robots.txt·AI 이용 금지 문구 점검
│   └── 회의록/
├── 07_원천/
│   ├── 제안서/
│   └── 사전교육/
├── 08_코칭/            # 코칭 3회 준비와 피드백
├── 09_데이터/
│   ├── catalog/        # datasets.yaml
│   ├── raw/            # <출처>/<데이터셋ID>/<수집일>/
│   │   └── collected/  open_assembly/  law_go_kr/  aihub/
│   ├── interim/
│   ├── processed/
│   └── samples/
├── 10_구현/
│   ├── src/
│   │   ├── config.py   # 경로·인증키·User-Agent
│   │   ├── collectors/ # 수집기
│   │   ├── pipeline/   # 변환
│   │   └── service/    # 웹 프로토타입
│   ├── scripts/        # collect_daily.py
│   ├── tests/  notebooks/  prompts/  static/
├── 11_실험/            # 저장소 제외
├── 12_기준/
│   ├── docs/  rules/  evals/
└── _체계/
```

09~12는 하네스 폴더다. 번호 폴더 아래 이름은 코드 import가 깨지지 않도록 영어로 둔다.

## 저장소에 올리지 않는 것

데이터(`09_데이터/raw·interim·processed`), 인증키(`.env`), 회사·교육 자료와 제출 서류(`00_제출`, `07_원천`, `06_증빙/회의록`), 실험 결과(`11_실험`). 기사 본문은 언론사 저작권물이다.
