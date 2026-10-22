# 출석 서비스

학생은 회원가입 없이 현장 QR로 접속해 수업 선택 → 학번·이름 → 서명 → 위치 확인을 거쳐 출석합니다. 조교는 명단·수업·현황·예외 처리를, 관리자는 계정과 시스템 정책까지 관리합니다. 행사 소개·행사명 관리 기능은 없습니다.

## Ubuntu VM에서 시작

대상: Ubuntu, 2 CPU, RAM 4GB, 디스크 32GB, Docker 사용 가능. 외부 HTTPS 프록시는 학교에서 제공하며 VM은 HTTP 80포트로 서비스합니다.

```bash
git clone <사용할-GitHub-저장소-주소> attendance
cd attendance
bash manage.sh
```

메뉴 **1 환경 점검 → 필요하면 2 인프라 설치 → 3 최초 설정 → 4 운영 실행 → 13 테스트 실행** 순서로 진행합니다. 기존 Docker가 있으면 그대로 사용합니다. 최초 설정에서 관리자 계정을 운영·테스트 각각의 DB에 생성합니다. 비밀번호는 소스에 저장하지 않습니다.

- 운영 담당자: <https://inno-pjk5401.apps.dauai.org/staff/>
- 테스트 제어: <https://inno-pjk5401.apps.dauai.org/test/staff/test-control/>
- 테스트 담당자 로그인: <https://inno-pjk5401.apps.dauai.org/test/staff/login/>

**테스트 제어에서 ‘기본 테스트 준비’를 누른 뒤 ‘테스트 QR 열기’를 선택하면 교수님들이 바로 체험할 수 있습니다.** 처음에는 ‘모의: 구역 안’이므로 위치 권한을 요청하지 않습니다. 실제 위치 시험 시 테스트 인정 구역을 설정하고 위치 모드를 ‘실제 위치’로 바꾸세요.

명단: 가상수업 3개, 각 70명. 학번 `20260001` / 이름 `가상학생01`부터 `20260070` / `가상학생70`까지 각자 다르게 배정합니다. 가상수업은 동일 시간에 열립니다.

## 문서

- [확정 요구사항·화면 구성](docs/requirements.md)
- [기술 구조·개발 계획](docs/architecture.md)
- [VM 설치·업데이트·백업·복구](docs/operations.md)
- [교수님 시연 및 검증 절차](docs/test-guide.md)
- [검증 결과와 남은 현장 확인](docs/verification.md)

## 로컬 개발 / 자동 테스트

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv/Scripts/Activate.ps1
pip install -r requirements.lock
export DEBUG=1
python manage.py migrate
python manage.py ensure_admin
python manage.py runserver
```

로컬은 SQLite를 사용합니다. 운영 Docker와 CI는 PostgreSQL을 사용합니다. `APP_ENV=sandbox`를 지정하면 로컬에서도 별도 `sandbox.sqlite3`, `/test/` 경로, 테스트 전용 서명 폴더를 사용합니다. 두 개발 서버를 띄울 때는 테스트 서버의 `PUBLIC_ORIGIN`도 해당 포트로 지정하세요.

```bash
bash scripts/check.sh
```

배포 자료에는 Python 의존성 버전, Django DB 마이그레이션, 프런트엔드 라이브러리를 고정해 포함했습니다. 서명·QR·기본 화면은 외부 CDN에서 스크립트를 받지 않습니다. 관리자 지도 배경만 OpenStreetMap 타일을 사용하며 타일 장애 시 좌표 직접 입력은 가능합니다.

운영 비밀값·실제 학생 데이터·서명·DB·백업은 GitHub에 올리지 마세요. 루트의 `.gitignore`와 `.dockerignore`가 이를 제외합니다. 이전 대화에서 중단된 `festival-check/` 템플릿은 이 프로젝트와 무관하며 배포·Git 추적에서 제외됩니다.
