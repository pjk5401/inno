#!/usr/bin/env bash
# Exercise menu helpers with isolated configuration and mocked Docker/socket probes.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/../manage.sh"
SUDO=()
python3() { command "${TEST_PYTHON:-python3}" "$@"; }
TEST_DIR=$(mktemp -d)
trap 'rm -f -- "$TEST_DIR/runtime.env" "$TEST_DIR/output"; rmdir -- "$TEST_DIR"' EXIT
ENV_FILE="$TEST_DIR/runtime.env"
printf 'PUBLIC_ORIGIN=https://old.example.edu\n' > "$ENV_FILE"
[[ $(http_port) == 80 ]]
printf 'HTTP_PORT=8080\n' >> "$ENV_FILE"
[[ $(http_port) == 8080 ]]

origin= port= network_config=
read_network_config <<< $'https://new.example.edu:8443\n08080' > "$TEST_DIR/output"
[[ $port == 8080 && $network_config == *'ALLOWED_HOSTS=new.example.edu,localhost,127.0.0.1'* ]]
read_network_config 'https://current.example.edu' 9000 <<< $'\n' > "$TEST_DIR/output"
[[ $origin == https://current.example.edu && $port == 9000 ]]
if read_network_config <<< $'\n80' > "$TEST_DIR/output" 2>&1; then
    printf 'Empty initial address was accepted\n'; exit 1
fi

dc() { :; }
ss() {
    [[ $* == '-ltn ( sport = :8080 )' ]]
    printf 'State Recv-Q Send-Q Local Address:Port Peer Address:Port\n'
    if [[ ${BUSY:-0} == 1 ]]; then printf 'LISTEN 0 128 0.0.0.0:8080 0.0.0.0:*\n'; fi
}
check_port
BUSY=1
if check_port > "$TEST_DIR/output"; then printf 'Occupied port was accepted\n'; exit 1; fi
grep -q '8080' "$TEST_DIR/output"
unset BUSY

build_and_migrate() { :; }
curl() {
    case "${*: -1}" in
        http://127.0.0.1:8080/health/|http://127.0.0.1:8080/test/health/) return 0;;
        *) printf 'Health check used the wrong port\n'; return 1;;
    esac
}
start_live > "$TEST_DIR/output"
start_test > "$TEST_DIR/output"
printf 'VM menu address, port, conflict and health-check tests passed\n'
