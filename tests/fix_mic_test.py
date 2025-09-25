#!/usr/bin/env python3
"""
マイク問題修正版テスト
"""

import sys
import pyaudio
import numpy as np
import time

def test_microphone_device(device_id, duration=5):
    """特定のマイクデバイスをテスト"""
    print(f"\n🔊 デバイス{device_id}のテストを開始します")
    
    p = pyaudio.PyAudio()
    device_info = p.get_device_info_by_index(device_id)
    print(f"テスト対象: {device_info['name']}")
    
    # サンプルレートを設定
    sample_rate = int(device_info['defaultSampleRate'])
    chunk_size = 1024
    
    try:
        # より寛容な設定でストリームを開く
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            input_device_index=device_id,
            frames_per_buffer=chunk_size
        )
        
        print(f"✅ サンプルレート {sample_rate}Hz で接続成功")
        print(f"🎵 {duration}秒間の音声レベルテスト開始...")
        print("💬 大きな声で「シリウスくん」と言ってください!")
        
        max_volume = 0
        frame_count = 0
        high_volume_frames = 0
        
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                data = stream.read(chunk_size, exception_on_overflow=False)
                frame_count += 1
                
                # 音声レベル計算 (型安全)
                audio_data = np.frombuffer(data, dtype=np.int16)
                if len(audio_data) > 0:
                    # float64に変換してから計算
                    audio_float = audio_data.astype(np.float64)
                    volume = np.sqrt(np.mean(audio_float**2))
                    max_volume = max(max_volume, volume)
                    
                    if volume > 200:
                        high_volume_frames += 1
                    
                    # リアルタイム表示 (1秒ごと)
                    if frame_count % (sample_rate // chunk_size) == 0:
                        elapsed = time.time() - start_time
                        bar = "█" * min(int(volume / 50), 30)
                        status = "🔊" if volume > 200 else "🔇"
                        print(f"{status} {elapsed:.1f}s レベル:{volume:6.0f} |{bar:<30}| 最大:{max_volume:.0f}")
            
            except Exception as e:
                print(f"❌ 読み取りエラー: {e}")
                break
        
        stream.stop_stream()
        stream.close()
        
        # 結果分析
        print(f"\n📊 テスト結果 (デバイス{device_id}: {device_info['name']}):")
        print(f"  - サンプルレート: {sample_rate}Hz")
        print(f"  - 最大音声レベル: {max_volume:.0f}")
        print(f"  - 高音量フレーム: {high_volume_frames}/{frame_count}")
        print(f"  - 音声検出率: {high_volume_frames/frame_count*100:.1f}%")
        
        if max_volume > 1000:
            print("✅ 音声レベル優秀 - このデバイスは完璧に動作します")
            recommendation = "excellent"
        elif max_volume > 500:
            print("✅ 音声レベル良好 - このデバイスは正常に動作します")
            recommendation = "good"
        elif max_volume > 100:
            print("⚠️  音声レベル低め - マイク音量を上げれば使用可能です")
            recommendation = "usable"
        else:
            print("❌ 音声レベル不十分 - このデバイスでは音声認識が困難です")
            recommendation = "poor"
        
        return {
            'device_id': device_id,
            'device_name': device_info['name'],
            'sample_rate': sample_rate,
            'max_volume': max_volume,
            'recommendation': recommendation,
            'detection_rate': high_volume_frames/frame_count*100 if frame_count > 0 else 0
        }
        
    except Exception as e:
        print(f"❌ デバイス{device_id}テストエラー: {e}")
        return None
    finally:
        p.terminate()

def main():
    print("🎤 マイクデバイステスト開始")
    
    # PyAudio初期化してデバイス一覧を取得
    p = pyaudio.PyAudio()
    
    input_devices = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0:
            input_devices.append((i, info['name']))
            print(f"デバイス{i}: {info['name']}")
    
    p.terminate()
    
    if not input_devices:
        print("❌ 入力デバイスが見つかりません")
        return
    
    print(f"\n📋 {len(input_devices)}個の入力デバイスが見つかりました")
    
    # 各デバイスをテスト
    results = []
    for device_id, device_name in input_devices:
        result = test_microphone_device(device_id, duration=8)
        if result:
            results.append(result)
        print("-" * 50)
        
        # ユーザーに次のテストを続けるか確認
        if device_id < input_devices[-1][0]:  # 最後のデバイスでなければ
            response = input(f"\n次のデバイスをテストしますか? (y/n): ")
            if response.lower() != 'y':
                break
    
    # 結果のまとめ
    print("\n" + "="*60)
    print("🎯 テスト結果まとめ:")
    
    if results:
        # 結果をスコア順にソート
        score_map = {'excellent': 4, 'good': 3, 'usable': 2, 'poor': 1}
        results.sort(key=lambda x: (score_map.get(x['recommendation'], 0), x['max_volume']), reverse=True)
        
        print("\n推奨順:")
        for i, result in enumerate(results, 1):
            status_icons = {
                'excellent': '🥇', 'good': '🥈', 
                'usable': '🥉', 'poor': '❌'
            }
            icon = status_icons.get(result['recommendation'], '❓')
            
            print(f"{i}. {icon} デバイス{result['device_id']}: {result['device_name']}")
            print(f"   最大音量: {result['max_volume']:.0f}, 検出率: {result['detection_rate']:.1f}%")
            print(f"   サンプルレート: {result['sample_rate']}Hz")
        
        # メインシステム用の推奨設定
        best = results[0]
        print(f"\n🔧 メインシステムでの推奨設定:")
        print(f"VoiceRecorder初期化時に以下を指定してください:")
        print(f"  device_index={best['device_id']}")
        print(f"  sample_rate={best['sample_rate']}")
        
        # 設定適用方法の表示
        print(f"\n💡 設定適用方法:")
        print(f"sync_siriusface.py の VoiceRecorder 初期化部分で:")
        print(f"self.voice_recorder = VoiceRecorder(device_index={best['device_id']})")
        
    else:
        print("❌ 使用可能なマイクデバイスが見つかりませんでした")
        print("\n🔧 macOSの設定を確認してください:")
        print("1. システム環境設定 > セキュリティとプライバシー > プライバシー > マイク")
        print("2. ターミナルまたはVS Codeにマイクへのアクセスを許可")
        print("3. システム環境設定 > サウンド > 入力 で入力音量を最大にする")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ テストを中断しました")
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()