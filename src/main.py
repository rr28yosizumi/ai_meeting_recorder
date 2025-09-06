import tkinter as tk
import threading
import time
import os
from .controller import RecorderController
from .view import BG_COLOR, FG_COLOR
from . import ai_control
from .resource_util import resource_path
try:
    import customtkinter as ctk
    _USE_CTK = True
except Exception:
    ctk = None
    _USE_CTK = False

import sys
if getattr(sys, 'frozen', False):
    import pyi_splash

def _center(win):
    win.update_idletasks()
    w = win.winfo_width(); h = win.winfo_height()
    sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
    x = (sw - w)//2; y = (sh - h)//2
    win.geometry(f"{w}x{h}+{x}+{y}")

def main():
    # スプラッシュ表示
    splash = tk.Tk()
    splash.overrideredirect(True)
    try:
        splash.configure(bg=BG_COLOR)
    except Exception:
        pass
    container = tk.Frame(splash, bd=1, relief='flat', bg=BG_COLOR)
    container.pack(padx=8, pady=8)
    img_label = None
    # リソース探索 (PyInstaller --onefile 対応 resource_util 経由)
    logo_path_candidates = [
        resource_path('logo.png'),
        resource_path('origin_logo.png'),
        os.path.join(os.getcwd(), 'logo.png'),
        os.path.join(os.path.dirname(__file__), 'logo.png'),
    ]
    logo_img = None
    for p in logo_path_candidates:
        if os.path.exists(p):
            try:
                logo_img = tk.PhotoImage(file=p)
                break
            except Exception:
                logo_img = None
    if logo_img is not None:
        img_label = tk.Label(container, image=logo_img, bg=BG_COLOR)
        img_label.image = logo_img  # keep ref
        img_label.pack(padx=10, pady=(10,4))
    lbl = tk.Label(container, text='AI Meeting Recorder 起動中...\nモデル読み込み中', padx=30, pady=10, font=('Segoe UI', 11), bg=BG_COLOR, fg=FG_COLOR)
    lbl.pack()
    # アイコン設定: PNG(推奨) -> ICO フォールバック (PyInstaller対応)
    icon_image = None
    icon_path_png = resource_path('amr24.png')
    icon_path_ico = resource_path('amr.ico')
    try:
        if os.path.exists(icon_path_png):
            try:
                icon_image = tk.PhotoImage(file=icon_path_png)
                splash.iconphoto(False, icon_image)
                splash._icon_image = icon_image
            except Exception:
                icon_image = None
        if icon_image is None and os.path.exists(icon_path_ico):
            try:
                splash.iconbitmap(icon_path_ico)
            except Exception:
                pass
    except Exception:
        pass
    splash.update()
    _center(splash)

    load_done = {'ok': False}

    def preload():
        start = time.time()
        ai_control.preload_models(logger=lambda m: None)
        load_done['ok'] = True
        elapsed = time.time() - start
        # 体感で一瞬で消えないよう最小表示時間
        min_show = 0.8
        if elapsed < min_show:
            time.sleep(min_show - elapsed)
        try:
            splash.after(0, splash.destroy)
        except Exception:
            pass

    threading.Thread(target=preload, daemon=True).start()
    splash.mainloop()

    if getattr(sys, 'frozen', False):
        pyi_splash.close()

    # メインGUI
    # CustomTkinter 利用可能ならメインウィンドウも CTk を使用
    if _USE_CTK:
        root = ctk.CTk()
    else:
        root = tk.Tk()
    root.title('AI Meeting Recorder (MVC)')
    # メインウィンドウにもアイコン適用
    try:
        if icon_image is not None:
            root.iconphoto(False, icon_image)
            root._icon_image = icon_image
        elif os.path.exists(icon_path_png):
            icon_image = tk.PhotoImage(file=icon_path_png)
            root.iconphoto(False, icon_image)
            root._icon_image = icon_image
        elif os.path.exists(icon_path_ico):
            root.iconbitmap(icon_path_ico)
    except Exception:
        pass
    controller = RecorderController(root)
    root.protocol('WM_DELETE_WINDOW', controller.on_close)
    root.mainloop()

if __name__ == '__main__':
    main()
