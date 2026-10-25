#!/usr/bin/env python3
#
#  verify_configuration.py
#  SimpleBCM
#
#  Created by laobamac on 2026/9/8.
#  Copyright © 2026 laobamac. All rights reserved.
#

import copy
import hashlib
import json
import plistlib
import tempfile
from pathlib import Path

from configure import APPLE_NVRAM, FIXUP, INJECTOR, drivers, fragment, merge
from preflight import check_configuration, enabled


def verify():
    checks = 0
    with tempfile.TemporaryDirectory(prefix="SimpleBCM-Config-") as temporary:
        oc = Path(temporary)
        for bundle, identifier, executable, _ in drivers(True):
            folder = oc / "Kexts" / bundle / "Contents"
            folder.mkdir(parents=True, exist_ok=True)
            if executable:
                (folder / "MacOS").mkdir(exist_ok=True)
                (folder / "MacOS" / executable).write_bytes(b"configuration fixture")
            (folder / "Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": identifier,
                "CFBundleVersion": "1.7.1" if bundle == "Lilu.kext" else "1.0.0"}))

        def issues(config, running=(25, 6, 0), manifest=None):
            (oc / "config.plist").write_bytes(plistlib.dumps(config))
            return check_configuration(oc, running, manifest)[0]

        def active(config, running=(25, 6, 0)):
            return [entry["BundlePath"] for entry in config["Kernel"]["Add"] if enabled(entry, running)]

        for optional in [False, True]:
            config = fragment(optional)
            assert active(config) == [entry[0] for entry in drivers(optional)]
            assert "NVRAM" not in config
            for running in [(25, 0, 0), (25, 1, 0), (25, 6, 0), (25, 99, 99)]:
                assert not issues(config, running), issues(config, running)
                checks += 1
            for running in [(24, 99, 99), (26, 0, 0)]:
                assert not active(config, running)
                assert issues(config, running)
                checks += 1

        old_fragment = fragment()
        for entry in old_fragment["Kernel"]["Add"]:
            entry.update(MinKernel="25.6.0", MaxKernel="25.6.0")
        upgraded = merge(old_fragment)
        for running in [(25, 0, 0), (25, 6, 0), (25, 99, 99)]:
            assert not issues(upgraded, running), issues(upgraded, running)
            checks += 1

        # Migrate the two-entry package and preserve the user's NVRAM exactly.
        original = fragment()
        original["Kernel"]["Add"] = original["Kernel"]["Add"][:2]
        original["Misc"] = {"Boot": {"PickerMode": "External"}}
        original["NVRAM"] = {"Add": {APPLE_NVRAM: {"boot-args": b"-v keepsyms=0 alcid=1\0"}}}
        before = copy.deepcopy(original)
        migrated = merge(original)
        assert original == before
        assert migrated["Misc"] == original["Misc"]
        assert migrated["NVRAM"] == original["NVRAM"]
        assert not issues(migrated), issues(migrated)
        assert active(migrated) == [entry[0] for entry in drivers()]
        assert merge(migrated) == migrated
        checks += 1

        # Replace duplicate Tahoe entries while preserving older/future OS ranges.
        original = fragment(True)
        for entry in original["Kernel"]["Add"][2:]:
            entry.update(MinKernel="", MaxKernel="")
        old_plugin = dict(original["Kernel"]["Add"][-1],
            BundlePath="IO80211FamilyLegacy.kext/Contents/PlugIns/AirPortBrcmNIC.kext")
        original["Kernel"]["Add"] += [old_plugin, copy.deepcopy(original["Kernel"]["Add"][3])]
        migrated = merge(original)
        for running in [(25, 0, 0), (25, 6, 0), (25, 99, 99)]:
            assert not issues(migrated, running), issues(migrated, running)
            assert active(migrated, running) == [entry[0] for entry in drivers(True)]
            checks += 1
        assert merge(migrated) == migrated
        assert old_plugin["BundlePath"] in active(migrated, (24, 6, 0))
        assert old_plugin["BundlePath"] in active(migrated, (26, 0, 0))
        checks += 1

        legacy_only = fragment()
        legacy_only["Kernel"]["Add"].append(dict(fragment(True)["Kernel"]["Add"][2], MinKernel="", MaxKernel="24.99.99"))
        migrated = merge(legacy_only)
        assert FIXUP[0] not in active(migrated)
        assert merge(migrated) == migrated
        checks += 1

        for mutation in ["duplicate-lilu", "old-lilu", "no-block", "missing-skywalk", "duplicate-skywalk",
                         "old-airport", "bad-path", "lilu-order", "missing-injector", "orphan-injector"]:
            config = fragment(mutation == "missing-injector")
            if mutation == "duplicate-lilu":
                config["Kernel"]["Add"].append(copy.deepcopy(config["Kernel"]["Add"][0]))
            elif mutation == "old-lilu":
                path = oc / "Kexts/Lilu.kext/Contents/Info.plist"
                saved = path.read_bytes()
                info = plistlib.loads(saved)
                info["CFBundleVersion"] = "1.7.0"
                path.write_bytes(plistlib.dumps(info))
            elif mutation == "no-block":
                config["Kernel"]["Block"] = []
            elif mutation == "missing-skywalk":
                config["Kernel"]["Add"].pop(2)
            elif mutation == "duplicate-skywalk":
                config["Kernel"]["Add"].append(copy.deepcopy(config["Kernel"]["Add"][2]))
            elif mutation == "old-airport":
                config["Kernel"]["Add"].append(old_plugin)
            elif mutation == "bad-path":
                config["Kernel"]["Add"][1]["ExecutablePath"] = "Contents/MacOS/Other"
            elif mutation == "lilu-order":
                config["Kernel"]["Add"].reverse()
            elif mutation == "missing-injector":
                config["Kernel"]["Add"].pop()
            elif mutation == "orphan-injector":
                config["Kernel"]["Add"].append(fragment(True)["Kernel"]["Add"][-1])
            assert issues(config), mutation
            if mutation == "old-lilu":
                path.write_bytes(saved)
            checks += 1

        manifest = {"files": {}}
        for path in (oc / "Kexts").rglob("*"):
            if path.is_file():
                rel = path.relative_to(oc / "Kexts").as_posix()
                prefix = "Extra/Optional/" if rel.startswith("AirportBrcmFixup.kext/") else "EFI/OC/Kexts/"
                manifest["files"][prefix + rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path = oc / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        assert not issues(fragment(True), manifest=manifest_path)
        path = oc / "Kexts/IOSkywalkFamily.kext/Contents/MacOS/IOSkywalkFamily"
        saved = path.read_bytes()
        path.write_bytes(b"changed")
        assert any("SHA-256" in issue for issue in issues(fragment(), manifest=manifest_path))
        path.write_bytes(saved)
        checks += 2

        config = fragment()
        config["Kernel"]["Add"][0]["BundlePath"] = "Shared/Lilu.kext"
        shared = oc / "Kexts/Shared"
        shared.mkdir()
        (oc / "Kexts/Lilu.kext").rename(shared / "Lilu.kext")
        assert not issues(merge(config))
        checks += 1

        for broken in [[], [fragment()["Kernel"]["Add"][0]] * 2]:
            try:
                merge({"Kernel": {"Add": broken}})
            except ValueError:
                checks += 1
            else:
                raise AssertionError("Invalid Lilu input accepted")
    return {"checks": checks, "kernelRange": "25.0.0–25.99.99", "driverLoading": "external",
            "optionalAirportBrcmFixup": True, "migrationIdempotent": True, "bootArgumentsPreserved": True}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2, ensure_ascii=False))
