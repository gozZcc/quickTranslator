# 划词翻译器

轻量级 Windows 桌面翻译工具。在任意应用中选中文本或复制文本，自动弹出翻译按钮，一键翻译。主窗口支持 8 种语言互译，深色/浅色主题自由切换。

**单文件 Python 应用，仅依赖标准库，无需 pip install。**

## v1 → v2 变更

| 特性 | v1 | v2 |
|------|----|----|
| 翻译方向 | 仅英→中 | 主窗口 8 语言互译 + 应用外英→中 |
| 源语言检测 | 无 | Unicode 范围自动检测 + LLM 兜底 |
| 剪贴板翻译 | 无 | Win32 API 监听，只读不写，不污染剪贴板 |
| UI 主题 | 固定浅色 | 深色/浅色一键切换，配置持久化 |
| 重新翻译 | 无 | 🔁 按钮清除缓存重新调 API |
| 划词翻译 | ✅ | ✅ 不变 |

## 功能

- **划词翻译** — 在任意应用中拖选或双击文本，自动弹出「译」按钮，点击即可翻译
- **剪贴板监听翻译** — 复制文本后自动弹出翻译按钮，不污染剪贴板内容
- **悬浮气泡** — 翻译结果以气泡形式显示在选中文本附近，悬停暂停自动关闭
- **多语言互译** — 主窗口支持中/英/日/韩/法/德/西/俄 8 种语言互译，自动检测源语言
- **深色/浅色主题** — 工具栏一键切换，自动保存偏好
- **重新翻译** — 翻译不满意时点击 🔁 清除缓存重新请求
- **多引擎支持** — OpenCode Zen、硅基流动、DeepSeek、OpenRouter、MyMemory（免配置）
- **翻译缓存** — LRU 缓存相同文本，减少 API 调用

## 快速开始

### 方式一：直接运行（需要 Python）

要求 Python 3.8+，无需安装额外依赖：

```bash
python translator.py
```

首次运行会自动生成 `config.json` 配置文件。

### 方式二：打包为 exe（无需 Python 环境）

双击 `build.bat`，完成后在 `dist/Translator.exe`。

或手动打包：

```bash
pip install pyinstaller
pyinstaller --onefile --name Translator --noconsole translator.py
```

## 配置

### 推荐配置（免费）

1. 启动程序，点击「⚙️ 设置」
2. 翻译服务选择 **OpenCode Zen（推荐，有免费模型）**
3. 模型选择 `big-pickle` 或其他带 `free` 的模型
4. 在 [opencode.ai/auth](https://opencode.ai/auth) 登录获取 API Key
5. 填入 API Key，保存

### config.json 字段

首次运行自动生成，也可在设置界面修改：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `provider` | 翻译服务标识 | `"opencode-zen"` |
| `api_base` | API 地址 | `"https://opencode.ai/zen/v1"` |
| `api_key` | API 密钥 | `""` |
| `model` | 模型名称 | `"big-pickle"` |
| `selection_translate` | 启用划词翻译 | `true` |
| `clipboard_translate` | 启用剪贴板监听翻译 | `false` |
| `theme` | 界面主题 | `"light"` |

## 使用方法

### 划词翻译

1. 确保设置中「启用划词翻译」已勾选
2. 切到任意应用（浏览器、文档、编辑器等）
3. 拖选或双击文本
4. 旁边弹出「译」按钮，点击
5. 翻译结果以气泡显示，8 秒后自动消失（悬停可暂停）

### 剪贴板监听翻译

1. 在设置中勾选「启用剪贴板监听翻译」
2. 在任意应用中复制文本（Ctrl+C）
3. 光标附近弹出「译」按钮，点击翻译
4. 不会修改剪贴板内容

### 主窗口翻译

1. 在左侧面板输入或粘贴文本
2. 工具栏选择源语言（支持「自动检测」）和目标语言
3. 停止输入 1 秒后自动翻译
4. 翻译不满意可点击 🔁 重新翻译

### 切换主题

点击工具栏右侧 🌙/☀️ 按钮，深色和浅色一键切换，下次启动自动保持。

## 支持的翻译引擎

| 引擎 | 需要 API Key | 说明 |
|------|-------------|------|
| OpenCode Zen | 是 | 推荐，有免费模型 |
| 硅基流动 SiliconFlow | 是 | 国产模型平台 |
| DeepSeek | 是 | DeepSeek 官方 API |
| OpenRouter | 是 | 多模型聚合平台 |
| MyMemory | 否 | 免配置，有请求限制 |

## 系统要求

- Windows 10 / 11
- Python 3.8+（仅源码运行时需要）
- 网络连接

## 项目结构

```
translator.py    主程序（单文件，无外部依赖）
build.bat        Windows 打包脚本
config.json      配置文件（首次运行自动生成，不含在仓库中）
CLAUDE.md        AI 开发指引
```

## License

MIT
