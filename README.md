# 📖 ZIP to PDF 批量转换工具

将超星书籍扫描 ZIP 压缩包批量转换为 PDF 文件。支持拖拽操作、流式低内存处理、按页数实时显示进度。

## ✨ 功能特性

- **拖拽操作** — 直接拖入 ZIP 文件或文件夹，自动识别并处理
- **低内存** — 分批处理（每批 20 页），大文件不爆内存
- **页级进度** — 实时显示已处理页数 / 总页数、处理速度（页/秒）、预计剩余时间
- **智能排序** — 按超星 PDG 命名规范自动排序（封面→书名页→版权页→前言→目录→正文→附录→封底）
- **自动清理** — 转换成功后自动删除源 ZIP 和解压目录，只保留 PDF
- **断点续传** — 已存在同名 PDF 时自动跳过
- **拟物风格 UI** — 复古拟物界面设计
- **单文件免安装** — 打包为单个 exe，双击即用，无需 Python 环境

## 📦 安装

### 方式一：下载 exe（推荐）

从 [Releases](../../releases) 下载最新版 `ZIP转PDF工具.exe`，双击即可运行。

### 方式二：从源码运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/pdg-pdf.git
cd pdg-pdf

# 安装依赖
pip install -r requirements.txt

# 运行 GUI 版本
python zip_to_pdf_gui.py

# 或运行命令行版本
python zip_to_pdf.py
```

## 🚀 使用方法

### GUI 版本

1. 双击运行 `ZIP转PDF工具.exe`
2. 拖拽 ZIP 文件到窗口，或点击「选择 ZIP 文件」按钮
3. 等待转换完成，PDF 保存在 exe 同级目录

### 命令行版本

将 `zip_to_pdf.py` 放到包含 ZIP 文件的目录，直接运行：

```bash
python zip_to_pdf.py
```

### 拖拽到 exe

直接将 ZIP 文件或文件夹拖到 `ZIP转PDF工具.exe` 上即可。

## 📁 项目结构

```
pdg-pdf/
├── zip_to_pdf.py        # 命令行版本
├── zip_to_pdf_gui.py    # GUI 版本（拖拽 + 进度条）
├── build.py             # PyInstaller 打包脚本
├── book_icon.ico        # 应用图标
├── requirements.txt     # Python 依赖
├── README.md
├── LICENSE
└── .gitignore
```

## 🔧 打包为 exe

```bash
pip install pyinstaller
python build.py
```

打包产物在 `dist/` 目录下。

## 🧠 技术细节

### 超星 PDG 文件

超星扫描书籍的 `.pdg` 文件本质是 JPEG 图片，只是改了扩展名。文件命名规范：

| 前缀 | 含义 | 排序优先级 |
|------|------|-----------|
| `cov` | 封面 | 0 |
| `bok` | 书名页 | 1 |
| `leg` | 版权页 | 2 |
| `fow` | 前言 | 3 |
| `!` | 封面图 | 4 |
| `toc` | 目录 | 5 |
| 数字 | 正文 | 6 |
| `att` | 附录 | 8 |
| `bac` | 封底 | 9 |

### 内存优化

大 ZIP（几百页高清扫描）一次性加载所有图片会 OOM。解决方案：

1. 每批处理 20 页，生成临时 PDF
2. 释放内存后处理下一批
3. 最后用 `pypdf` 合并所有批次
4. 清理临时文件

内存峰值从 O(总页数) 降到 O(20)。

## 🛠 依赖

- Python 3.8+
- Pillow — 图片处理
- pypdf — PDF 合并
- tkinterdnd2 — 拖拽支持（仅 GUI 版本）

## 📄 License

[MIT](LICENSE)
