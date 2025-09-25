#!/usr/bin/env python3
"""
マイクデバイス詳細テスト・修正スクリプト
"""

import sys
import pyaudio
import numpy as np
import time

class MicrophoneDeviceTest:
    def __init__(self):
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
    
    def list_audio_devices(self):
        """オーディオデバイスの詳細情報を表示"""
        p = pyaudio.PyAudio()
        print("🎤 詳細なオーディオデバイス情報:")
        
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"\nデバイス{i}:")
            print(f"  名前: {info['name']}")
            print(f"  最大入力チャンネル: {info['maxInputChannels']}")
            print(f"  最大出力チャンネル: {info['maxOutputChannels']}")
            print(f"  デフォルトサンプルレート: {info['defaultSampleRate']}")
            print(f"  ホストAPI: {p.get_host_api_info_by_index(info['hostApi'])['name']}")
            
            # 入力デバイスとして使用可能かチェック
            if info['maxInputChannels'] > 0:
                try:
                    # テストストリームを作成してみる
                    test_stream = p.open(
                        format=self.format,
                        channels=1,
                        rate=int(info['defaultSampleRate']),
                        input=True,
                        input_device_index=i,
                        frames_per_buffer=self.chunk_size
                    )
                    test_stream.close()
                    print(f"  ✅ 入力デバイスとして利用可能")
                except Exception as e:
                    print(f"  ❌ 入力デバイスとして使用不可: {e}")
        
        # デフォルトデバイス情報
        default_input = p.get_default_input_device_info()
        print(f"\n🎯 デフォルト入力デバイス: {default_input['name']} (デバイス{p.get_default_input_device_info()['index']})")
        
        p.terminate()
        return p.get_default_input_device_info()['index']
    
    def test_specific_device(self, device_id):
        """特定のデバイスで音声テストを実行"""
        print(f"\n🔊 デバイス{device_id}での音声テストを開始します")
        
        p = pyaudio.PyAudio()
        device_info = p.get_device_info_by_index(device_id)
        print(f"テスト対象: {device_info['name']}")
        
        try:
            # より高いサンプルレートを試す
            sample_rates = [44100, 48000, 16000, 22050]
            working_rate = None
            
            for rate in sample_rates:
                try:
                    stream = p.open(
                        format=self.format,
                        channels=self.channels,
                        rate=rate,
                        input=True,
                        input_device_index=device_id,
                        frames_per_buffer=self.chunk_size
                    )
                    working_rate = rate
                    print(f"✅ サンプルレート {rate}Hz で接続成功")
                    break
                except Exception as e:
                    print(f"❌ サンプルレート {rate}Hz で失敗: {e}")
                    continue
            
            if not working_rate:
                print("❌ どのサンプルレートでも接続できませんでした")
                return
            
            print("🎵 音声レベルテスト開始 (10秒間)...")
            print("💬 大きな声で話してください!")
            
            max_volume = 0
            frame_count = 0
            volumes = []
            
            start_time = time.time()
            while time.time() - start_time < 10:  # 10秒間テスト
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    frame_count += 1
                    
                    # 音声レベル計算
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    if len(audio_data) > 0:
                        volume = np.sqrt(np.mean(audio_data.astype(np.float64)**2))
                        volumes.append(volume)
                        max_volume = max(max_volume, volume)
                        
                        # リアルタイム表示
                        if frame_count % 15 == 0:  # 約1秒ごと
                            elapsed = time.time() - start_time
                            bar = "█" * min(int(volume / 100), 20)
                            print(f"🎤 {elapsed:.1f}s レベル:{volume:6.0f} |{bar:<20}| 最大:{max_volume:.0f}")
                
                except Exception as e:
                    print(f"❌ 読み取りエラー: {e}")
                    break
            
            stream.stop_stream()
            stream.close()
            
            # 結果分析
            print(f"\n📊 テスト結果 (デバイス{device_id}):")
            print(f"  - 使用サンプルレート: {working_rate}Hz")
            print(f"  - 最大音声レベル: {max_volume:.0f}")
            print(f"  - 平均音声レベル: {np.mean(volumes):.0f}")
            print(f"  - 総フレーム数: {frame_count}")
            
            if max_volume > 500:
                print("✅ 音声レベル良好 - このデバイスは正常に動作します")
                return device_id, working_rate
            elif max_volume > 100:
                print("⚠️  音声レベル低め - 使用可能ですがマイク音量を上げてください")
                return device_id, working_rate
            else:
                print("❌ 音声レベル不十分 - このデバイスでは音声認識が困難です")
                
        except Exception as e:
            print(f"❌ デバイステストエラー: {e}")
        finally:
            p.terminate()
        
        return None, None
    
    def test_all_input_devices(self):
        """すべての入力デバイスをテスト"""
        p = pyaudio.PyAudio()
        working_devices = []
        
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"\n{'='*50}")
                result = self.test_specific_device(i)
                if result[0] is not None:
                    working_devices.append(result)
        
        p.terminate()
        
        print(f"\n🎯 推奨設定:")
        if working_devices:
            best_device, best_rate = working_devices[0]
            print(f"  - 推奨デバイスID: {best_device}")
            print(f"  - 推奨サンプルレート: {best_rate}Hz")
            
            # メインシステム用の設定を生成
            print(f"\n🔧 メインシステムでの設定方法:")
            print(f"VoiceRecorder初期化時に以下を指定:")
            print(f"  device_index={best_device}")
            print(f"  sample_rate={best_rate}")
        else:
            print("❌ 動作する入力デバイスが見つかりませんでした")
        
        return working_devices

if __name__ == "__main__":
    tester = MicrophoneDeviceTest()
    
    # まずデバイス一覧を表示
    default_device = tester.list_audio_devices()
    
    # 全デバイスをテスト
    working_devices = tester.test_all_input_devices()
    
    if working_devices:
        print(f"\n✅ テスト完了! {len(working_devices)}個の動作するデバイスが見つかりました")
    else:
        print("\n❌ 動作するマイクデバイスが見つかりませんでした")
        print("🔧 macOSの設定を確認してください:")
        print("  1. システム環境設定 > セキュリティとプライバシー > プライバシー > マイク")
        print("  2. ターミナル/VS Code にマイクへのアクセスを許可")
        print("  3. 音声入力レベルを上げる (システム環境設定 > サウンド > 入力)")