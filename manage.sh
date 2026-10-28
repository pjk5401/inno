#!/usr/bin/env bash
# Ubuntu operator menu. Never sources a GitHub-provided .env or deletes another project.
set -Eeuo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
DATA=/var/lib/attendance
ENV_FILE="$DATA/config/runtime.env"
COMPOSE="$ROOT/compose.yml"
if [[ $(id -u) == 0 ]]; then SUDO=(); else SUDO=(sudo); fi
say() { printf '\n%s\n' "$*"; }
confirm() { local value; read -r -p "$1 [$2 입력]: " value; [[ $value == "$2" ]]; }
need_config() { "${SUDO[@]}" test -f "$ENV_FILE" || { say '먼저 3. 최초 설정을 실행하세요.'; return 1; }; }
dc() {
    local owner_dir
    owner_dir=$("${SUDO[@]}" docker ps -a --filter label=com.docker.compose.project=attendance --format '{{.Label "com.docker.compose.project.working_dir"}}' | sort -u)
    if [[ -n $owner_dir && $owner_dir != "$ROOT" ]]; then
        say "다른 경로의 attendance 프로젝트가 존재합니다: $owner_dir. 충돌 방지를 위해 중단합니다.";return 1
    fi
    "${SUDO[@]}" docker compose --project-directory "$ROOT" --env-file "$ENV_FILE" -f "$COMPOSE" --profile test "$@"
}
cfg() { "${SUDO[@]}" awk -F= -v key="$1" '$1==key {print substr($0,length(key)+2)}' "$ENV_FILE"; }
http_port() { local port; port=$(cfg HTTP_PORT); printf '%s' "${port:-80}"; }
read_network_config() {
    local current_origin=${1:-} current_port=${2:-80}
    say '외부 접속 주소 전체를 입력하세요. 예: https://attendance.example.edu 또는 https://attendance.example.edu:8443'
    read -r -p "외부 HTTPS 주소${current_origin:+ [$current_origin]}: " origin
    origin=${origin:-$current_origin}
    say 'VM HTTP 포트는 프록시가 연결할 포트입니다. 외부 HTTPS 포트와 다를 수 있습니다.'
    read -r -p "VM HTTP 포트 [$current_port]: " port
    port=${port:-$current_port}
    network_config=$(python3 "$ROOT/deploy/network_config.py" "$origin" "$port") || return 1
    port=$(printf '%s\n' "$network_config" | awk -F= '$1=="HTTP_PORT" {print $2}')
}
space_check() {
    local available
    available=$(df -Pk "$DATA" | awk 'NR==2 {print $4}')
    (( available >= 2097152 )) || { say '가용 공간이 2GB 미만입니다. 데이터는 자동 삭제하지 않습니다. 공간 확보 후 재시도하세요.'; return 1; }
}
check_environment() {
    say '서버 환경'
    cat /etc/os-release
    printf '\nCPU: '; getconf _NPROCESSORS_ONLN
    free -h
    df -h /
    if command -v docker >/dev/null; then "${SUDO[@]}" docker --version; "${SUDO[@]}" docker compose version || true; else say 'Docker 미설치'; fi
    say '현재 리스닝 포트 (최초 설정에서 사용할 VM HTTP 포트를 선택하세요)'
    "${SUDO[@]}" ss -ltnp || true
}
install_infra() {
    [[ -f /etc/os-release ]] || return 1
    . /etc/os-release
    [[ $ID == ubuntu ]] || { say '이 설치 메뉴는 Ubuntu 전용입니다.'; return 1; }
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y ca-certificates curl git python3 openssl tar gzip iproute2
    if command -v docker >/dev/null; then
        "${SUDO[@]}" docker compose version >/dev/null 2>&1 || {
            say '기존 Docker에 Compose 플러그인이 없습니다. 기존 설치 방식을 확인해 Compose 플러그인을 설치해주세요. Docker는 교체하지 않습니다.'
            return 1
        }
        "${SUDO[@]}" docker compose up --help | grep -- '--wait-timeout' >/dev/null || {
            say '현재 Compose가 너무 오래되었습니다. --wait-timeout을 지원하는 Compose v2로 업데이트한 뒤 다시 실행하세요.';return 1
        }
        say '기존 Docker 및 Compose를 사용합니다.'
        return
    fi
    "${SUDO[@]}" install -m 0755 -d /etc/apt/keyrings
    "${SUDO[@]}" curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    "${SUDO[@]}" chmod a+r /etc/apt/keyrings/docker.asc
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' "$(dpkg --print-architecture)" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" | "${SUDO[@]}" tee /etc/apt/sources.list.d/attendance-docker.list >/dev/null
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    "${SUDO[@]}" systemctl enable --now docker
}
prepare_dirs() {
    "${SUDO[@]}" mkdir -p "$DATA/config" "$DATA/postgres" "$DATA/signatures/live" "$DATA/signatures/test" "$DATA/backups"
    "${SUDO[@]}" chmod 700 "$DATA/config"
    "${SUDO[@]}" chown -R 10001:10001 "$DATA/signatures"
    "${SUDO[@]}" chmod 755 "$DATA" "$DATA/signatures" "$DATA/signatures/live" "$DATA/signatures/test"
    # Backups may be listed by the app but file contents remain root-only.
    "${SUDO[@]}" chmod 755 "$DATA/backups"
}
setup() {
    if "${SUDO[@]}" test -f "$ENV_FILE"; then say '기존 설정을 보존합니다. 주소·포트는 17번, 계정은 11번 메뉴에서 변경하세요.'; return; fi
    command -v openssl >/dev/null || { say '2. 필수 인프라 설치를 먼저 실행하세요.'; return 1; }
    "${SUDO[@]}" docker compose version >/dev/null
    prepare_dirs
    local origin port network_config trust temp
    read_network_config
    say '학교 프록시가 X-Forwarded-Proto를 정제하고 VM 직접 접근이 제한된 것이 확인된 경우에만 1을 선택하세요.'
    read -r -p 'HTTPS 프록시 헤더 신뢰 [0]: ' trust
    trust=${trust:-0}; [[ $trust == 0 || $trust == 1 ]] || return 1
    temp=$(mktemp)
    {
        printf '%s\nTRUST_PROXY_HTTPS=%s\n' "$network_config" "$trust"
        printf 'POSTGRES_PASSWORD=%s\nLIVE_DB_PASSWORD=%s\nTEST_DB_PASSWORD=%s\nLIVE_SECRET_KEY=%s\nTEST_SECRET_KEY=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" "$(openssl rand -hex 48)" "$(openssl rand -hex 48)"
    } > "$temp"
    "${SUDO[@]}" install -m 600 "$temp" "$ENV_FILE"
    rm -f -- "$temp"
    say '설정을 저장했습니다. 최초 빌드·DB 준비를 진행합니다.'
    build_and_migrate
    say '운영·테스트 환경에 사용할 최초 관리자 계정을 설정합니다.'
    account_menu both
    say '최초 설정 완료. 4번으로 서비스를 실행하세요.'
}
wait_db() {
    local i
    for i in $(seq 1 60); do
        if dc exec -T db pg_isready -U postgres >/dev/null 2>&1; then return; fi
        sleep 2
    done
    say 'DB가 준비되지 않았습니다. 로그를 확인해주세요.';return 1
}
build_and_migrate() {
    need_config; space_check
    dc config --quiet
    dc build live
    dc up -d db
    wait_db
    dc run --rm --no-deps live python manage.py migrate --noinput
    dc run --rm --no-deps test python manage.py migrate --noinput
    dc run --rm --no-deps live python manage.py check
    dc run --rm --no-deps test python manage.py check
}
check_port() {
    local port; port=$(http_port)
    if dc ps --status running --services | grep -qx nginx; then return; fi
    if "${SUDO[@]}" ss -ltn "( sport = :$port )" | tail -n +2 | grep -q .; then
        say "${port}포트를 다른 서비스가 사용하고 있습니다. 기존 프로젝트를 자동 중지하지 않습니다.";return 1
    fi
}
start_live() {
    need_config;check_port;build_and_migrate
    dc up -d --wait --wait-timeout 120 db live nginx
    curl --fail --silent --show-error -H "Host: $(cfg PUBLIC_ORIGIN | sed 's#https://##')" "http://127.0.0.1:$(http_port)/health/"
    say "운영 주소: $(cfg PUBLIC_ORIGIN)/staff/"
}
start_test() {
    need_config;check_port;build_and_migrate
    dc up -d --wait --wait-timeout 120 db live test nginx
    curl --fail --silent --show-error -H "Host: $(cfg PUBLIC_ORIGIN | sed 's#https://##')" "http://127.0.0.1:$(http_port)/test/health/"
    say "테스트 제어: $(cfg PUBLIC_ORIGIN)/test/staff/test-control/"
}
change_network() (
    set -Eeuo pipefail
    need_config
    local origin port network_config temp saved running old_port
    old_port=$(http_port)
    read_network_config "$(cfg PUBLIC_ORIGIN)" "$old_port"
    if [[ $port != "$old_port" ]] && "${SUDO[@]}" ss -ltn "( sport = :$port )" | tail -n +2 | grep -q .; then
        say "${port}포트를 다른 서비스가 사용하고 있습니다. 설정을 변경하지 않았습니다.";return 1
    fi
    running=$(dc ps --status running --services | grep -E '^(live|test|nginx)$' || true)
    temp=$(mktemp)
    trap 'rm -f -- "$temp"' EXIT
    "${SUDO[@]}" python3 "$ROOT/deploy/network_config.py" "$origin" "$port" --env-file "$ENV_FILE" > "$temp"
    "${SUDO[@]}" docker compose --project-directory "$ROOT" --env-file "$temp" -f "$COMPOSE" --profile test config --quiet
    saved="$DATA/config/runtime-before-network-$(date -u +%Y%m%dT%H%M%S)-$(openssl rand -hex 3).env"
    "${SUDO[@]}" install -m 600 "$ENV_FILE" "$saved"
    "${SUDO[@]}" install -m 600 "$temp" "$ENV_FILE"
    say "이전 설정 보관: $saved"
    if [[ -n $running ]]; then
        dc up -d --no-deps --wait --wait-timeout 120 $running
    fi
    say "주소·포트 변경 완료: $(cfg PUBLIC_ORIGIN) (VM HTTP $(http_port))"
    say '정지 상태인 환경은 4번/13번으로 실행하세요. 외부 프록시의 도메인·인증서·연결 포트도 맞추고, 주소가 바뀌면 현장 QR을 다시 인쇄하세요.'
)
account_menu() {
    need_config
    local target=${1:-} username password password2 payload service
    if [[ -z $target ]]; then read -r -p '대상 (live/test/both) [both]: ' target;target=${target:-both};fi
    [[ $target == live || $target == test || $target == both ]] || return 1
    read -r -p '관리자 아이디: ' username
    read -r -s -p '새 비밀번호 (10자 이상): ' password;printf '\n'
    read -r -s -p '비밀번호 확인: ' password2;printf '\n'
    [[ $password == "$password2" ]] || { say '비밀번호가 일치하지 않습니다.';return 1; }
    payload=$(printf '%s\n%s' "$username" "$password" | python3 -c 'import sys,json; u,p=sys.stdin.read().split("\n",1);print(json.dumps({"username":u,"password":p}))')
    unset password password2
    dc up -d db;wait_db
    if [[ $target == both ]]; then
        for service in live test; do printf '%s' "$payload" | dc run --rm --no-deps -T "$service" python manage.py ensure_admin --json-stdin;done
    else printf '%s' "$payload" | dc run --rm --no-deps -T "$target" python manage.py ensure_admin --json-stdin;fi
    unset payload
}
backup() (
    set -Eeuo pipefail
    need_config;space_check
    local stage name running commit usage available db_bytes media_kb
    dc up -d db;wait_db
    db_bytes=$(dc exec -T db psql -U postgres -At -c "SELECT sum(pg_database_size(datname)) FROM pg_database WHERE datname IN ('attendance_live','attendance_test')")
    media_kb=$("${SUDO[@]}" du -sk "$DATA/signatures" | awk '{print $1}')
    available=$(df -Pk "$DATA" | awk 'NR==2 {print $4}')
    (( available > (db_bytes/1024 + media_kb)*2 + 524288 )) || { say 'DB·서명 복사본과 압축 파일을 함께 만들 여유 공간이 부족합니다.';return 1; }
    stage=$("${SUDO[@]}" mktemp -d "$DATA/backups/.stage.XXXXXX")
    name="attendance-$(date -u +%Y%m%dT%H%M%S)-$(openssl rand -hex 3).tar.gz"
    running=$(dc ps --status running --services | grep -E '^(live|test)$' || true)
    cleanup_backup() { "${SUDO[@]}" rm -rf -- "$stage"; if [[ -n $running ]]; then dc up -d $running || true;fi; }
    trap cleanup_backup EXIT
    dc stop live test
    dc up -d db;wait_db
    # No writers remain; DB dumps and signature files form one consistent checkpoint.
    dc exec -T db pg_dump -U postgres -Fc attendance_live | "${SUDO[@]}" tee "$stage/live.dump" >/dev/null
    dc exec -T db pg_dump -U postgres -Fc attendance_test | "${SUDO[@]}" tee "$stage/test.dump" >/dev/null
    "${SUDO[@]}" cp "$ENV_FILE" "$stage/config.env"
    "${SUDO[@]}" cp -a "$DATA/signatures" "$stage/signatures"
    commit=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf unknown)
    printf '{"version":1,"commit":"%s","created_utc":"%s"}\n' "$commit" "$(date -u +%FT%TZ)" | "${SUDO[@]}" tee "$stage/manifest.json" >/dev/null
    usage=$("${SUDO[@]}" du -sk "$stage" | awk '{print $1}');available=$(df -Pk "$DATA" | awk 'NR==2 {print $4}')
    (( available > usage + 524288 )) || { say '백업 압축 공간이 부족합니다. 불완전한 백업은 제거합니다.';return 1; }
    "${SUDO[@]}" tar -C "$stage" -czf "$DATA/backups/$name.partial" .
    "${SUDO[@]}" mv "$DATA/backups/$name.partial" "$DATA/backups/$name"
    "${SUDO[@]}" chmod 600 "$DATA/backups/$name"
    (cd "$DATA/backups"; "${SUDO[@]}" sha256sum "$name" | "${SUDO[@]}" tee "$name.sha256" >/dev/null)
    say "백업 완료: $DATA/backups/$name"
)
restore_backup() (
    set -Eeuo pipefail
    need_config;space_check
    local name stage archive backup_commit current_commit checkout_needed=0
    "${SUDO[@]}" ls -lh "$DATA/backups/"*.tar.gz 2>/dev/null || true
    read -r -p '복구할 파일명 (.tar.gz): ' name
    [[ $name =~ ^attendance-[a-zA-Z0-9-]+\.tar\.gz$ ]] || { say '올바른 백업 파일명을 입력하세요.';return 1; }
    archive="$DATA/backups/$name"
    "${SUDO[@]}" test -f "$archive"; "${SUDO[@]}" test -f "$archive.sha256"
    (cd "$DATA/backups"; "${SUDO[@]}" sha256sum --check "$name.sha256")
    stage=$("${SUDO[@]}" mktemp -d "$DATA/backups/.restore.XXXXXX")
    trap '"${SUDO[@]}" rm -rf -- "$stage"' EXIT
    "${SUDO[@]}" python3 "$ROOT/deploy/archive.py" "$archive" "$stage"
    backup_commit=$("${SUDO[@]}" python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["commit"])' "$stage/manifest.json")
    current_commit=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || printf unknown)
    if [[ $backup_commit != unknown && $backup_commit != "$current_commit" ]]; then
        [[ $backup_commit =~ ^[a-f0-9]{40}$ ]] || { say '백업의 소스 버전 정보가 올바르지 않습니다.';return 1; }
        [[ -z $(git -C "$ROOT" status --porcelain) ]] || { say '로컬 소스 변경을 먼저 보존해주세요. 소스와 데이터를 변경하지 않았습니다.';return 1; }
        git -C "$ROOT" cat-file -e "$backup_commit^{commit}" || { say '백업의 커밋이 로컬에 없습니다. GitHub에서 해당 이력을 받은 후 재시도해주세요.';return 1; }
        say "복구할 소스 버전: $backup_commit (현재: $current_commit)"
        confirm '백업 직후 소스도 해당 버전의 detached HEAD로 전환합니다.' CHECKOUT || return
        checkout_needed=1
    fi
    confirm '운영·테스트 DB와 서명을 선택한 백업으로 되돌립니다.' RESTORE || return
    backup
    dc stop live test nginx
    if (( checkout_needed )); then git -C "$ROOT" checkout --detach "$backup_commit";fi
    "${SUDO[@]}" install -m 600 "$stage/config.env" "$ENV_FILE"
    dc up -d --force-recreate db;wait_db
    dc exec -T db bash /docker-entrypoint-initdb.d/10-databases.sh
    for database in live test; do
        "${SUDO[@]}" cat "$stage/$database.dump" | dc exec -T db pg_restore -U postgres --clean --if-exists --exit-on-error -d "attendance_$database"
    done
    # Delete only the explicitly fixed, verified service-owned signature directory.
    [[ $("${SUDO[@]}" realpath "$DATA/signatures") == /var/lib/attendance/signatures ]] || return 1
    "${SUDO[@]}" rm -rf -- /var/lib/attendance/signatures
    "${SUDO[@]}" cp -a "$stage/signatures" "$DATA/signatures"
    prepare_dirs
    dc build live
    dc up -d --wait --wait-timeout 120 db live test nginx
    say '복구 완료. 브라우저에서 새로 로그인하고 기록을 확인하세요.'
)
update_service() {
    need_config
    git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null
    [[ -z $(git -C "$ROOT" status --porcelain) ]] || { say '로컬 변경사항이 있어 업데이트를 중단합니다. 변경을 보존·정리한 뒤 다시 실행하세요.';return 1; }
    local running old_commit
    running=$(dc ps --status running --services | grep -E '^(live|test)$' || true)
    old_commit=$(git -C "$ROOT" rev-parse HEAD)
    backup
    git -C "$ROOT" pull --ff-only
    dc stop live test
    build_and_migrate
    if [[ -n $running ]]; then dc up -d --wait --wait-timeout 120 $running nginx;fi
    say "업데이트 완료. 이전 소스 버전: $old_commit"
}
delete_service() {
    need_config
    say '1. 실행 구성만 제거 (데이터·설정·백업 보존)'
    say '2. 운영·테스트 데이터까지 제거 (백업 보존)'
    say '3. 백업까지 완전 제거'
    local choice path
    read -r -p '선택 [1]: ' choice;choice=${choice:-1}
    [[ $choice =~ ^[123]$ ]] || return 1
    confirm '출석 서비스 구성만 제거합니다. 다른 프로젝트는 변경하지 않습니다.' DELETE || return
    if [[ $choice != 1 ]]; then confirm '출석·서명을 포함한 운영 및 테스트 데이터를 삭제합니다.' DELETE-DATA || return;fi
    if [[ $choice == 3 ]]; then confirm '백업도 영구 삭제합니다. 복구할 수 없습니다.' DELETE-BACKUPS || return;fi
    dc down --remove-orphans
    if [[ $choice != 1 ]]; then
        for path in /var/lib/attendance/postgres /var/lib/attendance/signatures /var/lib/attendance/config; do
            [[ $("${SUDO[@]}" realpath -m "$path") == "$path" ]] || { say '예상하지 않은 경로입니다. 중단합니다.';return 1; }
            "${SUDO[@]}" du -sh "$path" || true
            "${SUDO[@]}" rm -rf -- "$path"
        done
    fi
    if [[ $choice == 3 ]]; then
        [[ $("${SUDO[@]}" realpath /var/lib/attendance/backups) == /var/lib/attendance/backups ]] || return 1
        "${SUDO[@]}" rm -rf -- /var/lib/attendance/backups
    fi
    say '선택한 범위를 삭제했습니다. 소스코드와 Docker 자체는 보존합니다.'
}
run_choice() {
    case "$1" in
        1) check_environment;;
        2) install_infra;;
        3) setup;;
        4) start_live;;
        5) need_config;dc stop nginx live test db;;
        6) need_config;dc restart;;
        7) update_service;;
        8) need_config;dc ps;df -h "$DATA";read -r -p '최근 로그도 표시할까요? [y/N]: ' answer;if [[ $answer == y ]];then dc logs --tail 100;fi;;
        9) backup;;
        10) restore_backup;;
        11) account_menu;;
        12) delete_service;;
        13) start_test;;
        14) need_config;dc stop test;;
        15) need_config;confirm '테스트 DB·서명을 초기화하고 가상 명단을 생성합니다.' RESET && dc run --rm test python manage.py reset_sandbox --confirm RESET;;
        16) need_config;dc run --rm --no-deps test python scripts/load_test.py --origin "$(cfg PUBLIC_ORIGIN)";;
        17) change_network;;
        *) say '메뉴 번호를 확인해주세요.';;
    esac
}
if [[ ${BASH_SOURCE[0]} != "$0" ]]; then return 0;fi
if [[ ${1:-} == --check-syntax ]]; then exit 0;fi
[[ $(uname -s) == Linux ]] || { say '이 스크립트는 Ubuntu VM에서 실행해주세요.';exit 1; }
while true; do
    cat <<'MENU'

┌ 출석 서비스 · Ubuntu VM 관리 ──────────────────────┐
  1 환경 점검          2 필수 인프라 설치
  3 최초 설정          4 운영 서비스 실행
  5 전체 서비스 정지   6 재시작
  7 GitHub 업데이트    8 상태 / 로그
  9 백업 생성         10 백업 복구
 11 관리자 계정       12 서비스 삭제
 13 테스트 환경 실행  14 테스트 환경 정지
 15 테스트 초기화     16 테스트 HTTP 부하 점검
  17 접속 주소 / VM 포트 변경
  0 종료
└───────────────────────────────────────────────────┘
MENU
    read -r -p '선택: ' choice || break
    [[ $choice == 0 ]] && break
    # A child shell keeps errexit active even though the parent handles failure.
    set +e
    (set -Eeuo pipefail;run_choice "$choice")
    result=$?
    set -e
    if (( result != 0 ));then say '작업을 완료하지 못했습니다. 위 오류를 확인하세요. 기존 데이터는 자동 삭제하지 않으며, 업데이트·복구 실패 시 서비스가 정지 상태일 수 있습니다.';fi
done
