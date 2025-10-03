#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Prépare les modèles locaux requis par Watcher.

Usage: scripts/setup-local-models.sh [options]

Options:
  --model-dir DIR        Répertoire de destination pour le modèle GGUF (défaut: models/llm)
  --embeddings-dir DIR   Répertoire de destination pour le modèle d'embedding (défaut: models/embeddings)
  --force                Réinstalle les fichiers même s'ils existent déjà
  -h, --help             Affiche cette aide et quitte
USAGE
}

MODEL_DIR="models/llm"
EMB_DIR="models/embeddings"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-dir)
      MODEL_DIR="$2"
      shift 2
      ;;
    --embeddings-dir)
      EMB_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Option inconnue: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

LLM_REPO="TheBloke/SmolLM-135M-Instruct-GGUF"
LLM_FILE="smollm-135m-instruct.Q4_0.gguf"
LLM_TARGET="${MODEL_DIR}/${LLM_FILE}"

EMBED_MODEL="sentence-transformers/all-MiniLM-L6-v2"
EMBED_TARGET="${EMB_DIR}/all-MiniLM-L6-v2"

mkdir -p "${MODEL_DIR}" "${EMB_DIR}"

if [[ ${FORCE} -ne 0 || ! -f "${LLM_TARGET}" ]]; then
  echo "Téléchargement du modèle llama.cpp (${LLM_FILE})..."
  python - <<'PY'
from pathlib import Path
from huggingface_hub import hf_hub_download

repo = "TheBloke/SmolLM-135M-Instruct-GGUF"
filename = "smollm-135m-instruct.Q4_0.gguf"
target = Path("${LLM_TARGET}")
path = hf_hub_download(repo_id=repo, filename=filename, local_dir=target.parent, local_dir_use_symlinks=False)
target.parent.mkdir(parents=True, exist_ok=True)
downloaded = Path(path)
if downloaded.resolve() != target.resolve():
    if target.exists():
        target.unlink()
    downloaded.rename(target)
PY
  python - <<'PY'
from hashlib import sha256
from pathlib import Path

target = Path("${LLM_TARGET}")
digest = sha256(target.read_bytes()).hexdigest()
sha_file = target.with_suffix(target.suffix + ".sha256")
sha_file.write_text(f"{digest}  {target.name}\n", encoding="utf-8")
print(f"SHA256({target.name})={digest}")
PY
else
  echo "Modèle llama.cpp déjà présent (${LLM_TARGET})."
fi

if [[ ${FORCE} -ne 0 || ! -d "${EMBED_TARGET}" ]]; then
  echo "Téléchargement du modèle d'embedding (${EMBED_MODEL})..."
  python - <<'PY'
from pathlib import Path
import shutil
from sentence_transformers import SentenceTransformer

model_id = "sentence-transformers/all-MiniLM-L6-v2"
target = Path("${EMBED_TARGET}")
model = SentenceTransformer(model_id, cache_folder=target.parent, trust_remote_code=False)
if target.exists():
    shutil.rmtree(target)
model.save(str(target))
PY
else
  echo "Modèle d'embedding déjà présent (${EMBED_TARGET})."
fi

echo "Modèles locaux prêts."
