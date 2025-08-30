import threading
import queue
import sounddevice as sd
import numpy as np
import os
from .model import RecorderModel
from .view import RecorderView
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
            self._process_minutes()
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
        if not result.get('success'):
            err = result.get('error')
            if err:
                self.view.log(f"議事録生成失敗: {err}")
        else:
            if result.get('summary_file'):
                self.view.log(f"要約ファイル: {result['summary_file']}")

    def transcribe_and_summarize(self):
        wav_file = self.view.wav_path.get()
        if not os.path.exists(wav_file):
            self.view.log(f"指定されたWAVファイルが存在しません: {wav_file}")
            return
        self.view.log(f"WAVファイルから文字起こし・要約を実行: {wav_file}")
        self._process_minutes()
        self.view.show_info('要約完了', '要約処理が終了しました。')
