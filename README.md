# 划词翻译器

轻量级 Windows 桌面翻译工具。在任意应用中选中英文文本，自动弹出翻译按钮，一键翻译为中文。也支持主窗口手动输入翻译。

**单文件 Python 应用，仅依赖标准库，无需 pip install。**

## 功能

- **划词翻译** — 在任意应用中拖选或双击英文文本，自动弹出「译」按钮，点击即可翻译
- **悬浮气泡** — 翻译结果以气泡形式显示在选中文本附近，悬停暂停自动关闭
- **主窗口翻译** — 左侧输入/粘贴文本，自动翻译显示在右侧，支持输入防抖
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

**方法 A：使用打包脚本**

双击 `build.bat`，完成后在 `dist/Translator.exe`。

**方法 B：手动打包**

```bash
pip install pyinstaller
pyinstaller --onefile --name Translator --noconsole translator.py
```

打包产物在 `dist/Translator.exe`，可以复制到任意位置运行。

## 配置

### 推荐配置（免费）

1. 启动程序，点击「设置」按钮
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
| `selection_translate` | 是否启用划词翻译 | `true` |

## 使用方法

### 划词翻译

1. 启动程序，确保划词翻译已开启（设置中勾选）
2. 切到任意应用（浏览器、文档、编辑器等）
3. 拖选或双击英文文本
4. 旁边弹出「译」按钮，点击
5. 翻译结果以气泡显示在文本附近，8 秒后自动消失（悬停可暂停）

### 主窗口翻译

1. 在左侧面板输入或粘贴文本
2. 停止输入 1 秒后自动翻译
3. 翻译结果显示在右侧面板

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
translator.py    主程序（单文件，约 1300 行，无外部依赖）
build.bat        Windows 一键打包脚本
config.json      配置文件（首次运行自动生成，不含在仓库中）
```

## 开发计划 (v2.0)

- [ ] **多语言翻译** — 自动检测源语言，用户选择目标语言（中/英/日/韩/法/德/西/俄），工具栏下拉切换
- [ ] **剪贴板监听翻译** — 监听剪贴板变化，复制文本后在光标附近弹出翻译按钮（支持终端环境）

## License

MIT
