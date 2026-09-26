"""Build LinkedIn Studio.app using the Mac's existing Apple developer tools."""
import argparse
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = 'com.almond.linkedin-studio'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path.home() / 'Applications/LinkedIn Studio.app')
    parser.add_argument('--skip-service', action='store_true', help='Build only; do not update the installed review service')
    args = parser.parse_args()
    destination = args.output.expanduser().resolve()
    if destination.exists():
        info = destination / 'Contents/Info.plist'
        if not info.exists() or plistlib.loads(info.read_bytes()).get('CFBundleIdentifier') != BUNDLE_ID:
            raise SystemExit(f'Refusing to replace an unrelated application: {destination}')
    with tempfile.TemporaryDirectory(prefix='linkedin-studio-build-') as temp:
        build = Path(temp)
        app = build / 'LinkedIn Studio.app'
        executable = app / 'Contents/MacOS/LinkedInStudio'
        resources = app / 'Contents/Resources'
        executable.parent.mkdir(parents=True)
        resources.mkdir(parents=True)
        cache = Path(tempfile.gettempdir()) / 'linkedin-studio-swift-cache'
        subprocess.run(['xcrun', 'swiftc', '-O', '-module-cache-path', str(cache),
                        str(ROOT / 'macos/LinkedInStudio.swift'), '-o', str(executable)], check=True)
        icon_tool = build / 'make-icon'
        subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(cache),
                        str(ROOT / 'macos/GenerateIcon.swift'), '-o', str(icon_tool)], check=True)
        iconset = build / 'Studio.iconset'
        subprocess.run([str(icon_tool), str(iconset)], check=True)
        subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(resources / 'Studio.icns')], check=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
            'CFBundleIdentifier': BUNDLE_ID,
            'CFBundleName': 'LinkedIn Studio', 'CFBundleDisplayName': 'LinkedIn Studio',
            'CFBundleExecutable': 'LinkedInStudio', 'CFBundlePackageType': 'APPL',
            'CFBundleShortVersionString': '1.0', 'CFBundleVersion': '1',
            'CFBundleIconFile': 'Studio.icns', 'LSMinimumSystemVersion': '13.0',
            'NSHighResolutionCapable': True,
            'NSHumanReadableCopyright': 'Almond · Personal LinkedIn review desk',
            'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        }))
        subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        if not args.skip_service:
            subprocess.run([sys.executable, str(ROOT / 'scripts/install_review_service.py')], check=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(app, destination, dirs_exist_ok=True)
    print(f'Installed: {destination}')
    print('Open LinkedIn Studio from Applications or Spotlight. Keep its icon in the Dock for quick access.')


if __name__ == '__main__':
    main()
