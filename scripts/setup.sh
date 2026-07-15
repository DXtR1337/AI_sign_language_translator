# Install Python dependencies.
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPOSITORY_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"

python -m pip install pip --upgrade
cd "$REPOSITORY_ROOT"
python -m pip install -r "src/requirements.txt"
