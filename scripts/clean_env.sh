# 1. Clear bytecode
find . -type d -name '__pycache__' -exec rm -r {} +
find . -name '*.py[co]' -delete

# 2. Remove venv and lock
rm -rf .venv uv.lock

rm -f requirements.txt

# 3. (optional) Clean uv cache
uv cache clean

# 4. Re-sync
uv sync

# reload env
source .venv/bin/activate

uv export --format requirements-txt > requirements.txt

# rebuild erquirements
uv pip install -r requirements.txt
