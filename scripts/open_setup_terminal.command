#!/bin/zsh
cd "${0:A:h}/.." || exit 1
clear
cat <<'EOF'
LinkedIn Agent Local Setup

Paste your secrets into the commands below, then press Enter.
Do not paste secrets into chat.

1) Set Gemini and LinkedIn app credentials:

export GEMINI_API_KEY="PASTE_NEW_GEMINI_KEY_HERE"
export LINKEDIN_CLIENT_ID="PASTE_LINKEDIN_CLIENT_ID_HERE"
export LINKEDIN_CLIENT_SECRET="PASTE_NEW_LINKEDIN_CLIENT_SECRET_HERE"

2) Start LinkedIn OAuth:

PYTHONPATH=.vendor:src python3 -m linkedin_ai_agent.cli auth-local

3) After browser approval, store the printed access token without adding it to shell history:

read -r -s LINKEDIN_ACCESS_TOKEN
export LINKEDIN_ACCESS_TOKEN

4) Get your personal LinkedIn owner URN:

PYTHONPATH=.vendor:src python3 -m linkedin_ai_agent.cli whoami

5) After config/agent.yaml has owner_urn, run:

PYTHONPATH=.vendor:src python3 -m linkedin_ai_agent.cli run --dry-run

EOF
exec /bin/zsh -l
