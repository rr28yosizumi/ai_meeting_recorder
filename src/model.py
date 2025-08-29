import os
import numpy as np
import scipy.io.wavfile as wav
import tempfile
from pydub import AudioSegment
from .setting import AppSettings

INIT_YAML = os.path.join(os.getcwd(), "init.yml")

class RecorderModel:
    def __init__(self, settings=None):
        if settings is not None:
            self.settings = settings
        else:
            if os.path.exists(INIT_YAML):
                self.settings = AppSettings.load(INIT_YAML)
            else:
                self.settings = AppSettings()
        self.reset()

    def reset(self):
        self.mic_frames = []
        self.spk_frames = []
        self.same_device = False

    def save_settings(self):
        self.settings.save(INIT_YAML)

    def mix_and_save(self, logger=None):
        # same_device の場合は mic_frames のみ保存
        if self.same_device:
            if not self.mic_frames:
                if logger: logger("録音データがありません")
                return False
            mic_data = np.concatenate(self.mic_frames, axis=0)
            mic_int16 = np.clip(mic_data, -1, 1)
            mic_int16 = (mic_int16 * 32767).astype(np.int16)
            wav.write(self.settings.wav_file, self.settings.sample_rate, mic_int16)
            if logger: logger(f"録音保存: {self.settings.wav_file}")
            return True
        # 両方ある場合はミックス
        if self.mic_frames and self.spk_frames:
            mic_data = np.concatenate(self.mic_frames, axis=0)
            spk_data = np.concatenate(self.spk_frames, axis=0)
            mic_int16 = np.clip(mic_data, -1, 1)
            mic_int16 = (mic_int16 * 32767).astype(np.int16)
            spk_int16 = np.clip(spk_data, -1, 1)
            spk_int16 = (spk_int16 * 32767).astype(np.int16)
            mic_wav_path = os.path.join(tempfile.gettempdir(), "mic_temp.wav")
            spk_wav_path = os.path.join(tempfile.gettempdir(), "spk_temp.wav")
            wav.write(mic_wav_path, self.settings.sample_rate, mic_int16)
            wav.write(spk_wav_path, self.settings.sample_rate, spk_int16)
            mic_seg = AudioSegment.from_wav(mic_wav_path)
            spk_seg = AudioSegment.from_wav(spk_wav_path)
            if len(mic_seg) < len(spk_seg):
                mic_seg = mic_seg.append(AudioSegment.silent(duration=len(spk_seg)-len(mic_seg), frame_rate=self.settings.sample_rate), crossfade=0)
            elif len(spk_seg) < len(mic_seg):
                spk_seg = spk_seg.append(AudioSegment.silent(duration=len(mic_seg)-len(spk_seg), frame_rate=self.settings.sample_rate), crossfade=0)
            mixed_seg = mic_seg.overlay(spk_seg)
            mixed_seg.export(self.settings.wav_file, format="wav")
            if logger: logger(f"録音保存: {self.settings.wav_file}")
            return True
        if logger: logger("録音データがありません")
        return False
