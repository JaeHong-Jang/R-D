"""언론사 정치 섹션에서 기사를 수집해 CSV로 저장한다.

설치:  pip install requests trafilatura
실행 예:
    python crawl_news.py                       # 전체 언론사, 섹션 1~3쪽
    python crawl_news.py --pages 10            # 섹션 10쪽까지
    python crawl_news.py --sites 뉴시스 한겨레   # 고른 언론사만
    python crawl_news.py --list                # 언론사 목록 보기

결과: data/news_politics.csv (한 행에 기사 1건, 엑셀에서 바로 열림). 다시 실행하면 새 기사만 덧붙인다.

지키는 것: 각 사이트 robots.txt가 막은 주소는 건너뛰고, 같은 사이트에는 --delay 초 간격으로만 요청한다.
수집한 본문은 저작권이 언론사에 있으므로 내부 분석용으로만 쓰고 공개 저장소에 올리지 않는다.
"""
import argparse
import csv
import html
import re
import time
import urllib.robotparser
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import lxml.html
import requests
import trafilatura

USER_AGENT = "student-research-crawler/0.1 (university R&D project; politics news analysis)"
OUT = Path(__file__).resolve().parent / "data" / "news_politics.csv"
FIELDS = ["url", "media", "category", "title", "date", "author", "content", "collected_at"]

# list: 정치 섹션 목록 주소 ({page}는 쪽 번호), article: 기사 주소 형식(정규식)
# section: 목록에 다른 분야 기사가 섞이는 사이트에서, 기사 페이지의 분야 표시가 이 값일 때만 저장
# body: 자동 본문 추출이 잘 안 되는 사이트에서 본문이 들어 있는 요소(XPath)
# 뺀 곳: 연합뉴스·YTN(기사마다 "AI 학습 및 활용 금지" 명시), MBC(robots.txt 전면 금지), 경향신문(크롤러 요청에 403), 조선일보·KBS·JTBC(자바스크립트로 본문 구성)
SITES = {
    "정책브리핑": {"list": "https://www.korea.kr/briefing/pressReleaseList.do?pageIndex={page}",
                 "article": r"https://www\.korea\.kr/briefing/pressReleaseView\.do\?newsId=\d+",
                 "body": '//div[contains(@class,"view_cont")]'},
    "뉴시스": {"list": "https://www.newsis.com/politic/list/?cid=10300&scid=10301&page={page}",
             "article": r"https://www\.newsis\.com/view/NISX\d+_\d+", "section": "정치",
             "body": '//div[@class="viewer"]/article'},
    "프레시안": {"list": "https://www.pressian.com/pages/news-politics-list?page={page}",
              "article": r"https://www\.pressian\.com/pages/articles/\d+"},
    "오마이뉴스": {"list": "https://www.ohmynews.com/NWS_Web/ArticlePage/Total_Article.aspx?PAGE_CD=C0400&pageno={page}",
               "article": r"https://www\.ohmynews\.com/NWS_Web/View/at_pg\.aspx\?CNTN_CD=A\d+"},
    "SBS": {"list": "https://news.sbs.co.kr/news/newsSection.do?sectionType=01&pageIdx={page}",
            "article": r"https://news\.sbs\.co\.kr/news/endPage\.do\?news_id=N\d+"},
    "한겨레": {"list": "https://www.hani.co.kr/arti/politics?page={page}",
             "article": r"https://www\.hani\.co\.kr/arti/politics/\w+/\d+\.html"},
    "중앙일보": {"list": "https://www.joongang.co.kr/politics?page={page}",
              "article": r"https://www\.joongang\.co\.kr/article/\d+"},
    "동아일보": {"list": "https://www.donga.com/news/Politics?p={offset}&prod=news&ymd=&m=",
              "article": r"https://www\.donga\.com/news/Politics/article/all/\d+/\d+/1"},
    "노컷뉴스": {"list": "https://www.nocutnews.co.kr/news/politics?page={page}",
              "article": r"https://www\.nocutnews\.co\.kr/news/\d+"},
}


class Fetcher:
    """robots.txt를 확인하고, 사이트별 요청 간격을 지키며 페이지를 가져온다."""

    def __init__(self, delay):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.robots = {}
        self.last = {}

    def allowed(self, url):
        host = urlsplit(url).netloc
        if host not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(f"https://{host}/robots.txt", timeout=15)
                rp.parse(r.text.splitlines() if r.ok and "<html" not in r.text[:300].lower() else [])
            except requests.RequestException:
                rp.parse(["User-agent: *", "Disallow: /"])  # 확인 못 하면 수집하지 않는다
            self.robots[host] = rp
        return self.robots[host].can_fetch(USER_AGENT, url)

    def get(self, url):
        if not self.allowed(url):
            return None
        host = urlsplit(url).netloc
        wait = self.delay - (time.time() - self.last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            r = self.session.get(url, timeout=20)
        except requests.RequestException as e:
            print(f"    요청 실패 {url}: {type(e).__name__}")
            return None
        finally:
            self.last[host] = time.time()
        if r.status_code != 200:
            print(f"    HTTP {r.status_code} {url}")
            return None
        if r.encoding and r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r.text


def article_links(page_html, base, pattern):
    links = []
    for href in re.findall(r'href=["\']([^"\'#]+)', page_html):
        m = re.match(pattern, urljoin(base, html.unescape(href)))
        if m and m.group(0) not in links:
            links.append(m.group(0))
    return links


def parse_article(page_html, url, site):
    section = SITES[site].get("section")
    if section:
        m = re.search(r'property="article:section" content="([^"]*)"', page_html)
        if m and m.group(1) != section:
            return "다른 분야"
    doc = None
    for precise in (True, False):  # 엄격하게 뽑아 본문이 안 나오면 느슨하게 다시 시도
        doc = trafilatura.bare_extraction(page_html, url=url, include_comments=False, include_tables=False,
                                          favor_precision=precise, with_metadata=True)
        doc = doc if doc is None or isinstance(doc, dict) else doc.as_dict()
        if doc and (len(doc.get("text") or "") >= 200 or SITES[site].get("body")):
            break
    if not doc:
        return None
    raw = doc.get("text") or ""
    body_xpath = SITES[site].get("body")
    if body_xpath:
        found = lxml.html.fromstring(page_html).xpath(body_xpath)
        if not found:
            return None
        for junk in found[0].xpath(".//script|.//style|.//iframe|.//figure"):
            junk.drop_tree()
        for br in found[0].xpath(".//br"):
            br.tail = "\n" + (br.tail or "")
        raw = found[0].text_content()
    lines = [ln.strip() for ln in raw.splitlines()]
    text = "\n".join(ln for ln in lines if ln and ln != "AD")
    title = (doc.get("title") or "").strip()
    if len(text) < 200 or not title:
        return None
    return {"url": url, "media": site, "category": "정치", "title": title,
            "date": doc.get("date"), "author": doc.get("author"), "content": text,
            "collected_at": datetime.now().isoformat(timespec="seconds")}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sites", nargs="*", default=list(SITES), help="수집할 언론사 (기본: 전체)")
    ap.add_argument("--pages", type=int, default=3, help="언론사마다 볼 목록 쪽수")
    ap.add_argument("--delay", type=float, default=1.5, help="같은 사이트 요청 사이 간격(초)")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--list", action="store_true", help="언론사 목록만 출력")
    args = ap.parse_args()

    if args.list:
        print("\n".join(SITES))
        return
    unknown = [s for s in args.sites if s not in SITES]
    if unknown:
        raise SystemExit(f"목록에 없는 언론사: {unknown}  (--list 로 확인)")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if args.out.exists():
        with open(args.out, encoding="utf-8-sig", newline="") as f:
            seen = {row["url"] for row in csv.DictReader(f)}
    print(f"이미 수집된 기사 {len(seen):,}건")

    fetcher = Fetcher(args.delay)
    total = 0
    is_new = not args.out.exists()
    with open(args.out, "a", encoding="utf-8-sig", newline="") as out:  # utf-8-sig: 엑셀에서 한글이 깨지지 않게
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        for site in args.sites:
            cfg = SITES[site]
            saved = skipped = failed = other = 0
            for page in range(1, args.pages + 1):
                list_url = cfg["list"].format(page=page, offset=(page - 1) * 10 + 1)
                page_html = fetcher.get(list_url)
                if page_html is None:
                    print(f"  [{site}] 목록 {page}쪽을 가져오지 못함 (robots.txt 금지 또는 오류)")
                    break
                links = article_links(page_html, list_url, cfg["article"])
                new = [u for u in links if u not in seen]
                skipped += len(links) - len(new)
                if not links or (page > 1 and not new):
                    break  # 더 넘겨도 새 기사가 없음
                for url in new:
                    seen.add(url)
                    art_html = fetcher.get(url)
                    row = art_html and parse_article(art_html, url, site)
                    if row == "다른 분야":
                        other += 1
                        continue
                    if not row:
                        failed += 1
                        continue
                    writer.writerow(row)
                    out.flush()
                    saved += 1
            total += saved
            print(f"[{site}] 새로 저장 {saved}건, 이미 있음 {skipped}건, 다른 분야 {other}건, 실패 {failed}건", flush=True)
    print(f"완료: 새 기사 {total:,}건 → {args.out}")


if __name__ == "__main__":
    main()
