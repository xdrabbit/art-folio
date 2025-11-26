#!/usr/bin/env bash
set -euo pipefail
# Easy local runner for development
if [ ! -d venv ]; then
  python3 -m venv venv
fi
. venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=app.py
export FLASK_ENV=development

python app.py
