"""Validate deployment endpoints and update only network keys in runtime.env."""
import argparse
import ipaddress
from pathlib import Path
import re
from urllib.parse import urlsplit


def port_number(value):
    if not re.fullmatch(r'[0-9]{1,5}', value) or not 1 <= int(value) <= 65535:
        raise ValueError('포트는 1~65535 사이의 숫자로 입력하세요.')
    return str(int(value))


def network_values(origin, port):
    origin = origin.strip()
    if not origin or re.search(r'[\s\\]', origin):
        raise ValueError('외부 HTTPS 주소 전체를 입력하세요. 예: https://attendance.example.edu:8443')
    try:
        url = urlsplit(origin)
        host = url.hostname
        external_port = url.port
    except ValueError as exc:
        raise ValueError('주소 또는 포트 형식이 올바르지 않습니다.') from exc
    if (url.scheme != 'https' or not host or url.username is not None
            or url.password is not None or url.path not in ('', '/')
            or '?' in origin or '#' in origin or url.netloc.endswith(':')):
        raise ValueError('경로·쿼리·계정 정보 없는 HTTPS 주소를 입력하세요.')
    if ':' in host:
        try:
            ipaddress.IPv6Address(host)
        except ValueError as exc:
            raise ValueError('IPv6 주소 형식이 올바르지 않습니다.') from exc
        host = '[' + host + ']'
    elif len(host) > 253 or any(
        not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
        for label in host.split('.')
    ):
        raise ValueError('올바른 도메인 또는 IP 주소를 입력하세요.')
    suffix = '' if external_port is None else ':' + port_number(str(external_port))
    return {
        'PUBLIC_ORIGIN': 'https://' + host + suffix,
        'ALLOWED_HOSTS': ','.join(dict.fromkeys([host, 'localhost', '127.0.0.1'])),
        'HTTP_PORT': port_number(port),
    }


def update_config(current, values):
    # Never source runtime.env; preserve credentials and unrelated settings verbatim.
    lines = [line for line in current.splitlines()
             if line.partition('=')[0].strip() not in values]
    lines.extend(f'{key}={value}' for key, value in values.items())
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin')
    parser.add_argument('port')
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    try:
        values = network_values(args.origin, args.port)
    except ValueError as exc:
        parser.error(str(exc))
    current = args.env_file.read_text(encoding='utf-8') if args.env_file else ''
    print(update_config(current, values), end='')


if __name__ == '__main__':
    main()
