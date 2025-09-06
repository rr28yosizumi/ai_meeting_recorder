"""AI (Whisper + Gemini) 制御モジュール

例外ハンドリング強化版:
 - Whisperモデル読み込み失敗時のリトライと明示ログ
 - 音声ファイル不存在/空コンテンツ検出
 - Gemini要約時の API キー未設定 / ネットワーク / レート制限 / 一般例外捕捉
 - 失敗時に処理継続 (文字起こし成功→要約失敗 など) を許容し構造化結果を返却
 - Whisperモデルはキャッシュしループ毎の再ロードを防止
"""

from typing import Callable, List, Dict, Optional
import os
import time

try:
    import google.generativeai as genai
except Exception:  # ライブラリ未インストールや読み込み失敗
    genai = None  # 後でチェック

try:
    import whisper
except Exception:
    whisper = None

from . import sound_control

WhisperLogger = Callable[[str], None]

_WHISPER_MODEL_CACHE = {
    "name": None,
    "model": None
}

def _log(logger: Optional[WhisperLogger], msg: str):
    if logger:
        try:
            logger(msg)
        except Exception:
            pass

def _load_whisper(model_size: str, logger: Optional[WhisperLogger]):
    """Whisperモデルをキャッシュ付きでロード"""
    if whisper is None:
        _log(logger, "Whisperライブラリが読み込めなかったため文字起こしをスキップします")
        return None
    if _WHISPER_MODEL_CACHE["model"] is not None and _WHISPER_MODEL_CACHE["name"] == model_size:
        return _WHISPER_MODEL_CACHE["model"]
    try:
        _log(logger, f"Whisperモデル '{model_size}' を読み込み中…")
        model = whisper.load_model(model_size)
        _WHISPER_MODEL_CACHE["name"] = model_size
        _WHISPER_MODEL_CACHE["model"] = model
        _log(logger, "Whisperモデル読み込み完了")
        return model
    except Exception as e:
        _log(logger, f"Whisperモデル読み込み失敗: {e}")
        return None

def preload_models(logger: Optional[WhisperLogger]=None, whisper_model: str="small"):
    """起動時の事前ロード用ユーティリティ

    メインGUI表示前に呼び出して重いモデルの遅延をスプラッシュ中に吸収。
    Whisperが無い場合は黙ってスキップ。
    """
    _load_whisper(whisper_model, logger)

def summarize_minutes_gemini(prompt: str, text: str, gemini_api_key: str, logger: Optional[WhisperLogger]=None,
                              model_name: str='gemini-2.0-flash-lite', max_retry: int = 2, retry_wait: float = 3.0) -> str:
    """Gemini APIを使った要約 (例外安全)

    Returns: 要約文字列 (失敗時はエラーメッセージ含む簡易メッセージ)
    """
    if not gemini_api_key:
        _log(logger, "Gemini APIキーが未設定のため要約をスキップします")
        return "(要約スキップ: APIキー未設定)"
    if genai is None:
        _log(logger, "google.generativeai がインポートできないため要約をスキップします")
        return "(要約スキップ: ライブラリ未利用)"
    try:
        genai.configure(api_key=gemini_api_key)
    except Exception as e:
        _log(logger, f"Gemini設定失敗: {e}")
        return f"(要約失敗: 設定エラー {e})"

    full_prompt = prompt + text
    last_err = None
    for attempt in range(1, max_retry+2):  # 初回 + リトライ回数
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(full_prompt)
            # APIは成功だが text が無いケース
            summary_text = getattr(response, 'text', None)
            if not summary_text:
                summary_text = "(要約取得失敗: レスポンスにtextがありません)"
            return summary_text
        except Exception as e:
            last_err = e
            _log(logger, f"Gemini要約失敗 (試行{attempt}): {e}")
            if attempt <= max_retry:
                time.sleep(retry_wait)
            else:
                break
    return f"(要約失敗: {last_err})"

def transcribe_audio_whisper(file_path: str, lang: str="ja", model_size: str="small", logger: Optional[WhisperLogger]=None,
                             **whisper_kwargs) -> str:
    """Whisperで文字起こし (例外安全)

    whisper_kwargs に transcribe の追加パラメータ (temperature など) を渡せる
    Returns: テキスト (失敗時はエラーメッセージを括弧付きで返却)
    """
    if not os.path.exists(file_path):
        _log(logger, f"音声ファイルが存在しません: {file_path}")
        return "(文字起こし失敗: ファイルなし)"
    model = _load_whisper(model_size, logger)
    if model is None:
        return "(文字起こし失敗: Whisperモデル未ロード)"
    try:
        result = model.transcribe(file_path, language=lang, **whisper_kwargs)
        if "segments" in result:
            text = "\n".join(seg.get("text", "").strip() for seg in result["segments"]) or "(空)"
        else:
            text = result.get("text", "") or "(空)"
        return text
    except Exception as e:
        _log(logger, f"Whisper文字起こし失敗: {e}")
        return f"(文字起こし失敗: {e})"

def create_meeting_report(prompt: str, voice: str, chunk_dir: str, split_seconds: int,
                          out_voice_text: str, gemini_key: str, logger: Optional[WhisperLogger]=None,
                          lang: str="ja", whisper_model: str="small") -> Dict[str, Optional[str]]:
    """議事録作成統合処理 (例外安全)

    Returns:
        dict: {
            'success': bool,
            'transcription_file': str | None,
            'summary_file': str | None,
            'error': str | None
        }
    """
    start_time = time.time()
    _log(logger, "議事録作成処理開始")
    result: Dict[str, Optional[str]] = {
        'success': False,
        'transcription_file': None,
        'summary_file': None,
        'error': None
    }
    try:
        if not os.path.exists(voice):
            raise FileNotFoundError(f"音声ファイルが存在しません: {voice}")
        try:
            chunk_files = sound_control.split_audio_by_time(voice, chunk_dir, split_seconds)
        except Exception as e:
            raise RuntimeError(f"音声分割失敗: {e}") from e
        if not chunk_files:
            raise RuntimeError("分割後のチャンクが生成されませんでした")
        all_text_parts: List[str] = []
        for f in chunk_files:
            _log(logger, f"Whisperで文字起こし中: {f}")
            part = transcribe_audio_whisper(f, lang=lang, model_size=whisper_model, logger=logger)
            all_text_parts.append(part)
        all_text = "\n".join(all_text_parts)
        try:
            with open(out_voice_text, "w", encoding="utf-8") as out:
                out.write(all_text)
            _log(logger, f"文字起こし完了: {out_voice_text}")
        except Exception as e:
            raise RuntimeError(f"文字起こし書き込み失敗: {e}") from e
        result['transcription_file'] = out_voice_text

        _log(logger, f"Gemini議事録作成開始: {out_voice_text}")
        summary = summarize_minutes_gemini(prompt, all_text, gemini_key, logger=logger)
        summary_file = os.path.splitext(out_voice_text)[:1][0] + "_summary.txt"
        try:
            with open(summary_file, "w", encoding="utf-8") as out:
                out.write(summary)
            _log(logger, f"Gemini議事録作成完了: {summary_file}")
        except Exception as e:
            _log(logger, f"要約ファイル書き込み失敗: {e}")
            # 要約失敗でも transcription は成功として継続
            result['error'] = f"要約保存失敗: {e}"
        result['summary_file'] = summary_file
        result['success'] = True
        duration = time.time() - start_time
        _log(logger, f"議事録処理完了 (所要 {duration:.1f}s)")
        return result
    except Exception as fatal:
        result['error'] = str(fatal)
        _log(logger, f"議事録処理致命的エラー: {fatal}")
        return result
