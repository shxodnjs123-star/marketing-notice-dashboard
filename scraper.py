
import json, re, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).parent
DATA = BASE / "data" / "notices.json"
KST = timezone(timedelta(hours=9))
HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; MarketingNoticeMonitor/2.0)"}
NAVER="https://ads.naver.com/notice"
KAKAO="https://lounge-board.kakao.com/bulletin/list?serviceType=KAKAOMOMENT"

def uid(p,u,t):
    return hashlib.sha256(f"{p}|{u}|{t}".encode()).hexdigest()[:20]

def load():
    if DATA.exists(): return json.loads(DATA.read_text(encoding="utf-8"))
    return {"updated_at":None,"notices":[]}

def save(x):
    DATA.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding="utf-8")

def naver():
    r=requests.get(NAVER,headers=HEADERS,timeout=20); r.raise_for_status()
    s=BeautifulSoup(r.text,"html.parser"); out=[]; seen=set()
    for a in s.find_all("a",href=True):
        title=" ".join(a.stripped_strings); href=a["href"]
        if not title or "notice" not in href.lower(): continue
        if href.startswith("/"): href="https://ads.naver.com"+href
        txt=" ".join((a.parent.stripped_strings if a.parent else a.stripped_strings))
        m=re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})",txt)
        if not m: continue
        date=f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        key=uid("NAVER",href,title)
        if key in seen: continue
        seen.add(key)
        out.append({"platform":"NAVER","id":key,"title":title,"category":"","date":date,"url":href,"read":False,"important":False})
    return out

def kakao():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    out=[]; seen=set()
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        page=b.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(KAKAO,wait_until="networkidle",timeout=60000)
        page.wait_for_timeout(3000)
        for a in page.locator("a").all():
            try:
                title=" ".join(a.inner_text().split()); href=a.get_attribute("href") or ""
                if not title or "/bulletin/" not in href: continue
                if href.startswith("/"): href="https://lounge-board.kakao.com"+href
                parent=" ".join(a.locator("xpath=..").inner_text().split())
                if not re.search(r"20\d{2}[.\-/]",parent):
                    parent=" ".join(a.locator("xpath=../..").inner_text().split())
                m=re.search(r"(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})",parent)
                if not m: continue
                date=f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                key=uid("KAKAO",href,title)
                if key in seen: continue
                seen.add(key)
                out.append({"platform":"KAKAO","id":key,"title":title,"category":"카카오모먼트","date":date,"url":href,"read":False,"important":False})
            except Exception:
                pass
        b.close()
    return out

def rss(platform, url):
    from email.utils import parsedate_to_datetime
    from xml.etree import ElementTree as ET
    response = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    out = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        date = item.findtext("pubDate")
        if not title or not link.startswith("https://") or not date: continue
        day = parsedate_to_datetime(date).astimezone(KST).date().isoformat()
        out.append({"platform":platform,"id":uid(platform,link,title),"title":title,"category":"공식 뉴스","date":day,"url":link,"read":False,"important":False})
    return out

AD_RE = re.compile(r"광고|캠페인|어드밴티지|전환 측정|마케팅|advantage\+?|\bads?\b|advertis|campaign|conversion|measurement|bidding|performance max|demand gen|merchant center", re.I)
EXCLUDE_RE = re.compile(r"success stor|case stud|성공 사례|실적 발표|quarterly results", re.I)
def relevant(n):
    return bool(AD_RE.search(n["title"])) and not EXCLUDE_RE.search(n["title"])

def dated_page(platform, url, pattern):
    from urllib.parse import urljoin, urlsplit
    response=requests.get(url,headers=HEADERS,timeout=30)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    out=[]; seen=set()
    for a in soup.select("a[href]"):
        link=urljoin(response.url,a["href"])
        if not re.search(pattern,urlsplit(link).path): continue
        if urlsplit(link).hostname != urlsplit(response.url).hostname: continue
        title=" ".join(a.stripped_strings)
        if len(title)<8 or link in seen: continue
        seen.add(link)
        try:
            page=requests.get(link,headers=HEADERS,timeout=15)
            page.raise_for_status()
            article=BeautifulSoup(page.text,"html.parser")
            h=article.select_one("main h1, article h1, h1")
            if h: title=" ".join(h.stripped_strings)
            tag=article.select_one('meta[property="article:published_time"], time[datetime], meta[itemprop="datePublished"]')
            raw=(tag.get("content") or tag.get("datetime") or "") if tag else ""
            m=re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",raw)
            if not m:
                m=re.search(r"(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일",article.get_text(" ",strip=True))
            if not m: continue
            day=datetime(int(m[1]),int(m[2]),int(m[3])).date().isoformat()
            out.append({"platform":platform,"id":uid(platform,link,title),"title":title,"category":"한국어 공식 공지","date":day,"url":link,"read":False,"important":False})
        except Exception as e: print("article",str(e)[:100])
        if len(seen)>=150: break
    return out

def collect_sources(platform, sources):
    out=[]
    for name, fn, filter_ads in sources:
        try:
            items=fn()
            if filter_ads: items=[n for n in items if relevant(n)]
            print(platform,name,len(items))
            out.extend(items)
        except Exception as e: print(platform,name,str(e)[:200])
    return out

def google():
    return collect_sources("GOOGLE",[
        ("한국어 공지",lambda:dated_page("GOOGLE","https://support.google.com/google-ads/announcements/9048695?hl=ko",r"/google-ads/answer/\d+"),False),
        ("한국어 제품",lambda:dated_page("GOOGLE","https://business.google.com/kr/accelerate/announcements/",r"/kr/accelerate/(?:announcements|resources)/.+"),False),
        ("정책",lambda:dated_page("GOOGLE","https://support.google.com/adspolicy/announcements/9048695?hl=ko",r"/adspolicy/answer/\d+"),False)])

def meta():
    return collect_sources("META",[
        ("한국어",lambda:dated_page("META","https://about.fb.com/ko/news/",r"/ko/news/20\d{2}/\d{2}/.+"),True)])


PUBLISHERS = {"플레이디":"플레이디","메조미디어":"메조미디어","인크로스":"인크로스","DMC미디어":"DMC미디어","DMC":"DMC미디어","모비데이즈":"모비데이즈","나스미디어":"KT나스미디어","Meta":"Meta","구글":"Google"}
def report_list(url, kind):
    from urllib.parse import urljoin, urlsplit
    response=requests.get(url,headers=HEADERS,timeout=30)
    response.raise_for_status()
    soup=BeautifulSoup(response.text,"html.parser")
    out=[]; seen=set()
    cutoff=(datetime.now(KST).date()-timedelta(days=90)).isoformat()
    for a in soup.select("a[href]"):
        link=urljoin(response.url,a["href"])
        if kind=="iboss" and not re.search(r"/ab-3208-\d+$",urlsplit(link).path): continue
        if kind=="adic" and "/lit/report/show.do" not in link: continue
        if kind=="mezzo" and urlsplit(link).hostname!="cdn.cjmezzomedia.com": continue
        if link in seen: continue
        title=" ".join(a.stripped_strings)
        if len(title)<8 or title.startswith("Download"): continue
        pub="메조미디어" if kind=="mezzo" else ""
        day=None
        for node in [a,*list(a.parents)[:5]]:
            txt=" ".join(node.stripped_strings)
            dates=set(re.findall(r"(20\d{2})[.-](\d{2})[.-](\d{2})",txt))
            if len(dates)!=1: continue
            if not pub:
                pub=next((v for k,v in PUBLISHERS.items() if k.lower() in txt.lower()),"")
            if not pub: continue
            y,m,d=next(iter(dates))
            try: day=datetime(int(y),int(m),int(d)).date().isoformat()
            except ValueError: continue
            break
        if not pub or not day: continue
        if kind=="iboss":
            title=re.sub(r"^.*?(\[[^\]]+\])",r"\1",title)
            title=re.split(r"\s+(?:메조미디어|인크로스|DMC미디어|플레이디|모비데이즈|케이티나스미디어|Meta|구글)\s+20\d{2}[.-]",title)[0]
            title=re.split(r"\s+20\d{2}\.\d{2}\.\d{2}\s+\d+",title)[0]
        seen.add(link)
        out.append({"platform":"REPORT","id":uid("REPORT",link,title),"title":title,"publisher":pub,"category":"마케팅 리포트","date":day,"url":link,"read":False,"important":False})
    return out

def reports():
    items=collect_sources("REPORT",[
        ("메조미디어",lambda:report_list("https://cjmezzomedia.com/insight-m","mezzo"),False),
        ("광고정보센터",lambda:report_list("https://www.adic.or.kr/lit/report/list.do","adic"),False),
        ("아이보스",lambda:report_list("https://www.i-boss.co.kr/ab-3207","iboss"),False)])
    seen=set(); out=[]
    for n in items:
        title=re.sub(r"^\[[^\]]+\]\s*","",n["title"])
        key=(n["publisher"],re.sub(r"\W+","",title).lower())
        if key in seen: continue
        seen.add(key); out.append(n)
    return out

def update():
    data=load(); old={n["id"]:n for n in data.get("notices",[]) if n["platform"] not in ("GOOGLE","META") or n.get("category")=="한국어 공식 공지"}
    fresh=[]
    status={}
    for platform, fn in [("NAVER",naver),("GOOGLE",google),("META",meta),("REPORT",reports)]:
        try:
            items=fn()
            fresh.extend(items)
            status[platform]={"ok":bool(items),"count":len(items),"checked_at":datetime.now(KST).isoformat()}
            if not items: status[platform]["error"]="No items extracted"
        except Exception as e:
            status[platform]={"ok":False,"count":0,"error":str(e)[:300],"checked_at":datetime.now(KST).isoformat()}
        print(platform,status[platform])
    status["KAKAO"]={"mode":"manual","count":0,"reason":"Login required"}
    data["source_status"]=status
    for n in fresh:
        if n["id"] in old:
            # Preserve user state
            old[n["id"]].update({k:v for k,v in n.items() if k not in ("read","important")})
        else:
            old[n["id"]]=n
    notices=list(old.values())
    notices.sort(key=lambda x:(x.get("date",""),x.get("id","")),reverse=True)
    data["notices"]=notices
    data["updated_at"]=datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    save(data)
    print("updated",len(notices))

if __name__=="__main__": update()
