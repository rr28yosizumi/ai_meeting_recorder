import tkinter as tk
import threading
import time
import os
from .controller import RecorderController
from . import ai_control

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
    container = tk.Frame(splash, bd=1, relief='flat', bg='white')
    container.pack(padx=8, pady=8)
    img_label = None
    logo_path_candidates = [
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
        img_label = tk.Label(container, image=logo_img, bg='white')
        img_label.image = logo_img  # keep ref
        img_label.pack(padx=10, pady=(10,4))
    lbl = tk.Label(container, text='AI Meeting Recorder 起動中...\nモデル読み込み中', padx=30, pady=10, font=('Segoe UI', 11), bg='white')
    lbl.pack()
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

    # メインGUI
    root = tk.Tk()
    root.title('AI Meeting Recorder (MVC)')
    controller = RecorderController(root)
    root.protocol('WM_DELETE_WINDOW', controller.on_close)
    root.mainloop()

if __name__ == '__main__':
    main()
