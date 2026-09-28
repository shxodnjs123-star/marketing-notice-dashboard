
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

def update():
    data=load(); old={n["id"]:n for n in data.get("notices",[])}
    fresh=naver()+kakao()
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
