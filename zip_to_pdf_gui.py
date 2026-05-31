# -*- coding: utf-8 -*-
"""
ZIP转PDF工具 - 拖拽版（流式低内存 + 页级进度 + 拟物风格UI）
"""
import os
import sys
import zipfile
import threading
import tempfile
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from PIL import Image
from pypdf import PdfWriter, PdfReader

BATCH_SIZE = 20

# ============ 拟物配色 ============
COL_BG        = '#F0EDE6'   # 主背景 - 仿纸张米白
COL_PANEL     = '#E8E4DC'   # 面板背景
COL_FRAME_BG  = '#DDD8CE'   # 框架背景
COL_BORDER    = '#B8B0A0'   # 边框
COL_DARK_LINE = '#8C8478'   # 深色线条
COL_SHADOW    = '#C8C0B0'   # 阴影色
COL_TEXT       = '#2C2824'   # 主文字
COL_TEXT_SUB   = '#6B6358'   # 副文字
COL_ACCENT     = '#8B5E3C'   # 强调色 - 皮革棕
COL_BTN_FACE   = '#D4CFC6'   # 按钮面
COL_BTN_PRESS  = '#B8B2A8'   # 按钮按下
COL_GREEN      = '#5B8C5A'   # 成功绿
COL_DROP_BG    = '#FAF8F4'   # 拖拽区背景
COL_DROP_BD    = '#A09888'   # 拖拽区边框
COL_PROGRESS   = '#7B9E6B'   # 进度条
COL_PROGRESS_BG = '#D4CFC6'  # 进度条背景
COL_LOG_BG     = '#2A2622'   # 日志背景
COL_LOG_FG     = '#D4CFC6'   # 日志文字


# ============ 核心转换逻辑 ============

def get_sort_key(filename):
    name = os.path.splitext(filename)[0].lower()
    prefix_order = {
        'cov': 0, 'bok': 1, 'leg': 2, 'fow': 3,
        '!': 4, 'toc': 5, 'att': 8, 'bac': 9,
    }
    for prefix, order in prefix_order.items():
        if name.startswith(prefix):
            num_part = name[len(prefix):].lstrip('0') or '0'
            try:
                return (order, int(num_part))
            except ValueError:
                return (order, 0)
    clean = name.lstrip('0') or '0'
    try:
        return (6, int(clean))
    except ValueError:
        return (7, 0)


def is_image_file(filepath):
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except Exception:
        return False


def extract_zip(zip_path, extract_dir):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        return True, None
    except Exception as e:
        return False, str(e)


def find_pdg_dir(base_dir):
    extensions = ('.pdg', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif')
    for f in os.listdir(base_dir):
        if f.lower().endswith(extensions):
            return base_dir
    for d in os.listdir(base_dir):
        sub = os.path.join(base_dir, d)
        if os.path.isdir(sub):
            for f in os.listdir(sub):
                if f.lower().endswith(extensions):
                    return sub
    return base_dir


def _collect_image_files(image_dir):
    extensions = ('.pdg', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif')
    image_dir = find_pdg_dir(image_dir)
    files = []
    for f in os.listdir(image_dir):
        if f.lower().endswith(extensions):
            full_path = os.path.join(image_dir, f)
            if is_image_file(full_path):
                files.append((f, full_path))
    files.sort(key=lambda x: get_sort_key(x[0]))
    return files


def _save_batch_as_pdf(image_paths, pdf_path):
    images = []
    first = None
    try:
        for p in image_paths:
            img = Image.open(p)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            if first is None:
                first = img
            else:
                images.append(img)
        if first is None:
            return False
        first.save(pdf_path, 'PDF', save_all=True, append_images=images, quality=95)
        return True
    finally:
        if first:
            try: first.close()
            except: pass
        for img in images:
            try: img.close()
            except: pass


def _merge_pdfs(pdf_paths, output_path):
    writer = PdfWriter()
    for p in pdf_paths:
        reader = PdfReader(p)
        for page in reader.pages:
            writer.add_page(page)
    with open(output_path, 'wb') as f:
        writer.write(f)
    writer.close()


def images_to_pdf(image_dir, pdf_path, log_fn=print, on_page_done=None):
    files = _collect_image_files(image_dir)
    total = len(files)
    if total == 0:
        return False, '没有有效图片文件'

    log_fn(f'  有效图片: {total} 个，分批处理（每批 {BATCH_SIZE} 页）')

    if total <= BATCH_SIZE:
        image_paths = [p for _, p in files]
        ok = _save_batch_as_pdf(image_paths, pdf_path)
        if ok:
            if on_page_done:
                for i in range(1, total + 1):
                    on_page_done(i, total)
            return True, total
        return False, '生成PDF失败'

    tmp_dir = tempfile.mkdtemp(prefix='pdg2pdf_')
    batch_pdfs = []
    page_done = 0
    batch_idx = 0

    try:
        for start in range(0, total, BATCH_SIZE):
            batch = files[start:start + BATCH_SIZE]
            batch_paths = [p for _, p in batch]
            batch_pdf = os.path.join(tmp_dir, f'batch_{batch_idx:04d}.pdf')

            ok = _save_batch_as_pdf(batch_paths, batch_pdf)
            if not ok:
                return False, f'批次 {batch_idx} 转换失败'

            batch_pdfs.append(batch_pdf)
            batch_idx += 1
            page_done += len(batch)

            if on_page_done:
                for i in range(page_done - len(batch) + 1, page_done + 1):
                    on_page_done(i, total)

        _merge_pdfs(batch_pdfs, pdf_path)
        pdf_size = os.path.getsize(pdf_path)
        log_fn(f'  [完成] {total} 页 → PDF ({pdf_size:,} bytes)')
        return True, total

    except Exception as e:
        return False, str(e)

    finally:
        for p in batch_pdfs:
            try: os.remove(p)
            except: pass
        try: os.rmdir(tmp_dir)
        except: pass


# ============ 拟物风格组件 ============

class SkeuoButton(tk.Canvas):
    """拟物风格按钮"""
    def __init__(self, parent, text='', command=None, bg=COL_BTN_FACE,
                 fg=COL_TEXT, accent=COL_ACCENT, width=160, height=36, **kw):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, bg=parent['bg'])
        self.command = command
        self.bg_normal = bg
        self.bg_press = COL_BTN_PRESS
        self.fg = fg
        self.accent = accent
        self.w = width
        self.h = height
        self._text = text
        self._enabled = True
        self._draw_normal()

        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Enter>', lambda e: self._draw_hover() if self._enabled else None)
        self.bind('<Leave>', lambda e: self._draw_normal() if self._enabled else None)

    def _draw_normal(self):
        self.delete('all')
        w, h = self.w, self.h
        # 阴影
        self.create_rectangle(2, 3, w, h+1, fill=COL_SHADOW, outline='')
        # 按钮主体 - 上亮下暗渐变模拟
        self.create_rectangle(1, 1, w-1, h//2, fill='#DDD8CE', outline='')
        self.create_rectangle(1, h//2, w-1, h-1, fill=self.bg_normal, outline='')
        # 边框
        self.create_rectangle(1, 1, w-2, h-2, outline=COL_BORDER, width=1)
        self.create_line(2, 2, w-3, 2, fill='#E8E4DC')  # 顶部高光
        self.create_line(2, 2, 2, h-3, fill='#E8E4DC')  # 左侧高光
        # 文字
        self.create_text(w//2, h//2, text=self._text, fill=self.fg,
                         font=('Microsoft YaHei', 10, 'bold'))

    def _draw_hover(self):
        self.delete('all')
        w, h = self.w, self.h
        self.create_rectangle(2, 3, w, h+1, fill=COL_SHADOW, outline='')
        self.create_rectangle(1, 1, w//2, h-1, fill='#E0DBD2', outline='')
        self.create_rectangle(w//2, 1, w-1, h-1, fill='#D8D3CA', outline='')
        self.create_rectangle(1, 1, w-2, h-2, outline='#A09888', width=1)
        self.create_line(2, 2, w-3, 2, fill='#EEEAE4')
        self.create_text(w//2, h//2, text=self._text, fill=self.fg,
                         font=('Microsoft YaHei', 10, 'bold'))

    def _draw_pressed(self):
        self.delete('all')
        w, h = self.w, self.h
        self.create_rectangle(1, 1, w-1, h-1, fill=self.bg_press, outline=COL_DARK_LINE)
        self.create_line(2, h-3, w-2, h-3, fill=COL_SHADOW)
        self.create_line(w-3, 2, w-3, h-2, fill=COL_SHADOW)
        self.create_text(w//2+1, h//2+1, text=self._text, fill=self.fg,
                         font=('Microsoft YaHei', 10, 'bold'))

    def _on_press(self, e):
        if self._enabled:
            self._draw_pressed()

    def _on_release(self, e):
        if self._enabled:
            self._draw_normal()
            if self.command:
                self.command()

    def config_state(self, enabled):
        self._enabled = enabled
        if enabled:
            self._draw_normal()
        else:
            self.delete('all')
            w, h = self.w, self.h
            self.create_rectangle(1, 1, w-1, h-1, fill=COL_FRAME_BG, outline=COL_BORDER)
            self.create_text(w//2, h//2, text=self._text, fill=COL_TEXT_SUB,
                             font=('Microsoft YaHei', 10))


class SkeuoProgress(tk.Canvas):
    """拟物风格进度条"""
    def __init__(self, parent, width=400, height=22, **kw):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, bg=parent['bg'])
        self.w = width
        self.h = height
        self._value = 0
        self._max = 100
        self._draw_bar()

    def _draw_bar(self):
        self.delete('all')
        w, h = self.w, self.h
        # 外框 - 凹陷效果
        self.create_rectangle(0, 0, w, h, fill=COL_PROGRESS_BG, outline='')
        self.create_rectangle(0, 0, w, h, outline=COL_DARK_LINE, width=1)
        self.create_line(1, 1, w-2, 1, fill=COL_SHADOW)
        self.create_line(1, 1, 1, h-2, fill=COL_SHADOW)
        # 进度填充
        if self._value > 0 and self._max > 0:
            fill_w = max(2, int((self._value / self._max) * (w - 4)))
            # 渐变模拟：上半亮、下半暗
            self.create_rectangle(2, 2, fill_w+2, h//2,
                                  fill='#8DB87E', outline='')
            self.create_rectangle(2, h//2, fill_w+2, h-2,
                                  fill=COL_PROGRESS, outline='')
            # 高光
            self.create_line(2, 2, fill_w+2, 2, fill='#A0CC90')

    def set_value(self, value, maximum=100):
        self._value = value
        self._max = maximum
        self._draw_bar()


# ============ GUI ============

class ZipToPdfApp:
    def __init__(self):
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title('ZIP → PDF 转换工具')
        self.root.geometry('640x560')
        self.root.resizable(True, True)
        self.root.configure(bg=COL_BG)

        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.converting = False
        self.total_pages = 0
        self.processed_pages = 0
        self._page_start_time = None
        self.setup_ui()

        if len(sys.argv) > 1:
            self.root.after(500, lambda: self.process_files(sys.argv[1:]))

    def _make_sep(self, parent):
        """拟物风格分隔线"""
        f = tk.Frame(parent, bg=COL_BG, height=4)
        f.pack(fill='x', padx=5, pady=6)
        tk.Frame(f, bg=COL_SHADOW, height=1).pack(fill='x', padx=2)
        tk.Frame(f, bg='#F5F2EC', height=1).pack(fill='x', padx=2)

    def setup_ui(self):
        # === 顶部标题栏 - 仿皮革质感 ===
        header = tk.Frame(self.root, bg=COL_ACCENT, height=52)
        header.pack(fill='x')
        header.pack_propagate(False)

        tk.Label(header, text='📖  ZIP → PDF  转换工具',
                 font=('Microsoft YaHei', 15, 'bold'),
                 bg=COL_ACCENT, fg='#FFF8F0').pack(side='left', padx=20, pady=8)

        tk.Label(header, text='流式处理 · 大文件不爆内存',
                 font=('Microsoft YaHei', 9),
                 bg=COL_ACCENT, fg='#D4C4B0').pack(side='right', padx=20)

        # === 主体容器 ===
        body = tk.Frame(self.root, bg=COL_BG)
        body.pack(fill='both', expand=True, padx=16, pady=10)

        # --- 拖拽区域 ---
        self.drop_outer = tk.Frame(body, bg=COL_BG)
        self.drop_outer.pack(fill='x', pady=(0, 8))

        # 外层阴影
        tk.Frame(self.drop_outer, bg=COL_SHADOW, height=2).pack(fill='x', padx=(3, 0))
        shadow_right = tk.Frame(self.drop_outer, bg=COL_SHADOW, width=2)
        shadow_right.pack(side='right', fill='y', pady=(0, 2))

        self.drop_frame = tk.Frame(self.drop_outer, bg=COL_DROP_BG,
                                    relief='solid', bd=1,
                                    highlightbackground=COL_DROP_BD,
                                    highlightthickness=1)
        self.drop_frame.pack(fill='x', padx=(0, 2), pady=(0, 2))

        self.drop_label = tk.Label(self.drop_frame,
                                    text='🔽  拖拽 ZIP 文件或文件夹到此处  🔽\n\n（也可以点击下方按钮选择文件）',
                                    font=('Microsoft YaHei', 11),
                                    bg=COL_DROP_BG, fg=COL_TEXT_SUB,
                                    justify='center', cursor='hand2')
        self.drop_label.pack(pady=22)

        if HAS_DND:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self.on_drop)

        # --- 按钮区 ---
        btn_frame = tk.Frame(body, bg=COL_BG)
        btn_frame.pack(fill='x', pady=6)

        self.btn_select = SkeuoButton(btn_frame, text='📂  选择 ZIP 文件',
                                       command=self.select_files,
                                       width=170, height=38)
        self.btn_select.pack(side='left', padx=(0, 8))

        self.btn_folder = SkeuoButton(btn_frame, text='📁  选择文件夹',
                                       command=self.select_folder,
                                       bg=COL_GREEN, fg='white',
                                       width=170, height=38)
        self.btn_folder.pack(side='left')

        # --- 进度区 ---
        prog_frame = tk.Frame(body, bg=COL_BG)
        prog_frame.pack(fill='x', pady=8)

        self.progress_bar = SkeuoProgress(prog_frame, width=580, height=24)
        self.progress_bar.pack(fill='x')

        # 页数 + 速度行
        info_frame = tk.Frame(body, bg=COL_BG)
        info_frame.pack(fill='x', pady=2)

        self.counter_label = tk.Label(info_frame, text='0 / 0 页',
                                       font=('Consolas', 13, 'bold'),
                                       bg=COL_BG, fg=COL_ACCENT)
        self.counter_label.pack(side='left')

        self.speed_label = tk.Label(info_frame, text='',
                                     font=('Microsoft YaHei', 9),
                                     bg=COL_BG, fg=COL_TEXT_SUB)
        self.speed_label.pack(side='right')

        self.status_label = tk.Label(body, text='就绪',
                                      font=('Microsoft YaHei', 9),
                                      bg=COL_BG, fg=COL_TEXT)
        self.status_label.pack(fill='x', pady=(2, 6))

        self._make_sep(body)

        # --- 日志区 ---
        log_header = tk.Label(body, text='📋  转换日志',
                               font=('Microsoft YaHei', 9, 'bold'),
                               bg=COL_BG, fg=COL_TEXT, anchor='w')
        log_header.pack(fill='x', pady=(0, 3))

        log_frame = tk.Frame(body, bg=COL_DARK_LINE, bd=1)
        log_frame.pack(fill='both', expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8, font=('Consolas', 9),
            state='disabled', bg=COL_LOG_BG, fg=COL_LOG_FG,
            insertbackground='white', bd=0,
            highlightthickness=0, relief='flat')
        self.log_text.pack(fill='both', expand=True, padx=1, pady=1)

        # --- 底栏 ---
        self._make_sep(body)
        footer = tk.Frame(body, bg=COL_BG)
        footer.pack(fill='x', pady=(0, 4))
        tk.Label(footer, text=f'输出目录: {self.app_dir}',
                 font=('Microsoft YaHei', 8),
                 bg=COL_BG, fg=COL_TEXT_SUB, anchor='w').pack(fill='x')

    def log(self, msg):
        self.log_text.config(state='normal')
        self.log_text.insert('end', msg + '\n')
        self.log_text.see('end')
        self.log_text.config(state='disabled')

    def set_status(self, msg):
        self.status_label.config(text=msg)

    def _update_page_progress(self, current, total):
        def _do():
            self.processed_pages = current
            self.total_pages = total
            self.progress_bar.set_value(current, total)
            self.counter_label.config(text=f'{current} / {total} 页')
            if self._page_start_time and current > 0:
                elapsed = (datetime.now() - self._page_start_time).total_seconds()
                speed = current / elapsed if elapsed > 0 else 0
                remaining = (total - current) / speed if speed > 0 else 0
                self.speed_label.config(
                    text=f'{speed:.1f} 页/秒 · 剩余 {remaining:.0f} 秒')
        self.root.after(0, _do)

    def on_drop(self, event):
        if self.converting:
            return
        raw = event.data
        files = []
        i = 0
        while i < len(raw):
            if raw[i] == '{':
                j = raw.index('}', i)
                files.append(raw[i+1:j])
                i = j + 2
            elif raw[i] == ' ':
                i += 1
            else:
                j = i
                while j < len(raw) and raw[j] != ' ':
                    j += 1
                files.append(raw[i:j])
                i = j
        self.process_files(files)

    def select_files(self):
        if self.converting:
            return
        from tkinter import filedialog
        files = filedialog.askopenfilenames(
            title='选择 ZIP 文件',
            filetypes=[('ZIP 文件', '*.zip'), ('所有文件', '*.*')])
        if files:
            self.process_files(list(files))

    def select_folder(self):
        if self.converting:
            return
        from tkinter import filedialog
        folder = filedialog.askdirectory(title='选择包含 ZIP 文件的文件夹')
        if folder:
            zip_files = [os.path.join(folder, f) for f in os.listdir(folder)
                         if f.lower().endswith('.zip')]
            if zip_files:
                self.process_files(zip_files)
            else:
                messagebox.showinfo('提示', '所选文件夹中没有 ZIP 文件')

    def process_files(self, file_list):
        zip_files = []
        for f in file_list:
            f = f.strip()
            if not f:
                continue
            if os.path.isfile(f) and f.lower().endswith('.zip'):
                zip_files.append(f)
            elif os.path.isdir(f):
                for item in os.listdir(f):
                    if item.lower().endswith('.zip'):
                        zip_files.append(os.path.join(f, item))
        if not zip_files:
            messagebox.showinfo('提示', '没有找到 ZIP 文件')
            return

        self.converting = True
        self.btn_select.config_state(False)
        self.btn_folder.config_state(False)
        self.progress_bar.set_value(0)
        self.counter_label.config(text='0 / 0 页')
        self.speed_label.config(text='')
        self._page_start_time = None
        threading.Thread(target=self.convert_thread, args=(zip_files,), daemon=True).start()

    def convert_thread(self, zip_files):
        total_zips = len(zip_files)
        success = 0
        fail = 0
        skip = 0
        grand_processed_pages = 0

        self.root.after(0, lambda: self.log(f'\n{"="*50}'))
        self.root.after(0, lambda: self.log(f'开始处理 {total_zips} 个 ZIP 文件（每批 {BATCH_SIZE} 页）'))
        self.root.after(0, lambda: self.log(f'输出目录: {self.app_dir}'))
        self.root.after(0, lambda: self.log(f'{"="*50}'))

        for idx, zip_path in enumerate(zip_files, 1):
            zip_name = os.path.splitext(os.path.basename(zip_path))[0]
            pdf_path = os.path.join(self.app_dir, f'{zip_name}.pdf')
            extract_dir = os.path.join(self.app_dir, zip_name)

            self.root.after(0, lambda n=zip_name: self.set_status(f'[{idx}/{total_zips}] {n}'))
            self.root.after(0, lambda n=zip_name, i=idx, t=total_zips:
                            self.log(f'\n[{i}/{t}] {n}'))

            if os.path.exists(pdf_path):
                self.root.after(0, lambda: self.log(f'  [跳过] PDF已存在'))
                skip += 1
                continue

            if not os.path.exists(extract_dir):
                self.root.after(0, lambda: self.log(f'  解压中...'))
                ok, err = extract_zip(zip_path, extract_dir)
                if not ok:
                    self.root.after(0, lambda e=err: self.log(f'  [错误] 解压失败: {e}'))
                    fail += 1
                    continue
            else:
                self.root.after(0, lambda: self.log(f'  解压目录已存在'))

            self._page_start_time = datetime.now()
            self.root.after(0, lambda: self.log(f'  转换中...'))

            def log_from_thread(msg):
                self.root.after(0, lambda m=msg: self.log(m))

            ok, result = images_to_pdf(
                extract_dir, pdf_path,
                log_fn=log_from_thread,
                on_page_done=self._update_page_progress
            )

            if ok:
                success += 1
                grand_processed_pages += result
                self.root.after(0, lambda r=result:
                                self.log(f'  [完成] {r} 页'))
                try:
                    os.remove(zip_path)
                    self.root.after(0, lambda: self.log(f'  [清理] 已删除源文件'))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log(f'  [警告] 删除源文件失败: {err}'))
                try:
                    shutil.rmtree(extract_dir, ignore_errors=True)
                    self.root.after(0, lambda: self.log(f'  [清理] 已删除解压目录'))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log(f'  [警告] 删除解压目录失败: {err}'))
            else:
                fail += 1
                self.root.after(0, lambda r=result:
                                self.log(f'  [错误] {r}'))

        self.root.after(0, lambda: self.log(f'\n{"="*50}'))
        self.root.after(0, lambda: self.log(
            f'完成！成功: {success} | 跳过: {skip} | 失败: {fail} | 总页数: {grand_processed_pages}'))
        self.root.after(0, lambda: self.set_status(
            f'完成 — 成功:{success} 跳过:{skip} 失败:{fail} ({grand_processed_pages}页)'))
        self.root.after(0, lambda: self.progress_bar.set_value(100, 100))

        def reset_ui():
            self.converting = False
            self.btn_select.config_state(True)
            self.btn_folder.config_state(True)
            summary = (
                f'转换任务全部完成！\n\n'
                f'✅ 成功: {success} 个\n'
                f'⏭ 跳过: {skip} 个\n'
                f'❌ 失败: {fail} 个\n'
                f'📄 总页数: {grand_processed_pages} 页\n\n'
                f'PDF 保存位置:\n{self.app_dir}'
            )
            messagebox.showinfo('任务完成', summary)
        self.root.after(0, reset_ui)

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = ZipToPdfApp()
    app.run()
