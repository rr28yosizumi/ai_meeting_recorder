import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np
import scipy.io.wavfile as wav
import os

# 録音設定
SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 600 * 30  # 最大録音時間（例: 30分）

def record_audio(filename):
    import queue
    print("録音開始... Ctrl+Cで中断できます")
    q = queue.Queue()
    frames = []

    def callback(indata, frames_count, time, status):
        if status:
            print(status)
        q.put(indata.copy())

    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback):
            while True:
                frames.append(q.get())
    except KeyboardInterrupt:
        print("録音を中断しました")
    except Exception as e:
        print(f"エラー: {e}")

    if frames:
        audio = np.concatenate(frames, axis=0)
        write(filename, SAMPLE_RATE, audio)
        print(f"録音保存: {filename}")
    else:
        print("録音データがありません")


def split_audio(input_file, output_dir, min_silence_len=1000, silence_thresh=-40):
    """
    音声ファイル（WAV）を無音区間で分割する関数。
    Args:
        input_file (str): 入力音声ファイル（WAV形式）のパス。
        output_dir (str): 分割後の音声ファイルを保存するディレクトリ。
        min_silence_len (int): 無音と判定する最小区間長（ミリ秒）。
        silence_thresh (int): 無音判定の閾値（dB）。この値より小さい振幅を無音とみなす。
    Returns:
        files (list): 分割された音声ファイル（WAV）のパスリスト。
    仕様:
        - 入力WAVファイルを読み込み、振幅がsilence_thresh以下の区間を無音と判定。
        - min_silence_lenミリ秒以上の無音区間で分割。
        - 分割した音声をoutput_dirにchunk_番号.wavとして保存。
        - 分割ファイルのパスリストを返す。
    """
    os.makedirs(output_dir, exist_ok=True)
    rate, data = wav.read(input_file)
    if data.ndim > 1:
        data = data[:,0]  # モノラル化
    # 振幅をdBに変換
    data_db = 20 * np.log10(np.abs(data.astype(np.float32)) + 1e-10)
    silence_thresh_db = silence_thresh
    # 無音区間の検出
    silent = data_db < silence_thresh_db
    # min_silence_lenミリ秒以上の無音区間を検出
    min_silence_samples = int(rate * min_silence_len / 1000)
    split_points = []
    count = 0
    for i, s in enumerate(silent):
        if s:
            count += 1
        else:
            if count >= min_silence_samples:
                split_points.append(i)
            count = 0
    # 分割
    files = []
    start = 0
    for idx, end in enumerate(split_points + [len(data)]):
        if end - start > min_silence_samples:
            chunk = data[start:end]
            out_file = os.path.join(output_dir, f"chunk_{idx+1}.wav")
            # wav.write(out_file, rate, chunk.astype(np.int16))
            wav.write(out_file, rate, chunk)
            files.append(out_file)
        start = end
    return files


def split_audio_by_time(input_file, output_dir, split_seconds=30):
    """
    音声ファイルを指定した秒数ごとに分割
    """
    os.makedirs(output_dir, exist_ok=True)
    rate, data = wav.read(input_file)
    if data.ndim > 1:
        data = data[:,0]  # モノラル化
    samples_per_split = int(rate * split_seconds)
    files = []
    for i in range(0, len(data), samples_per_split):
        chunk = data[i:i+samples_per_split]
        out_file = os.path.join(output_dir, f"time_chunk_{i//samples_per_split+1}.wav")
        #wav.write(out_file, rate, chunk.astype(np.int16))
        wav.write(out_file, rate, chunk)
        files.append(out_file)
    return files
