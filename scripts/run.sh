#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if [[ -f .env ]]; then
  # Komut satırında verilmiş değişkenler .env değerlerinden daha önceliklidir.
  KLIPFORGE_OVERRIDE_NAMES=()
  KLIPFORGE_OVERRIDE_VALUES=()
  KLIPFORGE_OVERRIDE_COUNT=0
  for KLIPFORGE_ENV_NAME in \
    KLIPFORGE_VENV_DIR \
    KLIPFORGE_HOST \
    KLIPFORGE_PORT \
    KLIPFORGE_DATA_DIR \
    KLIPFORGE_MODELS_DIR \
    KLIPFORGE_WHISPER_MODEL \
    KLIPFORGE_WHISPER_LANGUAGE \
    KLIPFORGE_ALLOW_MODEL_DOWNLOAD \
    KLIPFORGE_OLLAMA_MODEL \
    KLIPFORGE_OLLAMA_URL \
    KLIPFORGE_WORKERS \
    KLIPFORGE_MAX_UPLOAD_BYTES \
    KLIPFORGE_MAX_VIDEO_SECONDS; do
    if declare -p "${KLIPFORGE_ENV_NAME}" >/dev/null 2>&1; then
      KLIPFORGE_OVERRIDE_NAMES[KLIPFORGE_OVERRIDE_COUNT]="${KLIPFORGE_ENV_NAME}"
      KLIPFORGE_OVERRIDE_VALUES[KLIPFORGE_OVERRIDE_COUNT]="${!KLIPFORGE_ENV_NAME}"
      ((KLIPFORGE_OVERRIDE_COUNT += 1))
    fi
  done

  set -a
  # shellcheck disable=SC1091
  source .env
  set +a

  for ((KLIPFORGE_INDEX = 0; KLIPFORGE_INDEX < KLIPFORGE_OVERRIDE_COUNT; KLIPFORGE_INDEX += 1)); do
    printf -v "${KLIPFORGE_OVERRIDE_NAMES[KLIPFORGE_INDEX]}" '%s' \
      "${KLIPFORGE_OVERRIDE_VALUES[KLIPFORGE_INDEX]}"
    export "${KLIPFORGE_OVERRIDE_NAMES[KLIPFORGE_INDEX]}"
  done
fi

VENV_DIR="${KLIPFORGE_VENV_DIR:-${ROOT_DIR}/.venv}"
HOST="${KLIPFORGE_HOST:-127.0.0.1}"
PORT="${KLIPFORGE_PORT:-3210}"
export KLIPFORGE_HOST="${HOST}"
export KLIPFORGE_PORT="${PORT}"
export KLIPFORGE_ALLOW_MODEL_DOWNLOAD="${KLIPFORGE_ALLOW_MODEL_DOWNLOAD:-0}"

if [[ ! "${PORT}" =~ ^[0-9]+$ ]] || (( PORT < 1 || PORT > 65535 )); then
  printf 'Hata: Geçersiz KLIPFORGE_PORT değeri: %s\n' "${PORT}" >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  printf 'Hata: Python sanal ortamı bulunamadı: %s\n' "${VENV_DIR}" >&2
  printf 'Önce ./scripts/setup.sh çalıştırın.\n' >&2
  exit 1
fi

for binary in ffmpeg ffprobe; do
  if ! command -v "${binary}" >/dev/null 2>&1; then
    printf 'Hata: %s PATH üzerinde bulunamadı.\n' "${binary}" >&2
    exit 1
  fi
done

if [[ ! -f frontend/dist/index.html ]]; then
  if [[ -d frontend/node_modules ]]; then
    printf 'Frontend çıktısı bulunamadı; mevcut bağımlılıklarla derleniyor...\n'
    npm --prefix frontend run build
  else
    printf 'Hata: frontend/dist ve frontend/node_modules bulunamadı.\n' >&2
    printf 'Önce ./scripts/setup.sh çalıştırın.\n' >&2
    exit 1
  fi
fi

case "${KLIPFORGE_ALLOW_MODEL_DOWNLOAD}" in
  1|[Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Oo][Nn])
    printf 'Uyarı: Bu çalıştırmada model indirme için ağ erişimine açık onay verilmiş durumda.\n' >&2
    ;;
esac

if [[ "${HOST}" != "127.0.0.1" && "${HOST}" != "localhost" && "${HOST}" != "::1" ]]; then
  printf 'Uyarı: Sunucu yerel makine dışına açılıyor (%s). Uygulamada kimlik doğrulama yoktur.\n' "${HOST}" >&2
fi

printf 'KlipForge Local başlatılıyor: http://%s:%s\n' "${HOST}" "${PORT}"
printf 'Bu terminal açık kaldığı sürece uygulama çalışır. Durdurmak için Ctrl+C kullanın.\n'
exec "${VENV_DIR}/bin/python" -m uvicorn app.main:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers 1

