# DB 구조
`schema.sql`: SQLite 초기 테이블 정의. 서버 시작 시 `src/storage/database.py`가 자동 적용합니다. 실행 DB는 `runtime/deploy.sqlite3`에 생성됩니다. 향후 변경은 번호가 붙은 마이그레이션 SQL로 추가하고 적용 순서를 문서화합니다. 현재 별도 마이그레이션은 없습니다.
