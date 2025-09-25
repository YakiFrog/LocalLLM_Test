#!/usr/bin/env python3
"""
統合起動スクリプト
シリウス表情サーバー(main.py)とシリウス音声対話UI(sync_siriusface.py)を同時起動
"""

import sys
import time
import subprocess
import threading
import signal
import os
from pathlib import Path

# プロセス管理用
main_process = None
ui_process = None

def start_main_server():
    """main.py（表情サーバー）を起動"""
    global main_process
    try:
        # パスを設定
        main_py_path = "/Users/kotaniryota/NLAB/sirius_face_anim/python/main.py"
        python_path = "/Users/kotaniryota/NLAB/sirius_face_anim/python/bin/python"
        
        if not Path(main_py_path).exists():
            print(f"❌ main.pyが見つかりません: {main_py_path}")
            return False
        
        print("🚀 シリウス表情サーバー(main.py)を起動中...")
        
        # 仮想環境のPythonでmain.pyを起動
        main_process = subprocess.Popen(
            [python_path, main_py_path],
            cwd="/Users/kotaniryota/NLAB/sirius_face_anim/python",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # 起動確認のため少し待機
        time.sleep(3)
        
        if main_process.poll() is None:
            print("✅ シリウス表情サーバーが起動しました (PID: {})".format(main_process.pid))
            
            # ログを別スレッドで監視
            def monitor_main_logs():
                if main_process and main_process.stdout:
                    for line in iter(main_process.stdout.readline, ''):
                        if line.strip():
                            print(f"[表情サーバー] {line.strip()}")
            
            log_thread = threading.Thread(target=monitor_main_logs, daemon=True)
            log_thread.start()
            
            return True
        else:
            print("❌ シリウス表情サーバーの起動に失敗しました")
            if main_process.stderr:
                error_output = main_process.stderr.read()
                print(f"エラー出力: {error_output}")
            return False
            
    except Exception as e:
        print(f"❌ 表情サーバー起動エラー: {e}")
        return False

def start_ui():
    """sync_siriusface.py（音声対話UI）を起動"""
    global ui_process
    try:
        print("🚀 シリウス音声対話UI(sync_siriusface.py)を起動中...")
        
        # 現在のディレクトリでsync_siriusface.pyを起動
        python_path = "./bin/python"
        
        ui_process = subprocess.Popen(
            [python_path, "ui/sync_siriusface.py"],
            cwd="/Users/kotaniryota/NLAB/LocalLLM_Test",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        if ui_process.poll() is None:
            print("✅ シリウス音声対話UIが起動しました (PID: {})".format(ui_process.pid))
            
            # ログを別スレッドで監視
            def monitor_ui_logs():
                if ui_process and ui_process.stdout:
                    for line in iter(ui_process.stdout.readline, ''):
                        if line.strip():
                            print(f"[音声対話UI] {line.strip()}")
            
            log_thread = threading.Thread(target=monitor_ui_logs, daemon=True)
            log_thread.start()
            
            return True
        else:
            print("❌ シリウス音声対話UIの起動に失敗しました")
            if ui_process.stderr:
                error_output = ui_process.stderr.read()
                print(f"エラー出力: {error_output}")
            return False
            
    except Exception as e:
        print(f"❌ 音声対話UI起動エラー: {e}")
        return False

def cleanup_processes():
    """プロセスをクリーンアップ"""
    global main_process, ui_process
    
    print("\n🛑 プロセスを終了中...")
    
    if ui_process:
        try:
            ui_process.terminate()
            ui_process.wait(timeout=5)
            print("✅ 音声対話UIを終了しました")
        except subprocess.TimeoutExpired:
            ui_process.kill()
            print("⚠️ 音声対話UIを強制終了しました")
        except Exception as e:
            print(f"❌ 音声対話UI終了エラー: {e}")
    
    if main_process:
        try:
            main_process.terminate()
            main_process.wait(timeout=5)
            print("✅ 表情サーバーを終了しました")
        except subprocess.TimeoutExpired:
            main_process.kill()
            print("⚠️ 表情サーバーを強制終了しました")
        except Exception as e:
            print(f"❌ 表情サーバー終了エラー: {e}")

def signal_handler(signum, frame):
    """シグナルハンドラー"""
    print(f"\n📢 シグナル {signum} を受信しました")
    cleanup_processes()
    sys.exit(0)

def wait_for_processes():
    """プロセス終了を待機"""
    global main_process, ui_process
    
    try:
        while True:
            # プロセスの状態をチェック
            main_running = main_process and main_process.poll() is None
            ui_running = ui_process and ui_process.poll() is None
            
            if not main_running and not ui_running:
                print("📢 全てのプロセスが終了しました")
                break
            
            if not main_running:
                print("⚠️ 表情サーバーが予期せず終了しました")
                if main_process and main_process.stderr:
                    error_output = main_process.stderr.read()
                    if error_output:
                        print(f"エラー出力: {error_output}")
            
            if not ui_running:
                print("⚠️ 音声対話UIが予期せず終了しました")
                if ui_process and ui_process.stderr:
                    error_output = ui_process.stderr.read()
                    if error_output:
                        print(f"エラー出力: {error_output}")
                break  # UIが終了したら全体を終了
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n📢 Ctrl+Cが押されました")
    finally:
        cleanup_processes()

def main():
    """メイン関数"""
    print("🎭 シリウス統合システム起動")
    print("=" * 50)
    
    # シグナルハンドラー設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 1. 表情サーバー起動
        if not start_main_server():
            print("❌ 表情サーバーの起動に失敗したため、終了します")
            sys.exit(1)
        
        # サーバー起動待機
        print("⏳ 表情サーバーの準備完了を待機中...")
        time.sleep(5)
        
        # 2. 音声対話UI起動
        if not start_ui():
            print("❌ 音声対話UIの起動に失敗しました")
            cleanup_processes()
            sys.exit(1)
        
        print("\n🎉 全システムが起動完了しました！")
        print("💡 使用方法:")
        print("  • 音声対話UIで会話を開始")
        print("  • 表情タグ付きLLM応答で自動表情切り替え")
        print("  • Ctrl+Cで全システム終了")
        print("\n⏳ システム監視中...")
        
        # プロセス監視
        wait_for_processes()
        
    except Exception as e:
        print(f"❌ システム起動エラー: {e}")
        cleanup_processes()
        sys.exit(1)

if __name__ == "__main__":
    main()