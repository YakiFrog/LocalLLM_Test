#!/usr/bin/env python3
"""
シリウス音声対話システム - メインエントリポイント
整理されたフォルダ構造での統合起動
"""

import sys
import os
from pathlib import Path

# プロジェクトルートパスを追加
project_root = Path(__file__).parent
sys.path.append(str(project_root / "core"))
sys.path.append(str(project_root / "ui"))
sys.path.append(str(project_root / "utils"))

def main():
    """メイン実行関数"""
    print("🎭 シリウス音声対話システム")
    print("=" * 50)
    print("1. システム統合起動 (推奨)")
    print("2. 音声対話UIのみ起動")
    print("3. テストメニュー")
    print("=" * 50)
    
    choice = input("選択してください (1-3): ").strip()
    
    if choice == "1":
        # 統合システム起動
        from launch_sirius_system import main as launch_main
        launch_main()
    elif choice == "2":
        # UI単体起動
        from sync_siriusface import main as ui_main
        ui_main()
    elif choice == "3":
        # テストメニュー
        show_test_menu()
    else:
        print("無効な選択です")

def show_test_menu():
    """テストメニューを表示"""
    print("\n🧪 テストメニュー")
    print("=" * 30)
    print("1. 表情システムテスト")
    print("2. LLM接続テスト") 
    print("3. 音声認識テスト")
    print("4. 戻る")
    
    choice = input("選択してください (1-4): ").strip()
    
    if choice == "1":
        # 表情システムテスト
        sys.path.append(str(Path(__file__).parent / "tests"))
        from test_sirius_expressions import main as test_main
        test_main()
    elif choice == "2":
        # LLM接続テスト
        sys.path.append(str(Path(__file__).parent / "tests"))
        from test_mistral_model import main as test_main
        test_main()
    elif choice == "3":
        # 音声認識テスト
        sys.path.append(str(Path(__file__).parent / "tests"))
        from detailed_mic_test import main as test_main
        test_main()
    elif choice == "4":
        main()
    else:
        print("無効な選択です")

if __name__ == "__main__":
    main()