# Private Text Window

Private Text Window 是一个 Windows 本地文本输入小工具，适合在屏幕上临时记录内容，但又不想让完整输入历史直接暴露出来的场景。

它的核心思路是：完整文本会保存在本地历史中，但主窗口默认只显示光标前指定数量的字符。你可以正常输入、换行、移动光标、删除、复制全部历史，也可以一键展开完整内容进行普通文本编辑。

## 说明

本项目代码完全由 AI 生成。发布者和使用者在运行前应自行检查代码、启动脚本和数据保存逻辑，确认符合自己的安全与隐私要求后再使用。

## 功能特点

- 默认白色小窗口，可调透明度、字号和最近显示字数
- 默认启动时显示边框和设置栏，可一键切换无边框模式
- 隐藏模式下只显示光标前 N 个字符，不直接展示全部历史
- 展开模式下可像普通文本框一样编辑完整内容
- 支持中文、英文、空格、符号、粘贴和 Enter 换行
- 支持复制全部历史、二次确认清空历史
- 支持窗口置顶、任务栏图标、最小化到任务栏
- 历史和设置保存在本地，不依赖网络服务

## 本地数据

程序会自动生成并使用 `private_text_window.ico` 作为窗口和任务栏图标。
窗口打开期间会一直保留任务栏图标；即使切到无边框模式，也可以从任务栏找回窗口。

完整内容保存在同目录的 `history.txt`，设置保存在 `settings.json`。

## 启动

推荐双击：

```text
run_private_text_window.vbs
```

这个入口会用 `pythonw.exe` 后台启动，不会出现命令行黑框，也不会依赖 Windows 的 `.pyw` 文件关联。

备用入口：

```text
run_private_text_window.bat
```

如果要从命令行调试，可以在当前目录运行：

```powershell
python .\private_text_window.py
```

说明：`.pyw` 启动依赖 Windows 的 Python Launcher 文件关联。当前机器上的 `.pyw` 关联指向了不存在的 Python 路径，所以不再提供 `.pyw` 作为启动入口。

每次启动都会默认显示边框和设置栏；透明度、字号、显示字数、窗口位置等设置会维持上一次状态。

## 环境

- Windows 10/11
- Python 3，需包含标准库 `tkinter`
- 无第三方 Python 依赖

运行时会在程序目录生成或更新 `history.txt`、`settings.json`、`private_text_window.ico`。其中 `history.txt` 和 `settings.json` 是本地个人数据，已在 `.gitignore` 中排除，不建议提交到 GitHub。

## 快捷键

- `Ctrl+B`：切换无边框 / 有标题栏和设置栏
- `Ctrl+E`：展开 / 收起全部内容
- 隐藏模式下 `Ctrl+C`：复制全部历史内容，保留换行
- 任意模式下 `Ctrl+Shift+C`：复制全部历史内容，保留换行
- `Ctrl+Shift+Delete`：二次确认后清空全部内容
- `Ctrl+Q`：退出
- `Ctrl+M`：最小化到任务栏
- `Ctrl+T`：切换置顶
- `Ctrl+Up` / `Ctrl+Down`：提高 / 降低窗口透明度
- `Ctrl+=` / `Ctrl+-`：增大 / 减小字体
- 隐藏模式下 `Ctrl+Right` / `Ctrl+Left`：增加 / 减少显示字数
- 隐藏模式下 `Left` / `Right`：在完整文本中移动输入光标

无边框模式下，拖动窗口顶部的白色细条可以移动窗口，拖动右下角的小区域可以缩放窗口。
