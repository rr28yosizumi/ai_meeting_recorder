import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import queue
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import os
import numpy as np
import scipy.io.wavfile as wav
import sounddevice as sd

from .setting import AppSettings
from . import ai_control

INIT_YAML = os.path.join(os.getcwd(), "init.yml")

class RecorderGUI:
    def on_close(self):
        # 現在のGUI値をsettingsへ反映
        self.settings.minutes_file = self.output_path.get()
        self.settings.gemini_api_key = self.gemini_key_var.get()
        self.settings.prompt = self.prompt_entry.get("1.0", tk.END)
        # 必要に応じて他のパラメータも反映
        self.settings.save(INIT_YAML)
        self.master.destroy()

    def __init__(self, master, settings=None):
        self.master = master
        master.title("議事録作成ツール")
        # 設定ファイル読み込み
        if os.path.exists(INIT_YAML):
            self.settings = AppSettings.load(INIT_YAML)
        else:
            self.settings = settings or AppSettings()
        # 終了時に設定保存
        self.master.protocol("WM_DELETE_WINDOW", self.on_close)

        row= 0

        # 音声波形の表示用
        self.is_recording = False
        self.is_paused = False
        self.audio_queue = queue.Queue()
        self.frames = []
        self.stream = None
        self.device_var = tk.StringVar()
        self.output_path = tk.StringVar(value=self.settings.minutes_file)
        self.gemini_key_var = tk.StringVar(value=self.settings.gemini_api_key)
        self.fig = Figure(figsize=(5,2))
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('black')  # 背景を黒
        self.line, = self.ax.plot([], [], color='lime')  # 初期は緑色
        self.preview_stream = None
        self.preview_frames = []
        self.ax.set_ylim(-1, 1)
        self.ax.set_xlim(0, 1000)
        self.ax.tick_params(axis='x', colors='white')  # x軸目盛り文字色を白
        self.ax.tick_params(axis='y', colors='white')  # y軸目盛り文字色を白
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['right'].set_color('white')
        self.canvas = FigureCanvasTkAgg(self.fig, master)
        self.canvas.get_tk_widget().grid(row=row, column=0, columnspan=4)
        row += 1

        # デバイス選択（マイク）
        ttk.Label(master, text="マイク入力デバイス:").grid(row=row, column=0)
        self.mic_device_var = tk.StringVar()
        mic_devices = [d['name'] for d in sd.query_devices() if d['max_input_channels'] > 0]
        self.mic_device_combo = ttk.Combobox(master, textvariable=self.mic_device_var, state="readonly")
        self.mic_device_combo['values'] = mic_devices
        self.mic_device_combo.current(0)
        self.mic_device_combo.grid(row=row, column=1, columnspan=3, sticky="ew")
        self.mic_device_combo.bind('<<ComboboxSelected>>', self.on_device_change)
        row += 1

        # デバイス選択（スピーカー）
        ttk.Label(master, text="スピーカー出力デバイス:").grid(row=row, column=0)
        self.spk_device_var = tk.StringVar()
        spk_devices = [d['name'] for d in sd.query_devices() if d['max_input_channels'] > 0]
        self.spk_device_combo = ttk.Combobox(master, textvariable=self.spk_device_var, state="readonly")
        self.spk_device_combo['values'] = spk_devices
        self.spk_device_combo.current(0)
        self.spk_device_combo.grid(row=row, column=1, columnspan=3, sticky="ew")
        self.spk_device_combo.bind('<<ComboboxSelected>>', self.on_device_change)
        row += 1

        # 言語選択コンボボックス
        ttk.Label(master, text="文字起こし言語:").grid(row=row, column=0)
        self.lang_var = tk.StringVar(value="ja")
        self.lang_combo = ttk.Combobox(master, textvariable=self.lang_var, state="readonly")
        self.lang_combo['values'] = ["日本語 (ja)", "英語 (en)"]
        self.lang_combo.current(0)
        self.lang_combo.grid(row=row, column=1, columnspan=1, sticky="ew")
        row += 1

         # Gemini APIキー入力
        ttk.Label(master, text="Gemini APIキー:").grid(row=row, column=0)
        self.gemini_key_entry = ttk.Entry(master, textvariable=self.gemini_key_var, show="*")
        self.gemini_key_entry.grid(row=row, column=1, columnspan=3, sticky="ew")
        row += 1

        # 出力先指定
        ttk.Label(master, text="議事録出力先:").grid(row=row, column=0)
        self.output_entry = ttk.Entry(master, textvariable=self.output_path)
        self.output_entry.grid(row=row, column=1, columnspan=2, sticky="ew")
        self.btn_output = ttk.Button(master, text="参照", command=self.select_output)
        self.btn_output.grid(row=row, column=3)
        row += 1

        # プロンプト入力
        ttk.Label(master, text="Geminiプロンプト:").grid(row=row, column=0)
        self.prompt_entry = scrolledtext.ScrolledText(master, height=4)
        self.prompt_entry.grid(row=row, column=1, columnspan=3, sticky="nsew")
        self.prompt_entry.insert(tk.END, self.settings.prompt)
        # ウィンドウサイズに合わせてプロンプト欄が拡大・縮小するよう設定
        master.grid_rowconfigure(row, weight=1)
        master.grid_columnconfigure(1, weight=1)
        master.grid_columnconfigure(2, weight=1)
        master.grid_columnconfigure(3, weight=1)
        row += 1

        # ボタン
        self.btn_record = ttk.Button(master, text="録音開始", command=self.start_recording)
        self.btn_record.grid(row=row, column=0)
        self.btn_pause = ttk.Button(master, text="録音中断", command=self.pause_recording, state="disabled")
        self.btn_pause.grid(row=row, column=1)
        self.btn_resume = ttk.Button(master, text="録音再開", command=self.resume_recording, state="disabled")
        self.btn_resume.grid(row=row, column=2)
        self.btn_stop = ttk.Button(master, text="録音終了", command=self.stop_recording, state="disabled")
        self.btn_stop.grid(row=row, column=3)
        row += 1

        # ログ表示
        ttk.Label(master, text="ログ:").grid(row=row, column=0)
        self.log_box = scrolledtext.ScrolledText(master, height=4, state="disabled")
        self.log_box.grid(row=row, column=1, columnspan=3, sticky="ew")
        row += 1

        self.record_thread = None
        self.start_preview_stream()
        self.update_waveform()
        
    def on_device_change(self, event=None):
        self.stop_preview_stream()
        self.start_preview_stream()

    def start_preview_stream(self):
        # プレビュー用ストリーム開始
        mic_name = self.mic_device_var.get()
        mic_id = [i for i, d in enumerate(sd.query_devices()) if d['name'] == mic_name][0]
        self.preview_frames = []
        def preview_callback(indata, frames_count, time, status):
            if status:
                self.log(f"プレビュー: {status}")
            self.preview_frames.append(indata.copy())
            if len(self.preview_frames) > 10:
                self.preview_frames.pop(0)
        try:
            self.preview_stream = sd.InputStream(samplerate=self.settings.sample_rate, channels=self.settings.channels, device=mic_id, callback=preview_callback)
            self.preview_stream.start()
        except Exception as e:
            self.log(f"プレビューエラー: {e}")

    def stop_preview_stream(self):
        if self.preview_stream:
            try:
                self.preview_stream.stop()
                self.preview_stream.close()
            except Exception:
                pass
            self.preview_stream = None

    def log(self, msg):
        self.log_box['state'] = 'normal'
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
        self.log_box['state'] = 'disabled'
        self.master.update_idletasks()  # 即時反映

    def select_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt")
        if path:
            self.output_path.set(path)

    def start_recording(self):
        self.stop_preview_stream()
        self.line.set_color('red')  # 波形色を赤に
        self.is_recording = True
        self.is_paused = False
        self.frames = []
        self.mic_queue = queue.Queue()
        self.spk_queue = queue.Queue()
        self.btn_record['state'] = 'disabled'
        self.btn_pause['state'] = 'normal'
        self.btn_resume['state'] = 'disabled'
        self.btn_stop['state'] = 'normal'
        self.log("録音開始")
        mic_name = self.mic_device_var.get()
        spk_name = self.spk_device_var.get()
        mic_id = [i for i, d in enumerate(sd.query_devices()) if d['name'] == mic_name][0]
        spk_id = [i for i, d in enumerate(sd.query_devices()) if d['name'] == spk_name][0]
        self.record_thread = threading.Thread(target=self.record_audio, args=(mic_id, spk_id))
        self.record_thread.start()

    def pause_recording(self):
        self.is_paused = True
        self.btn_pause['state'] = 'disabled'
        self.btn_resume['state'] = 'normal'
        self.log("録音中断")

    def resume_recording(self):
        self.is_paused = False
        self.btn_pause['state'] = 'normal'
        self.btn_resume['state'] = 'disabled'
        self.log("録音再開")

    def stop_recording(self):
        self.line.set_color('lime')  # 波形色を緑に
        self.is_recording = False
        self.btn_record['state'] = 'normal'
        self.btn_pause['state'] = 'disabled'
        self.btn_resume['state'] = 'disabled'
        self.btn_stop['state'] = 'disabled'
        self.log("録音終了")
        if self.record_thread:
            self.record_thread.join()
        # WAV保存
        if self.frames:
            audio = np.concatenate(self.frames, axis=0)
            # float32 → int16 変換（WAV標準）
            audio_int16 = np.clip(audio, -1, 1)
            audio_int16 = (audio_int16 * 32767).astype(np.int16)
            wav.write(self.settings.wav_file, self.settings.sample_rate, audio_int16)
            self.log(f"録音保存: {self.settings.wav_file}")
            self.process_minutes()
        else:
            self.log("録音データがありません")
        self.start_preview_stream()

    def record_audio(self, mic_id, spk_id):
        def mic_callback(indata, frames_count, time, status):
            if status:
                self.log(f"マイク: {status}")
            if not self.is_paused and self.is_recording:
                self.mic_queue.put(indata.copy())
        def spk_callback(indata, frames_count, time, status):
            if status:
                self.log(f"スピーカー: {status}")
            if not self.is_paused and self.is_recording:
                self.spk_queue.put(indata.copy())
        try:
            with sd.InputStream(samplerate=self.settings.sample_rate, channels=self.settings.channels, device=mic_id, callback=mic_callback), \
                 sd.InputStream(samplerate=self.settings.sample_rate, channels=self.settings.channels, device=spk_id, callback=spk_callback):
                while self.is_recording:
                    try:
                        mic_frame = self.mic_queue.get(timeout=0.1)
                        spk_frame = self.spk_queue.get(timeout=0.1)
                        # shapeを揃える
                        min_len = min(len(mic_frame), len(spk_frame))
                        mic_frame = mic_frame[:min_len]
                        spk_frame = spk_frame[:min_len]
                        # 合成（平均）
                        mixed = ((mic_frame.astype(np.float32) + spk_frame.astype(np.float32)) / 2).astype(np.float32)
                        self.frames.append(mixed)
                    except queue.Empty:
                        continue
        except Exception as e:
            self.log(f"録音エラー: {e}")

    def update_waveform(self):
        if self.is_recording and self.frames:
            data = np.concatenate(self.frames, axis=0)
            if len(data) > 1000:
                data = data[-1000:]
            self.line.set_data(np.arange(len(data)), data.flatten())
            self.ax.set_xlim(0, len(data))
            self.ax.set_ylim(-1, 1)
            self.canvas.draw()
        elif not self.is_recording and self.preview_frames:
            data = np.concatenate(self.preview_frames, axis=0)
            if len(data) > 1000:
                data = data[-1000:]
            self.line.set_data(np.arange(len(data)), data.flatten())
            self.ax.set_xlim(0, len(data))
            self.ax.set_ylim(-1, 1)
            self.canvas.draw()
        self.master.after(100, self.update_waveform)

    def process_minutes(self):
        # 言語選択値を取得
        lang = "ja" if self.lang_var.get().startswith("日本語") else "en"
        ai_control.create_meeting_report(
            self.prompt_entry.get("1.0", tk.END),
            self.settings.wav_file,
            self.settings.chunk_dir,
            self.settings.record_seconds,
            self.output_path.get(),
            self.gemini_key_var.get(),
            logger=self.log,
            lang=lang
        )
    

def main():
    root = tk.Tk()
    app = RecorderGUI(root)
    root.mainloop()