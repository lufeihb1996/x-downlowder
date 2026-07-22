# X Video Downloader (Vercel Serverless PWA)

一个极速、美观、免会员且无视 Twitter/X 媒体防盗链限制的推特视频下载器。本应用针对移动端（尤其是 iOS Safari）进行了深度 PWA 适配，可一键“添加到主屏幕”作为独立 App 运行。

---

## 🌟 核心特性

- **Vercel Serverless 部署**：基于 Vercel Python 3 运行时，免维护、零服务器开销。
- **免防盗链限制（Download Proxy）**：内置数据流代理（`api/proxy.py`），自动注入官方 Referer 头部，彻底解决直接下载 `twimg.com` 视频时报 **HTTP 403 Forbidden** 的问题。
- **PWA (Progressive Web App) 支持**：配置离线 `sw.js` 缓存和 `manifest.json`，在 iOS/Android 上支持“添加到主屏幕”实现全屏原生 App 体验。
- **竖屏视频智能分类**：前端依据视频短边像素，智能判断并标记 vertical 视频的真实分辨率等级（1080P/720P/480P）。

## 🚀 本地启动与运行 (Local Running)

在 `x-downloader` 根目录下，通过 Python 运行本地集成服务端：

```bash
# 启动本地服务 (默认端口 8088)
python server.py

# 或通过 npm / pnpm 启动
npm start
```

服务启动后，在浏览器访问：
👉 **http://localhost:8088**

---

## 📂 项目结构

```text
x-downloader/
├── api/
│   ├── parse.py          # Python Serverless 函数 - 视频解析器 (调用 yt-dlp)
│   └── proxy.py          # Python Serverless 函数 - 下载代理流 (绕过 403)
├── public/               # 静态网页资源
│   ├── index.html        # 极简奢华暗黑毛玻璃 UI
│   ├── style.css         # Neon Glow 自适应 CSS 样式
│   ├── app.js            # 剪贴板粘贴与数据交互逻辑
│   ├── manifest.json     # PWA 桌面配置文件
│   ├── sw.js             # 离线 Service Worker
│   └── icon.svg/png      # PWA 品牌图标
├── requirements.txt      # Python 依赖库声明 (yt-dlp)
├── vercel.json           # Vercel v2 编译及路由配置文件
└── package.json          # 极简 package.json，避免 Vercel 编译器空指针崩溃
```

---

## 🛠️ 技术架构演进与决策历史 (Architecture Evolution)

### 阶段一：Node.js 本地服务器 (server.js) ❌
*   **设计**：最初使用 Node.js Express 搭建本地服务，并使用 Node 库 `youtube-dl-exec` 调用 `yt-dlp` 进行视频解析。
*   **问题**：`yt-dlp` 底层是用 Python 编写的。Node.js 接口在调用它时，需要在命令行执行 `python3` 进程。然而，Vercel 部署 Node.js 服务分配的容器极为精简，**不包含 Python 运行环境**，导致报错 `env: 'python3': No such file or directory`。
*   **结论**：即使改用 Next.js 部署 Node.js 后端，该底层系统限制依然存在。

### 阶段二：清空 Node 依赖触发 Vercel 编译器冲突 ❌
*   **设计**：将后端全部改写为 `api/` 目录下的 Python Serverless 脚本，并删除了 Node 的 `server.js` 和 `package.json`。
*   **问题**：由于 Vercel 控制台创建该项目时默认锁定了 “Node.js/Next.js” 框架模板，删除 `package.json` 后，Vercel 编译器在进行依赖扫描时因为找不到该文件而发生空指针崩溃（报错 `Cannot read properties of undefined (reading 'fsPath')`）。

### 阶段三：原生 Python Serverless + 显式打包配置 (当前方案)  
*   **设计**：
    1.  重构后端 API 为原生 Python (`api/parse.py` & `api/proxy.py`)，并在 `requirements.txt` 中写入 `yt-dlp`。Vercel 识别后会**自动为其分配预装 Python 3 环境的沙箱**，免去了 Node 跨语言调用的尴尬。
    2.  保留一个极简的 `{ "private": true }` 的 `package.json` 消除编译器的 fsPath 检测死锁。
    3.  通过 `vercel.json` 显式划分静态包编译（`@vercel/static`）与 Python 编译（`@vercel/python`）。
*   **成果**：成功兼顾了 Vercel 的免费托管和 Python `yt-dlp` 的极强解析能力。

---

## 🔒 绕过 Twitter 防盗链原理

直接访问 Twitter 的视频流地址（`https://video.twimg.com/...`）时，由于 Referer 不是推特官方，CDN 会直接拦截并返回 403。

本项目通过 `/api/proxy?url=<CDN地址>` 代理请求：
```python
# api/proxy.py 核心伪装
req = urllib.request.Request(
    url,
    headers={
        'User-Agent': 'Mozilla/5.0 ...',
        'Referer': 'https://x.com/' # 模拟官方来源，安全绕过 403
    }
)
```
服务器拿到响应流后，向客户端追加 `Content-Disposition: attachment` 响应头，以流（Stream）的形式回传给浏览器，强制触发系统下载行为，保障 100% 下载成功率。

---

## 📱 iPhone 手机保存至相册说明

由于 iOS 浏览器沙盒限制，网页端无法静默保存文件到相册，需要手动导出：
1. 用 **Safari 浏览器** 打开本项目网址，点击底部的“分享” 📤 按钮，选择 **“添加到主屏幕”**。
2. 像 App 一样启动它，粘贴链接解析。
3. 点击画质下载，在 Safari 提示中确认“下载”。
4. 下载完成后，点击 Safari 状态栏的下载管理器（或系统自带的 **“文件” App** ➡️ **“下载”** 文件夹）。
5. 打开视频，点击左下角 **“分享” 📤** ➡️ 选择 **“保存视频” (Save Video)** 即可安全导入相册。
