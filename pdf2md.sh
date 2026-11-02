#!/usr/bin/env bash
# pdf2md - convert PDF documents to LLM-friendly Markdown using the published Docker image.
# Only Docker is needed on the host.
#
#   pdf2md.sh document.pdf [more.pdf ...] [-o DIR] [--no-images] [--pages 1-20] [--lang spa] ...
#
# Each document goes to <DIR>/<document name>/<document name>.md with its figures in images/.
# -o / --output-dir DIR defaults to the current directory.
#
#   pdf2md.sh --dedupe DIR [more DIR ...]
#
# removes byte-identical duplicate images from already converted folders and relinks them
# (new conversions do this automatically).
# Override the image with PDF2MD_IMAGE=... (e.g. a pinned version tag).
set -euo pipefail

IMAGE="${PDF2MD_IMAGE:-ghcr.io/jorgetutor/pdf2md:latest}"
OUT_DIR="$PWD"

usage() {
  echo "usage: $(basename "$0") file.pdf [more.pdf ...] [-o DIR] [options]" >&2
  echo "       $(basename "$0") --dedupe DIR [more DIR ...]   (dedupe images of converted folders)" >&2
  echo "converter options:" >&2
  docker run --rm "$IMAGE" --help 2>/dev/null | sed -n '/^options:/,$p' | sed 1d >&2 || true
  exit 1
}

command -v docker >/dev/null || { echo "error: docker is required" >&2; exit 1; }

if [ "${1:-}" = "--dedupe" ]; then
  shift; [ $# -gt 0 ] || usage
  docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE" >&2
  status=0
  for dir in "$@"; do
    if [ ! -d "$dir/images" ]; then echo "error: no images/ folder in: $dir" >&2; status=1; continue; fi
    DIR="$(realpath "$dir")"
    docker run --rm -u "$(id -u):$(id -g)" -v "$DIR":/doc "$IMAGE" /doc --dedupe-only 2>&1 \
      | sed "s#^/doc:#$DIR:#" >&2 || status=1
  done
  exit "$status"
fi

PDFS=() ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage ;;
    -o|--output-dir) OUT_DIR="$2"; shift 2 ;;
    --pages|--lang) ARGS+=("$1" "$2"); shift 2 ;;
    -*) ARGS+=("$1"); shift ;;
    *) PDFS+=("$1"); shift ;;
  esac
done
[ "${#PDFS[@]}" -gt 0 ] || usage

OUT_DIR="$(realpath -m "$OUT_DIR")"
mkdir -p "$OUT_DIR"
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull "$IMAGE" >&2

status=0
for pdf in "${PDFS[@]}"; do
  PDF="$(realpath "$pdf")"
  if [ ! -f "$PDF" ]; then echo "error: no such file: $pdf" >&2; status=1; continue; fi
  set +o pipefail
  docker run --rm -u "$(id -u):$(id -g)" \
    -v "$(dirname "$PDF")":/in:ro -v "$OUT_DIR":/out \
    "$IMAGE" "/in/$(basename "$PDF")" --output-dir /out ${ARGS[@]+"${ARGS[@]}"} 2>&1 \
    | grep -v "^OCR on page\|^Using Tesseract\|^=== Document\|^Generating markdown\|^Parsing [0-9]* pages\|^Line cannot\|^Image too small" \
    | sed "s#/out/#$OUT_DIR/#" >&2
  rc="${PIPESTATUS[0]}"
  set -o pipefail
  [ "$rc" -eq 0 ] || status="$rc"
done
exit "$status"
