# Cai Install Web GUI

<div align="center">

![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![License](https://img.shields.io/badge/License-GPLv3-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Active-success.svg)

**一款基于现代 Web 技术的 Steam 清单下载与自动入库工具。**

[📥 下载最新版本](https://github.com/pvzcxw/Cai-install-Web-GUI/releases) • [📖 报告问题](https://github.com/pvzcxw/Cai-install-Web-GUI/issues) • [💬 加入群聊](http://qm.qq.com/cgi-bin/qm/qr?_wv=1027&k=LSm4c51Ef0F3EOpwtojGJRohf50Jh2Ts&authKey=W3uFCwrxNT%2FtBQ%2BeSfR1TmzOn67ZS7Xax9gBgythNeLQgdhUNJ9DJ0W0ocrFqNuE&noverify=0&group_code=993782526)

</div>

## 📖 项目简介

**Cai Install Web GUI** 是原版 [Cai-Install](https://github.com/pvzcxw/Cai-install) 的重构版本，外观设计灵感来源于 [Onekey_GUI](https://github.com/qwq-xinkeng/Onekey_GUI)。本项目采用 Flask + Vue/原生JS 架构构建，抛弃了传统的终端界面，为您提供了一个拥有 Material Design 3 风格的精美图形化界面。

它旨在帮助用户一键下载 Steam 游戏清单（Manifest）及密钥（DepotKey），并自动配置到 **SteamTools** 或 **GreenLuma** 中，实现游戏的便捷入库。

---

## ✨ 核心特性

### 🎮 游戏入库与解锁
*   **智能环境检测**：自动识别本地 Steam 路径，并自动判断使用的是 SteamTools 还是 GreenLuma。
*   **多源清单下载**：内置多个清单库（GitHub 搜索、SWA V2、Sudama、ManifestHub、清单不求人等）。
*   **自定义仓库源**：支持用户随时添加自定义的 GitHub 仓库或 ZIP 压缩包直链作为清单下载源。
*   **DLC 自动补全**：自动抓取并整合游戏缺失的免费/无 Depot 密钥的 DLC（多数据源回退，防封锁）。

### 🧩 创意工坊支持 (新功能)
*   **创意工坊直连**：输入创意工坊物品 ID 或链接，即可直接下载对应清单。
*   **DepotKey 自动修补**：针对创意工坊物品，支持从云端拉取并自动修补 LUA 文件中的 `depotkey`。
*   **多目录分发**：支持将清单文件灵活下发至 `config/depotcache` 和 `depotcache`。

### 📁 可视化入库管理 (Library Manager)
*   **直观的界面**：以网格卡片的形式展示当前已解锁的游戏（包含游戏封面与名称提取）。
*   **一键清理**：告别繁琐的本地文件操作，一键删除无效的 `.lua` (SteamTools) 或 `.txt` (GreenLuma) 及其关联的 `.manifest` 冗余文件。

### 🎨 现代化 Web UI
*   **Material Design 3**：极致流畅的动画、Snackbar 提示与响应式布局。
*   **个性化定制**：支持深色/浅色模式切换，支持自定义背景壁纸（可调模糊度、饱和度、亮度）。
*   **实时日志流**：后端运行日志通过 Socket.IO 实时推送到前端控制台，执行进度一目了然。

### ⚡ 针对国内环境优化
*   内置网络连通性检测（`checkcn`）。针对大陆网络环境，自动启用多个 GitHub Proxy 镜像加速下载，告别网络连接失败。

### 📸 界面展示 (Screenshots)

这里是 Cai Install Web GUI 的实际运行界面：

<div align="center">
  <!-- 如果你用的是方法一，把下面的链接换成相对路径，比如 assets/main.png -->
  <!-- 如果你用的是方法二，把下面的链接换成 GitHub 自动生成的链接 -->
  <img src="https://github.com/pvzcxw/Cai-install-Web-GUI/blob/main/assets/Image_1775439952399_184.png" width="800" alt="主界面">
</div>

<br>

| 自定义清单库 (Library Manager) | 设置个性化 (Settings & Theme) |
| :---: | :---: |
| <img src="https://github.com/pvzcxw/Cai-install-Web-GUI/blob/main/assets/Image_1775439965814_911.png" width="400"> | <img src="https://github.com/pvzcxw/Cai-install-Web-GUI/blob/main/assets/Image_1775439964899_911.png" width="400"> |

---

## 🛠️ 安装与运行

### 环境要求
*   **操作系统**：Windows 10 / 11
*   **浏览器**：Chrome / Edge / Firefox (建议使用 Chrome 50+ 内核)
*   **依赖软件**：[SteamTools](https://steamtools.net/) 或 [GreenLuma](https://csrin.ru/) (需提前安装其中之一)
*   **开发环境** (仅针对从源码运行)：Python 3.8 或更高版本。

### 方式一：下载整合包 (推荐)
前往 [Releases](https://github.com/pvzcxw/Cai-install-Web-GUI/releases) 页面，下载最新的打包版本，解压后双击运行 `.exe` 文件即可启动。

### 方式二：从源码运行
1. 克隆本仓库到本地：
    ```bash
    git clone https://github.com/pvzcxw/Cai-install-Web-GUI.git
    cd Cai-install-Web-GUI
    ```
2. 安装所需 Python 依赖库：
    ```bash
    pip install Flask Flask-SocketIO httpx aiofiles colorlog vdf ujson
    ```
3. 启动程序：
    ```bash
    python app.py
    ```
    *(启动时会弹出一个小窗口提示选择端口，默认 `5000`，点击启动后浏览器会自动打开 Web 界面。)*

---

## 💡 使用指南

1. **配置 GitHub Token (强烈建议)**：
    * 首次使用时，请前往右上角 **“设置”**。
    * 填入您的 GitHub Personal Access Token (如何获取请自行百度)。这能极大提高 GitHub API 的请求上限，避免搜索或下载清单时触发频率限制（Rate Limit）。
2. **搜索游戏**：
    * 在主页“游戏搜索”框输入游戏名（如：*艾尔登法环*），点击搜索，获取对应的 **AppID**。
3. **选择入库方式**：
    * 填入 AppID。
    * 选择一个清单源（推荐使用 `SteamAutoCracks/ManifestHub(2)` 或 `自动搜索GitHub`）。
    * 若使用 SteamTools，可勾选“启用自动更新”、“额外入库所有可用DLC”等选项。
4. **执行任务**：
    * 点击“开始任务”，等待日志打印完成。
    * 完成后，点击“重启 Steam”使配置生效。

---

## ⚠️ 免责声明与防骗警告

*   **完全免费开源**：本工具及其源代码完全免费，且基于 GPL-3.0 协议开源。**严禁任何形式的商业化使用或打包倒卖！**
*   **防骗提醒**：目前存在部分无良商家（如 B站某同名资源站、闲鱼倒卖者等）盗用本开源代码及免费清单库，加入卡密系统进行收费倒卖。请广大玩家擦亮眼睛，切勿花冤枉钱。
*   **风险自负**：本工具仅供代码学习与技术交流。使用本工具对 Steam 客户端进行修改所带来的一切后果（包括但不限于账号封禁），由使用者自行承担。

---

## 🤝 鸣谢名单

本项目的诞生离不开以下开源项目与开发者的无私奉献：

*   **核心逻辑**：[Cai-install](https://github.com/pvzcxw/Cai-install) (by pvzcxw)
*   **UI 灵感**：[Onekey_GUI](https://github.com/qwq-xinkeng/Onekey_GUI) (by qwq-xinkeng)
*   **VDF Writer**：由 `KS-MLC` 提供技术支持
*   **DLC 检索及入库**：由 `B-I-A-O` 提供技术支持
*   **清单不求人**：由 `☆☆☆☆` 提供技术支持
*   **清单源与技术支持**：感谢 `FQQ`, `oureveryday`, `blanktming`, `wxy1343`, `Auiowu`, `宏` 等大佬的帮助。

---

## 📜 许可证

本项目采用 [GPL-3.0 License](LICENSE) 开源。请遵守开源协议，尊重原作者的劳动成果。

---
<div align="center">
<i>如果你觉得这个项目对你有帮助，请给个 ⭐ Star 支持一下！</i>
</div>
