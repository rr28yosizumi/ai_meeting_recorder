"""View layer (CustomTkinter版)

CustomTkinter が利用できない環境でも動作するようフォールバックを備える。
Controller から期待される公開属性:
  mic_device_combo, spk_device_combo, lang_combo, gemini_key_entry,
  output_entry, wav_entry, btn_output, btn_wav, prompt_entry,
  btn_record, btn_pause, btn_resume, btn_stop, btn_transcribe,
  log_box, update_waveform(), log(), ask_save_text(), ask_open_wav(), show_info()
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

try:
    import customtkinter as ctk
    _USE_CTK = True
except Exception:  # ライブラリ未導入時フォールバック
    ctk = None
    _USE_CTK = False

# カラーテーマ設定
BG_COLOR = '#001a33'   # 濃いネイビー
FG_COLOR = 'white'


class RecorderView:
    def __init__(self, master):
        self.master = master
        if _USE_CTK:
            ctk.set_appearance_mode("system")
            ctk.set_default_color_theme("blue")
            try:
                master.configure(fg_color=BG_COLOR)
            except Exception:
                pass
        master.title("議事録作成ツール")
        if not _USE_CTK:
            try:
                master.configure(bg=BG_COLOR)
            except Exception:
                pass
        self._build_layout()

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------
    def _build_layout(self):
        row = 0
        # Matplotlib Figure (黒背景波形)
        self.fig = Figure(figsize=(8, 2))
        self.ax_mic = self.fig.add_subplot(121)
        self.ax_spk = self.fig.add_subplot(122)
        # Figure / Axes 背景色をアプリ共通の濃いネイビーに統一
        try:
            self.fig.patch.set_facecolor(BG_COLOR)
        except Exception:
            pass
        for ax in (self.ax_mic, self.ax_spk):
            ax.set_facecolor(BG_COLOR)
            ax.set_ylim(-1, 1)
            ax.set_xlim(0, 1000)
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            for spine in ax.spines.values():
                spine.set_color('white')
        self.line_mic, = self.ax_mic.plot([], [], color='lime')
        self.line_spk, = self.ax_spk.plot([], [], color='cyan')
        self.ax_mic.set_title('mic', color='white')
        self.ax_spk.set_title('speaker', color='white')
        # 念のため既存タイトルオブジェクトにも色適用（古い Matplotlib 互換）
        try:
            self.ax_mic.title.set_color('white')
            self.ax_spk.title.set_color('white')
        except Exception:
            pass
        self.canvas = FigureCanvasTkAgg(self.fig, self.master)
        self.canvas.get_tk_widget().grid(row=row, column=0, columnspan=4, padx=4, pady=4, sticky='nsew')
        row += 1

        # Tk変数
        self.mic_device_var = tk.StringVar()
        self.spk_device_var = tk.StringVar()
        self.lang_var = tk.StringVar(value='日本語 (ja)')
        self.gemini_key_var = tk.StringVar()
        self.output_path = tk.StringVar()
        self.wav_path = tk.StringVar()

        # ヘルパ: CTk が無ければ ttk 風代替 (ここでは標準 tk) を使用
        WidgetLabel = ctk.CTkLabel if _USE_CTK else tk.Label
        WidgetEntry = ctk.CTkEntry if _USE_CTK else tk.Entry
        WidgetButton = ctk.CTkButton if _USE_CTK else tk.Button
        WidgetTextbox = ctk.CTkTextbox if _USE_CTK else tk.Text
        WidgetCombo = ctk.CTkComboBox if _USE_CTK else tk.OptionMenu
        # 共通スタイル kwargs (メソッドスコープ内に配置)
        label_kwargs = {'text_color': FG_COLOR} if _USE_CTK else {'fg': FG_COLOR, 'bg': BG_COLOR}
        entry_kwargs = {'text_color': FG_COLOR, 'fg_color': '#003355'} if _USE_CTK else {'fg': FG_COLOR, 'bg': '#002244', 'insertbackground': FG_COLOR}
        btn_kwargs = {'text_color': FG_COLOR, 'fg_color': '#003c66', 'hover_color': '#005999'} if _USE_CTK else {'fg': FG_COLOR, 'bg': '#003c66', 'activebackground': '#005999', 'activeforeground': FG_COLOR}
        textbox_kwargs = {'text_color': FG_COLOR, 'fg_color': '#002244'} if _USE_CTK else {'fg': FG_COLOR, 'bg': '#002244', 'insertbackground': FG_COLOR}

        # マイクデバイス
        WidgetLabel(self.master, text="マイク入力デバイス:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='w')
        if _USE_CTK:
            self.mic_device_combo = WidgetCombo(self.master, variable=self.mic_device_var, values=[])
        else:
            self.mic_device_combo = tk.OptionMenu(self.master, self.mic_device_var, "")
            self.mic_device_combo.configure(bg='#002244', fg=FG_COLOR, highlightthickness=0, activebackground='#003c66', activeforeground=FG_COLOR)
        self.mic_device_combo.grid(row=row, column=1, columnspan=3, sticky='ew', padx=4, pady=4)
        row += 1

        # スピーカーデバイス
        WidgetLabel(self.master, text="スピーカー出力デバイス:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='w')
        if _USE_CTK:
            self.spk_device_combo = WidgetCombo(self.master, variable=self.spk_device_var, values=[])
        else:
            self.spk_device_combo = tk.OptionMenu(self.master, self.spk_device_var, "")
            self.spk_device_combo.configure(bg='#002244', fg=FG_COLOR, highlightthickness=0, activebackground='#003c66', activeforeground=FG_COLOR)
        self.spk_device_combo.grid(row=row, column=1, columnspan=3, sticky='ew', padx=4, pady=4)
        row += 1

        # 言語
        WidgetLabel(self.master, text="文字起こし言語:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='w')
        if _USE_CTK:
            self.lang_combo = WidgetCombo(self.master, variable=self.lang_var, values=["日本語 (ja)", "英語 (en)"])
            try:
                self.lang_combo.set(self.lang_var.get())
            except Exception:
                pass
        else:
            self.lang_combo = tk.OptionMenu(self.master, self.lang_var, "日本語 (ja)", "英語 (en)")
            self.lang_combo.configure(bg='#002244', fg=FG_COLOR, highlightthickness=0, activebackground='#003c66', activeforeground=FG_COLOR)
        self.lang_combo.grid(row=row, column=1, columnspan=1, sticky='ew', padx=4, pady=4)
        row += 1

        # Gemini API キー
        WidgetLabel(self.master, text="Gemini APIキー:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='w')
        self.gemini_key_entry = WidgetEntry(self.master, textvariable=self.gemini_key_var, show='*', **entry_kwargs)
        self.gemini_key_entry.grid(row=row, column=1, columnspan=3, sticky='ew', padx=4, pady=4)
        row += 1

        # 出力先
        WidgetLabel(self.master, text="議事録出力先:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='w')
        self.output_entry = WidgetEntry(self.master, textvariable=self.output_path, **entry_kwargs)
        self.output_entry.grid(row=row, column=1, columnspan=2, sticky='ew', padx=4, pady=4)
        self.btn_output = WidgetButton(self.master, text='参照', **btn_kwargs)
        self.btn_output.grid(row=row, column=3, padx=4, pady=4, sticky='ew')
        row += 1

        # WAV保存先
        WidgetLabel(self.master, text="録音WAV保存先:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='w')
        self.wav_entry = WidgetEntry(self.master, textvariable=self.wav_path, **entry_kwargs)
        self.wav_entry.grid(row=row, column=1, columnspan=2, sticky='ew', padx=4, pady=4)
        self.btn_wav = WidgetButton(self.master, text='参照', **btn_kwargs)
        self.btn_wav.grid(row=row, column=3, padx=4, pady=4, sticky='ew')
        row += 1

        # プロンプト
        WidgetLabel(self.master, text="Geminiプロンプト:", **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='nw')
        self.prompt_entry = WidgetTextbox(self.master, height=8, **textbox_kwargs)
        if not _USE_CTK:
            self.prompt_entry.configure(height=6)
        self.prompt_entry.grid(row=row, column=1, columnspan=3, sticky='nsew', padx=4, pady=4)
        self.master.grid_rowconfigure(row, weight=1)
        for c in (1, 2, 3):
            self.master.grid_columnconfigure(c, weight=1)
        row += 1

        # 録音ボタン群
        self.btn_record = WidgetButton(self.master, text='録音開始', **btn_kwargs)
        self.btn_record.grid(row=row, column=0, padx=4, pady=6, sticky='ew')
        self.btn_pause = WidgetButton(self.master, text='録音中断', state='disabled', **btn_kwargs)
        self.btn_pause.grid(row=row, column=1, padx=4, pady=6, sticky='ew')
        self.btn_resume = WidgetButton(self.master, text='録音再開', state='disabled', **btn_kwargs)
        self.btn_resume.grid(row=row, column=2, padx=4, pady=6, sticky='ew')
        self.btn_stop = WidgetButton(self.master, text='録音終了', state='disabled', **btn_kwargs)
        self.btn_stop.grid(row=row, column=3, padx=4, pady=6, sticky='ew')
        row += 1

        # 文字起こし実行
        self.btn_transcribe = WidgetButton(self.master, text='WAVから文字起こし・要約', **btn_kwargs)
        self.btn_transcribe.grid(row=row, column=0, columnspan=4, padx=4, pady=6, sticky='ew')
        row += 1

        # ログ
        WidgetLabel(self.master, text='ログ:', **label_kwargs).grid(row=row, column=0, padx=4, pady=4, sticky='nw')
        self.log_box = WidgetTextbox(self.master, height=8, **textbox_kwargs)
        if _USE_CTK:
            self.log_box.configure(state='disabled')
        else:
            self.log_box.configure(state='disabled', height=8)
        self.log_box.grid(row=row, column=1, columnspan=3, sticky='nsew', padx=4, pady=4)
        self.master.grid_rowconfigure(row, weight=1)

    # ------------------------------------------------------------------
    # ログ出力
    # ------------------------------------------------------------------
    def log(self, msg: str):
        if _USE_CTK:
            self.log_box.configure(state='normal')
            self.log_box.insert('end', msg + '\n')
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        else:
            self.log_box.configure(state='normal')
            self.log_box.insert('end', msg + '\n')
            self.log_box.see('end')
            self.log_box.configure(state='disabled')
        self.master.update_idletasks()

    # ------------------------------------------------------------------
    # 波形更新
    # ------------------------------------------------------------------
    def update_waveform(self, mic_frames, spk_frames):
        # 録音状態に応じてライン色を切り替え
        try:
            if getattr(self, '_is_recording', False):
                self.line_mic.set_color('red')
                self.line_spk.set_color('red')
            else:
                self.line_mic.set_color('lime')
                self.line_spk.set_color('cyan')
        except Exception:
            pass
        if mic_frames:
            mic_data = np.concatenate(mic_frames, axis=0)
            if len(mic_data) > 1000:
                mic_data = mic_data[-1000:]
            self.line_mic.set_data(range(len(mic_data)), mic_data.flatten())
            self.ax_mic.set_xlim(0, len(mic_data))
        else:
            self.line_mic.set_data([], [])
            self.ax_mic.set_xlim(0, 1000)
        if spk_frames:
            spk_data = np.concatenate(spk_frames, axis=0)
            if len(spk_data) > 1000:
                spk_data = spk_data[-1000:]
            self.line_spk.set_data(range(len(spk_data)), spk_data.flatten())
            self.ax_spk.set_xlim(0, len(spk_data))
        else:
            self.line_spk.set_data([], [])
            self.ax_spk.set_xlim(0, 1000)
        self.ax_mic.set_ylim(-1, 1)
        self.ax_spk.set_ylim(-1, 1)
        self.canvas.draw()

    def set_recording_state(self, is_recording: bool):
        self._is_recording = is_recording

    # ------------------------------------------------------------------
    # ダイアログ
    # ------------------------------------------------------------------
    def ask_save_text(self):
        return filedialog.asksaveasfilename(defaultextension='.txt')

    def ask_open_wav(self):
        return filedialog.askopenfilename(defaultextension='.wav', filetypes=[('WAV files', '*.wav')])

    def show_info(self, title, msg):
        messagebox.showinfo(title, msg)

    # ------------------------------------------------------------------
    # デバイスリスト更新 (Controller から呼び出し)
    # ------------------------------------------------------------------
    def set_device_options(self, mic_list, spk_list):
        self._set_option_values(self.mic_device_combo, self.mic_device_var, mic_list)
        self._set_option_values(self.spk_device_combo, self.spk_device_var, spk_list)
        # 先頭を自動選択（未設定時）
        if mic_list and not self.mic_device_var.get():
            self.mic_device_var.set(mic_list[0])
            if _USE_CTK:
                try:
                    self.mic_device_combo.set(mic_list[0])
                except Exception:
                    pass
        if spk_list and not self.spk_device_var.get():
            self.spk_device_var.set(spk_list[0])
            if _USE_CTK:
                try:
                    self.spk_device_combo.set(spk_list[0])
                except Exception:
                    pass

    def _set_option_values(self, widget, var, values):
        if _USE_CTK:
            try:
                widget.configure(values=values)
            except Exception:
                pass
        else:
            menu = widget['menu']
            menu.delete(0, 'end')
            for v in values:
                menu.add_command(label=v, command=lambda val=v: var.set(val))
