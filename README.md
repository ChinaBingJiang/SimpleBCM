<!--
  README.md
  SimpleBCM

  Created by laobamac on 2026/9/7.
  Copyright © 2026 laobamac. All rights reserved.
-->
<div align="center">

# SimpleBCM

**在 macOS Tahoe 上恢复 Broadcom 无线支持**

![Version](https://img.shields.io/badge/version-1.0.0-2563eb)
![macOS](https://img.shields.io/badge/macOS-Tahoe%2026-111827)
![Architecture](https://img.shields.io/badge/arch-x86__64-6b7280)
![OpenCore](https://img.shields.io/badge/boot-OpenCore-16a34a)

**简体中文** · [English](README.en.md)

OpenCore 注入 · 原生无线 API · 自动连接 · 隔空投送

</div>

---

SimpleBCM 是一个 Lilu 插件，通过 OpenCore 独立加载配套 Broadcom 驱动，并适配 Tahoe 的无线控制和事件接口。不修改系统卷，不替换系统框架。

## 要求

| 项目 | 要求 |
| :--- | :--- |
| 系统 | macOS Tahoe 全系列（Darwin 25.x） |
| 架构 | Intel x86_64 |
| 引导 | OpenCore |
| 依赖 | Lilu ≥ 1.7.1，以及包内固定版本的配套驱动 |

## 安装

1. 解压发行包，将 `EFI/OC/Kexts` 中的驱动放入可回退的 EFI 副本；Lilu 仅保留一个启用版本。
2. 合入 `config.fragment.plist`，加载顺序为 **Lilu → SimpleBCM → IOSkywalkFamily → IO80211FamilyLegacy → AirPortBrcmNIC-Tahoe**。
3. 对系统 `com.apple.iokit.IOSkywalkFamily` 设置 `Kernel → Block → Exclude`；配置示例已包含此项。
4. 运行 `Extra/Tools/preflight.py`，再用当前 OpenCore 版本配套的 `ocvalidate` 校验完整配置。
5. 从该 EFI 启动，使用系统 Wi-Fi 界面连接网络。

仅部分旧网卡（如 BCM943224）需要 AirportBrcmFixup 及其 NIC Injector。将 `Extra/Optional/AirportBrcmFixup.kext` 放入 `EFI/OC/Kexts`，使用 `Extra/Optional/config.AirportBrcmFixup.fragment.plist`，或在配置生成命令末尾添加 `--airportbrcmfixup`。可选示例会将 AirportBrcmFixup 放在 SimpleBCM 后，并添加 `AirPortBrcmNIC_Injector` 条目。

IO80211FamilyLegacy 内置的旧 AirPort 插件与独立 Tahoe AirPort 驱动不能同时启用，发行包已移除旧插件。各驱动均独立加载；升级时复制 `EFI/OC/Kexts` 并重新生成配置。日常使用 Release 版本，排查时可替换为 `Debug/SimpleBCM.kext`。

发行包根目录为：

```text
EFI/                    配套驱动与 Release 版 SimpleBCM
Debug/SimpleBCM.kext     Debug 版本
Release/SimpleBCM.kext   Release 版本
config.fragment.plist   默认配置示例
Extra/                  文档、工具、源码、符号、验证报告及可选驱动
```

<details>
<summary>生成配置副本与启动前检查</summary>

从解压后的发行包目录执行：

```sh
python3 Extra/Tools/configure.py /Volumes/USB/EFI/OC/config.plist --output /Volumes/USB/EFI/OC/config.SimpleBCM.plist
```

生成器要求输入配置已有唯一启用的 Lilu，只输出单独副本。它会补齐独立驱动条目、处理旧配置中的重复项，并保留原有启动参数。旧网卡可添加 `--airportbrcmfixup`；已有 Tahoe 范围内启用的 AirportBrcmFixup 会自动保留。审阅后将副本用作 USB EFI 的 `config.plist`，再执行：

```sh
python3 Extra/Tools/preflight.py /Volumes/USB/EFI/OC --manifest Extra/manifest.json
```

preflight 检查 Tahoe 版本范围、加载顺序、Lilu 最低版本、重复或冲突的驱动及实际文件。`--manifest` 额外核对 SimpleBCM、配套驱动和已启用的可选 AirportBrcmFixup 文件哈希，允许使用现有的 Lilu ≥ 1.7.1。运行时不按系统小版本、构建号或 UUID 限制加载。

</details>

## 启动参数

| 参数 | 用途 |
| :--- | :--- |
| `-simplebcmoff` | 停用驱动 |
| `-simplebcmdbg` | 开启 Debug 版本日志 |

Release 保留基本状态计数，命令错误明细仅在 Debug 记录。

## 状态与诊断

```sh
./Extra/bcmprobe
python3 Extra/Tools/collect.py
```

`Extra/bcmprobe` 默认查询 CoreWLAN 和 IORegistry，不输出 SSID、BSSID 或密码；`./Extra/bcmprobe --scan` 会实际发起扫描。采集脚本按需保存驱动、客户端、awdl0 状态和相关系统日志，无常驻监听。

`PatchState=7` 与 `Status=ReadyForHardwareValidation` 表示接口挂接完成，联网状态以实际连接为准。`Commands`、`Events`、`Notifications`、`LastRequest` 和 `LastResult` 保留真实计数与返回码。

## 构建

需要完整 Xcode、Git 和 Python 3，实际使用的工具链为 Xcode 26.5 / 17F42。

```sh
python3 Tools/build.py --configuration Debug
python3 Tools/build.py --configuration Release
python3 Tools/build.py --configuration Release --analyze
python3 Tools/package.py
```

输出为 `dist/SimpleBCM-1.0.0-Tahoe-x86_64.zip`。构建会校验固定上游依赖，附带的验证报告记录实际测试环境。全系列 Tahoe 不设小版本准入限制；当前 1.0.0 仍需重启实测，不能据此视为所有版本均已验证。

CI 与 SimpleHDA 采用相同的构建发布流程，运行于 `macos-26-intel`：推送分支自动构建 Debug/Release、静态分析、验证并更新 `v1.0.0-alpha` 预发布；PR 只构建，不发布。发布正式 Release 时，标签须为 `1.0.0` 或 `v1.0.0`。Alpha 安装包名附带提交短 SHA，正式包保持上述名称。CI 的系统接口验证不能代替网卡重启实测。

## 致谢

[Lilu](https://github.com/acidanthera/Lilu) · [MacKernelSDK](https://github.com/acidanthera/MacKernelSDK) · [OpenCore Legacy Patcher](https://github.com/dortania/OpenCore-Legacy-Patcher) · [PatcherSupportPkg](https://github.com/dortania/PatcherSupportPkg) · [Apple XNU](https://github.com/apple-oss-distributions/xnu)

第三方组件及许可见 [NOTICE](NOTICE.md)，发行包 `Extra/Licenses` 目录附有 Lilu、OCLP 和 MacKernelSDK 许可。

<div align="center">

Copyright © 2026 **laobamac**. All rights reserved.

</div>
