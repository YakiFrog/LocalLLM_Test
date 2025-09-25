#!/usr/bin/env python3
"""
リアルタイム監視テストスクリプト
監視機能が動作しているかを簡単にチェック
"""

import sys
import pyaudio
import numpy as np
import time
from threading import Thread, Event

class SimpleMonitoringTest:
    def __init__(self):
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        self.is_monitoring = False
        self.stop_event = Event()
    
    def start_monitoring_test(self):
        """簡単な音声監視テスト"""
        print("🔊 音声監視テストを開始します")
        print("📋 このテストでは以下を確認します:")
        print("  1. マイクからの音声入力")
        print("  2. 音声レベルの検出")
        print("  3. 継続的な監視動作")
        print("💡 話しかけると音声レベルが表示されます")
        print("⏹️  Ctrl+C で終了")
        
        self.is_monitoring = True
        
        # PyAudio初期化
        try:
            p = pyaudio.PyAudio()
            
            print(f"🎤 利用可能なマイクデバイス:")
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    print(f"  デバイス{i}: {info['name']}")
            
            stream = p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            print("✅ マイク接続成功")
            print("🎵 音声監視を開始中...")
            
            frame_count = 0
            high_volume_count = 0
            start_time = time.time()
            
            while self.is_monitoring:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    frame_count += 1
                    
                    # 音声レベル計算
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume = np.sqrt(np.mean(audio_data**2))
                    
                    # 定期的に状態報告
                    if frame_count % 30 == 0:  # 約2秒ごと
                        elapsed = time.time() - start_time
                        if volume > 200:
                            high_volume_count += 1
                            print(f"🔊 フレーム#{frame_count} 音声レベル:{volume:.0f} 経過:{elapsed:.1f}s ✅")
                        else:
                            print(f"🔇 フレーム#{frame_count} 音声レベル:{volume:.0f} 経過:{elapsed:.1f}s")
                    
                    # 高い音声レベルを検出
                    if volume > 500:
                        print(f"📣 大きな音声を検出! レベル:{volume:.0f} - 「シリウスくん」と言ってみてください")
                    
                except Exception as e:
                    print(f"❌ 音声読み取りエラー: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\n⏹️ テストを停止します")
        except Exception as e:
            print(f"❌ 初期化エラー: {e}")
        finally:
            self.is_monitoring = False
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            if 'p' in locals():
                p.terminate()
            
            # 結果サマリー
            print(f"\n📊 テスト結果:")
            print(f"  - 総フレーム数: {frame_count}")
            print(f"  - 音声検出回数: {high_volume_count}")
            print(f"  - 実行時間: {time.time() - start_time:.1f}秒")
            
            if high_volume_count > 0:
                print("✅ マイクは正常に動作しています")
                print("💡 メインシステムでも監視が動作するはずです")
            else:
                print("⚠️  音声が検出されませんでした")
                print("🔧 マイクの設定やアクセス許可を確認してください")

if __name__ == "__main__":
    try:
        import numpy
        print("✅ numpy利用可能")
    except ImportError:
        print("❌ numpyが見つかりません。pip install numpy を実行してください")
        sys.exit(1)
    
    try:
        import pyaudio
        print("✅ pyaudio利用可能")
    except ImportError:
        print("❌ pyaudioが見つかりません。pip install pyaudio を実行してください")
        sys.exit(1)
    
    tester = SimpleMonitoringTest()
    tester.start_monitoring_test()