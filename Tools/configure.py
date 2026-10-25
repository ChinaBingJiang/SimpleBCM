#!/usr/bin/env python3
#
#  configure.py
#  SimpleBCM
#
#  Created by laobamac on 2026/9/9.
#  Copyright © 2026 laobamac. All rights reserved.
#

import argparse
import copy
import plistlib
from pathlib import Path


MINIMUM = "25.0.0"
MAXIMUM = "25.99.99"
BUNDLE = "cn.laobamac.SimpleBCM"
APPLE_NVRAM = "7C436110-AB2A-4BBB-A880-FE41995C9F82"
DRIVERS = [
    ("Lilu.kext", "as.vit9696.Lilu", "Lilu", "Lilu 1.7.1 or newer; keep one enabled copy"),
    ("SimpleBCM.kext", BUNDLE, "SimpleBCM", "Tahoe wireless control and event bridge"),
    ("IOSkywalkFamily.kext", "com.apple.iokit.IOSkywalkFamily", "IOSkywalkFamily", "OCLP IOSkywalk payload"),
    ("IO80211FamilyLegacy.kext", "com.apple.iokit.IO80211FamilyLegacy", "IO80211FamilyLegacy", "Legacy wireless backend"),
    ("AirPortBrcmNIC-Tahoe.kext", "com.apple.driver.AirPort.BrcmNIC", "AirPortBrcmNIC", "Tahoe Broadcom backend"),
]
FIXUP = ("AirportBrcmFixup.kext", "as.lvs1974.AirportBrcmFixup", "AirportBrcmFixup", "Optional: older Broadcom cards such as BCM943224")
INJECTOR = ("AirportBrcmFixup.kext/Contents/PlugIns/AirPortBrcmNIC_Injector.kext", "as.lvs1974.AirportBrcmNICInjector", "", "Optional: NIC matching for older cards")
CONFLICTING_DRIVERS = {"AirPortBrcmNIC.kext", "AirPortBrcm4360_Injector.kext"}
MANAGED_KEXT_NAMES = {Path(entry[0]).name for entry in DRIVERS[1:] + [FIXUP, INJECTOR]} | CONFLICTING_DRIVERS


def drivers(airportbrcmfixup=False):
    return DRIVERS[:2] + ([FIXUP] if airportbrcmfixup else []) + DRIVERS[2:] + ([INJECTOR] if airportbrcmfixup else [])


def fragment(airportbrcmfixup=False):
    entries = [dict(Arch="x86_64", BundlePath=path, Comment=comment, Enabled=True,
                    ExecutablePath=f"Contents/MacOS/{executable}" if executable else "", PlistPath="Contents/Info.plist",
                    MinKernel=MINIMUM, MaxKernel=MAXIMUM) for path, _, executable, comment in drivers(airportbrcmfixup)]
    block = dict(Arch="x86_64", Comment="Allow injected IOSkywalk", Enabled=True,
                 Identifier="com.apple.iokit.IOSkywalkFamily", MinKernel=MINIMUM, MaxKernel=MAXIMUM, Strategy="Exclude")
    return {"Kernel": {"Add": entries, "Block": [block]}}


def kernel_range(entry):
    minimum = tuple(int(n) for n in (entry.get("MinKernel") or "0.0.0").split('.'))
    maximum = tuple(int(n) for n in (entry.get("MaxKernel") or "999.0.0").split('.'))
    return minimum, maximum


def outside_tahoe(entry):
    minimum, maximum = kernel_range(entry)
    if maximum < (25, 0, 0) or minimum > (25, 99, 99):
        return [entry]
    result = []
    if minimum < (25, 0, 0):
        result.append(dict(entry, MaxKernel="24.99.99"))
    if maximum > (25, 99, 99):
        result.append(dict(entry, MinKernel="26.0.0"))
    return result


def merge(original, airportbrcmfixup=False):
    result = copy.deepcopy(original)
    kernel = result["Kernel"]
    existing = kernel["Add"]
    lilu = [entry for entry in existing if entry.get("Enabled") and Path(entry.get("BundlePath", "")).name == "Lilu.kext"]
    if len(lilu) != 1:
        raise ValueError("输入配置必须已有唯一启用的 Lilu.kext；需要版本 1.7.1 或更新。")
    # Older SimpleBCM fragments also pinned Lilu itself to one Tahoe release.
    # Extend that range without narrowing any existing support for other systems.
    for key, bound, compare in [("MinKernel", MINIMUM, lambda a, b: a > b),
                                ("MaxKernel", MAXIMUM, lambda a, b: a < b)]:
        current = lilu[0].get(key, "")
        if current and compare(tuple(int(n) for n in current.split('.')), tuple(int(n) for n in bound.split('.'))):
            lilu[0][key] = bound
    airportbrcmfixup = airportbrcmfixup or any(entry.get("Enabled") and Path(entry.get("BundlePath", "")).name
                                              in ("AirportBrcmFixup.kext", "AirPortBrcmNIC_Injector.kext") and
                                              kernel_range(entry)[0] <= (25, 99, 99) and
                                              kernel_range(entry)[1] >= (25, 0, 0) for entry in existing)
    replacement = fragment(airportbrcmfixup)["Kernel"]["Add"][1:]
    filtered = []
    for entry in existing:
        path = entry.get("BundlePath", "")
        if Path(path).name == "SimpleBCM.kext":
            continue
        if Path(path).name in MANAGED_KEXT_NAMES:
            filtered.extend(outside_tahoe(entry))
        else:
            filtered.append(entry)
    insert = next(i for i, entry in enumerate(filtered) if entry is lilu[0]) + 1
    filtered[insert:insert] = replacement
    kernel["Add"] = filtered
    blocks = []
    for entry in kernel.get("Block", []):
        if entry.get("Identifier") == "com.apple.iokit.IOSkywalkFamily":
            blocks.extend(outside_tahoe(entry))
        else:
            blocks.append(entry)
    kernel["Block"] = blocks + fragment()["Kernel"]["Block"]
    return result


def save(path, value):
    data = plistlib.dumps(value, sort_keys=False)
    header = b'<!--\n  config.fragment.plist\n  SimpleBCM\n\n  Created by laobamac on 2026/9/14.\n  Copyright (c) 2026 laobamac. All rights reserved.\n-->\n'
    data = data.replace(b'<?xml version="1.0" encoding="UTF-8"?>\n', b'<?xml version="1.0" encoding="UTF-8"?>\n' + header, 1)
    path.write_bytes(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--airportbrcmfixup", action="store_true", help="为 BCM943224 等旧网卡添加可选 AirportBrcmFixup")
    args = parser.parse_args()
    if args.input and args.input.resolve() == args.output.resolve():
        raise ValueError("输出必须是单独的配置副本，不能覆盖输入。")
    value = merge(plistlib.loads(args.input.read_bytes()), args.airportbrcmfixup) if args.input else fragment(args.airportbrcmfixup)
    if args.output.exists():
        raise FileExistsError(args.output)
    save(args.output, value)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
