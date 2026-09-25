"""Expose actual posting status independently of the workflow's process status."""
import json
from pathlib import Path

for filename, title in [("agent_result.json", "LinkedIn agent outcome"), ("token_status.json", "Token status")]:
    path = Path(filename)
    print(f"### {title}\n")
    if not path.exists():
        print("No result was produced. Inspect the failed step.\n")
        continue
    try:
        payload = json.loads(path.read_text())
        print("```json\n" + json.dumps(payload, indent=2) + "\n```\n")
    except ValueError:
        print("The result could not be parsed. Inspect the run logs.\n")
