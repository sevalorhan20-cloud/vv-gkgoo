#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${KLIPFORGE_VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_AI="${KLIPFORGE_INSTALL_AI:-1}"
REBUILD_FRONTEND="${KLIPFORGE_REBUILD_FRONTEND:-0}"
DOWNLOAD_MODEL_REQUEST="${KLIPFORGE_SETUP_DOWNLOAD_MODEL:-ask}"
DOWNLOAD_MODEL=0
MODEL_SIZE="${KLIPFORGE_SETUP_MODEL_SIZE:-base}"

is_true() {
  case "${1}" in
    1|[Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Oo][Nn]) return 0 ;;
    *) return 1 ;;
  esac
}

is_false() {
  case "${1}" in
    0|[Ff][Aa][Ll][Ss][Ee]|[Nn][Oo]|[Oo][Ff][Ff]) return 0 ;;
    *) return 1 ;;
  esac
}

fail() {
  printf 'Hata: %s\n' "$*" >&2
  exit 1
}

validate_model_size() {
  case "${MODEL_SIZE}" in
    tiny|base|small|medium|large-v3) ;;
    *) fail "Geçersiz model: ${MODEL_SIZE}. tiny, base, small, medium veya large-v3 kullanın." ;;
  esac
}

model_approximate_size() {
  case "${MODEL_SIZE}" in
    tiny) printf '~80 MB' ;;
    base) printf '~150 MB' ;;
    small) printf '~500 MB' ;;
    medium) printf '~1.5 GB' ;;
    large-v3) printf '~3 GB' ;;
  esac
}

command -v "${PYTHON_BIN}" >/dev/null 2>&1 || fail "${PYTHON_BIN} bulunamadı. Python 3.11+ kurun."
command -v ffmpeg >/dev/null 2>&1 || fail "ffmpeg bulunamadı. Önce FFmpeg paketini kurun."
command -v ffprobe >/dev/null 2>&1 || fail "ffprobe bulunamadı. Önce FFmpeg paketini kurun."

PYTHON_VERSION="$("${PYTHON_BIN}" -c 'import platform; print(platform.python_version())')"
if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  fail "Python 3.11+ gerekli; bulunan sürüm: ${PYTHON_VERSION} (${PYTHON_BIN})"
fi

BUILD_FRONTEND=0
if is_true "${REBUILD_FRONTEND}" || [[ ! -f "${ROOT_DIR}/frontend/dist/index.html" ]]; then
  BUILD_FRONTEND=1
  command -v node >/dev/null 2>&1 || fail "Hazır frontend çıktısı bulunamadı; yeniden derlemek için Node.js ^20.19.0 veya >=22.12.0 kurun."
  command -v npm >/dev/null 2>&1 || fail "Hazır frontend çıktısı bulunamadı; Node.js ile npm kurun."
  NODE_VERSION="$(node -p 'process.versions.node')"
  if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major > 22 ? 0 : 1)'; then
    fail "Node.js ^20.19.0 veya >=22.12.0 gerekli; bulunan sürüm: ${NODE_VERSION}"
  fi
else
  printf 'Hazır frontend çıktısı bulundu; Node.js kurulumu gerekmiyor.\n'
fi

case "${DOWNLOAD_MODEL_REQUEST}" in
  ask|ASK|Ask)
    if [[ -t 0 && -t 1 ]]; then
      validate_model_size
      MODEL_APPROXIMATE_SIZE="$(model_approximate_size)"
      while true; do
        printf 'Yerel transkripsiyon için faster-whisper %s modeli (%s) indirilsin mi? [E/h]: ' \
          "${MODEL_SIZE}" "${MODEL_APPROXIMATE_SIZE}" >&2
        IFS= read -r MODEL_REPLY || MODEL_REPLY=""
        case "${MODEL_REPLY}" in
          ""|[Ee]|[Ee][Vv][Ee][Tt]|[Yy]|[Yy][Ee][Ss]) DOWNLOAD_MODEL=1; break ;;
          [Hh]|[Hh][Aa][Yy][Ii][Rr]|[Nn]|[Nn][Oo]) DOWNLOAD_MODEL=0; break ;;
          *) printf 'Lütfen evet için E/Enter, hayır için H yazın.\n' >&2 ;;
        esac
      done
    else
      printf 'Etkileşimsiz kurulum: Whisper modeli indirilmedi. Açık indirme için KLIPFORGE_SETUP_DOWNLOAD_MODEL=1 kullanın.\n'
    fi
    ;;
  *)
    if is_true "${DOWNLOAD_MODEL_REQUEST}"; then
      DOWNLOAD_MODEL=1
    elif is_false "${DOWNLOAD_MODEL_REQUEST}"; then
      DOWNLOAD_MODEL=0
    else
      fail "Geçersiz KLIPFORGE_SETUP_DOWNLOAD_MODEL değeri: ${DOWNLOAD_MODEL_REQUEST}. ask, 1 veya 0 kullanın."
    fi
    ;;
esac

cd "${ROOT_DIR}"

printf 'Python sanal ortamı hazırlanıyor: %s\n' "${VENV_DIR}"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

VENV_PYTHON="${VENV_DIR}/bin/python"
if ! "${VENV_PYTHON}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  VENV_PYTHON_VERSION="$("${VENV_PYTHON}" -c 'import platform; print(platform.python_version())')"
  fail "Mevcut sanal ortam Python 3.11+ kullanmıyor (${VENV_PYTHON_VERSION}). ${VENV_DIR} klasörünü kaldırıp kurulumu yeniden çalıştırın."
fi
"${VENV_PYTHON}" -m pip install --upgrade pip

if is_true "${INSTALL_AI}" || is_true "${DOWNLOAD_MODEL}"; then
  printf 'Temel ve AI Python bağımlılıkları kuruluyor...\n'
  if ! "${VENV_PYTHON}" -m pip install -r requirements-ai.txt; then
    printf 'Uyarı: AI bağımlılıkları kurulamadı; uygulama temel heuristik modda hazırlanıyor.\n' >&2
    "${VENV_PYTHON}" -m pip install -r requirements.txt
    DOWNLOAD_MODEL=0
  fi
else
  printf 'Temel Python bağımlılıkları kuruluyor...\n'
  "${VENV_PYTHON}" -m pip install -r requirements.txt
fi

if (( BUILD_FRONTEND == 1 )); then
  printf 'Frontend bağımlılıkları kuruluyor...\n'
  if [[ -f frontend/package-lock.json ]]; then
    npm --prefix frontend ci --no-audit --no-fund
  else
    npm --prefix frontend install --no-audit --no-fund
  fi

  printf 'Frontend production çıktısı oluşturuluyor...\n'
  npm --prefix frontend run build
else
  printf 'Paketle gelen hazır frontend çıktısı kullanılıyor.\n'
fi

mkdir -p data/projects models

if [[ ! -f .env ]]; then
  cp .env.example .env
  printf '.env, .env.example üzerinden oluşturuldu.\n'
else
  printf 'Mevcut .env korundu.\n'
fi

if is_true "${DOWNLOAD_MODEL}"; then
  validate_model_size

  MODEL_DIR="${ROOT_DIR}/models/faster-whisper-${MODEL_SIZE}"
  if [[ -f "${MODEL_DIR}/model.bin" ]]; then
    printf 'Whisper modeli zaten hazır: %s\n' "${MODEL_DIR}"
  else
    printf 'Açık kurulum onayıyla Whisper modeli indiriliyor: %s\n' "${MODEL_SIZE}"
    if "${VENV_PYTHON}" - "${MODEL_SIZE}" "${MODEL_DIR}" <<'PY'
from pathlib import Path
import sys

from huggingface_hub import snapshot_download

model_size = sys.argv[1]
target = Path(sys.argv[2]).resolve()
target.mkdir(parents=True, exist_ok=True)
snapshot_download(
    repo_id=f"Systran/faster-whisper-{model_size}",
    local_dir=str(target),
)
if not (target / "model.bin").is_file():
    raise SystemExit(f"Model indirildi ancak model.bin bulunamadı: {target}")
print(f"Model hazır: {target}")
PY
    then
      :
    else
      printf 'Uyarı: Whisper modeli indirilemedi. Kurulum tamamlanacak; uygulama model eklenene kadar heuristik modda çalışacak.\n' >&2
      printf 'Yeniden denemek için: KLIPFORGE_SETUP_DOWNLOAD_MODEL=1 KLIPFORGE_SETUP_MODEL_SIZE=%s ./scripts/setup.sh\n' "${MODEL_SIZE}" >&2
    fi
  fi
else
  printf 'Model indirilmedi. Yerel model eklemek için README.md dosyasına bakın.\n'
fi

printf '\nKurulum tamamlandı. Başlatmak için:\n  ./scripts/run.sh\n'
printf 'Arayüz: http://127.0.0.1:3210\n'

