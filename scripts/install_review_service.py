"""Install the loopback review service into macOS Application Support."""
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = Path.home() / 'Library/Application Support/Almond LinkedIn Studio'
cache = target / '.review_cache'
cache.mkdir(parents=True, exist_ok=True)
for name in ('src', 'web', 'config', '.vendor'):
    source = root / name
    if source.exists():
        shutil.copytree(source, target / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
launcher = target / 'scripts/run_review.py'
launcher.parent.mkdir(exist_ok=True)
shutil.copy2(root / 'scripts/run_review.py', launcher)
gh_relative = Path('.tools/gh_2.94.0_macOS_arm64/bin/gh')
if (root / gh_relative).exists():
    (target / gh_relative).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / gh_relative, target / gh_relative)
label = 'com.almond.linkedin-review'
domain = f'gui/{os.getuid()}'
subprocess.run(['launchctl', 'bootout', f'{domain}/{label}'], capture_output=True)
plist_path = Path.home() / f'Library/LaunchAgents/{label}.plist'
plist_path.parent.mkdir(parents=True, exist_ok=True)
plist_path.write_bytes(plistlib.dumps({
    'Label': label, 'ProgramArguments': [sys.executable, str(launcher)],
    'WorkingDirectory': str(target),
    'EnvironmentVariables': {'PYTHONDONTWRITEBYTECODE': '1'},
    'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 30,
    'StandardOutPath': str(cache / 'service.log'),
    'StandardErrorPath': str(cache / 'service-error.log'),
}))
subprocess.run(['launchctl', 'bootstrap', domain, str(plist_path)], check=True)
print(f'Installed review service: {target}')
print('Open http://127.0.0.1:8765')
