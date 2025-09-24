#!/usr/bin/env python3
"""
ウェイクワード検出のテストスクリプト
"""

import pyaudio
import tempfile
import wave
import os
import time
from faster_whisper import WhisperModel

class SimpleWakeWordDetector:
    def __init__(self):
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        self.wake_words = ["シリウスくん", "シリウス君", "しりうすくん"]
        self.buffer_duration = 3.0  # 3秒間のバッファ
        self.check_interval = 1.5   # 1.5秒ごとにチェック
        
        # Whisperモデルロード
        print("🔄 Faster-Whisperモデルをロード中...")
        self.whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        print("✅ モデルロード完了")
        
        self.audio_buffer = []
        self.last_check = 0
        self.running = False
    
    def start_monitoring(self):
        """監視開始"""
        print("🔊 ウェイクワード監視を開始します...")
        print(f"🎯 検出対象: {', '.join(self.wake_words)}")
        print("📢 「シリウスくん」と言ってみてください（Ctrl+Cで終了）")
        
        self.running = True
        
        # PyAudio初期化
        p = pyaudio.PyAudio()
        stream = p.open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
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
                
                # 音声レベルチェック（デバッグ用）
                if len(self.audio_buffer) % 20 == 0:
                    import numpy as np
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume = np.sqrt(np.mean(audio_data**2))
                    if volume > 200:
                        print(f"🎤 音声検出: レベル={volume:.0f}")
                
                # 定期的にウェイクワード検出
                current_time = time.time()
                if (current_time - self.last_check >= self.check_interval and 
                    len(self.audio_buffer) >= buffer_frames // 2):
                    
                    self.last_check = current_time
                    print(f"🔍 ウェイクワード検出実行中... (バッファ: {len(self.audio_buffer)}フレーム)")
                    
                    if self.check_wake_word():
                        print("🎉 ウェイクワード検出成功！")
                        break
                        
        except KeyboardInterrupt:
            print("\n⏹️ 監視を停止します")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    def check_wake_word(self):
        """ウェイクワード検出処理"""
        try:
            # 音声データを一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(pyaudio.get_sample_size(self.format))
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(b''.join(self.audio_buffer))
            
            # 音声認識
            segments, info = self.whisper_model.transcribe(
                temp_filename,
                language="ja",
                beam_size=1,
                temperature=0.2,
                no_speech_threshold=0.6
            )
            
            # 認識結果を取得
            full_text = ""
            for segment in segments:
                full_text += segment.text.strip()
            
            print(f"📝 認識結果: '{full_text}'")
            
            # ウェイクワード検索
            for wake_word in self.wake_words:
                if wake_word in full_text:
                    print(f"✅ ウェイクワード検出: '{wake_word}' in '{full_text}'")
                    return True
                # 柔軟マッチング
                elif self.flexible_match(wake_word, full_text):
                    print(f"✅ ウェイクワード検出（柔軟）: '{wake_word}' ~ '{full_text}'")
                    return True
            
            # 一時ファイル削除
            try:
                os.unlink(temp_filename)
            except:
                pass
                
        except Exception as e:
            print(f"❌ ウェイクワード検出エラー: {e}")
        
        return False
    
    def flexible_match(self, wake_word, text):
        """柔軟マッチング"""
        patterns = [
            "シリウス", "しりうす", "君", "くん",
            "sirius", "Sirius"
        ]
        
        found_count = 0
        for pattern in patterns:
            if pattern in text:
                found_count += 1
        
        return found_count >= 2  # 2つ以上のパターンがマッチした場合

if __name__ == "__main__":
    detector = SimpleWakeWordDetector()
    detector.start_monitoring()