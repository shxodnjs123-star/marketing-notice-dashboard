
import json
from pathlib import Path
import streamlit as st

BASE = Path(__file__).parent
DATA = BASE / "data" / "notices.json"

st.set_page_config(page_title="광고 공지 관제판", page_icon="📢", layout="wide")

def load():
    if not DATA.exists():
        return {"updated_at": None, "notices": []}
    return json.loads(DATA.read_text(encoding="utf-8"))

def save(data):
    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def tags(n):
    text = f"{n.get('title','')} {n.get('category','')}".lower()
    result = []
    rules = {
        "검색광고": ["파워링크","검색광고","쇼핑검색","브랜드검색"],
        "디스플레이": ["gfa","디스플레이","성과형","배너"],
        "쇼핑": ["쇼핑","상품","스마트스토어"],
        "검수/정책": ["검수","정책","제한","금지","심사"],
        "과금/입찰": ["과금","입찰","광고비","수수료","예산"],
        "소재": ["소재","문구","이미지","동영상"],
        "시스템": ["점검","장애","시스템","오류"],
        "프로모션": ["프로모션","이벤트","혜택","쿠폰"],
    }
    for tag, words in rules.items():
        if any(w in text for w in words):
            result.append(tag)
    return result or ["기타"]

data = load()
notices = data.get("notices", [])

# 자동 태그 보강
for n in notices:
    n["tags"] = tags(n)
    n.setdefault("read", False)
    n.setdefault("important", False)

st.title("📢 광고 플랫폼 공지 관제판")
st.caption("네이버 광고주센터 + 카카오모먼트 공지를 한 곳에서 확인")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("전체", len(notices))
c2.metric("미확인", sum(not n.get("read") for n in notices))
c3.metric("중요", sum(n.get("important") for n in notices))
c4.metric("네이버", sum(n.get("platform")=="NAVER" for n in notices))
c5.metric("카카오", sum(n.get("platform")=="KAKAO" for n in notices))

if data.get("updated_at"):
    st.caption(f"마지막 수집: {data['updated_at']}")

with st.sidebar:
    st.header("🔎 필터")
    platforms = st.multiselect("플랫폼", ["NAVER","KAKAO"], ["NAVER","KAKAO"])
    statuses = st.multiselect("상태", ["미확인","중요","확인"], ["미확인","중요","확인"])
    tag_options = sorted({t for n in notices for t in n.get("tags", [])})
    selected_tags = st.multiselect("주제", tag_options)
    keyword = st.text_input("검색", placeholder="파워링크 / GFA / 검수 / 과금...")
    sort = st.radio("정렬", ["최신순","중요·미확인 우선"], index=0)
    limit = st.slider("표시 개수", 10, 200, 50, 10)

filtered = []
for n in notices:
    if n.get("platform") not in platforms:
        continue
    status = "미확인" if not n.get("read") else "확인"
    if n.get("important"):
        status = "중요"
    if status not in statuses:
        continue
    if selected_tags and not set(selected_tags).intersection(n.get("tags", [])):
        continue
    q = keyword.lower().strip()
    if q and q not in (n.get("title","") + " " + n.get("category","")).lower():
        continue
    filtered.append(n)

if sort == "최신순":
    filtered.sort(key=lambda x:(x.get("date",""),x.get("id","")), reverse=True)
else:
    filtered.sort(key=lambda x:(not x.get("important"),x.get("read"),x.get("date","")), reverse=False)

st.subheader(f"공지 {len(filtered)}건")

for i, n in enumerate(filtered[:limit]):
    platform = "🔵 NAVER" if n.get("platform")=="NAVER" else "🟡 KAKAO"
    state = "⭐ 중요" if n.get("important") else ("🆕 미확인" if not n.get("read") else "확인")
    with st.container(border=True):
        left, right = st.columns([7,2])
        with left:
            st.markdown(f"### {state}  {n.get('title','')}")
            st.caption(f"{platform}  ·  {n.get('category') or '공지'}  ·  {n.get('date','')}")
            if n.get("tags"):
                st.write(" ".join(f"`{t}`" for t in n["tags"]))
        with right:
            if n.get("url"):
                st.link_button("원문 보기 ↗", n["url"], use_container_width=True)
            a,b = st.columns(2)
            if a.button("확인" if not n.get("read") else "미확인", key=f"r{i}_{n['id']}"):
                n["read"] = not n.get("read")
                save(data)
                st.rerun()
            if b.button("중요" if not n.get("important") else "해제", key=f"i{i}_{n['id']}"):
                n["important"] = not n.get("important")
                save(data)
                st.rerun()

st.divider()
st.caption("※ 신규 공지는 수집 시 미확인 상태로 저장됩니다. 확인/중요 상태는 데이터 파일에 저장됩니다.")
