# -*- coding: utf-8 -*-
"""PyInstaller 打包脚本"""
import os
import sys
from PyInstaller.__main__ import run

# 确保图标存在
ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'book_icon.ico')
if not os.path.exists(ico_path):
    print('图标文件不存在，生成中...')
    from PIL import Image, ImageDraw
    def make_icon(size=256):
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        pad = 20
        draw.polygon([(size//2,pad+10),(pad+5,pad+30),(pad+5,size-pad-10),(size//2,size-pad)],
                      fill=(245,240,230), outline=(120,100,80))
        draw.polygon([(size//2,pad+10),(size-pad-5,pad+30),(size-pad-5,size-pad-10),(size//2,size-pad)],
                      fill=(255,252,245), outline=(120,100,80))
        draw.line([(size//2,pad+10),(size//2,size-pad)], fill=(100,80,60), width=3)
        for i in range(6):
            y = pad+60+i*28
            draw.line([(pad+30,y),(size//2-20,y)], fill=(160,140,120), width=2)
            draw.line([(size//2+20,y),(size-pad-30,y)], fill=(160,140,120), width=2)
        rx = size//2+30
        draw.polygon([(rx,pad+10),(rx+12,pad+10),(rx+12,pad+80),(rx+6,pad+70),(rx,pad+80)], fill=(200,50,50))
        return img
    icon = make_icon(256)
    sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)]
    icons = [icon.resize(s, Image.LANCZOS) for s in sizes]
    icons[0].save(ico_path, format='ICO', sizes=sizes, append_images=icons[1:])
    print(f'图标已生成: {ico_path}')

args = [
    'zip_to_pdf_gui.py',
    '--name=ZIP转PDF工具',
    '--onefile',
    '--windowed',
    '--noconfirm',
    '--clean',
    f'--icon={ico_path}',
    '--hidden-import=PIL',
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=tkinterdnd2',
    '--hidden-import=tkinterdnd2.TkinterDnD',
    '--collect-all=tkinterdnd2',
    '--collect-data=tkinterdnd2',
    '--collect-submodules=tkinterdnd2',
    '--distpath=dist',
]
run(args)
