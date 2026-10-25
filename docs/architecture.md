# 기술 구조와 개발 계획

## 구조

학교 HTTPS 프록시 → VM Nginx:80 → 운영 Django(live) 또는 테스트 Django(test) → PostgreSQL. `/test/`는 테스트 앱으로 전달하며 경로를 제거하지 않는다. 운영 앱은 테스트 라우트를 제공하지 않는다. 모바일 화면은 Django 템플릿, 자체 반응형 CSS, Vanilla JavaScript로 구성한다. 앞선 Bootstrap 제안 대신 동일한 모바일 요구를 충족하는 작은 자체 스타일시트를 사용해 외부 UI 의존성을 줄였다.

- Python 3.12, Django 5.2 LTS, PostgreSQL 17, Gunicorn, Nginx, Docker Compose.
- Python 버전은 requirements.lock에 고정. 프런트 라이브러리 Signature Pad 5.0.4, Leaflet 1.9.4를 라이선스와 함께 저장.
- openpyxl/Pillow로 명단·서명 Excel, qrcode로 QR 이미지 생성.
- 학생은 표준 브라우저 Geolocation을 사용. 지도는 조교 화면에서만 OSM 타일 호출.
- 실시간 서버 연결 대신 고정 QR 한 번 로드·학생 세션/가능 수업 상태 10초 확인·서버 시계 30초 동기화. 현황은 조회/새로고침 방식.

## 자원

VM 2 CPU / 4GB RAM / 32GB 기준. 컨테이너 메모리 상한: DB 768MB, 운영 768MB, 테스트 512MB, Nginx 128MB. PostgreSQL shared_buffers 128MB, 최대 연결 60. 운영 Gunicorn 2 workers × 2 threads, 테스트 1 × 2. 실제 성능 수치는 VM에서 검증한다. 초기 구현은 Redis/Celery를 요구하지 않는다.

## 데이터

Policy(위치·시간·테스트 시계), Course(수업 회차), Enrollment(수업별 명단), Attempt(익명 작성 세션), Attendance(확정 기록·서명 경로·정책 스냅샷), Audit(수정 이력), RateBucket(요청 횟수), Django User/Session.

학생 명단 유일키는 `(course, student_id)`, 수업 Attendance는 Enrollment에 1:1. 타 학과 Attendance는 enrollment 없이 학과/학번/이름/guest_date를 직접 저장하며 `(guest_date, student_id)` 조건부 유일 제약으로 하루 1회를 보장한다. 체크 제약으로 두 기록 유형을 구분한다. 트랜잭션과 행 잠금으로 중복 제출/정정 충돌 방지. 최종 제출은 정책 행 잠금을 사용해 테스트 초기화와 경합하지 않게 한다. 이 구간에 저장된 서명 생성이 포함되므로 VM 부하 시험에서 병목을 측정한다.

학생 응답에는 다른 학생 명단·서명·개별 기록을 제공하지 않는다. 같은 작성 세션의 통신 재시도는 기존 완료 결과를 반환하며, 다른 세션이 이미 출석한 학번을 입력하면 중복 안내만 제공한다.

## QR와 시간

QR은 운영 `/enter/`, 테스트 `/test/enter/`의 고정 URL이다. 담당자 화면에서 같은 PNG를 로드·다운로드·인쇄한다. 이전 토큰 URL도 접속 경로 호환을 위해 진입 가능하지만 토큰은 출석 권한 증거로 사용하지 않는다. QR 진입마다 서버 저장 5분 Attempt를 만들며 테스트 세대는 Attempt에만 적용한다. 클라이언트 타이머를 신뢰하지 않는다. 정책·시각·명단·위치·서명은 서버에서 검사한다.

테스트 시계는 기준 테스트 시각 + 실제 경과 시간이다. 운영은 해당 필드를 무시한다. 브라우저 위치 timestamp는 실제 시계로 최신 여부를 검사한다. 수업 시간과 5분 세션은 테스트 시계로 검사한다. 위치 모의는 실제 좌표/측정시각 검증 후 테스트 서버에서만 구역 판정 결과를 대체하며 기록에 출처를 남긴다. 모의 모드도 좌표를 수신·저장한다.

## 보안과 배포

관리자/조교 역할 검사, Django CSRF, HttpOnly 세션 쿠키, 환경별 쿠키 이름·경로, HTTPS secure 쿠키. QR와 입력 쿼리는 웹 액세스 로그에 기록하지 않는다. 서명은 비공개 FileField 경로에 저장하고 인증된 조회를 통해서만 제공한다. PNG 재디코딩, 크기·빈 이미지 검증. 스프레드시트 압축 해제 크기·행 수·형식 검사.

PostgreSQL 운영/테스트 DB에서 PUBLIC CONNECT를 제거하고 각각 독립 사용자만 허용한다. 앱 컨테이너에는 자기 환경 DB 비밀번호만 제공한다. DB 포트는 외부 공개하지 않는다. `.env` 대신 `/var/lib/attendance/config/runtime.env`를 VM에만 생성한다.

학교 프록시가 HTTPS 헤더를 정제하고 VM 원본 접근을 제한하는지 확인한 뒤 TRUST_PROXY_HTTPS를 사용한다. 기본 0에서도 외부 HTTPS 도메인을 CSRF 허용 출처로 설정하고 Secure 쿠키를 발급한다. 앱 수준 HTTPS 리다이렉트는 기본 비활성으로 두어 프록시 리다이렉트 루프를 피한다. 외부 HTTP→HTTPS 강제 및 인증서는 학교 인프라에서 확인한다.

## 구현 및 검증 단계

브라우저 학번 등록은 `BrowserIdentity`에 저장한다. QR 교환 시 서명된 임의 UUID 쿠키를 발급하며, 학번 자체를 쿠키에 담지 않는다. HttpOnly·SameSite=Lax·운영 Secure 속성, 1년 유효기간, 운영/테스트별 이름·경로를 사용한다. 담당자 로그아웃과 출석 세션 만료로는 등록이 해제되지 않는다. 출석 시 쿠키 소유자와 Attempt 소유자를 확인하고, 트랜잭션 안에서 브라우저 행을 잠가 최초 성공한 학번만 등록한다.

브라우저 학번 변경 웹 경로는 제공하지 않는다. 예외는 조교가 기존 수동 출석·정정 기능에서 처리하며 브라우저 등록을 해제하지 않는다. 기존 데이터 호환성을 위해 브라우저 revision 필드는 유지한다. 테스트 전체 초기화는 등록도 삭제한다. 마이그레이션 이전의 작성 세션은 새 QR 접속이 필요하며, 기존 출석 기록은 보존한다.

1. 확정 요구사항/화면/예외 규칙 문서화.
2. 모델·권한·시간·QR·위치·중복 방지 구현.
3. 모바일 학생 화면·조교 운영·시스템 관리 연결.
4. Excel 등록·수정·두 종류 출력 구현.
5. 별도 테스트 앱·DB·시계·시나리오·초기화 구현.
6. VM 메뉴 설치·실행·정지·업데이트·삭제·백업·복구 구현.
7. 자동 테스트(운영/테스트 각각), 브라우저 흐름 점검, 배포 설정 검증.
8. 사용자 VM에서 PostgreSQL 동시 접속, 프록시, 실제 위치, 장치, 백업 복구 검증.

## 출처

- Django 배포: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- PostgreSQL 지원: https://www.postgresql.org/support/versioning/
- Docker Compose: https://docs.docker.com/compose/how-tos/production/
- Geolocation: https://www.w3.org/TR/geolocation/
- openpyxl: https://openpyxl.readthedocs.io/en/stable/images.html
- Signature Pad: https://github.com/szimek/signature_pad

## 수업 삭제

관리자·조교 전용 확인 화면에서 삭제 대상 수와 엑셀 다운로드를 제공한다. POST에 CSRF·수업명·사유와 30분 유효 서명 토큰을 요구한다. 토큰은 수업·명단·출석 내용의 지문을 포함한다. Policy→Course→Enrollment 순으로 행을 잠근 뒤 최신 지문을 비교하여 미리보기 이후 추가·수정된 기록의 무심코 삭제를 막는다. 삭제와 감사 이력 저장은 하나의 트랜잭션이며 서명 파일은 커밋 후 제거한다. 파일 정리 실패는 서버 로그에 남긴다. 실제 PostgreSQL 동시성 검증은 VM에서 수행한다.
