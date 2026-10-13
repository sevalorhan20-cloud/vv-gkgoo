#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Sunucuyla ayni .env degerlerini kullan; disaridan verilen degerleri koru.
EXPLICIT_PORT="${KLIPFORGE_PORT+x}"
EXPLICIT_HOST="${KLIPFORGE_HOST+x}"
EXPLICIT_VENV="${KLIPFORGE_VENV_DIR+x}"
if [[ -f .env ]]; then
  ENV_PORT="$(set +u; source .env; printf '%s' "${KLIPFORGE_PORT:-3210}")"
  ENV_HOST="$(set +u; source .env; printf '%s' "${KLIPFORGE_HOST:-127.0.0.1}")"
  ENV_VENV="$(set +u; source .env; printf '%s' "${KLIPFORGE_VENV_DIR:-${SCRIPT_DIR}/.venv}")"
  [[ -n "${EXPLICIT_PORT}" ]] || export KLIPFORGE_PORT="${ENV_PORT}"
  [[ -n "${EXPLICIT_HOST}" ]] || export KLIPFORGE_HOST="${ENV_HOST}"
  [[ -n "${EXPLICIT_VENV}" ]] || export KLIPFORGE_VENV_DIR="${ENV_VENV}"
fi

VENV_DIR="${KLIPFORGE_VENV_DIR:-${SCRIPT_DIR}/.venv}"
VENV_PYTHON="${VENV_DIR}/bin/python"

NEEDS_SETUP=0
if [[ ! -x "${VENV_PYTHON}" ]]; then
  NEEDS_SETUP=1
elif ! "${VENV_PYTHON}" -c 'import fastapi, uvicorn' >/dev/null 2>&1; then
  NEEDS_SETUP=1
elif [[ ! -f frontend/dist/index.html ]]; then
  NEEDS_SETUP=1
fi

if (( NEEDS_SETUP == 1 )); then
  printf 'Ilk kurulum hazirlaniyor. Bu islem birkac dakika surebilir.\n'
  bash scripts/setup.sh
fi

if [[ ! -x "${VENV_PYTHON}" ]]; then
  printf 'Hata: Kurulumdan sonra Python sanal ortami bulunamadi: %s\n' "${VENV_DIR}" >&2
  exit 1
fi

PORT="${KLIPFORGE_PORT:-3210}"
HOST="${KLIPFORGE_HOST:-127.0.0.1}"

case "${HOST}" in
  0.0.0.0|127.0.0.1) BROWSER_HOST="127.0.0.1" ;;
  ::|::1) BROWSER_HOST="[::1]" ;;
  *) BROWSER_HOST="${HOST}" ;;
esac

APP_URL="http://${BROWSER_HOST}:${PORT}"
SERVER_PID=""

stop_server() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" 2>/dev/null; then
    kill -TERM "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
}

trap stop_server EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

printf 'KlipForge Local baslatiliyor...\n'
bash scripts/run.sh &
SERVER_PID=$!

READY=0
for ((ATTEMPT = 1; ATTEMPT <= 240; ATTEMPT += 1)); do
  if ! kill -0 "${SERVER_PID}" 2>/dev/null; then
    if wait "${SERVER_PID}"; then
      SERVER_STATUS=0
    else
      SERVER_STATUS=$?
    fi
    SERVER_PID=""
    printf 'Hata: Yerel sunucu baslatilamadi (cikis kodu: %s). Yukaridaki hata mesajini kontrol edin.\n' \
      "${SERVER_STATUS}" >&2
    exit "${SERVER_STATUS:-1}"
  fi

  if "${VENV_PYTHON}" - "${BROWSER_HOST#[}" "${PORT}" <<'PY' >/dev/null 2>&1
import http.client
import sys

host = sys.argv[1].rstrip("]")
port = int(sys.argv[2])
connection = http.client.HTTPConnection(host, port, timeout=0.4)
try:
    connection.request("GET", "/api/health")
    response = connection.getresponse()
    raise SystemExit(0 if 200 <= response.status < 500 else 1)
finally:
    connection.close()
PY
  then
    READY=1
    break
  fi

  sleep 0.25
done

if (( READY == 0 )); then
  printf 'Hata: Yerel sunucu 60 saniye icinde hazir olmadi. Yukaridaki kayitlari kontrol edin.\n' >&2
  exit 1
fi

printf '\nKlipForge Local hazir: %s\n' "${APP_URL}"
printf 'Bu terminali acik tutun. Kapatmak icin Ctrl+C kullanin.\n\n'

if command -v open >/dev/null 2>&1; then
  (open "${APP_URL}" >/dev/null 2>&1 || true) &
elif command -v xdg-open >/dev/null 2>&1; then
  (xdg-open "${APP_URL}" >/dev/null 2>&1 || true) &
elif command -v wslview >/dev/null 2>&1; then
  (wslview "${APP_URL}" >/dev/null 2>&1 || true) &
fi

if wait "${SERVER_PID}"; then
  SERVER_STATUS=0
else
  SERVER_STATUS=$?
fi
SERVER_PID=""
exit "${SERVER_STATUS}"
