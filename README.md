
# 광고 플랫폼 공지 관제판 V2

## 포함 기능
- 네이버 광고주센터 / 카카오모먼트 공지 수집
- 최신순 정렬
- 플랫폼 필터
- 주제 자동 태깅
- 검색
- 미확인 / 확인 상태
- 중요 표시
- 중요·미확인 우선 정렬
- 원문 바로가기
- 하루 2회 자동 수집
- GitHub Actions 기반 자동 업데이트

## 실행
```bash
pip install -r requirements.txt
python -m playwright install chromium
python scraper.py
streamlit run app.py
```

## 운영
GitHub Actions가 한국시간 09:00 / 21:00에 수집합니다.
Streamlit Cloud 등에 저장소를 연결하면 웹 대시보드로 사용할 수 있습니다.

## 데이터 구조
`data/notices.json`에 공지와 확인/중요 상태가 저장됩니다.

## 주의
네이버/카카오 사이트의 HTML 또는 동적 렌더링 구조가 변경되면 scraper.py의 선택자를 수정해야 합니다.
