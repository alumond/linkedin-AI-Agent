"""Entry point for macOS login launch, without shell environment dependencies."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / '.vendor'), str(root / 'src')]
from linkedin_ai_agent.review_server import serve

serve()
