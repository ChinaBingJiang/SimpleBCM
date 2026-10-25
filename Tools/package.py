#!/usr/bin/env python3
#
#  package.py
#  SimpleBCM
#
#  Created by laobamac on 2026/9/13.
#  Copyright © 2026 laobamac. All rights reserved.
#

import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from configure import FIXUP, INJECTOR, fragment, save
from bootstrap import validate_payloads
from verify import source_fingerprint
from macho import Image


ROOT = Path(__file__).resolve().parent.parent
VERSION = "1.0.0"
NAME = f"SimpleBCM-{VERSION}-Tahoe-x86_64"


def package_name(channel, sha=None):
    if channel == "rel":
        return NAME
    sha = sha or os.environ.get("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", sha):
        raise ValueError("Invalid commit SHA")
    return f"{NAME}-alpha-{sha[:7]}"


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "xcuserdata"))
    else:
        shutil.copy2(source, target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=["pre", "rel"], default="rel")
    args = parser.parse_args()
    package_label = package_name(args.channel)
    configured_version = re.search(r"^MODULE_VERSION\s*=\s*(\S+)", (ROOT / "Config/Kernel.xcconfig").read_text(), re.M).group(1)
    if configured_version != VERSION:
        raise RuntimeError("驱动版本与打包版本不一致。")
    validate_payloads()
    fingerprint, _ = source_fingerprint()
    lilu = ROOT / "build/Lilu/Release/Lilu.kext/Contents/MacOS/Lilu"
    lilu_digest = hashlib.sha256(lilu.read_bytes()).hexdigest()
    validation_mode = None
    for configuration in ["Debug", "Release"]:
        info = json.loads((ROOT / f"build/Validation-{configuration}.json").read_text())
        binary = ROOT / f"build/DerivedData/Build/Products/{configuration}/SimpleBCM.kext/Contents/MacOS/SimpleBCM"
        bundle_info = plistlib.loads((binary.parent.parent / "Info.plist").read_bytes())
        if bundle_info["CFBundleVersion"] != VERSION or bundle_info["CFBundleShortVersionString"] != VERSION:
            raise RuntimeError(f"{configuration} 的驱动版本与发行版本不一致。")
        if info["sourceFingerprint"] != fingerprint or info["sha256"] != hashlib.sha256(binary.read_bytes()).hexdigest():
            raise RuntimeError(f"{configuration} 尚未通过当前源码版本的验证。")
        if info["liluSHA256"] != lilu_digest:
            raise RuntimeError(f"Lilu 与 {configuration} 验证使用的二进制不一致。")
        if info["driverLoading"] != "external":
            raise RuntimeError(f"{configuration} 不是独立驱动构建。")
        if validation_mode and validation_mode != info["validationMode"]:
            raise RuntimeError("Debug 和 Release 的验证模式不一致。")
        validation_mode = info["validationMode"]
        symbols = ROOT / f"build/DerivedData/Build/Products/{configuration}/SimpleBCM.kext.dSYM/Contents/Resources/DWARF/SimpleBCM"
        if Image(symbols).uuid != info["uuid"]:
            raise RuntimeError(f"{configuration} 符号文件与已验证二进制不一致。")
    validation_environment = {"OSBuild": info["OSBuild"], "validationMode": validation_mode}
    analysis = ROOT / "build/analyze-Release.log"
    analysis_report = json.loads((ROOT / "build/Analysis-Release.json").read_text())
    if not analysis_report["passed"] or analysis_report["sourceFingerprint"] != fingerprint or \
            analysis_report["logSHA256"] != hashlib.sha256(analysis.read_bytes()).hexdigest():
        raise RuntimeError("Release 静态分析尚未覆盖当前源码。")
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".package-", dir=dist) as temporary:
        stage = Path(temporary) / package_label
        stage.mkdir()
        extra = stage / "Extra"
        kexts = stage / "EFI/OC/Kexts"
        copy(ROOT / "build/DerivedData/Build/Products/Release/SimpleBCM.kext", kexts / "SimpleBCM.kext")
        copy(ROOT / "build/Lilu/Release/Lilu.kext", kexts / "Lilu.kext")
        for name, relative in {
            "IOSkywalkFamily.kext": "IOSkywalkFamily-v1.2.0/IOSkywalkFamily.kext",
            "IO80211FamilyLegacy.kext": "IO80211FamilyLegacy-v1.0.0/IO80211FamilyLegacy.kext",
            "AirPortBrcmNIC-Tahoe.kext": "AirPortBrcmNIC-Tahoe-v1.0.0/AirPortBrcmNIC-Tahoe.kext",
        }.items():
            copy(ROOT / ".research/binaries" / relative, kexts / name)
        old_plugin = kexts / "IO80211FamilyLegacy.kext/Contents/PlugIns"
        if old_plugin.exists():
            shutil.rmtree(old_plugin)
        optional = extra / "Optional/AirportBrcmFixup.kext"
        copy(ROOT / ".research/binaries/AirportBrcmFixup-v2.2.1-RELEASE/AirportBrcmFixup.kext", optional)
        old_injector = optional / "Contents/PlugIns/AirPortBrcm4360_Injector.kext"
        if old_injector.exists():
            shutil.rmtree(old_injector)
        for configuration in ["Debug", "Release"]:
            copy(ROOT / f"build/DerivedData/Build/Products/{configuration}/SimpleBCM.kext", stage / configuration / "SimpleBCM.kext")
            copy(ROOT / f"build/DerivedData/Build/Products/{configuration}/SimpleBCM.kext.dSYM", extra / f"Symbols/{configuration}/SimpleBCM.kext.dSYM")
            copy(ROOT / f"build/Validation-{configuration}.json", extra / f"Validation-{configuration}.json")
            copy(ROOT / f"build/DependencySymbols-{configuration}.json", extra / f"DependencySymbols-{configuration}.json")
        copy(analysis, extra / "Analysis-Release.log")
        copy(ROOT / "build/Analysis-Release.json", extra / "Analysis-Release.json")
        copy(ROOT / "build/Lilu-build.json", extra / "Lilu-build.json")
        copy(ROOT / "build/DerivedData/Build/Products/Release/bcmprobe", extra / "bcmprobe")
        for name in ["README.md", "README.en.md", "NOTICE.md"]:
            copy(ROOT / name, extra / name)
        copy(ROOT / "Docs", extra / "Docs")
        for path in ["SimpleBCM", "SimpleBCM.xcodeproj", "Config", "Probe", "Tools", "README.md", "README.en.md", "NOTICE.md", "Docs", ".github", ".gitignore"]:
            copy(ROOT / path, extra / "Sources" / path)
        for name in ["configure.py", "preflight.py", "collect.py"]:
            copy(ROOT / "Tools" / name, extra / "Tools" / name)
        for name, path in {"Lilu-LICENSE.txt": ".research/Lilu/LICENSE.txt", "OCLP-LICENSE.txt": ".research/OpenCore-Legacy-Patcher/LICENSE.txt",
                           "MacKernelSDK-LICENSE.txt": ".research/MacKernelSDK/LICENSE.txt"}.items():
            source = ROOT / path
            if source.is_file():
                copy(source, extra / "Licenses" / name)
        save(stage / "config.fragment.plist", fragment())
        save(extra / "Optional/config.AirportBrcmFixup.fragment.plist", fragment(airportbrcmfixup=True))
        dependencies = []
        for entry in fragment()["Kernel"]["Add"]:
            bundle = kexts / entry["BundlePath"]
            info = plistlib.loads((bundle / entry["PlistPath"]).read_bytes())
            dependencies.append({"path": entry["BundlePath"], "identifier": info["CFBundleIdentifier"], "version": info["CFBundleVersion"]})
            if entry["ExecutablePath"] and not (bundle / entry["ExecutablePath"]).is_file():
                raise RuntimeError(f"缺少 {entry['ExecutablePath']}")
        optional_dependencies = []
        for bundle_path, identifier, _, _ in [FIXUP, INJECTOR]:
            info = plistlib.loads((extra / "Optional" / bundle_path / "Contents/Info.plist").read_bytes())
            optional_dependencies.append({"path": "Extra/Optional/" + bundle_path, "identifier": identifier, "version": info["CFBundleVersion"]})
        manifest = {"copyright": "Copyright © 2026 laobamac. All rights reserved.", "project": "SimpleBCM", "version": VERSION,
                    "system": "macOS Tahoe", "kernel": "25.x", "architecture": "x86_64", "hardwareValidation": "pending",
                    "validationEnvironment": validation_environment, "driverLoading": "external", "channel": args.channel,
                    "optionalBundles": optional_dependencies,
                    "sourceFingerprint": fingerprint, "bundles": dependencies, "files": {}}
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                manifest["files"][str(path.relative_to(stage))] = hashlib.sha256(path.read_bytes()).hexdigest()
        (extra / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        destination = dist / package_label
        if destination.exists():
            previous = destination / "Extra/manifest.json"
            if not previous.is_file():
                previous = destination / "manifest.json"
            if not previous.is_file() or json.loads(previous.read_text()).get("project") != "SimpleBCM":
                raise FileExistsError(destination)
            shutil.rmtree(destination)
        shutil.move(str(stage), destination)
    archive = dist / (package_label + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                output.write(path, str(Path(package_label) / path.relative_to(destination)))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / (archive.name + ".sha256")).write_text(f"{digest}  {archive.name}\n")
    print(f"{archive}\nSHA-256 {digest}")


if __name__ == "__main__":
    main()
