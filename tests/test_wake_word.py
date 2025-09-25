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
        self.sample_rate = 48000        # sync_siriusfaceと同じ（MacBook Air最適化）
        self.chunk_size = 1024
        self.channels = 1
        self.format = pyaudio.paInt16
        self.device_index = 1           # MacBook Air内蔵マイク
        
        # 「シリウスくん」専用設定
        self.wake_words = ["シリウスくん"]
        
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
                
                # 音声レベルチェック（sync_siriusfaceと同じ）
                if len(self.audio_buffer) % 15 == 0:  # 15フレームに1回表示（約1秒ごと）
                    import numpy as np
                    audio_data = np.frombuffer(data, dtype=np.int16)
                    volume = np.sqrt(np.mean(audio_data**2))
                    status_icon = "🔊" if volume > self.volume_threshold else "🔇"
                    print(f"� 監視中... フレーム#{len(self.audio_buffer)}, 音声レベル:{volume:.0f} {status_icon}")
                
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
                            print("\n" + "="*50)
                            print("🎉 「シリウスくん」検出成功！")
                            print("="*50)
                            break
                    # 音声レベル不足時はサイレント（ログ出力なし）
                        
        except KeyboardInterrupt:
            print("\n⏹️ 監視を停止します")
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
    
    def check_wake_word(self):
        """ウェイクワード検出処理（sync_siriusfaceと同じ実装）"""
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
                
                # 「シリウスくん」の検出チェック（詳細表示）
                if "シリウスくん" in full_text:
                    print(f"✅ 【完全一致】 「シリウスくん」が含まれています")
                    return True
                elif self.flexible_match("シリウスくん", full_text):
                    print(f"✅ 【柔軟一致】 シリウス関連ワードが検出されました")
                    return True
                else:
                    print(f"❌ 「シリウスくん」またはその類似表現が見つかりません")
                    # どのパターンも一致しなかった場合の詳細情報
                    self.show_match_analysis(full_text)
            else:
                print("❌ 音声認識できませんでした（無音または認識不可）")
            
            # 一時ファイル削除
            try:
                os.unlink(temp_filename)
            except:
                pass
                
        except Exception as e:
            print(f"❌ ウェイクワード検出エラー: {e}")
        
        return False
    
    def flexible_match(self, wake_word, text):
        """高精度柔軟マッチング（音韻類似性も考慮）"""
        # 基本的な変換パターン
        basic_patterns = [
            wake_word,                                    # シリウスくん
            wake_word.replace('シリウス', 'しりうす'),      # しりうすくん  
            wake_word.replace('くん', '君'),               # シリウス君
            'シリウス',                                   # 短縮形
            'しりうす',                                   # ひらがな短縮形
            'シリウス君',                                 # 漢字版
            'しりうす君'                                  # ひらがな+漢字
        ]
        
        # 音韻類似パターン（認識ミスに対応）
        phonetic_patterns = [
            'シリュースくん',     # よくある認識ミス
            'シリュース君',       # 漢字版
            'しりゅーすくん',     # ひらがな版
            'シリュウスくん',     # 別の認識ミス
            'シリューズくん',     # 別のパターン
            'シリユースくん',     # 別のパターン
            'シリウースくん',     # 長音違い
            'シリエスくん',       # 短縮認識ミス
            'シリース',           # 短縮形の認識ミス
            'シリュース',         # 短縮形
        ]
        
        # 部分文字列マッチング（より柔軟）
        core_patterns = [
            'シリウ',            # コア部分
            'しりう',            # ひらがなコア
            'シリュ',            # 認識ミスコア
        ]
        
        # すべてのパターンをチェック
        all_patterns = basic_patterns + phonetic_patterns
        for pattern in all_patterns:
            if pattern in text:
                print(f"🎯 マッチパターン: '{pattern}' found in '{text}'")
                return True
        
        # コア部分 + 敬語の組み合わせチェック
        for core in core_patterns:
            if core in text and ('くん' in text or '君' in text or 'さん' in text):
                print(f"🎯 コア+敬語マッチ: '{core}' + 敬語 in '{text}'")
                return True
        
        return False
    
    def show_match_analysis(self, text):
        """マッチング分析を表示（デバッグ用）"""
        print("🔍 詳細マッチング分析:")
        
        # 文字単位での類似性チェック
        target = "シリウスくん"
        similarity_chars = []
        
        for char in target:
            if char in text:
                similarity_chars.append(f"'{char}'✅")
            else:
                similarity_chars.append(f"'{char}'❌")
        
        print(f"   文字チェック: {' '.join(similarity_chars)}")
        
        # よくある認識ミスパターンの確認
        common_mistakes = [
            ('シリュース', 'ウ→ュー変換ミス'),
            ('シリウース', '長音追加'),
            ('シリエス', 'ウ脱落'),
            ('しりうす', 'ひらがな変換'),
            ('君', 'くん→君変換')
        ]
        
        found_patterns = []
        for mistake, description in common_mistakes:
            if mistake in text:
                found_patterns.append(f"'{mistake}'({description})")
        
        if found_patterns:
            print(f"   類似パターン: {', '.join(found_patterns)}")
        else:
            print(f"   類似パターン: 見つかりませんでした")

if __name__ == "__main__":
    detector = SimpleWakeWordDetector()
    detector.start_monitoring()