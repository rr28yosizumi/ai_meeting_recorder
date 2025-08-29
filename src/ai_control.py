import google.generativeai as genai
import whisper
import os
from . import sound_control

def summarize_minutes_gemini(prompt, text, gemini_api_key):
    """
    Gemini APIを使って議事録要約を作成する関数。
    Args:
        prompt (str): Geminiに渡すプロンプト（要約指示やフォーマット指定など）。
        text (str): 議事録の元となるテキスト（音声認識結果など）。
        gemini_api_key (str): Gemini APIキー。
    Returns:
        str: Geminiから返された要約テキスト。
    仕様:
        - Gemini APIにプロンプトと議事録テキストを渡して要約を生成。
        - 返却された要約テキストを返す。
    """
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    prompt = prompt + text
    response = model.generate_content(prompt)
    return response.text

def transcribe_audio_whisper(file_path, lang="ja"):
    """
    Whisperモデルを使って音声ファイルを文字起こしする関数。
    Args:
        file_path (str): 音声ファイル（WAV等）のパス。
    Returns:
        str: Whisperによる文字起こし結果（テキスト）。
    仕様:
        - 指定した音声ファイルをWhisperモデルで文字起こし。
        - セグメントごとに改行を挿入してテキストを返す。
    """
    model = whisper.load_model("small")
    result = model.transcribe(file_path, language=lang)
    # セグメントごとに改行を挿入
    if "segments" in result:
        text = "\n".join([seg["text"].strip() for seg in result["segments"]])
    else:
        text = result["text"]
    return text


def create_meeting_report(prompt,voice,chunk_dir,split_seconds,out_voice_text,gemini_key,logger=None,lang="ja"):
    logger("議事録作成処理開始")

    chunk_files = sound_control.split_audio_by_time(voice, chunk_dir, split_seconds)
    all_text = ""
    for f in chunk_files:
        logger(f"Whisperで文字起こし中: {f}")
        text = transcribe_audio_whisper(f, lang=lang)
        all_text += text + "\n"

    with open(out_voice_text, "w", encoding="utf-8") as out:
        out.write(all_text)
    logger(f"文字お越し完了: {out_voice_text}")

    logger(f"Gemini議事録作成開始: {out_voice_text}")
    summary = summarize_minutes_gemini(prompt,all_text, gemini_key)
    summary_file = os.path.splitext(out_voice_text)[0] + "_summary.txt"
    with open(summary_file, "w", encoding="utf-8") as out:
        out.write(summary)
    logger(f"Gemini議事録作成完了: {summary_file}")
