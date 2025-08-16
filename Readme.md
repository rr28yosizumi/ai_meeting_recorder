
# ai_meeting_recorder

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

#### pipでインストール

一部ライブラリは`pip`でインストールします。

```powershell
pip install sounddevice matplotlib google-generativeai openai-whisper numba --upgrade --ignore-installed
```

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


## 使い方

```powershell
ai_meeting_recorder
```

GUIが起動します。  
マイク・スピーカー・言語・APIキー・出力先などを設定し、録音・議事録作成を行えます。

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