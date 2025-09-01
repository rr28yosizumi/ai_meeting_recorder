import threading
import queue
import sounddevice as sd
import numpy as np
import os
from .resource_util import resource_path as _res_path
import tkinter as tk
try:
    from PIL import Image, ImageSequence, ImageTk  # 高品質GIF用
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False
from .model import RecorderModel
from .view import RecorderView, BG_COLOR, FG_COLOR
from . import ai_control

class RecorderController:
    def __init__(self, master):
        self.model = RecorderModel()
        self.view = RecorderView(master)
        self.is_recording = False
        self.is_paused = False
        self.preview_streams = []
        self.mic_queue = queue.Queue()
        self.spk_queue = queue.Queue()
        self.preview_mic_frames = []
        self.preview_spk_frames = []
        self.record_thread = None
        self._wire_events()
        self._populate_devices()
        # 初期値を設定ファイルから反映
        self.view.output_path.set(self.model.settings.minutes_file)
        self.view.wav_path.set(self.model.settings.wav_file)
        self.view.gemini_key_var.set(self.model.settings.gemini_api_key)
        if self.model.settings.prompt:
            try:
                self.view.prompt_entry.delete('1.0', 'end')
                self.view.prompt_entry.insert('end', self.model.settings.prompt)
            except Exception:
                pass
        self.start_preview()
        self._schedule_waveform_update()
        # 議事録処理状態
        self.processing_minutes = False
        self.processing_overlay = None

    # 汎用ボタン状態変更（CustomTkinter/Tk 両対応）
    def _set_state(self, widget, state: str):
        for fn in (lambda w,s: w.configure(state=s), lambda w,s: w.__setitem__('state', s)):
            try:
                fn(widget, state)
                break
            except Exception:
                continue

    def _set_states(self, mapping: dict):
        for w, st in mapping.items():
            self._set_state(w, st)
        try:
            self.view.master.update_idletasks()
        except Exception:
            pass

    def on_close(self):
        """ウィンドウクローズ時に設定を保存"""
        self.model.settings.minutes_file = self.view.output_path.get()
        self.model.settings.wav_file = self.view.wav_path.get()
        self.model.settings.gemini_api_key = self.view.gemini_key_var.get()
        try:
            self.model.settings.prompt = self.view.prompt_entry.get('1.0', 'end')
        except Exception:
            pass
        self.model.save_settings()
        # 録音中なら停止
        try:
            self.is_recording = False
        except Exception:
            pass
        self.view.master.destroy()

    def _wire_events(self):
        v = self.view
        v.btn_output.configure(command=self.select_output)
        v.btn_wav.configure(command=self.select_wav)
        v.btn_record.configure(command=self.start_recording)
        v.btn_pause.configure(command=self.pause_recording)
        v.btn_resume.configure(command=self.resume_recording)
        v.btn_stop.configure(command=self.stop_recording)
        v.btn_transcribe.configure(command=self.transcribe_and_summarize)
        # 変数トレースでツールキット非依存の変更検知
        try:
            self.view.mic_device_var.trace_add('write', lambda *a: self.restart_preview())
            self.view.spk_device_var.trace_add('write', lambda *a: self.restart_preview())
        except Exception:
            pass

    def _populate_devices(self):
        devices = sd.query_devices()
        mic_list = [d['name'] for d in devices if d['max_input_channels'] > 0]
        spk_list = [d['name'] for d in devices if d['max_input_channels'] > 0]
        try:
            self.view.set_device_options(mic_list, spk_list)
        except Exception:
            # フォールバック (旧 ttk Combobox の可能性など)
            try:
                self.view.mic_device_combo['values'] = mic_list
                self.view.spk_device_combo['values'] = spk_list
                if mic_list:
                    self.view.mic_device_combo.current(0)
                if spk_list:
                    self.view.spk_device_combo.current(0)
            except Exception:
                pass

    def select_output(self):
        path = self.view.ask_save_text()
        if path:
            self.view.output_path.set(path)
            self.model.settings.minutes_file = path
            self.model.save_settings()

    def select_wav(self):
        path = self.view.ask_open_wav()
        if path:
            self.view.wav_path.set(path)
            self.model.settings.wav_file = path
            self.model.save_settings()
        self._update_transcribe_button_state()

    def _update_transcribe_button_state(self):
        if self.is_recording:
            self.view.btn_transcribe['state'] = 'disabled'
            return
        wav_file = self.view.wav_path.get()
        if not wav_file or not os.path.exists(wav_file):
            self.view.btn_transcribe['state'] = 'disabled'
        else:
            self.view.btn_transcribe['state'] = 'normal'

    def start_preview(self):
        self.stop_preview()
        mic_name = self.view.mic_device_var.get()
        spk_name = self.view.spk_device_var.get()
        devices = sd.query_devices()
        mic_id = [i for i,d in enumerate(devices) if d['name']==mic_name][0] if mic_name else None
        spk_id = [i for i,d in enumerate(devices) if d['name']==spk_name][0] if spk_name else None
        self.preview_mic_frames = []
        self.preview_spk_frames = []
        def mic_cb(indata, frames, time, status):
            if status:
                self.view.log(f"プレビュー(マイク): {status}")
            self.preview_mic_frames.append(indata.copy())
            if len(self.preview_mic_frames) > 10:
                self.preview_mic_frames.pop(0)
        def spk_cb(indata, frames, time, status):
            if status:
                self.view.log(f"プレビュー(スピーカー): {status}")
            self.preview_spk_frames.append(indata.copy())
            if len(self.preview_spk_frames) > 10:
                self.preview_spk_frames.pop(0)
        try:
            if mic_id is not None:
                s1 = sd.InputStream(samplerate=self.model.settings.sample_rate, channels=self.model.settings.channels, device=mic_id, callback=mic_cb)
                s1.start()
                self.preview_streams.append(s1)
            if spk_id is not None:
                s2 = sd.InputStream(samplerate=self.model.settings.sample_rate, channels=self.model.settings.channels, device=spk_id, callback=spk_cb)
                s2.start()
                self.preview_streams.append(s2)
        except Exception as e:
            self.view.log(f"プレビューエラー: {e}")

    def stop_preview(self):
        for s in self.preview_streams:
            try:
                s.stop(); s.close()
            except Exception:
                pass
        self.preview_streams = []
        self.preview_mic_frames = []
        self.preview_spk_frames = []

    def restart_preview(self):
        if not self.is_recording:
            self.start_preview()

    def start_recording(self):
        self.stop_preview()
        self.is_recording = True
        self.is_paused = False
        self.model.reset()
        self._set_states({
            self.view.btn_record: 'disabled',
            self.view.btn_pause: 'normal',
            self.view.btn_resume: 'disabled',
            self.view.btn_stop: 'normal'
        })
        try:
            self.view.set_recording_state(True)
        except Exception:
            pass
        self.view.log('録音開始')
        mic_name = self.view.mic_device_var.get()
        spk_name = self.view.spk_device_var.get()
        devices = sd.query_devices()
        mic_id = [i for i,d in enumerate(devices) if d['name']==mic_name][0]
        spk_id = [i for i,d in enumerate(devices) if d['name']==spk_name][0]
        self.model.same_device = (mic_id == spk_id)
        if self.model.same_device:
            self.view.log('マイクとスピーカーが同じデバイスのため、マイクのみ録音します')
            self.record_thread = threading.Thread(target=self._record_loop, args=(mic_id, None))
        else:
            self.record_thread = threading.Thread(target=self._record_loop, args=(mic_id, spk_id))
        self.record_thread.start()
        self._update_transcribe_button_state()

    def pause_recording(self):
        if not self.is_recording: return
        self.is_paused = True
        self._set_states({
            self.view.btn_pause: 'disabled',
            self.view.btn_resume: 'normal'
        })
        self.view.log('録音中断')

    def resume_recording(self):
        if not self.is_recording: return
        self.is_paused = False
        self._set_states({
            self.view.btn_pause: 'normal',
            self.view.btn_resume: 'disabled'
        })
        self.view.log('録音再開')

    def stop_recording(self):
        if not self.is_recording: return
        self.is_recording = False
        if self.record_thread:
            self.record_thread.join()
        self._set_states({
            self.view.btn_record: 'normal',
            self.view.btn_pause: 'disabled',
            self.view.btn_resume: 'disabled',
            self.view.btn_stop: 'disabled'
        })
        try:
            self.view.set_recording_state(False)
        except Exception:
            pass
        self.view.log('録音終了')
        if self.model.mix_and_save(logger=self.view.log):
            # 非同期で議事録生成
            self._start_minutes_processing()
            # 録音保存後、最新のwavパスをGUIへ反映
            self.view.wav_path.set(self.model.settings.wav_file)
        self.restart_preview()
        self._update_transcribe_button_state()

    def _record_loop(self, mic_id, spk_id):
        def mic_cb(indata, frames, time, status):
            if status:
                self.view.log(f"マイク: {status}")
            if not self.is_paused and self.is_recording:
                self.model.mic_frames.append(indata.copy())
        def spk_cb(indata, frames, time, status):
            if status:
                self.view.log(f"スピーカー: {status}")
            if not self.is_paused and self.is_recording and spk_id is not None:
                self.model.spk_frames.append(indata.copy())
        try:
            if spk_id is None:
                with sd.InputStream(samplerate=self.model.settings.sample_rate, channels=self.model.settings.channels, device=mic_id, callback=mic_cb):
                    while self.is_recording:
                        sd.sleep(100)
            else:
                with sd.InputStream(samplerate=self.model.settings.sample_rate, channels=self.model.settings.channels, device=mic_id, callback=mic_cb), \
                     sd.InputStream(samplerate=self.model.settings.sample_rate, channels=self.model.settings.channels, device=spk_id, callback=spk_cb):
                    while self.is_recording:
                        sd.sleep(100)
        except Exception as e:
            self.view.log(f"録音エラー: {e}")

    def _schedule_waveform_update(self):
        if self.is_recording:
            mic_frames = self.model.mic_frames
            spk_frames = self.model.spk_frames
            # 録音中は赤色表示
            try:
                self.view.line_mic.set_color('red')
                self.view.line_spk.set_color('red')
            except Exception:
                pass
        else:
            mic_frames = self.preview_mic_frames
            spk_frames = self.preview_spk_frames
            # 非録音時は元の色へ戻す
            try:
                self.view.line_mic.set_color('lime')
                self.view.line_spk.set_color('cyan')
            except Exception:
                pass
        self.view.update_waveform(mic_frames, spk_frames)
        self._update_transcribe_button_state()
        self.view.master.after(100, self._schedule_waveform_update)

    def _process_minutes(self):
        lang = 'ja' if self.view.lang_var.get().startswith('日本語') else 'en'
        result = ai_control.create_meeting_report(
            self.view.prompt_entry.get('1.0', 'end'),
            self.model.settings.wav_file,
            self.model.settings.chunk_dir,
            self.model.settings.record_seconds,
            self.view.output_path.get(),
            self.view.gemini_key_var.get(),
            logger=self.view.log,
            lang=lang
        )
        # 念のため None ガード
        if result is None:
            result = {'success': False, 'error': 'create_meeting_report returned None'}
        if not result.get('success'):
            err = result.get('error')
            if err:
                self.view.log(f"議事録生成失敗: {err}")
        else:
            if result.get('summary_file'):
                self.view.log(f"要約ファイル: {result['summary_file']}")
        return result

    def transcribe_and_summarize(self):
        wav_file = self.view.wav_path.get()
        if not os.path.exists(wav_file):
            self.view.log(f"指定されたWAVファイルが存在しません: {wav_file}")
            return
        self.view.log(f"WAVファイルから文字起こし・要約を実行: {wav_file}")
        self._start_minutes_processing()

    # ---------------- 議事録生成 非同期処理 ----------------
    def _start_minutes_processing(self):
        if self.processing_minutes:
            self.view.log('既に議事録処理中です')
            return
        self.processing_minutes = True
        self._show_processing_overlay()
        # 処理中は関連ボタンを無効化
        self._set_states({
            self.view.btn_record: 'disabled',
            self.view.btn_pause: 'disabled',
            self.view.btn_resume: 'disabled',
            self.view.btn_stop: 'disabled',
            self.view.btn_transcribe: 'disabled'
        })
        th = threading.Thread(target=self._minutes_thread_body, daemon=True)
        th.start()

    def _minutes_thread_body(self):
        try:
            result = self._process_minutes()
        except Exception as e:
            self.view.log(f"議事録処理中例外: {e}")
            result = {'success': False, 'error': str(e)}
        # UI スレッドへ戻す
        self.view.master.after(0, lambda r=result: self._finish_minutes_processing(r))

    def _finish_minutes_processing(self, result):
        # 型ガード
        if not isinstance(result, dict):
            result = {'success': False, 'error': 'unexpected result object'}
        self.processing_minutes = False
        self._hide_processing_overlay()
        # ボタン再有効化
        self._set_states({
            self.view.btn_record: 'normal',
            self.view.btn_transcribe: 'normal'
        })
        self._update_transcribe_button_state()
        if result.get('success'):
            self.view.show_info('要約完了', '要約処理が終了しました。')
        else:
            self.view.show_info('要約失敗', '要約処理でエラーが発生しました。ログを確認してください。')

    def _show_processing_overlay(self):
        try:
            if getattr(self, 'processing_overlay', None) and tk.Toplevel.winfo_exists(self.processing_overlay):
                return
            top = tk.Toplevel(self.view.master)
            top.title('処理中')
            top.transient(self.view.master)
            top.grab_set()
            try:
                top.configure(bg=BG_COLOR)
            except Exception:
                pass
            # テキストラベル (背景/前景をテーマ適用)
            lbl_text = tk.Label(top, text='議事録生成中...\nしばらくお待ちください', padx=20, pady=10, bg=BG_COLOR, fg=FG_COLOR)
            lbl_text.pack()

            # GIF アニメーション (output.gif) を読み込み (存在しない場合はスキップ)
            gif_path_candidates = [
                _res_path('output.gif'),  # 推奨配置場所 (PyInstaller対応)
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output.gif'),
                os.path.join(os.getcwd(), 'output.gif')
            ]
            gif_path = None
            for p in gif_path_candidates:
                if os.path.exists(p):
                    gif_path = p
                    break
            if gif_path:
                try:
                    if _PIL_AVAILABLE:
                        # Pillow を使って全フレーム読み込み（透明度/最適化考慮）
                        img = Image.open(gif_path)
                        frames = []
                        durations = []
                        for i, frame in enumerate(ImageSequence.Iterator(img)):
                            # RGBA へ変換して画質を維持
                            fr = frame.convert('RGBA')
                            frames.append(ImageTk.PhotoImage(fr))
                            # フレーム毎の duration(ms) を取得（無い場合 80ms）
                            d = frame.info.get('duration', img.info.get('duration', 80))
                            durations.append(d if d > 0 else 80)
                            if i > 300:  # 安全上限
                                break
                        if frames:
                            gif_label = tk.Label(top, image=frames[0], bd=0, bg=BG_COLOR)
                            gif_label.pack(padx=10, pady=(0, 10))
                            top._gif_frames = frames
                            top._gif_durations = durations
                            top._gif_index = 0

                            def _animate_pil():
                                try:
                                    if not tk.Toplevel.winfo_exists(top):
                                        return
                                    frs = getattr(top, '_gif_frames', [])
                                    if not frs:
                                        return
                                    top._gif_index = (top._gif_index + 1) % len(frs)
                                    gif_label.configure(image=frs[top._gif_index])
                                    durs = getattr(top, '_gif_durations', [80])
                                    delay = durs[top._gif_index] if top._gif_index < len(durs) else 80
                                    top.after(delay, _animate_pil)
                                except Exception:
                                    pass
                            # 最初の遅延（0 だと固まる場合があるので最小 20ms）
                            first_delay = max(20, durations[0] if durations else 80)
                            top.after(first_delay, _animate_pil)
                    else:
                        # Pillow 無しフォールバック: 従来の tk.PhotoImage による読み込み
                        frames = []
                        idx = 0
                        while True:
                            try:
                                frame = tk.PhotoImage(file=gif_path, format=f'gif -index {idx}')
                            except Exception:
                                break
                            frames.append(frame)
                            idx += 1
                            if idx > 200:
                                break
                        if frames:
                            gif_label = tk.Label(top, image=frames[0], bd=0, bg=BG_COLOR)
                            gif_label.pack(padx=10, pady=(0, 10))
                            top._gif_frames = frames
                            top._gif_index = 0
                            def _animate_fallback():
                                try:
                                    if not tk.Toplevel.winfo_exists(top):
                                        return
                                    frs = getattr(top, '_gif_frames', [])
                                    if not frs:
                                        return
                                    top._gif_index = (top._gif_index + 1) % len(frs)
                                    gif_label.configure(image=frs[top._gif_index])
                                    top.after(80, _animate_fallback)
                                except Exception:
                                    pass
                            top.after(80, _animate_fallback)
                        if not frames:
                            self.view.log('GIFフレームが読み込めません (フォールバック)')
                except Exception as e:
                    self.view.log(f"GIF読み込み失敗: {e}")
            # 中央配置
            try:
                top.update_idletasks()
                w = top.winfo_width(); h = top.winfo_height()
                sw = top.winfo_screenwidth(); sh = top.winfo_screenheight()
                x = (sw - w)//2; y = (sh - h)//2
                top.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass
            self.processing_overlay = top
        except Exception as e:
            self.view.log(f"処理中画面表示エラー: {e}")

    def _hide_processing_overlay(self):
        top = getattr(self, 'processing_overlay', None)
        if not top:
            return
        try:
            top.grab_release()
        except Exception:
            pass
        try:
            top.destroy()
        except Exception:
            pass
        self.processing_overlay = None
