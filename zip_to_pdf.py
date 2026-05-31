# -*- coding: utf-8 -*-
"""
批量转换工具：ZIP解压 + PDG转PDF（流式，低内存版）
用法：将此脚本放到包含ZIP文件的目录，运行即可。

功能：
  1. 解压目录下所有 .zip 文件到同名子目录
  2. 将每个子目录中的 .pdg 文件（实际为图片）合并为一个 PDF
  3. 分批处理，每批 BATCH_SIZE 页，避免大文件爆内存
  4. 自动识别 PNG/JPEG/BMP/TIFF 格式
  5. 按文件名排序（封面→目录→正文）
  6. 生成详细日志

支持的PDG文件名格式：
  cov001.pdg, !00001.pdg, 000001.pdg, fow001.pdg, bok001.pdg 等
"""
import os
import sys
import zipfile
import tempfile
import shutil
from datetime import datetime
from PIL import Image
from pypdf import PdfWriter, PdfReader

BATCH_SIZE = 20  # 每批处理的页数，控制内存峰值


def get_sort_key(filename):
    """PDG文件排序：按超星规范排序（封面→前言→目录→正文→附录→封底）"""
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
    """检查文件是否为有效图片（不加载到内存，只读头部）"""
    try:
        with Image.open(filepath) as img:
            img.verify()
        return True
    except Exception:
        return False


def extract_zip(zip_path, extract_dir):
    """解压ZIP文件"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        return True, None
    except Exception as e:
        return False, str(e)


def find_pdg_dir(base_dir):
    """Find the actual directory containing PDG files (may be in a subdirectory)"""
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
    """收集并排序目录中的图片文件列表"""
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
    """将一批图片路径保存为单个PDF（逐张打开→转RGB→收集→保存→全部关闭）"""
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
    """将多个PDF合并为一个"""
    writer = PdfWriter()
    for p in pdf_paths:
        reader = PdfReader(p)
        for page in reader.pages:
            writer.add_page(page)
    with open(output_path, 'wb') as f:
        writer.write(f)
    writer.close()


def images_to_pdf(image_dir, pdf_path, log=print, on_page_done=None):
    """
    将目录中的图片合并为PDF（流式分批，低内存版）

    参数:
        image_dir:   图片所在目录
        pdf_path:    输出PDF路径
        log:         日志回调 log(msg)
        on_page_done: 进度回调 on_page_done(current_page, total_pages)

    返回:
        (True, page_count) 或 (False, error_msg)
    """
    files = _collect_image_files(image_dir)
    total = len(files)
    if total == 0:
        msg = '没有有效图片文件'
        log(f'  [跳过] {msg}')
        return False, msg

    log(f'  有效图片: {total} 个，分批处理（每批 {BATCH_SIZE} 页）')

    # 如果总量不大，直接一次性处理（省去临时文件和合并开销）
    if total <= BATCH_SIZE:
        image_paths = [p for _, p in files]
        ok = _save_batch_as_pdf(image_paths, pdf_path)
        if ok:
            if on_page_done:
                for i in range(1, total + 1):
                    on_page_done(i, total)
            log(f'  [完成] {total} 页 → PDF')
            return True, total
        else:
            return False, '生成PDF失败'

    # 大文件：分批处理 → 合并
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
                log(f'  [错误] 批次 {batch_idx} 转换失败')
                return False, f'批次 {batch_idx} 转换失败'

            batch_pdfs.append(batch_pdf)
            batch_idx += 1

            # 更新进度
            page_done += len(batch)
            if on_page_done:
                for i in range(page_done - len(batch) + 1, page_done + 1):
                    on_page_done(i, total)
            log(f'  批次 {batch_idx}: {len(batch)} 页完成 ({page_done}/{total})')

        # 合并所有批次PDF
        log(f'  合并 {len(batch_pdfs)} 个批次...')
        _merge_pdfs(batch_pdfs, pdf_path)

        pdf_size = os.path.getsize(pdf_path)
        log(f'  [完成] {total} 页 → PDF ({pdf_size:,} bytes)')
        return True, total

    except Exception as e:
        log(f'  [错误] {e}')
        return False, str(e)

    finally:
        # 清理临时文件
        for p in batch_pdfs:
            try: os.remove(p)
            except: pass
        try: os.rmdir(tmp_dir)
        except: pass


def main():
    work_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    log_file = os.path.join(work_dir, f'convert_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log(f'ZIP→PDG→PDF 批量转换工具（流式低内存版）')
    log(f'执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    log(f'工作目录: {work_dir}')
    log(f'每批页数: {BATCH_SIZE}')
    log(f'{"="*80}')

    zip_files = [f for f in os.listdir(work_dir) if f.lower().endswith('.zip')]
    if not zip_files:
        log('目录下没有 .zip 文件!')
        input('按回车退出...')
        return

    log(f'找到 {len(zip_files)} 个 ZIP 文件\n')

    total_zips = len(zip_files)
    extracted = 0
    converted = 0
    skipped = 0
    errors = 0
    total_pages = 0

    for idx, zip_file in enumerate(sorted(zip_files), 1):
        zip_path = os.path.join(work_dir, zip_file)
        zip_name = os.path.splitext(zip_file)[0]
        extract_dir = os.path.join(work_dir, zip_name)
        pdf_path = os.path.join(work_dir, f'{zip_name}.pdf')

        log(f'[{idx}/{total_zips}] 处理: {zip_file}')

        if os.path.exists(pdf_path):
            log(f'  [跳过] PDF已存在')
            skipped += 1
            continue

        if not os.path.exists(extract_dir):
            log(f'  解压中...')
            ok, err = extract_zip(zip_path, extract_dir)
            if not ok:
                log(f'  [错误] 解压失败: {err}')
                errors += 1
                continue
            extracted += 1
        else:
            log(f'  解压目录已存在')

        log(f'  转换中...')
        ok, result = images_to_pdf(extract_dir, pdf_path, log)
        if ok:
            converted += 1
            total_pages += result
            # 删除源ZIP
            try:
                os.remove(zip_path)
                log(f'  [清理] 已删除源文件: {zip_file}')
            except Exception as e:
                log(f'  [警告] 删除源文件失败: {e}')
            # 删除解压目录
            try:
                shutil.rmtree(extract_dir, ignore_errors=True)
                log(f'  [清理] 已删除解压目录')
            except Exception as e:
                log(f'  [警告] 删除解压目录失败: {e}')
        else:
            errors += 1
        log('')

    log(f'{"="*80}')
    log(f'执行结果汇总:')
    log(f'  ZIP文件总数: {total_zips}')
    log(f'  新解压: {extracted}')
    log(f'  成功转PDF: {converted} ({total_pages} 页)')
    log(f'  跳过: {skipped}')
    log(f'  错误: {errors}')

    with open(log_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines))
    print(f'\n日志已保存: {log_file}')
    input('按回车退出...')


if __name__ == '__main__':
    main()
