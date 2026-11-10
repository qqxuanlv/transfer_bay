# TransferBay

TransferBay 在 Mac 和 Windows 之间通过局域网传文件、发文字。打开两端应用，输入六位配对码并核对屏幕上的校验词，即可双向传输。文件自动保存到接收电脑，文字可以直接复制。

## 下载安装

| 系统 | 下载 | 安装方式 |
| --- | --- | --- |
| macOS 13 或更高版本，Apple 芯片 | [Mac 安装包（DMG）](https://github.com/qqxuanlv/transfer_bay/releases/latest/download/TransferBay-macOS-arm64.dmg) | 打开磁盘映像，把 TransferBay 拖入 Applications。 |
| Windows 10 / 11，x64 | [Windows 安装程序（EXE）](https://github.com/qqxuanlv/transfer_bay/releases/latest/download/TransferBay-Windows-x64-Setup.exe) | 双击安装到当前用户，从桌面或开始菜单启动。 |

升级前请先退出正在运行的版本。Mac 可按 `⌘Q`，Windows 可右键悬浮窗选择退出。如果系统询问网络权限，请允许 TransferBay 访问本地网络。安装包未进行商业开发者签名，macOS 版使用本地签名，未公证。历次发布及附件见 [GitHub Releases](https://github.com/qqxuanlv/transfer_bay/releases)。

## 第一次配对

1. 在能通过局域网互访的两台电脑上打开 TransferBay。
2. 在任意一端输入另一端显示的六位数字，点击「连接」。
3. 两边会显示同一组校验词。核对一致后，在收到请求的电脑上点击「词一致，允许连接」。

配对后，可以在同一连接中连续发送多个文件或多条文字。要更换接收设备，先断开当前连接。

## 文件和文字

**文件**　把文件拖进窗口，或点「选择文件」。对方会自动保存到系统下载目录下的「TransferBay 接收」，再按发送端分入「来自 Mac」或「来自 Windows」。同名文件自动编号。可多选，每个文件最多 2 GB。传输完成后可点「接收文件夹」打开保存位置。

Mac 上，拖着文件靠近菜单栏的纸飞机，会弹出投递窗口。Windows 上可以直接把文件拖到置顶悬浮窗，双击悬浮窗可回到主界面。关闭主窗口后，桌面应用可以继续运行。

**文字**　切换到「文字」，输入或粘贴内容，点「发送文字」。Mac 可按 `⌘ Enter`，Windows 可按 `Ctrl Enter`。普通回车用来换行。对方可以一键复制完整原文，包括换行和空格。单条上限为 4096 个 UTF-16 单元，部分表情占两个单元。文字功能需要两端均为 1.8 或更高版本。

**记录**　「传输记录」下分别列出文件记录和文字记录，各自保留最近 80 条。清空文字记录只影响本机的文字历史。清空文件记录不会删除已保存的文件。

## 网络与排查

- **六位码找不到设备**　先核对两端版本和窗口上的当前配对码。可互访的 `192.168.x.x` 子网支持跨网段定位，其他网络也可以通过同一 IPv4 前两段或局域网广播发现。找不到时，在「其他连接方式」里使用对方的备用长码，或使用对方的连接地址和旧版六位码。
- **需要指定端口**　默认数据端口是 TCP 8765。可在「设置」中修改，退出并重开应用后生效。端口占用时，以窗口显示的实际地址为准。短码还可使用 TCP 47773–47787 中的一个定位端口，局域网发现使用 UDP 47772。
- **地址直连也失败**　确认接收端仍在运行，并检查专用网络防火墙、VPN 路由或访客 Wi-Fi 隔离。传输使用 HTTP，适合可信局域网。

## 从源码运行

在安装了 Python 3.9 或更新版本的电脑上运行：

```sh
python3 server.py
```

打开终端显示的地址。两台设备要分别启动桌面端或服务。浏览器模式可以体验配对和传输，菜单栏投递、Windows 悬浮窗和后台自动接收由桌面客户端提供。

## 构建发行包

macOS 需要 Apple 芯片、Xcode Command Line Tools 和 Python 3.12。在项目根目录运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install pyinstaller==6.22.3
bash scripts/build_mac.sh
```

Windows 需要 Python 3.12、Visual Studio 的 x64 C++ 开发工具、Windows SDK 和 NSIS 3。在 x64 Developer PowerShell 中把 `makensis.exe` 加入 PATH，然后运行：

```powershell
py -3.12 scripts/build_windows.py
```

Windows 构建脚本下载并校验 Python 嵌入式运行时，也可通过 `PYTHON_EMBED_ZIP` 指向本地副本。两个平台均输出到 `release/`，可用 `OUT_DIR` 更改输出位置。

`server.py` 处理配对和传输，`text_history.py` 保存桌面端文字历史，`static/` 是共享界面，`packaging/` 包含原生窗口、悬浮窗及安装程序定义。

## 验证

```sh
python3 tests/routed_code.py
python3 tests/short_pair_flow.py
```

在安装了 Google Chrome 的 Mac 上，还可在虚拟环境中安装 `playwright`，运行 `python tests/background_flow.py`。该测试启动两个隔离的桌面服务，覆盖配对确认、双向文字复制、记录独立清空、文件自动落盘及后台投递。
