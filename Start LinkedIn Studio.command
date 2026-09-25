#!/bin/zsh
cd "${0:A:h}"
if ! curl -fsS --max-time 2 'http://127.0.0.1:8765/' >/dev/null; then
  python3 scripts/install_review_service.py || exit 1
fi
open 'http://127.0.0.1:8765'
