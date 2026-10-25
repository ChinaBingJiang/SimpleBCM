#!/usr/bin/env python3
#
#  build.py
#  SimpleBCM
#
#  Created by laobamac on 2026/9/23.
#  Copyright © 2026 laobamac. All rights reserved.
#

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def build_dependency():
    binary = ROOT / "build/Lilu/Release/Lilu.kext/Contents/MacOS/Lilu"
    record = ROOT / "build/Lilu-build.json"
    if binary.is_file() and record.is_file():
        saved = json.loads(record.read_text())
        if saved.get("revision") == "dc01cb583295ceded4f42a6310a15e3abac1c025" and saved["sha256"] == hashlib.sha256(binary.read_bytes()).hexdigest():
            return
    command = ["xcodebuild", "-project", str(ROOT / ".research/Lilu/Lilu.xcodeproj"), "-target", "Lilu", "-configuration", "Release",
               f"SYMROOT={ROOT}/build/Lilu", f"OBJROOT={ROOT}/build/LiluIntermediates", "ARCHS=x86_64", "ONLY_ACTIVE_ARCH=YES",
               "MACOSX_DEPLOYMENT_TARGET=10.13", "CODE_SIGNING_ALLOWED=NO",
               f"KERNEL_EXTENSION_HEADER_SEARCH_PATHS={ROOT}/.research/MacKernelSDK/Headers",
               f"KERNEL_FRAMEWORK_HEADERS={ROOT}/.research/MacKernelSDK/Headers",
               f"LIBRARY_SEARCH_PATHS={ROOT}/.research/MacKernelSDK/Library/universal", "build"]
    with (ROOT / "build/build-Lilu.log").open("w") as output:
        subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)
    record.write_text(json.dumps({"copyright": "Copyright © 2026 laobamac. All rights reserved.", "repository": "https://github.com/acidanthera/Lilu",
                                 "revision": "dc01cb583295ceded4f42a6310a15e3abac1c025", "version": "1.7.1", "locallyBuilt": True,
                                 "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(), "buildCommand": command}, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration", choices=["Debug", "Release"], default="Release")
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / "Tools/bootstrap.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "Tools/profiles.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "Tools/audit_codecs.py")], check=True)
    folder = ROOT / "build"
    folder.mkdir(exist_ok=True)
    build_dependency()
    action = "analyze" if args.analyze else "build"
    log = folder / f"{action}-{args.configuration}.log"
    command = ["xcodebuild", "-project", str(ROOT / "SimpleBCM.xcodeproj"), "-scheme", "SimpleBCM",
               "-configuration", args.configuration, "-destination", "generic/platform=macOS",
               "-derivedDataPath", str(folder / "DerivedData"), action]
    with log.open("w") as output:
        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
    for line in log.read_text().splitlines():
        if any(token in line for token in ["warning:", "error:", "** BUILD", "** ANALYZE"]):
            print(line)
    if result.returncode:
        print(f"构建日志：{log}", file=sys.stderr)
        raise SystemExit(result.returncode)
    if action == "build":
        subprocess.run([sys.executable, str(ROOT / "Tools/verify.py"), "--configuration", args.configuration], check=True)
    else:
        from verify import source_fingerprint
        (folder / f"Analysis-{args.configuration}.json").write_text(json.dumps({
            "sourceFingerprint": source_fingerprint()[0], "passed": True,
            "logSHA256": hashlib.sha256(log.read_bytes()).hexdigest(),
        }, indent=2) + "\n")


if __name__ == "__main__":
    main()
