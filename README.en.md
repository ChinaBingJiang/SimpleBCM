<!--
  README.en.md
  SimpleBCM

  Created by laobamac on 2026/9/17.
  Copyright © 2026 laobamac. All rights reserved.
-->
<div align="center">

# SimpleBCM

**Restore Broadcom Wi-Fi support on macOS Tahoe**

![Version](https://img.shields.io/badge/version-1.0.0-2563eb)
![macOS](https://img.shields.io/badge/macOS-Tahoe%2026-111827)
![Architecture](https://img.shields.io/badge/arch-x86__64-6b7280)
![OpenCore](https://img.shields.io/badge/boot-OpenCore-16a34a)

[简体中文](README.md) · **English**

OpenCore injection · Native wireless APIs · Auto-join · AirDrop

</div>

---

SimpleBCM is a Lilu plug-in that adapts the wireless control and event interfaces of companion Broadcom drivers to Tahoe. Each driver loads separately through OpenCore. It does not modify the system volume or replace system frameworks.

## Requirements

| Item | Requirement |
| :--- | :--- |
| System | All macOS Tahoe releases (Darwin 25.x) |
| Architecture | Intel x86_64 |
| Bootloader | OpenCore |
| Dependencies | Lilu ≥ 1.7.1 and the pinned companion drivers in the package |

## Installation

1. Extract the package and copy the drivers from `EFI/OC/Kexts` into an EFI copy you can roll back. Keep exactly one enabled Lilu version.
2. Merge `config.fragment.plist`. Load in this order: **Lilu → SimpleBCM → IOSkywalkFamily → IO80211FamilyLegacy → AirPortBrcmNIC-Tahoe**.
3. Add a `Kernel → Block → Exclude` entry for the system `com.apple.iokit.IOSkywalkFamily`. The configuration example includes this setting.
4. Run `Extra/Tools/preflight.py`, then validate the complete configuration with `ocvalidate` from your OpenCore version.
5. Boot from that EFI and connect using the system Wi-Fi interface.

Only some older cards, such as BCM943224, need AirportBrcmFixup and its NIC Injector. Copy `Extra/Optional/AirportBrcmFixup.kext` to `EFI/OC/Kexts`, then use `Extra/Optional/config.AirportBrcmFixup.fragment.plist` or append `--airportbrcmfixup` to the configuration command. The optional example loads AirportBrcmFixup after SimpleBCM and adds the `AirPortBrcmNIC_Injector` entry.

The old AirPort plug-in inside IO80211FamilyLegacy and the standalone Tahoe AirPort driver must not both be enabled. The package removes the old plug-in. Each driver loads separately. To upgrade, copy `EFI/OC/Kexts` and regenerate the configuration. Use Release for daily use or replace SimpleBCM with `Debug/SimpleBCM.kext` for troubleshooting.

The package root contains:

```text
EFI/                    Companion drivers and Release SimpleBCM
Debug/SimpleBCM.kext     Debug build
Release/SimpleBCM.kext   Release build
config.fragment.plist   Default configuration example
Extra/                  Documentation, tools, sources, symbols, reports, optional drivers
```

<details>
<summary>Generate a configuration copy and run preflight checks</summary>

Run from the extracted package directory:

```sh
python3 Extra/Tools/configure.py /Volumes/USB/EFI/OC/config.plist --output /Volumes/USB/EFI/OC/config.SimpleBCM.plist
```

The generator requires exactly one enabled Lilu entry and writes a separate configuration copy. It adds the individual driver entries, handles duplicate entries from older configurations, and preserves existing boot arguments. For older cards, append `--airportbrcmfixup`; an existing AirportBrcmFixup entry enabled for Tahoe is preserved automatically. Review the copy, use it as the USB EFI's `config.plist`, then run:

```sh
python3 Extra/Tools/preflight.py /Volumes/USB/EFI/OC --manifest Extra/manifest.json
```

Preflight checks the Tahoe kernel range, load order, minimum Lilu version, duplicate or conflicting drivers, and actual files. `--manifest` also checks file hashes for SimpleBCM, its companion drivers, and an enabled optional AirportBrcmFixup. You can retain your existing Lilu ≥ 1.7.1. Runtime loading is not restricted by OS minor version, build number, or UUID.

</details>

## Boot arguments

| Argument | Purpose |
| :--- | :--- |
| `-simplebcmoff` | Disable the driver |
| `-simplebcmdbg` | Enable Debug build logging |

Release retains basic status counters. Detailed command errors are logged only in Debug builds.

## Status and diagnostics

```sh
./Extra/bcmprobe
python3 Extra/Tools/collect.py
```

By default, `Extra/bcmprobe` queries CoreWLAN and IORegistry without printing SSIDs, BSSIDs, or passwords. `./Extra/bcmprobe --scan` actively starts a scan. The collector saves driver, client, awdl0, and related system log information on demand, with no persistent listener.

`PatchState=7` and `Status=ReadyForHardwareValidation` indicate that interface hooks are installed. Confirm connectivity through actual use. `Commands`, `Events`, `Notifications`, `LastRequest`, and `LastResult` retain real counts and return codes.

## Building

Requires full Xcode, Git, and Python 3. The validated toolchain is Xcode 26.5 / 17F42.

```sh
python3 Tools/build.py --configuration Debug
python3 Tools/build.py --configuration Release
python3 Tools/build.py --configuration Release --analyze
python3 Tools/package.py
```

The output is `dist/SimpleBCM-1.0.0-Tahoe-x86_64.zip`. Builds verify pinned upstream dependencies; the included validation reports record the actual test environment. All Tahoe releases are allowed without minor-version gates. The current 1.0.0 build still requires a reboot test, so this does not imply that every release has been validated.

CI follows the SimpleHDA build-and-publish flow on `macos-26-intel`: branch pushes build Debug/Release, run static analysis and validation, and update the `v1.0.0-alpha` prerelease. Pull requests build without publishing. Formal Release tags must be `1.0.0` or `v1.0.0`. Alpha archive names include the short commit SHA; formal archives retain the name above. CI system-interface validation does not replace a hardware reboot test.

## Credits

[Lilu](https://github.com/acidanthera/Lilu) · [MacKernelSDK](https://github.com/acidanthera/MacKernelSDK) · [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher) · [PatcherSupportPkg](https://github.com/dortania/PatcherSupportPkg) · [Apple XNU](https://github.com/apple-oss-distributions/xnu)

See [NOTICE](NOTICE.md) for third-party components and licenses. The package's `Extra/Licenses` directory includes the Lilu, OCLP, and MacKernelSDK licenses.

<div align="center">

Copyright © 2026 **laobamac**. All rights reserved.

</div>
