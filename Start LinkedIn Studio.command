#!/bin/zsh
cd "${0:A:h}"
export PYTHONPATH=".vendor:src${PYTHONPATH:+:$PYTHONPATH}"
open 'http://127.0.0.1:8765'
exec python3 -m linkedin_ai_agent.review_server
