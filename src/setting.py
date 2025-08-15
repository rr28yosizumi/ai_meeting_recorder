import yaml
import os

# 録音設定
SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 600 * 30  # 最大録音時間（例: 30分）

# ファイル格納先
BASE_DIR = os.path.join(os.path.dirname(__file__))
WAV_FILE = os.path.join(BASE_DIR, "meeting.wav")
CHUNK_DIR = os.path.join(BASE_DIR, "chunks")
MINUTES_FILE = os.path.join(BASE_DIR, "meeting_minutes.txt")
SUMMARY_FILE = os.path.join(BASE_DIR, "meeting_summary.txt")

GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"  # Gemini APIキーを設定

G_PROMPT ="""
これから渡すのはメンバーとの1on1音声入力内容です。
文字起しの関係で会話の内容が途切れていたり断片的だったりするかもしれませんが、
適切に補完しつつ、以下の構造で読みやすく実務に使える1on1議事録を作成してください。

## 出力フォーマット（厳守）
- 文体はビジネス文書調で、簡潔かつ丁寧に
- 情報をカテゴリ別に整理し、可読性を重視
- 会話のニュアンスは正確に汲み取るが、冗長な表現は簡潔に要約

###  1on1議事録（対象者名）
**日時**：YYYY年MM月DD日  
**参加者**：渡邊 / （対象者名）

---

####  主なトピック・議題
- （箇条書き）

---

####  会話内容の要約

#####  業務状況と自己評価
- ...

#####  コミュニケーション上の課題
- ...

#####  その他の話題・相談
- ...

---

####  のフィードバック・提案
- ...

---

####  アクションアイテム（ToDo）
- [ ] ...

---

###  備考
- ...

---
以下がら音声入力の内容です\n
"""


class AppSettings:
	def __init__(self,
				 sample_rate=SAMPLE_RATE,      # サンプリングレート（Hz）
				 channels=CHANNELS,            # チャンネル数（1:モノラル, 2:ステレオ）
				 record_seconds=RECORD_SECONDS,# 最大録音時間（秒）
				 wav_file=WAV_FILE,            # 録音音声ファイルのパス
				 chunk_dir=CHUNK_DIR,          # 音声分割ファイルの保存ディレクトリ
				 minutes_file=MINUTES_FILE,    # 議事録テキストファイルのパス
				 summary_file=SUMMARY_FILE,    # Gemini要約ファイルのパス
				 gemini_api_key=GEMINI_API_KEY,# Gemini APIキー
				 prompt=G_PROMPT):             # Geminiに渡すプロンプト
		self.sample_rate = sample_rate
		self.channels = channels
		self.record_seconds = record_seconds
		self.wav_file = wav_file
		self.chunk_dir = chunk_dir
		self.minutes_file = minutes_file
		self.summary_file = summary_file
		self.gemini_api_key = gemini_api_key
		self.prompt = prompt

	def save(self, filepath):
		with open(filepath, "w", encoding="utf-8") as f:
			yaml.dump(self.__dict__, f, allow_unicode=True)

	@classmethod
	def load(cls, filepath):
		with open(filepath, "r", encoding="utf-8") as f:
			data = yaml.safe_load(f)
		return cls(**data)
