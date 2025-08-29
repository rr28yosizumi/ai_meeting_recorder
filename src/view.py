import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

class RecorderView:
    def __init__(self, master):
        self.master = master
        master.title("議事録作成ツール")
        self._build_layout()

    def _build_layout(self):
        row = 0
        self.fig = Figure(figsize=(8,2))
        self.ax_mic = self.fig.add_subplot(121)
        self.ax_spk = self.fig.add_subplot(122)
        for ax in [self.ax_mic, self.ax_spk]:
            ax.set_facecolor('black')
            ax.set_ylim(-1, 1)
            ax.set_xlim(0, 1000)
            ax.tick_params(axis='x', colors='white')
            ax.tick_params(axis='y', colors='white')
            for spine in ax.spines.values():
                spine.set_color('white')
        self.line_mic, = self.ax_mic.plot([], [], color='lime')
        self.line_spk, = self.ax_spk.plot([], [], color='cyan')
        self.ax_mic.set_title('mic')
        self.ax_spk.set_title('speaker')
        self.canvas = FigureCanvasTkAgg(self.fig, self.master)
        self.canvas.get_tk_widget().grid(row=row, column=0, columnspan=4)
        row += 1

        # Placeholder variables (will be wired by controller)
        self.mic_device_var = tk.StringVar()
        self.spk_device_var = tk.StringVar()
        self.lang_var = tk.StringVar(value='ja')
        self.gemini_key_var = tk.StringVar()
        self.output_path = tk.StringVar()
        self.wav_path = tk.StringVar()

        ttk.Label(self.master, text="マイク入力デバイス:").grid(row=row, column=0)
        self.mic_device_combo = ttk.Combobox(self.master, textvariable=self.mic_device_var, state="readonly")
        self.mic_device_combo.grid(row=row, column=1, columnspan=3, sticky='ew')
        row += 1

        ttk.Label(self.master, text="スピーカー出力デバイス:").grid(row=row, column=0)
        self.spk_device_combo = ttk.Combobox(self.master, textvariable=self.spk_device_var, state="readonly")
        self.spk_device_combo.grid(row=row, column=1, columnspan=3, sticky='ew')
        row += 1

        ttk.Label(self.master, text="文字起こし言語:").grid(row=row, column=0)
        self.lang_combo = ttk.Combobox(self.master, textvariable=self.lang_var, state="readonly", values=["日本語 (ja)", "英語 (en)"])
        self.lang_combo.grid(row=row, column=1, columnspan=1, sticky='ew')
        row += 1

        ttk.Label(self.master, text="Gemini APIキー:").grid(row=row, column=0)
        self.gemini_key_entry = ttk.Entry(self.master, textvariable=self.gemini_key_var, show='*')
        self.gemini_key_entry.grid(row=row, column=1, columnspan=3, sticky='ew')
        row += 1

        ttk.Label(self.master, text="議事録出力先:").grid(row=row, column=0)
        self.output_entry = ttk.Entry(self.master, textvariable=self.output_path)
        self.output_entry.grid(row=row, column=1, columnspan=2, sticky='ew')
        self.btn_output = ttk.Button(self.master, text='参照')
        self.btn_output.grid(row=row, column=3)
        row += 1

        ttk.Label(self.master, text="録音WAV保存先:").grid(row=row, column=0)
        self.wav_entry = ttk.Entry(self.master, textvariable=self.wav_path)
        self.wav_entry.grid(row=row, column=1, columnspan=2, sticky='ew')
        self.btn_wav = ttk.Button(self.master, text='参照')
        self.btn_wav.grid(row=row, column=3)
        row += 1

        ttk.Label(self.master, text="Geminiプロンプト:").grid(row=row, column=0)
        self.prompt_entry = scrolledtext.ScrolledText(self.master, height=4)
        self.prompt_entry.grid(row=row, column=1, columnspan=3, sticky='nsew')
        self.master.grid_rowconfigure(row, weight=1)
        for c in (1,2,3):
            self.master.grid_columnconfigure(c, weight=1)
        row += 1

        self.btn_record = ttk.Button(self.master, text='録音開始')
        self.btn_record.grid(row=row, column=0)
        self.btn_pause = ttk.Button(self.master, text='録音中断', state='disabled')
        self.btn_pause.grid(row=row, column=1)
        self.btn_resume = ttk.Button(self.master, text='録音再開', state='disabled')
        self.btn_resume.grid(row=row, column=2)
        self.btn_stop = ttk.Button(self.master, text='録音終了', state='disabled')
        self.btn_stop.grid(row=row, column=3)
        row += 1

        self.btn_transcribe = ttk.Button(self.master, text='WAVから文字起こし・要約')
        self.btn_transcribe.grid(row=row, column=0, columnspan=4, sticky='ew')
        row += 1

        ttk.Label(self.master, text='ログ:').grid(row=row, column=0)
        self.log_box = scrolledtext.ScrolledText(self.master, height=4, state='disabled')
        self.log_box.grid(row=row, column=1, columnspan=3, sticky='ew')

    def log(self, msg: str):
        self.log_box['state'] = 'normal'
        self.log_box.insert('end', msg + '\n')
        self.log_box.see('end')
        self.log_box['state'] = 'disabled'
        self.master.update_idletasks()

    def update_waveform(self, mic_frames, spk_frames):
        # mic_frames/spk_frames: list of numpy arrays or None
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
        self.ax_mic.set_ylim(-1,1)
        self.ax_spk.set_ylim(-1,1)
        self.canvas.draw()

    def ask_save_text(self):
        return filedialog.asksaveasfilename(defaultextension='.txt')

    def ask_open_wav(self):
        return filedialog.askopenfilename(defaultextension='.wav', filetypes=[('WAV files','*.wav')])

    def show_info(self, title, msg):
        messagebox.showinfo(title, msg)
