#!/usr/bin/env python3
"""
「シリウスくん」専用ウェイクワード検出テスト - リアルタイム監視
"""

import pyaudio
import tempfile
import wave
import os
import time
from faster_whisper import WhisperModel

class SiriusWakeWordDetector:
    def __init__(self):
        self.sample_rate = 48000        # sync_siriusfaceと同じ（MacBook Air最適化）
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        self.device_index = 1           # MacBook Air内蔵マイク
        
        # 「シリウスくん」専用設定
        self.wake_word = "シリウスくん"
        
        self.buffer_duration = 3.0  # 3秒間のバッファ
        self.check_interval = 1.5   # 1.5秒ごとにチェック
        self.volume_threshold = 20  # sync_siriusfaceと同じ低い閾値
        
        # Whisperモデルロード（sync_siriusfaceと同じ設定）
        print("🔄 Faster-Whisperモデル（medium）をロード中...")
        self.whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
        print("✅ モデルロード完了")
        
        self.audio_buffer = []
        self.last_check = 0
        self.running = False
    
    def start_monitoring(self):
        """監視開始"""
        print("="*50)
        print("🎤 シリウスくん検出テスト - リアルタイム監視中")
        print("🎯 検出ワード: シリウスくん")
        print("📢 マイクに向かって「シリウスくん」と言ってください")
        print("⏹️  終了: Ctrl+C")
        print("="*50)
        
        self.running = True
        
        # PyAudio初期化（MacBook Airマイクを指定）
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self.device_index,  # MacBook Airマイクを指定
            frames_per_buffer=self.chunk_size
        )
        
        try:
            buffer_frames = int(self.buffer_duration * self.sample_rate / self.chunk_size)
            
            while self.running:
                # 音声データ読み取り
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_buffer.append(data)
                
                # バッファサイズ制限
                if len(self.audio_buffer) > buffer_frames:
                    self.audio_buffer.pop(0)
                
                # 音声検出時のみログ出力（静音時はログなし）
                if len(self.audio_buffer) % 15 == 0:
                    import numpy as np
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume = np.sqrt(np.mean(audio_data**2))
                    if volume > self.volume_threshold:  # 音声が検出された時のみ表示
                        print(f"🎤 音声検出中... レベル:{volume:.0f} [リアルタイム処理中]")
                
                # 定期的にウェイクワード検出（sync_siriusfaceと同じロジック）
                current_time = time.time()
                if (current_time - self.last_check >= self.check_interval and 
                    len(self.audio_buffer) >= buffer_frames // 2):
                    
                    self.last_check = current_time
                    
                    # 音声レベルをチェックしてから認識処理へ（sync_siriusfaceと同じ）
                    import numpy as np
                    recent_audio = b''.join(self.audio_buffer[-10:])  # 最新10フレームをチェック
                    audio_data = np.frombuffer(recent_audio, dtype=np.int16)
                    volume = np.sqrt(np.mean(audio_data**2)) if len(audio_data) > 0 else 0
                    
                    if volume > self.volume_threshold:
                        print(f"🔍 認識開始... [音声レベル:{volume:.0f}] [リアルタイム解析中]")
                        if self.check_wake_word():
                            print("\\n" + "="*50)
                            print("🎉 「シリウスくん」検出成功！")
                            print("="*50)
                            break
                    # 音声レベル不足時はサイレント（ログ出力なし）
                        
        except KeyboardInterrupt:
            print("\\n⏹️ 監視を停止します")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    def check_wake_word(self):
        """ウェイクワード検出処理（シリウスくん専用）"""
        try:
            # 音声データを一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(pyaudio.get_sample_size(self.format))
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(b''.join(self.audio_buffer))
            
            # 音声認識実行
            print("⚡ Whisper解析中...", end="", flush=True)
            segments, info = self.whisper_model.transcribe(
                temp_filename,
                language="ja",
                beam_size=3,  # sync_siriusfaceと同じ
                temperature=0.0,  # sync_siriusfaceと同じ
                no_speech_threshold=0.2,  # sync_siriusfaceと同じ
                condition_on_previous_text=False,
                word_timestamps=False
            )
            
            # 認識結果を取得
            full_text = ""
            for segment in segments:
                full_text += segment.text.strip()
            
            print("完了")
            
            if full_text.strip():
                print(f"📝 認識結果: '{full_text}'")
                
                # 「シリウスくん」の検出チェック
                if "シリウスくん" in full_text:
                    print(f"✅ 完全一致: 「シリウスくん」検出")
                    return True
                elif self.flexible_match("シリウスくん", full_text):
                    print(f"✅ 部分一致: シリウス関連ワード検出")
                    return True
                else:
                    print(f"❌ 「シリウスくん」ではありません")
            else:
                print("❌ 音声認識できませんでした")
            
            # 一時ファイル削除
            try:
                os.unlink(temp_filename)
            except:
                pass
                
        except Exception as e:
            print(f"❌ エラー: {e}")
        
        return False
    
    def flexible_match(self, wake_word, text):
        """柔軟マッチング（シリウス関連ワードの検出）"""
        # シリウス関連の変換パターン
        patterns = [
            "シリウス",
            "しりうす", 
            "シリウス君",
            "しりうす君",
            "シリウスくん",
            "しりうすくん"
        ]
        
        for pattern in patterns:
            if pattern in text:
                return True
        return False

if __name__ == "__main__":
    detector = SiriusWakeWordDetector()
    detector.start_monitoring()