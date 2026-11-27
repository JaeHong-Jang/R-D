# 변경 기록

## 2026-11-28

- Windows 작업 스케줄러에 매일 9시·21시 수집 등록. 콘솔 창을 닫으면 수집이 끊겨 창 없이 실행(conhost --headless)하도록 함.
- 국회 의안은 월요일마다 전체, 다른 날은 최신 1,000건. 표결은 매번 전체.
- 판정 기준 초안(`02_judgment_criteria.md`)과 정답셋 후보 추출(`gold_candidates.py`) 추가. 후보 156개, 근거 후보 붙은 문장 33개.
- 국회·공공데이터포털 키 등록. 22대 국회 의안 21,299건, 표결 1,918건 수집.
- 정책뉴스 수집기 `policy_news.py` 추가, 최근 90일 677건 수집. 보도자료는 들어 있지 않음(모두 policy).
- 수집기 오류 메시지에서 인증키가 든 주소를 빼고, 정책뉴스는 연결이 끊기면 세 번까지 다시 시도하게 함.
- 서울 야간경제 해커톤의 하네스 폴더 체계를 들여왔다. 본선 자리는 `08_코칭`으로 바꿨다 (D-004).
- 파일 이동: `crawl_news.py` → `10_구현/src/collectors/news_press.py`, `build_dataset.py` → `10_구현/src/pipeline/aihub_clickbait.py`, `collect_evidence.py` → `assembly_bills.py`·`assembly_votes.py`로 나눔.
- 데이터 이동: `data/news_politics.csv` → `09_데이터/raw/collected/news_press/2026-11-27/articles.csv`, `data/PO_*.jsonl` → `09_데이터/interim/aihub_clickbait__PO_*.jsonl`.
- 인증키 파일 `api_keys.txt` → `.env`.
- 법제처 수집기 추가: `law_current.py`(현행법령), `law_detc.py`(헌재결정례).
- 매일 수집 진입점 `10_구현/scripts/collect_daily.py` 추가.

## 2026-11-27

- 뉴스 저장 형식을 JSONL에서 CSV로 바꿨다.
- 국회 수집기 추가.

## 2026-11-26

- 분야를 정치로 정했다 (D-001). 네이버·다음 대신 언론사 직접 수집 (D-002).
- 연합뉴스·YTN을 수집 대상에서 뺐다 (기사에 AI 활용 금지 명시).
