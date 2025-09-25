# シリウス音声対話システム セットアップガイド

## 必要システム要件

### 基本要件
- Python 3.8以上
- macOS (開発・テスト環境)
- マイクデバイス
- インターネット接続

### 外部システム
- **LM Studio**: ローカルLLMサーバー (http://127.0.0.1:1234)
- **VOICEVOX**: 音声合成API (http://127.0.0.1:50021) または VOICEVOX Core

## インストール手順

### 1. 基本パッケージのインストール
```bash
cd /Users/kotaniryota/NLAB/LocalLLM_Test
pip install -r requirements.txt
```

### 2. VOICEVOX Coreのインストール
VOICEVOX Coreは特別な手順が必要な場合があります：

#### 方法1: pipでインストール（推奨）
```bash
pip install voicevox-core
```

#### 方法2: 手動インストール
公式サイトからダウンロード: https://github.com/VOICEVOX/voicevox_core

### 3. システムレベル依存関係

#### macOS
```bash
# HomebrewでPortAudioをインストール（PyAudio用）
brew install portaudio

# 必要に応じてffmpegもインストール
brew install ffmpeg
```

### 4. 音声デバイス設定
MacBook Airの内蔵マイクをデフォルトで使用しますが、
他のマイクデバイスを使用する場合は、アプリケーション内の設定で変更可能です。

## 起動方法

### メイン起動
```bash
python sirius_main.py
```

### UI単体起動
```bash
cd ui
python sync_siriusface.py
```

## トラブルシューティング

### PyAudio関連エラー
```bash
# macOSでPortAudioエラーが出る場合
brew install portaudio
pip uninstall pyaudio
pip install pyaudio
```

### VOICEVOX Core関連エラー
- VOICEVOX本体アプリが起動していることを確認
- またはVOICEVOX Coreが正しくインストールされていることを確認

### faster-whisper関連エラー
```bash
# より軽量なモデルを使用
# アプリケーション内でモデルをbaseやsmallに変更
```

### PySide6関連エラー
```bash
pip uninstall PySide6
pip install PySide6
```

## 設定ファイル
- `prompt_configs.json`: LLMプロンプト設定
- `dialogue_data.json`: 対話データ設定（sirius_face_animプロジェクト）

## ログファイル
実行時のログは以下に出力されます：
- コンソール出力
- 各モジュールの個別ログ

## 注意事項
1. 初回起動時はWhisperモデルのダウンロードが必要（数GB）
2. LM Studioを事前に起動してモデルをロードしておく必要があります
3. VOICEVOXサーバーまたはVOICEVOX本体を起動しておく必要があります