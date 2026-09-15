# 开箱与刷机

把板子刷成 **AidLux 融合系统（Android 13 + Ubuntu 22.04）**，并完成 AidLux 初始化。

刷机会清空用户数据。联调板 `192.168.88.216` 上已有约 57G 数据（课程目录、大模型压缩包等）。**在你明确说「可以进 EDL」之前，本教程不会执行 `adb reboot edl`。**

## 2026-09-14 联调现场

这块板子现在就能用 ADB，不必先猜有没有线。

| 项 | 状态 |
| --- | --- |
| 型号 | `RhinoPi-X1`（`kalama`） |
| 序列号 | `FB803WFB5A300571` |
| USB ADB | 已连接 |
| 网络 ADB | `192.168.88.216:5555` 已连接 |
| Android | 13，`T04_LA_AL_SDK_V01.19b01` |
| 构建号 | `RhinoPi-X1.1.user.2026070119`（2026-07-01） |
| AidLux 标记 | `persist.aidlux.install=RhinoPi-X1.1.user.2026070119` |
| 本机 ADB | 已有（Android SDK `platform-tools` 37.0.0） |
| 本机 QFIL / 高通 USB 驱动 | **还没装** |
| C: 剩余空间 | 约 146 GB，够下镜像 |

在这台 Windows 上验证设备：

```bat
adb devices -l
```

应能看到类似：

```text
FB803WFB5A300571       device product:kalama model:RhinoPi_X1
192.168.88.216:5555    device product:kalama model:RhinoPi_X1
```

## 目标

- 知道系统镜像在哪下，以及整包和拆分装怎么选
- 在 Windows 上装好 USB 驱动和 QFIL
- 用 QFIL 刷机
- 开机后初始化 AidLux 到 100%

## 相关资料

- [工具下载目录](https://file.aidlux.com/files?folder_id=eda4c1da)
- [镜像列表页](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/resource-download/image_resource)
- [融合系统整包安装](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/getting-started/system-install/install_system)
- [融合系统拆分安装](https://rhinopi.docs.aidlux.com/rhino-x1-aidlux/getting-started/system-install/aidlux_install)

## 系统在哪找（2026-09-14 实查）

都在 [file.aidlux.com](https://file.aidlux.com/)，打开对应文件夹后点「下载」。网页可能要登录才能下。

| 用途 | 文件夹 | 当天看到的文件 | 大小 |
| --- | --- | --- | --- |
| Windows 刷机工具 | [eda4c1da](https://file.aidlux.com/files?folder_id=eda4c1da) | `QPST_2.7.496.zip`、`USB_Driver_qud.win.1.1_installer_10061.1.zip`、`platform-tools.zip` | 60 / 18 / 6 MB |
| 融合整包（一次刷完） | [4ccc30f9](https://file.aidlux.com/files?folder_id=4ccc30f9) | `RhinoPi-X1.T04_LA.user.2025121609.aidlux.zip` | 4.74 GB |
| 仅 Android | [a521955b](https://file.aidlux.com/files?folder_id=a521955b) | `RhinoPi-X1.T04_LA.user.2026070119.zip` | 1.85 GB |
| 仅 AidLux | [154a82b5](https://file.aidlux.com/files?folder_id=154a82b5) | `aidlux_3.0.0.124_enterprise_qc8550_lu2204_signed.zip` | 3.05 GB |
| OTA | [7368d645](https://file.aidlux.com/files?folder_id=7368d645) | 未在本次打开 | — |

怎么选：

- **新板、只想少一步**：下融合整包，刷完点 AidLux 初始化即可。注意整包当天是 **2025-12-16**，比联调板上的 **2026-07-01** 旧，会降级。
- **这块联调板要重刷且不想降级**：走拆分——先刷 Android `2026070119`，再用 `install.bat` 装 AidLux `3.0.0.124`。
- OTA 只给已经是融合系统、只想升级的人，不是第一次刷机。

把你实际下载的文件名记进 [实测记录](experience-log.md)。

## 你要准备什么

- 犀牛派 X1、DC 12V 5A 电源（刷机时不要拔电源）
- Windows 电脑
- USB Type-A 转 Type-C：Type-A 接电脑，Type-C 接板子
- 磁盘：整包约 5 GB，拆分约 5 GB，解压后再留一份空间

## 第一步：先装 Windows 工具（现在就能做）

本机 ADB 已经能用，不必再装 `platform-tools`。还缺驱动和 QFIL。

1. 打开 [工具目录](https://file.aidlux.com/files?folder_id=eda4c1da)
2. 下载并解压：
   - `USB_Driver_qud.win.1.1_installer_10061.1.zip` → 跑 `setup.exe`
   - `QPST_2.7.496.zip` → 跑 `QPST.2.7.496.1.exe`，一直 Next
3. QFIL 默认在 `C:\Program Files (x86)\Qualcomm\QPST\bin\QFIL.exe`，可发到桌面
4. 同时开始下镜像（按上面「怎么选」）

装完验收：

```bat
adb devices -l
dir "C:\Program Files (x86)\Qualcomm\QPST\bin\QFIL.exe"
```

## 第二步：进下载模式（等你确认后再做）

1. 板子上电，Type-C 保持连接，`adb devices` 看得到 `FB803WFB5A300571`
2. 进入 EDL：

   ```bat
   adb -s FB803WFB5A300571 reboot edl
   ```

   不要对 `192.168.88.216:5555` 这条网络 ADB 下 EDL，用 USB 这条。
3. 设备会变成 Qualcomm `9008` 端口，普通 `adb devices` 会空。

## 第三步：QFIL 刷机

1. 打开 QFIL → Configuration → FireHose：
   - Download Protocol：`0-Sahara`
   - Device Type：`ufs`
   - 勾选 `Reset After Download`
2. Select Port：选 `9008`
3. Build Type：`Flat Build`
4. 解压 ROM。Programmer 选 `xbl_s_devprg_ns.melf`（文件类型改成所有文件）
5. Load XML：按提示把弹出的 XML **都选上**（会弹两次）
6. Download，大约 5 分钟。看到 successful 后板子会自己重启

失败找阿加犀售后。这里不写强刷或绕过官方工具的做法。

## 第四步：装 / 初始化 AidLux

**整包**：Android 桌面上滑找到 AidLux，点开，等到 100%。

**拆分**：Android 刷完、`adb devices` 再次看到设备后，解压 AidLux zip，在 Windows 上跑 `install.bat`，提示 Success 后再到板子上完成初始化。

## 本步验收

- 板子能开机，风扇转
- Android 里 AidLux 初始化到 100%
- `adb devices` 或同网段能再连上
- 记下新的 `ro.build.version.incremental`

下一章：[登录与环境](02-login-and-env.md)

## 常见失败

| 现象 | 先查什么 |
| --- | --- |
| `adb devices` 空 | 线序、换 USB 口、装高通驱动；网络 ADB 可用 `adb connect 192.168.88.216:5555` 救急，刷机仍要 USB |
| 没有 9008 | 再 `adb reboot edl`；仍没有就断电重来，或看硬件文档里的 EDL 针 |
| QFIL 失败 | Programmer / XML 是否和该版本包匹配；Device Type 是否 `ufs` |
| 初始化卡住 | 等几分钟；供电是否 12V 5A。[论坛黑屏帖](https://forum.aidlux.com/) |

## 拍照点

见 [拍照清单](photo-checklist.md) 第 1 组。现在就能拍：板子线序、`adb devices`、工具目录、QFIL 安装界面。
