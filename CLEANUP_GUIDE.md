# 🗑️ LocalLLM_Test プロジェクト整理 - 削除推奨ファイル

## 整理完了 ✅
以下のファイルはフォルダ構造に整理されました：

### コアシステム（core/フォルダ）
- ✅ llm_face_controller.py → core/llm_face_controller.py
- ✅ main.py → core/main.py  
- ✅ expression_parser.py → core/expression_parser.py
- ✅ expression_validator.py → core/expression_validator.py
- ✅ phoneme_expression_sync.py → core/phoneme_expression_sync.py

### UIシステム（ui/フォルダ）
- ✅ sync_siriusface.py → ui/sync_siriusface.py

### ユーティリティ（utils/フォルダ）  
- ✅ launch_sirius_system.py → utils/launch_sirius_system.py
- ✅ prompt_tuning.py → utils/prompt_tuning.py
- ✅ start_sirius_system.sh → utils/start_sirius_system.sh

### テストファイル（tests/フォルダ）
- ✅ test_*.py → tests/ （全テストファイル）
- ✅ detailed_mic_test.py → tests/detailed_mic_test.py
- ✅ fix_mic_test.py → tests/fix_mic_test.py
- ✅ wake_word_gui.py → tests/wake_word_gui.py

## 🗑️ 削除可能なファイル（開発完了後）

以下のファイルは開発・デバッグ用のため、本番環境では不要です：

### マイクテスト関連（デバッグ用）
- tests/detailed_mic_test.py - マイクデバイステスト
- tests/fix_mic_test.py - マイク問題修正テスト  
- tests/test_monitoring.py - 監視システムテスト

### ウェイクワード実験ファイル（統合済み）
- tests/test_wake_word_simple.py - 簡易ウェイクワードテスト
- tests/test_wake_word.py - ウェイクワードテスト（旧版）
- tests/wake_word_gui.py - ウェイクワードGUI（sync_siriusface.pyに統合済み）

### 単体テストファイル（機能完成済み）
- tests/test_expression_fix.py - 表情修正テスト
- tests/test_expression_system.py - 表情システムテスト
- tests/test_mistral_model.py - Mistralモデルテスト
- tests/test_prompt_system.py - プロンプトシステムテスト
- tests/test_sirius_expressions.py - 表情テスト

## 📂 新しいフォルダ構造

```
LocalLLM_Test/
├── 📁 core/                    # コアシステム
│   ├── llm_face_controller.py  # メインコントローラー
│   ├── main.py                 # LM Studioクライアント  
│   ├── expression_parser.py    # 表情解析システム
│   ├── expression_validator.py # 表情検証システム
│   └── phoneme_expression_sync.py # 音韻同期システム
├── 📁 ui/                      # ユーザーインターフェース
│   └── sync_siriusface.py      # メインUI
├── 📁 utils/                   # ユーティリティ
│   ├── launch_sirius_system.py # システム起動
│   ├── prompt_tuning.py        # プロンプト管理
│   └── start_sirius_system.sh  # 起動スクリプト
├── 📁 tests/                   # テストファイル（開発用）
│   └── test_*.py               # 各種テスト・デバッグファイル
├── 📁 prompts/                 # プロンプトファイル
├── sirius_main.py              # 新メインエントリポイント
├── prompt_configs.json         # 設定ファイル
└── README.md                   # プロジェクト説明
```

## 🚀 新しい起動方法

### 1. 統合システム起動（推奨）
```bash
cd LocalLLM_Test
source bin/activate
python sirius_main.py
```

### 2. 従来の方法（utils経由）
```bash
cd LocalLLM_Test
source bin/activate  
python utils/launch_sirius_system.py
```

### 3. UI単体起動
```bash
cd LocalLLM_Test
source bin/activate
python ui/sync_siriusface.py
```

## 📝 メリット

### ✅ 改善点
1. **ファイル整理**: 機能ごとにフォルダ分けで管理しやすい
2. **開発効率**: コア機能とテスト機能が分離
3. **メンテナンス性**: 本番ファイルとデバッグファイルが明確
4. **拡張性**: 新機能追加時のフォルダ構造が明確
5. **可読性**: プロジェクト構造が一目で理解できる

### 🔄 importパス修正済み
- llm_face_controller.py: core/へのパス修正
- sync_siriusface.py: core/へのimportパス修正  
- launch_sirius_system.py: ui/sync_siriusface.pyパス修正
- start_sirius_system.sh: utils/launch_sirius_system.pyパス修正

## ⚠️ 注意事項

1. **Python Path**: 各ファイルのsys.path.append()を適切に設定済み
2. **相対パス**: フォルダ移動後も動作するよう絶対パスで指定
3. **テストファイル**: 開発中は残しておき、本番リリース時に削除推奨
4. **バックアップ**: 重要なファイルは削除前にバックアップ推奨

## 🎯 推奨作業手順

1. ✅ **整理完了**: ファイル移動とパス修正は完了
2. 🧪 **動作確認**: 新構造でシステムが正常動作するかテスト
3. 🗑️ **テストファイル削除**: 動作確認後、不要なテストファイルを削除
4. 📚 **ドキュメント更新**: READMEの起動方法を新構造に更新