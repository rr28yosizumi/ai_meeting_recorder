
# ai_meeting_recorder

<p align="center">
	<img src="src/resource/logo.png" alt="AI Meeting Recorder Logo" />
</p>

会議録音・議事録作成ツール  
音声を録音し、Whisperによる文字起こしとGemini APIによる要約を自動生成します。GUIで操作可能です。

## 特長

- マイク・スピーカーの音声を同時録音
- 録音音声の波形表示
- Whisperによる高精度文字起こし
- Gemini APIによる議事録要約
- 設定保存・読み込み（YAML）

## インストール

### 1. Python環境

- Python 3.8 以上

### 2. 必要なライブラリ

#### FFMpegのインストール

事前にFFMpegをインストールしてください
Windowsでのインストール方法は下記を参照
https://www.kkaneko.jp/tools/win/ffmpeg.html



#### その他依存

- `tkinter`（多くのPython環境で標準搭載）

### 3. セットアップ

```powershell
pip install .
```

※インストールで使えない場合、ai_meeting_recorderのディレクトリをカレントディレクトリにしてモジュール実行してください

```powershell
python -m src.main
```

※Pyinstallerを使う場合は、Whisperのデータを含めるようにしてください
```
pyinstaller ai_meeting_recorder.py --onefile --add-data "YOUR_PYTHON_DIR\Lib\site-packages\whisper:whisper"
```
参考
https://stackoverflow.com/questions/75981036/python-openai-whisper-filenotfounderror-when-running-a-standalone-created-with-p

## 使い方

```powershell
ai_meeting_recorder
```

GUIが起動します。  
マイク・スピーカー・言語・APIキー・出力先などを設定し、録音・議事録作成を行えます。

### 初回起動時の流れ
1. 起動するとスプラッシュ(ロゴ)が表示され、Whisper / Gemini 利用準備をロードします。
2. メインウィンドウが開いたら以下を設定:
	 - マイク入力デバイス / スピーカー出力デバイス
	 - 文字起こし言語 (日本語/英語)
	 - Gemini API キー（Google AI Studio で取得）
	 - 議事録出力先フォルダ
	 - 録音 WAV 保存先フォルダ
	 - プロンプト（議事録要約スタイルを指示）
3. [録音開始] ボタンで録音をスタート。波形が赤色になれば録音中です。
4. 必要なら [録音中断] → [録音再開] で一時停止可能。
5. [録音終了] で WAV を保存 (マイク/スピーカーを自動ミックス)。
6. [WAVから文字起こし・要約] を押すと Whisper 文字起こし + Gemini 要約を別スレッドで実行。
7. 完了後、議事録テキストをダイアログ保存できます。

### GUI 各要素
| 項目 | 説明 |
|------|------|
| マイク入力デバイス | sounddevice で列挙された録音デバイス |
| スピーカー出力デバイス | 再生経路キャプチャ用 (同一デバイス録音時は mic のみ) |
| 文字起こし言語 | Whisper モデルへ渡す言語ヒント |
| Gemini APIキー | `GEMINI_API_KEY` 相当。平文で保持したくない場合は環境変数管理推奨 |
| 議事録出力先 | 要約テキスト保存先フォルダ |
| 録音WAV保存先 | 録音終了時にミックス結果を保存 |
| Geminiプロンプト | 要約指示文（議事録フォーマット / 箇条書き / タスク抽出等） |
| 録音開始/中断/再開/終了 | 録音制御 (別スレッドで処理) |
| WAVから文字起こし・要約 | 既存 WAV からも処理可 (保存済みを参照) |
| ログ | 進行状況・エラーを表示 |

### 設定の保存
- ウィンドウを閉じると `init.yml` に現在値が保存され、次回起動で復元されます。
- APIキーをファイルに残したくない場合は `init.yml` を編集し除去 → 起動後に都度入力。

### 既存 WAV から処理する手順
1. 録音せずに先に WAV ファイルを `録音WAV保存先` に置く
2. [WAVから文字起こし・要約] を押す
3. Whisper → Gemini の順に処理 / 完了後保存ダイアログ


### Whisper モデルのサイズ最適化
- デフォルトで small / base などを選択し、`ai_control.py` 側でモデル名変更可。
- モデルキャッシュは `%LOCALAPPDATA%/whisper` (環境により異なる) に蓄積。

### Gemini API 利用制限
- 利用量制限超過時は要約失敗しログにエラー表示。
- リトライ戦略を導入したい場合は `ai_control.py` 内で再試行ロジックを追加可。

### トラブルシュート
| 症状 | 対処 |
|------|------|
| デバイス一覧が空 | オーディオデバイス使用中アプリを終了 / 権限確認 |
| 録音波形がフラット | マイク選択が誤り or 無音環境 / 入力ゲイン確認 |
| 文字起こしが英語になる | 言語選択が英語 / Whisper 自動検出の揺れ → プロンプトに言語固定指示 |
| Gemini 要約でエラー | APIキー無効 / 利用上限 / ネットワーク不通 |
| PyInstaller exe 起動が遅い | 初回キャッシュ展開 (Onefile) / モデルダウンロード待ち |
| ウィンドウが小さい | `main.py` の `root.geometry` を調整 |

### ログの活用
- GUI 下部ログは内部状態を簡易表示。詳細デバッグが必要な場合は `print` を `logging` へ切替しファイル出力する改修が容易です。

### セキュリティ / 秘匿情報
- APIキーは平文保存されるため、社内利用時は環境変数で上書きする仕組みを推奨。
- Whisper ローカル実行で音声は外部送信されません（Gemini 要約はテキストを送信）。

### アンインストール
```powershell
pip uninstall ai_meeting_recorder
```

### ライセンス / 第三者ライセンス
- 本体: MIT License
- 主要依存: numpy(BSD), sounddevice(MIT), matplotlib(BSD系), pydub(MIT), customtkinter(MIT), pillow(PIL/BSD), google-generativeai(Apache2.0), openai-whisper(MIT)
- 詳細は `THIRD_PARTY_LICENSES.txt` を参照

---
改善案・Issue は GitHub リポジトリへ。コントリビューション歓迎です。

## 設定ファイル

- `init.yml` に各種設定が保存されます。
- 初回起動時に自動生成されます。

## ファイル構成

- `src/` : モジュール本体
- `init.yml` : 設定ファイル
- `Readme.md` : 本ドキュメント
- `setup.py` : インストール用スクリプト

## ライセンス

MIT License