#!/usr/bin/env python3
"""
シリウス音声対話UIアプリケーション
PySide6 + ローカルLLM + VOICEVOX AudioQuery統合システム
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import os
import threading
import time
import logging

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QComboBox, 
    QProgressBar, QScrollArea, QFrame, QSplitter, QGroupBox,
    QCheckBox, QSpinBox, QSlider, QMessageBox, QDialog, QDialogButtonBox, QMenu,
    QTabWidget
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QColor, QShortcut, QKeySequence

# 音声関連のインポート
import speech_recognition as sr
import pyaudio
import wave
from faster_whisper import WhisperModel

# LLM Face Controllerのインポート
sys.path.append('/Users/kotaniryota/NLAB/LocalLLM_Test/core')
from llm_face_controller import LLMFaceController

# ログ設定
logger = logging.getLogger(__name__)

class VoiceRecorder(QThread):
    """音声録音・認識処理用スレッド"""
    recording_started = Signal()
    recording_stopped = Signal()
    transcription_ready = Signal(str)
    transcription_with_confidence = Signal(str, dict)  # テキストと信頼度情報
    error_occurred = Signal(str)
    wake_word_detected = Signal(str)  # ウェイクワード検出シグナル
    real_time_monitoring = Signal(bool)  # リアルタイム監視状態
    
    def __init__(self, model_name="medium", device_index=None):
        super().__init__()
        self.is_recording = False
        self.audio_data = []
        # 音声品質設定（日本語音声認識に最適化・高品質）
        self.sample_rate = 48000        # マイクのネイティブサンプルレートを使用
        self.chunk_size = 1024          # バッファサイズ
        self.channels = 1               # モノラル録音
        self.format = pyaudio.paInt16   # 16bit PCM
        self.record_seconds_min = 1.0   # 最小録音時間（秒）
        self.device_index = 1 if device_index is None else device_index  # MacBook Airのマイクをデフォルトで使用
        
        # 精度履歴管理
        self.confidence_history = []  # 信頼度履歴
        self.recognition_stats = {
            'total_recognitions': 0,
            'avg_confidence': 0.0,
            'min_confidence': 1.0,
            'max_confidence': 0.0
        }
        
        # 音声自動終了機能
        self.silence_detection_enabled = True  # 沈黙検出機能を有効にするかどうか
        self.silence_threshold = 2.0  # 沈黙検出の閾値（秒）
        self.silence_timer = QTimer()  # 沈黙検出用タイマー
        self.silence_timer.setSingleShot(True)
        self.silence_timer.timeout.connect(self.on_silence_detected)
        self.last_voice_time = 0  # 最後に音声が検出された時刻
        self.voice_threshold = 1000  # 音声レベルの閾値
        self.auto_stopped_by_silence = False  # 沈黙検出による自動停止フラグ
        
        # リアルタイム監視設定
        self.real_time_enabled = False  # リアルタイム監視の有効/無効
        self.wake_word_enabled = True  # ウェイクワード検出の有効/無効
        self.wake_words = [
            "シリウスくん", "シリウス君", "しりうすくん",
            "シリウス", "しりうす", "シリウスさん",
            "こんにちは", "おはよう", "起きて"  # より簡単な代替ワード
        ]  # 検出するウェイクワード
        self.wake_buffer_duration = 3.0  # ウェイクワード検出用バッファ時間（秒）
        self.wake_buffer = []  # ウェイクワード検出用音声バッファ
        self.wake_check_interval = 1.5  # ウェイクワード検出間隔（秒）
        self.last_wake_check = 0  # 最後のウェイクワード検出時刻
        
        # Whisperモデル（選択されたモデルを使用）
        self.load_whisper_model(model_name)
    
    def load_whisper_model(self, model_name):
        """Whisperモデルをロード"""
        try:
            # 警告を抑制
            import warnings
            warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
            
            print(f"🔄 Faster-Whisperモデル（{model_name}）をロード中...")
            # faster-whisperでは計算タイプとデバイスを指定可能
            # MacではCPUを使用、量子化で高速化
            self.whisper_model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8"  # 量子化で高速化・メモリ使用量削減
            )
            print(f"✅ Faster-Whisperモデル（{model_name}）のロードが完了しました")
            self.model_name = model_name
        except Exception as e:
            print(f"❌ Faster-Whisperモデルロードエラー: {e}")
            # フォールバック: large → medium → base の順で試行
            fallback_models = ["medium", "base", "small"]
            if model_name in fallback_models:
                fallback_models.remove(model_name)
            
            fallback_success = False
            for fallback_model in fallback_models:
                try:
                    print(f"🔄 フォールバック: {fallback_model}モデルを試行中...")
                    self.whisper_model = WhisperModel(
                        fallback_model,
                        device="cpu",
                        compute_type="int8"
                    )
                    print(f"✅ フォールバック成功: {fallback_model}モデルを使用します")
                    self.model_name = fallback_model
                    fallback_success = True
                    break
                except Exception as fallback_error:
                    print(f"❌ {fallback_model}モデルもロードに失敗: {fallback_error}")
                    continue
            
            if not fallback_success:
                print("❌ すべてのWhisperモデルのロードに失敗しました")
                self.whisper_model = None
                self.model_name = None
    
    @staticmethod
    def get_audio_devices():
        """利用可能な音声入力デバイスを取得"""
        devices = []
        try:
            p = pyaudio.PyAudio()
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                # 入力チャンネルがあるデバイスのみを追加
                if info['maxInputChannels'] > 0:
                    devices.append({
                        'index': i,
                        'name': info['name'],
                        'channels': info['maxInputChannels'],
                        'sample_rate': int(info['defaultSampleRate'])
                    })
            p.terminate()
        except Exception as e:
            print(f"❌ 音声デバイス取得エラー: {e}")
        return devices
    
    def start_recording(self):
        """録音開始"""
        if not self.is_recording:
            self.is_recording = True
            self.audio_data = []
            self.auto_stopped_by_silence = False  # フラグをリセット
            self.start()
    
    def stop_recording(self):
        """録音停止"""
        self.is_recording = False
        
        # 沈黙検出タイマーを停止
        if hasattr(self, 'silence_timer') and self.silence_timer.isActive():
            self.silence_timer.stop()
    
    def start_real_time_monitoring(self):
        """リアルタイム音声監視を開始"""
        if not self.real_time_enabled:
            self.real_time_enabled = True
            self.wake_buffer = []
            self.last_wake_check = 0
            print("🔊 リアルタイム音声監視を開始しました")
            print(f"🎯 検出対象ワード: {', '.join(self.wake_words)}")
            print(f"⚙️ 設定:")
            print(f"  - バッファ時間: {self.wake_buffer_duration}秒")
            print(f"  - チェック間隔: {self.wake_check_interval}秒")
            print(f"  - サンプルレート: {self.sample_rate}Hz")
            print(f"  - チャンクサイズ: {self.chunk_size}")
            
            self.real_time_monitoring.emit(True)
            # バックグラウンドで音声監視スレッドを開始
            if not self.isRunning():
                print("🎵 音声監視スレッドを開始しています...")
                self.start()
            else:
                print("⚠️ 音声監視スレッドは既に実行中です")
    
    def stop_real_time_monitoring(self):
        """リアルタイム音声監視を停止"""
        if self.real_time_enabled:
            self.real_time_enabled = False
            self.wake_buffer = []
            print("🔇 リアルタイム音声監視を停止しました")
            self.real_time_monitoring.emit(False)
    
    def check_wake_word(self, audio_chunk):
        """ウェイクワード検出処理"""
        if not self.wake_word_enabled or not self.real_time_enabled:
            return False
        
        import time
        current_time = time.time()
        
        # ウェイクワード検出用バッファに音声データを追加
        self.wake_buffer.append(audio_chunk)
        
        # 音声レベルをチェックしてデバッグ表示（監視が動いていることを確認）
        if len(self.wake_buffer) % 30 == 0:  # 30フレームに1回表示（約2秒ごと）
            import numpy as np
            audio_data = np.frombuffer(audio_chunk, dtype=np.int16)
            volume = np.sqrt(np.mean(audio_data**2))
            print(f"� 監視中... フレーム#{len(self.wake_buffer)}, 音声レベル:{volume:.0f} {'🔊' if volume > 200 else '🔇'}")
        
        # バッファサイズを制限（指定時間分のデータのみ保持）
        buffer_frames = int(self.wake_buffer_duration * self.sample_rate / self.chunk_size)
        if len(self.wake_buffer) > buffer_frames:
            self.wake_buffer.pop(0)
        
        # 定期的にウェイクワード検出を実行
        if current_time - self.last_wake_check >= self.wake_check_interval:
            self.last_wake_check = current_time
            
            if len(self.wake_buffer) >= buffer_frames // 2:  # 最低限の音声データが蓄積された場合
                # 音声レベルをチェックしてから認識処理へ
                import numpy as np
                recent_audio = b''.join(self.wake_buffer[-10:])  # 最新10フレームをチェック
                audio_data = np.frombuffer(recent_audio, dtype=np.int16)
                volume = np.sqrt(np.mean(audio_data**2)) if len(audio_data) > 0 else 0
                
                print(f"🔍 ウェイクワード検出を実行中... (バッファ:{len(self.wake_buffer)}, 音声レベル:{volume:.0f})")
                
                # 音声がある程度のレベル以上の場合のみ認識処理を実行
                if volume > 20:  # 音声レベル閾値をさらに下げて高感度に (80 -> 20)
                    print(f"🎤 音声レベル{volume:.0f}で認識処理開始")
                    return self.process_wake_word_detection()
                else:
                    print(f"🔇 音声レベルが低いため認識をスキップ (レベル:{volume:.0f} < 20)")
        
        return False
    
    def process_wake_word_detection(self):
        """蓄積された音声データでウェイクワード検出を実行"""
        try:
            print(f"🎯 ウェイクワード検出処理を開始 (バッファサイズ: {len(self.wake_buffer)}フレーム)")
            
            # バッファの音声データを一時ファイルに保存
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(pyaudio.get_sample_size(self.format))
                    wf.setframerate(self.sample_rate)
                    wf.writeframes(b''.join(self.wake_buffer))
            
            print(f"📁 音声データを一時ファイルに保存: {temp_filename}")
            
            # 短時間音声認識（低精度でも高速）
            if self.whisper_model:
                print("🔊 Whisperによる音声認識を開始...")
                segments, info = self.whisper_model.transcribe(
                    temp_filename,
                    language="ja",
                    beam_size=3,  # ビームサーチを増やして精度向上 (1 -> 3)
                    temperature=0.0,  # より確定的な結果を得る (0.2 -> 0.0)
                    no_speech_threshold=0.2,  # 音声なしの判定をさらに緩く (0.8 -> 0.2)
                    condition_on_previous_text=False,  # 前のテキストに依存しない
                    word_timestamps=False  # 単語タイムスタンプは不要
                )
                
                # 認識結果からウェイクワードを検索
                full_text = ""
                for segment in segments:
                    full_text += segment.text.strip()
                
                print(f"🔍 ウェイクワード検出チェック: '{full_text}'")
                
                # デバッグ: 認識された音声が空でない場合は詳細表示
                if full_text.strip():
                    print(f"📝 音声認識結果: 長さ={len(full_text)}, 内容='{full_text}'")
                    print(f"🎯 検索対象: {self.wake_words}")
                
                # ウェイクワードが含まれているかチェック（部分一致とより柔軟な検索）
                for wake_word in self.wake_words:
                    # 厳密一致
                    if wake_word in full_text:
                        print(f"✅ ウェイクワード検出（厳密一致）: '{wake_word}' in '{full_text}'")
                        self.wake_word_detected.emit(wake_word)
                        self.last_wake_check = time.time() + 2.0
                        return True
                    # 柔軟一致（ひらがな/カタカナ変換を考慮）
                    elif self.fuzzy_match_wake_word(wake_word, full_text):
                        print(f"✅ ウェイクワード検出（柔軟一致）: '{wake_word}' ~ '{full_text}'")
                        self.wake_word_detected.emit(wake_word)
                        self.last_wake_check = time.time() + 2.0
                        return True
            
            # 一時ファイルを削除
            try:
                os.unlink(temp_filename)
            except:
                pass
                
        except Exception as e:
            print(f"❌ ウェイクワード検出エラー: {e}")
        
        return False
    
    def fuzzy_match_wake_word(self, wake_word, text):
        """ウェイクワードの柔軟マッチング（ひらがな/カタカナ変換を考慮）"""
        # 基本的な変換パターン
        patterns = [
            wake_word,
            wake_word.replace('シリウス', 'しりうす'),
            wake_word.replace('くん', '君'),
            wake_word.replace('シリウス', 'シリウス'),
            'シリウス',
            'しりうす',
            'シリウス君',
            'しりうす君'
        ]
        
        for pattern in patterns:
            if pattern in text:
                return True
        return False
    
    def run(self):
        """録音処理実行"""
        try:
            # PyAudioの初期化
            p = pyaudio.PyAudio()
            
            # ストリーム開始
            stream = p.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,  # マイクデバイスを指定
                frames_per_buffer=self.chunk_size
            )
            
            # 録音開始またはリアルタイム監視開始のシグナル
            if self.is_recording:
                self.recording_started.emit()
            elif self.real_time_enabled:
                print("🎵 リアルタイム音声監視を開始します...")
                print("💡 マイクに向かって話してください")
            else:
                print("❌ 録音もリアルタイム監視も無効です")
                return
            
            # 沈黙検出の初期化
            import time
            self.last_voice_time = time.time()
            self.has_detected_voice = False  # 音声が検出されたかどうか
            
            # 録音ループ（通常録音とリアルタイム監視の両方に対応）
            loop_count = 0
            while self.is_recording or self.real_time_enabled:
                loop_count += 1
                
                # 100ループごとに状態を報告
                if loop_count % 100 == 0 and self.real_time_enabled and not self.is_recording:
                    print(f"📊 監視継続中 - ループ#{loop_count}, リアルタイム監視:{self.real_time_enabled}")
                
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # 通常録音モードの場合
                    if self.is_recording:
                        self.audio_data.append(data)
                        
                        # 音声レベル検出（沈黙検出用）
                        if self.silence_detection_enabled:
                            self.detect_voice_activity(data)
                    
                    # リアルタイム監視モードの場合
                    elif self.real_time_enabled:
                        # ウェイクワード検出
                        if self.check_wake_word(data):
                            # ウェイクワード検出時は監視を一時停止
                            break
                    
                except Exception as e:
                    print(f"録音エラー: {e}")
                    break
            
            # ストリーム停止
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            self.recording_stopped.emit()
            
            # 音声認識処理
            if self.audio_data:
                self.process_audio()
                
        except Exception as e:
            self.error_occurred.emit(f"録音処理エラー: {str(e)}")
    
    def process_audio(self):
        """音声データを処理してテキストに変換"""
        resample_filename = None  # リサンプリング用ファイル名を初期化
        
        try:
            # 録音時間をチェック
            total_frames = len(self.audio_data) * self.chunk_size
            duration = total_frames / self.sample_rate
            print(f"🎤 録音時間: {duration:.2f}秒")
            
            if duration < self.record_seconds_min:
                self.error_occurred.emit(f"録音時間が短すぎます（{duration:.1f}秒）。{self.record_seconds_min}秒以上録音してください。")
                return
            
            # 一時ファイルに音声データを保存
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                # WAVファイルとして保存（高品質設定）
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.channels)
                    wf.setsampwidth(pyaudio.get_sample_size(self.format))
                    wf.setframerate(self.sample_rate)
                    
                    # 音声データを結合して正規化
                    audio_bytes = b''.join(self.audio_data)
                    
                    # 簡単な音量正規化（オプション）
                    import array
                    audio_array = array.array('h', audio_bytes)
                    if len(audio_array) > 0:
                        # 最大音量を取得
                        max_amplitude = max(abs(sample) for sample in audio_array)
                        if max_amplitude > 0:
                            # 正規化係数を計算（70%の音量に調整）
                            normalization_factor = int(32767 * 0.7 / max_amplitude)
                            if normalization_factor > 1:
                                audio_array = array.array('h', [min(32767, max(-32768, int(sample * normalization_factor))) for sample in audio_array])
                                audio_bytes = audio_array.tobytes()
                    
                    wf.writeframes(audio_bytes)
            
            # Whisperは16kHzを推奨するため、48kHzで録音した場合はリサンプリング
            final_temp_filename = temp_filename
            resample_filename = None
            
            if self.sample_rate != 16000:
                print(f"🔄 音声データを{self.sample_rate}Hzから16000Hzにリサンプリング中...")
                try:
                    import librosa
                    # リサンプリング用の一時ファイルを作成
                    with tempfile.NamedTemporaryFile(suffix="_16k.wav", delete=False) as resample_file:
                        resample_filename = resample_file.name
                    
                    # librosaでリサンプリング
                    y, sr = librosa.load(temp_filename, sr=16000)
                    import soundfile as sf
                    sf.write(resample_filename, y, 16000)
                    final_temp_filename = resample_filename
                    print("✅ リサンプリング完了")
                except ImportError:
                    print("⚠️  librosaが利用できません。元のサンプルレートで処理します。")
                except Exception as e:
                    print(f"⚠️  リサンプリングエラー: {e}。元のサンプルレートで処理します。")
            
            # Faster-Whisperで音声認識（高精度日本語設定）
            if self.whisper_model:
                try:
                    print("🎤 音声認識処理開始（Faster-Whisper使用）...")
                    # faster-whisperでは segments と info を返す
                    # 単語レベルの信頼度情報を取得するため word_timestamps=True に変更
                    segments, info = self.whisper_model.transcribe(
                        final_temp_filename,  # リサンプリング済みファイルを使用
                        language="ja",              # 日本語指定
                        beam_size=5,                # ビームサーチサイズ（精度向上）
                        temperature=0.0,            # 決定論的出力（精度向上）
                        compression_ratio_threshold=2.4,  # 圧縮率閾値（ノイズ除去）
                        log_prob_threshold=-1.0,    # 確率閾値（低信頼度フィルタ）
                        no_speech_threshold=0.6,    # 無音判定閾値
                        condition_on_previous_text=False,  # 前のテキストに依存しない
                        initial_prompt="以下は日本語の音声です。",  # 日本語コンテキスト
                        word_timestamps=True,       # 単語レベルの信頼度取得のため有効化
                        vad_filter=True,           # Voice Activity Detection（音声区間検出）
                        vad_parameters=dict(min_silence_duration_ms=500)  # 無音区間の最小時間
                    )
                    
                    # セグメントからテキストと信頼度情報を抽出
                    segments_list = list(segments)  # ジェネレータをリストに変換
                    transcribed_text = "".join(segment.text for segment in segments_list).strip()
                    
                    # 信頼度情報を計算
                    confidence_info = self.calculate_confidence_metrics(segments_list, info)
                    
                    print(f"🎤 認識言語: {info.language} (確率: {info.language_probability:.2f})")
                    print(f"🎤 音声時間: {info.duration:.2f}秒")
                    print(f"📊 認識精度: {confidence_info['overall_confidence']:.1f}% (単語数: {confidence_info['word_count']})")
                    
                    # 結果の後処理（日本語特有の問題を修正）
                    if transcribed_text:
                        # 不要な空白や記号を除去
                        transcribed_text = transcribed_text.replace("。", "").replace("、", "").strip()
                        print(f"🎤 音声認識結果: '{transcribed_text}'")
                        
                        # 統計を更新
                        self.update_recognition_stats(confidence_info)
                        
                        # 通常のシグナルと信頼度付きシグナルの両方を送信
                        self.transcription_ready.emit(transcribed_text)
                        self.transcription_with_confidence.emit(transcribed_text, confidence_info)
                    else:
                        print("⚠️ 音声が認識できませんでした（空の結果）")
                        self.error_occurred.emit("音声が認識できませんでした。もう一度お試しください。")
                except Exception as e:
                    print(f"❌ Faster-Whisper音声認識エラー: {e}")
                    # エラー時のフォールバック処理を追加
                    error_msg = str(e)
                    if "CUDA" in error_msg or "GPU" in error_msg:
                        self.error_occurred.emit("GPU関連エラーが発生しました。CPUモードで再試行してください。")
                    elif "model" in error_msg.lower():
                        self.error_occurred.emit(f"モデルエラー: より軽量なモデル（baseやsmall）をお試しください。")
                    else:
                        self.error_occurred.emit(f"音声認識処理エラー: {error_msg}")
            else:
                self.error_occurred.emit("Faster-Whisperモデルが利用できません")
            
            # 一時ファイルを削除
            os.unlink(temp_filename)
            
        except Exception as e:
            self.error_occurred.emit(f"音声認識エラー: {str(e)}")
    
    def calculate_confidence_metrics(self, segments, info):
        """セグメントから信頼度メトリクスを計算"""
        try:
            word_confidences = []
            word_count = 0
            total_duration = 0
            
            for segment in segments:
                if hasattr(segment, 'words') and segment.words:
                    # 単語レベルの信頼度を取得
                    for word in segment.words:
                        if hasattr(word, 'probability') and word.probability is not None:
                            # 対数確率を信頼度パーセンテージに変換
                            confidence = min(100.0, max(0.0, (word.probability + 5.0) / 5.0 * 100))
                            word_confidences.append(confidence)
                            word_count += 1
                
                # セグメントレベルの情報
                if hasattr(segment, 'avg_logprob') and segment.avg_logprob is not None:
                    # 平均対数確率を信頼度に変換
                    segment_confidence = min(100.0, max(0.0, (segment.avg_logprob + 5.0) / 5.0 * 100))
                    word_confidences.append(segment_confidence)
                
                total_duration += getattr(segment, 'end', 0) - getattr(segment, 'start', 0)
            
            # 全体的な信頼度を計算
            if word_confidences:
                overall_confidence = sum(word_confidences) / len(word_confidences)
                min_confidence = min(word_confidences)
                max_confidence = max(word_confidences)
                std_confidence = (sum((x - overall_confidence) ** 2 for x in word_confidences) / len(word_confidences)) ** 0.5
            else:
                # フォールバック: 言語確率を使用
                overall_confidence = info.language_probability * 100 if hasattr(info, 'language_probability') else 50.0
                min_confidence = max_confidence = overall_confidence
                std_confidence = 0.0
                word_count = len(segments)
            
            return {
                'overall_confidence': overall_confidence,
                'min_confidence': min_confidence,
                'max_confidence': max_confidence,
                'std_confidence': std_confidence,
                'word_count': word_count,
                'segment_count': len(segments),
                'audio_duration': getattr(info, 'duration', total_duration),
                'language_probability': getattr(info, 'language_probability', 0.0) * 100,
                'word_confidences': word_confidences
            }
            
        except Exception as e:
            print(f"⚠️ 信頼度計算エラー: {e}")
            # エラー時のデフォルト値
            return {
                'overall_confidence': 50.0,
                'min_confidence': 50.0,
                'max_confidence': 50.0,
                'std_confidence': 0.0,
                'word_count': 0,
                'segment_count': len(segments) if segments else 0,
                'audio_duration': 0.0,
                'language_probability': 50.0,
                'word_confidences': []
            }
    
    def update_recognition_stats(self, confidence_info):
        """認識統計を更新"""
        self.recognition_stats['total_recognitions'] += 1
        self.confidence_history.append(confidence_info['overall_confidence'])
        
        # 最新20回の平均を計算
        recent_confidences = self.confidence_history[-20:]
        self.recognition_stats['avg_confidence'] = sum(recent_confidences) / len(recent_confidences)
        
        # 最小値・最大値を更新
        self.recognition_stats['min_confidence'] = min(self.recognition_stats['min_confidence'], confidence_info['overall_confidence'])
        self.recognition_stats['max_confidence'] = max(self.recognition_stats['max_confidence'], confidence_info['overall_confidence'])
        
        print(f"📊 認識統計 - 平均精度: {self.recognition_stats['avg_confidence']:.1f}% "
              f"(回数: {self.recognition_stats['total_recognitions']}, "
              f"範囲: {self.recognition_stats['min_confidence']:.1f}%-{self.recognition_stats['max_confidence']:.1f}%)")
    
    def get_recognition_stats(self):
        """認識統計を取得"""
        return self.recognition_stats.copy(), self.confidence_history.copy()
    
    def detect_voice_activity(self, audio_data):
        """音声活動を検出し、沈黙時間を監視"""
        import numpy as np
        import time
        
        try:
            # 音声データをnumpy配列に変換
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # RMS（Root Mean Square）で音声レベルを計算
            rms = np.sqrt(np.mean(audio_array.astype(np.float64) ** 2))
            
            current_time = time.time()
            
            # 音声が検出された場合
            if rms > self.voice_threshold:
                self.last_voice_time = current_time
                self.has_detected_voice = True
                
                # 沈黙タイマーをリセット
                if self.silence_timer.isActive():
                    self.silence_timer.stop()
            
            # 音声が検出されてから一定時間が経過し、沈黙が続いている場合
            elif self.has_detected_voice:
                silence_duration = current_time - self.last_voice_time
                
                # 沈黙検出タイマーを開始（まだ開始していない場合）
                if not self.silence_timer.isActive() and silence_duration >= 0.5:  # 0.5秒の遅延後に開始
                    remaining_time = max(0, self.silence_threshold - silence_duration)
                    if remaining_time > 0:
                        self.silence_timer.start(int(remaining_time * 1000))  # ミリ秒で指定
                    else:
                        # 既に閾値を超えている場合は即座に沈黙検出
                        self.on_silence_detected()
        
        except Exception as e:
            print(f"音声活動検出エラー: {e}")
    
    def on_silence_detected(self):
        """沈黙が検出された時の処理"""
        if self.is_recording and self.has_detected_voice:
            print("🔇 沈黙検出により自動録音終了")
            # 沈黙検出による自動終了フラグを設定
            self.auto_stopped_by_silence = True
            self.stop_recording()

class ConversationWorker(QThread):
    """会話処理用ワーカースレッド"""
    conversation_finished = Signal(dict)
    progress_update = Signal(str)  # 進行状況更新用シグナル
    
    def __init__(self, controller: LLMFaceController, user_message: str, expression: str, model_setting: str, prompt: str):
        super().__init__()
        self.controller = controller
        self.user_message = user_message
        self.expression = expression
        self.model_setting = model_setting
        self.prompt = prompt
        self._is_running = False
        self._force_stop = False  # 強制停止フラグ
        self.timeout_timer = None
    
    def force_stop(self):
        """強制停止メソッド"""
        logger.info("🚨 ConversationWorker強制停止が要求されました")
        self._force_stop = True
        self._is_running = False
        
        # スレッドの強制終了
        if self.isRunning():
            self.quit()
            if not self.wait(2000):  # 2秒待機
                logger.warning("⚠️ スレッド強制終了")
                self.terminate()
        
        # エラー結果を返す
        result = {
            "success": False,
            "user_message": self.user_message,
            "llm_response": None,
            "voice_success": False,
            "expression_success": False,
            "error": "処理が強制停止されました"
        }
        self.conversation_finished.emit(result)
    
    def run(self):
        """ワーカースレッドの実行"""
        self._is_running = True
        try:
            # スレッドが中断されていないかチェック
            if not self._is_running:
                return
                
            self.progress_update.emit("LLM応答を生成中...")
            
            # asyncioイベントループを作成
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # スレッドが中断されていないかチェック
                if not self._is_running:
                    return
                
                # LLMモデル設定を変更（タイムアウト付き）
                self.progress_update.emit("LLMモデル設定を変更中...")
                try:
                    model_start = time.time()
                    model_future = loop.run_in_executor(None, self.controller.set_llm_setting, self.model_setting)
                    loop.run_until_complete(asyncio.wait_for(model_future, timeout=10.0))
                    logger.info(f"⚡ モデル設定完了: {time.time() - model_start:.2f}秒")
                except asyncio.TimeoutError:
                    logger.error("❌ モデル設定タイムアウト（10秒）")
                    self.progress_update.emit("⚠️ モデル設定でタイムアウトが発生しました")
                    # エラーを投げずに続行
                
                # プロンプト設定を変更（タイムアウト付き）
                self.progress_update.emit("プロンプト設定を変更中...")
                try:
                    prompt_start = time.time()
                    prompt_future = loop.run_in_executor(None, self.controller.set_prompt, self.prompt)
                    loop.run_until_complete(asyncio.wait_for(prompt_future, timeout=5.0))
                    logger.info(f"⚡ プロンプト設定完了: {time.time() - prompt_start:.2f}秒")
                except asyncio.TimeoutError:
                    logger.error("❌ プロンプト設定タイムアウト（5秒）")
                    self.progress_update.emit("⚠️ プロンプト設定でタイムアウトが発生しました")
                    # エラーを投げずに続行
                
                # ⚡ タイムアウト短縮と高速化（段階的タイムアウト監視）
                # 強制停止チェック
                if self._force_stop or not self._is_running:
                    logger.info("🚨 LLM処理開始前に停止されました")
                    return
                
                self.progress_update.emit("🚀 LLM応答処理中...")
                
                try:
                    start_time = time.time()
                    
                    # 段階的タイムアウト監視とタイムアウト処理
                    async def monitor_progress():
                        for i in range(3):  # 10秒x3回 = 30秒
                            await asyncio.sleep(10)
                            # 強制停止チェック
                            if self._force_stop or not self._is_running:
                                return
                            elapsed = time.time() - start_time
                            if elapsed > 10 * (i + 1):
                                self.progress_update.emit(f"🔄 LLM応答待機中... ({elapsed:.0f}秒経過)")
                                logger.info(f"⏳ LLM処理進行中: {elapsed:.1f}秒経過")
                    
                    # メイン処理と監視を並列実行
                    main_task = self.controller.process_user_input(self.user_message, self.expression)
                    monitor_task = monitor_progress()
                    
                    # タイムアウト付きで実行
                    result = loop.run_until_complete(
                        asyncio.wait_for(
                            asyncio.ensure_future(main_task),
                            timeout=30.0  # 30秒タイムアウト
                        )
                    )
                    
                    elapsed_time = time.time() - start_time
                    logger.info(f"⚡ 対話処理時間: {elapsed_time:.2f}秒")
                    
                except asyncio.TimeoutError:
                    self.progress_update.emit("⚠️ タイムアウトエラー（30秒）")
                    logger.error("❌ LLM処理タイムアウト（30秒）")
                    result = {
                        "success": False,
                        "user_message": self.user_message,
                        "llm_response": None,
                        "voice_success": False,
                        "expression_success": False,
                        "error": "LLM処理がタイムアウトしました（30秒）。サーバーの応答が遅い可能性があります。"
                    }
                except Exception as e:
                    self.progress_update.emit(f"❌ LLM処理エラー: {str(e)}")
                    logger.error(f"❌ LLM処理エラー: {str(e)}")
                    result = {
                        "success": False,
                        "user_message": self.user_message,
                        "llm_response": None,
                        "voice_success": False,
                        "expression_success": False,
                        "error": f"LLM処理でエラーが発生しました: {str(e)}"
                    }
                
                # スレッドが中断されていないかチェック
                if self._is_running:
                    self.progress_update.emit("処理完了")
                    self.conversation_finished.emit(result)
                    
            finally:
                try:
                    # イベントループのクリーンアップ
                    if loop.is_running():
                        loop.stop()
                    
                    # 残っているタスクをキャンセル
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    # タスクの完了を待つ
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                        
                finally:
                    loop.close()
                
        except Exception as e:
            if self._is_running:  # スレッドが有効な場合のみエラーを報告
                error_result = {
                    "success": False,
                    "user_message": self.user_message,
                    "llm_response": None,
                    "voice_success": False,
                    "expression_success": False,
                    "error": f"会話処理エラー: {e}"
                }
                self.conversation_finished.emit(error_result)
        finally:
            self._is_running = False
    
    def stop_gracefully(self):
        """スレッドの優雅な停止"""
        self._is_running = False
        self.force_stop()  # 強制停止も実行

class PromptEditDialog(QDialog):
    """プロンプト編集ダイアログ"""
    
    def __init__(self, controller: LLMFaceController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        """UI初期化"""
        self.setWindowTitle("プロンプト編集")
        self.setGeometry(100, 100, 600, 400)
        
        # ダークテーマスタイル
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
            }
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
        """)
        
        layout = QVBoxLayout()
        
        # プロンプト選択
        select_layout = QHBoxLayout()
        select_layout.addWidget(QLabel("プロンプト選択:"))
        self.prompt_combo = QComboBox()
        self.prompt_combo.addItems(self.controller.get_available_prompts())
        self.prompt_combo.currentTextChanged.connect(self.load_prompt)
        select_layout.addWidget(self.prompt_combo)
        layout.addLayout(select_layout)
        
        # プロンプト編集エリア
        layout.addWidget(QLabel("プロンプト内容:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(200)
        layout.addWidget(self.prompt_edit)
        
        # 新規プロンプト名
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("保存名:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("新しいプロンプト名を入力")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # ボタン
        button_layout = QHBoxLayout()
        
        save_button = QPushButton("保存")
        save_button.clicked.connect(self.save_prompt)
        button_layout.addWidget(save_button)
        
        apply_button = QPushButton("適用")
        apply_button.clicked.connect(self.apply_prompt)
        button_layout.addWidget(apply_button)
        
        cancel_button = QPushButton("キャンセル")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("QPushButton { background-color: #757575; }")
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # 初期プロンプトをロード
        self.load_prompt()
    
    def load_prompt(self):
        """選択されたプロンプトをロード"""
        prompt_name = self.prompt_combo.currentText()
        if prompt_name:
            prompt_content = self.controller.load_prompt(prompt_name)
            self.prompt_edit.setPlainText(prompt_content)
            self.name_edit.setText(prompt_name)
    
    def save_prompt(self):
        """プロンプトを保存"""
        name = self.name_edit.text().strip()
        content = self.prompt_edit.toPlainText().strip()
        
        if not name:
            QMessageBox.warning(self, "警告", "プロンプト名を入力してください")
            return
        
        if not content:
            QMessageBox.warning(self, "警告", "プロンプト内容を入力してください")
            return
        
        success = self.controller.save_prompt(name, content)
        if success:
            QMessageBox.information(self, "成功", f"プロンプト '{name}' を保存しました")
            # プロンプト一覧を更新
            self.prompt_combo.clear()
            self.prompt_combo.addItems(self.controller.get_available_prompts())
            self.prompt_combo.setCurrentText(name)
        else:
            QMessageBox.critical(self, "エラー", "プロンプトの保存に失敗しました")
    
    def apply_prompt(self):
        """プロンプトを適用"""
        name = self.prompt_combo.currentText()
        if name:
            self.controller.set_prompt(name)
            QMessageBox.information(self, "成功", f"プロンプト '{name}' を適用しました")
            self.accept()

class LogDisplay(QWidget):
    """ログ表示ウィジェット"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # ツールバー
        toolbar_layout = QHBoxLayout()
        
        self.clear_log_button = QPushButton("ログクリア")
        self.clear_log_button.setMaximumHeight(30)
        self.clear_log_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #FF7043;
            }
        """)
        self.clear_log_button.clicked.connect(self.clear_logs)
        
        self.auto_scroll_checkbox = QCheckBox("自動スクロール")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 1px solid #4CAF50;
                border-radius: 3px;
            }
        """)
        
        toolbar_layout.addWidget(self.clear_log_button)
        toolbar_layout.addWidget(self.auto_scroll_checkbox)
        toolbar_layout.addStretch()
        
        # ログ表示エリア
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(200)
        
        # フォント設定
        font = QFont("SF Mono", 9)
        if not font.exactMatch():
            font = QFont("Menlo", 9)
            if not font.exactMatch():
                font = QFont("Monaco", 9)
        self.log_area.setFont(font)
        
        # スタイル設定
        self.log_area.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.log_area)
        self.setLayout(layout)
    
    def add_log(self, message: str, log_type: str = "info"):
        """ログメッセージを追加"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        colors = {
            "info": "#ffffff",
            "success": "#4CAF50", 
            "warning": "#FF9800",
            "error": "#F44336",
            "debug": "#9E9E9E"
        }
        color = colors.get(log_type, "#ffffff")
        
        log_entry = f"<span style='color: #666666;'>[{timestamp}]</span> <span style='color: {color};'>{message}</span>"
        self.log_area.append(log_entry)
        
        # 自動スクロール
        if self.auto_scroll_checkbox.isChecked():
            self.log_area.verticalScrollBar().setValue(
                self.log_area.verticalScrollBar().maximum()
            )
    
    def clear_logs(self):
        """ログをクリア"""
        self.log_area.clear()
        self.add_log("ログがクリアされました", "info")

class ConversationDisplay(QWidget):
    """会話表示ウィジェット"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # マージンを縮小
        layout.setSpacing(3)  # 間隔を縮小
        
        # 会話履歴表示エリア
        self.conversation_area = QTextEdit()
        self.conversation_area.setReadOnly(True)
        self.conversation_area.setMinimumHeight(250)  # 400から250に縮小
        
        # フォント設定（macOS対応）
        font = QFont("SF Pro Display", 10)
        if not font.exactMatch():
            font = QFont("Helvetica Neue", 10)
        self.conversation_area.setFont(font)
        
        # スタイル設定（ダークテーマ）
        self.conversation_area.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout.addWidget(self.conversation_area)
        self.setLayout(layout)
    
    def add_user_message(self, message: str):
        """ユーザーメッセージを追加"""
        self.conversation_area.append(f"<div style='color: #64B5F6; font-weight: bold; margin: 10px 0 5px 0;'>👤 あなた:</div>")
        self.conversation_area.append(f"<div style='margin-left: 20px; margin-bottom: 15px; background-color: #424242; color: #ffffff; padding: 8px; border-radius: 6px;'>{message}</div>")
        self.conversation_area.verticalScrollBar().setValue(
            self.conversation_area.verticalScrollBar().maximum()
        )
    
    def add_ai_message(self, message: str):
        """AIメッセージを追加"""
        self.conversation_area.append(f"<div style='color: #81C784; font-weight: bold; margin: 10px 0 5px 0;'>🤖 シリウス:</div>")
        self.conversation_area.append(f"<div style='margin-left: 20px; margin-bottom: 15px; background-color: #1B5E20; color: #ffffff; padding: 8px; border-radius: 6px;'>{message}</div>")
        self.conversation_area.verticalScrollBar().setValue(
            self.conversation_area.verticalScrollBar().maximum()
        )
    
    def add_system_message(self, message: str, message_type: str = "info"):
        """システムメッセージを追加"""
        colors = {
            "info": "#64B5F6",
            "success": "#81C784", 
            "warning": "#FFB74D",
            "error": "#E57373"
        }
        color = colors.get(message_type, "#BDBDBD")
        
        self.conversation_area.append(f"<div style='color: {color}; font-style: italic; margin: 5px 0; text-align: center;'>📢 {message}</div>")
        self.conversation_area.verticalScrollBar().setValue(
            self.conversation_area.verticalScrollBar().maximum()
        )
    
    def clear_conversation(self):
        """会話履歴をクリア"""
        self.conversation_area.clear()

class InputPanel(QWidget):
    """入力パネルウィジェット"""
    send_message = Signal(str, str, str, str)  # message, expression, model_setting, prompt
    
    def __init__(self):
        super().__init__()
        # 音声録音関連
        self.current_whisper_model = "medium"  # デフォルトモデル
        self.current_device_index = None  # デフォルトマイク
        self.voice_recorder = VoiceRecorder(self.current_whisper_model, self.current_device_index)
        self.voice_recorder.recording_started.connect(self.on_recording_started)
        self.voice_recorder.recording_stopped.connect(self.on_recording_stopped)
        self.voice_recorder.transcription_ready.connect(self.on_transcription_ready)
        self.voice_recorder.transcription_with_confidence.connect(self.on_transcription_with_confidence)
        self.voice_recorder.error_occurred.connect(self.on_voice_error)
        
        # 利用可能な音声デバイスを取得
        self.audio_devices = VoiceRecorder.get_audio_devices()
        
        # 自動送信設定
        self.auto_send_enabled = True  # 自動送信を有効にするかどうか
        self.auto_send_threshold = 90.0  # 自動送信する精度の閾値（%）- 高精度設定
        self.auto_send_min_words = 1  # 自動送信する最小単語数 - より緩い設定に変更
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)  # マージンを縮小
        layout.setSpacing(5)  # 間隔を縮小
        
        # メッセージ入力エリア（コンパクト化）
        input_group = QGroupBox("メッセージ入力")
        input_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 8px;  
                padding-top: 4px;  
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #64B5F6;
            }
        """)
        input_layout = QVBoxLayout()
        input_layout.setContentsMargins(8, 5, 8, 8)  # マージンを調整
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(60)  # 100から60に縮小
        self.message_input.setMinimumHeight(60)
        self.message_input.setPlaceholderText("ここにメッセージを入力してください...")
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 2px solid #64B5F6;
            }
        """)
        
        # Enterキーでの送信を設定
        self.message_input.installEventFilter(self)
        
        # 右クリックメニューで入力クリア機能を追加
        self.message_input.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.message_input.customContextMenuRequested.connect(self.show_input_context_menu)
        
        input_layout.addWidget(self.message_input)
        input_group.setLayout(input_layout)
        
        # 設定パネル（水平レイアウトでコンパクト化）
        settings_group = QGroupBox("設定")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 8px;  
                padding-top: 4px;  
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #64B5F6;
            }
        """)
        settings_layout = QHBoxLayout()  # 水平レイアウトに変更
        settings_layout.setSpacing(15)  # 間隔を調整
        settings_layout.setContentsMargins(8, 5, 8, 8)  # マージンを調整
        
        # 表情選択（コンパクト）
        expression_layout = QVBoxLayout()
        expression_layout.setSpacing(2)  # 間隔を縮小
        expression_label = QLabel("表情:")
        expression_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")  # フォントサイズ縮小
        expression_layout.addWidget(expression_label)
        self.expression_combo = QComboBox()
        self.expression_combo.addItems([
            "neutral", "happy", "sad", "angry", "surprised", 
            "crying", "hurt", "wink", "mouth3", "pien"
        ])
        self.expression_combo.setCurrentText("neutral")
        self.expression_combo.setMaximumHeight(28)  # 高さ制限
        self.expression_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;  
                min-width: 80px;  
                font-size: 11px;  
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 16px;  
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #ffffff;
                margin: 0 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #64B5F6;
            }
        """)
        expression_layout.addWidget(self.expression_combo)
        
        # Whisperモデル選択（コンパクト）
        whisper_layout = QVBoxLayout()
        whisper_layout.setSpacing(2)
        whisper_label = QLabel("Whisper:")
        whisper_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        whisper_layout.addWidget(whisper_label)
        self.whisper_combo = QComboBox()
        self.whisper_combo.addItems([
            "base", "small", "medium", "large"
        ])
        self.whisper_combo.setCurrentText(self.current_whisper_model)
        self.whisper_combo.setMaximumHeight(28)
        self.whisper_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
                min-width: 80px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 16px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #ffffff;
                margin: 0 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #64B5F6;
            }
        """)
        self.whisper_combo.currentTextChanged.connect(self.change_whisper_model)
        whisper_layout.addWidget(self.whisper_combo)
        
        # マイク選択（コンパクト）
        mic_layout = QVBoxLayout()
        mic_layout.setSpacing(2)
        mic_label = QLabel("マイク:")
        mic_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        mic_layout.addWidget(mic_label)
        self.mic_combo = QComboBox()
        
        # デフォルトマイクを追加
        self.mic_combo.addItem("デフォルト", None)
        
        # 利用可能なマイクデバイスを追加
        for device in self.audio_devices:
            device_name = device['name']
            # 名前が長い場合は短縮
            if len(device_name) > 20:
                device_name = device_name[:17] + "..."
            self.mic_combo.addItem(device_name, device['index'])
        
        self.mic_combo.setCurrentIndex(0)  # デフォルトを選択
        self.mic_combo.setMaximumHeight(28)
        self.mic_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
                min-width: 100px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 16px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #ffffff;
                margin: 0 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #64B5F6;
            }
        """)
        self.mic_combo.currentIndexChanged.connect(self.change_microphone)
        mic_layout.addWidget(self.mic_combo)
        
        # LLMモデル選択（コンパクト）
        model_layout = QVBoxLayout()
        model_layout.setSpacing(2)
        model_label = QLabel("LLMモデル:")
        model_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        model_layout.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "mistral_default", "mistral_conservative", "mistral_creative", "mistral_precise",
            "default", "conservative", "creative", "precise"
        ])
        self.model_combo.setCurrentText("mistral_default")
        self.model_combo.setMaximumHeight(28)
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
                min-width: 100px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 16px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #ffffff;
                margin: 0 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #64B5F6;
            }
        """)
        model_layout.addWidget(self.model_combo)
        
        # プロンプト選択（コンパクト）
        prompt_layout = QVBoxLayout()
        prompt_layout.setSpacing(2)
        prompt_label = QLabel("プロンプト:")
        prompt_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        prompt_layout.addWidget(prompt_label)
        
        # プロンプトコンボボックスと編集ボタンを水平に配置
        prompt_controls = QHBoxLayout()
        prompt_controls.setSpacing(5)
        
        self.prompt_combo = QComboBox()
        self.prompt_combo.setCurrentText("default")
        self.prompt_combo.setMaximumHeight(28)
        self.prompt_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
                min-width: 100px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 16px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #ffffff;
                margin: 0 2px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #64B5F6;
            }
        """)
        
        # プロンプト編集ボタン（小型化）
        prompt_edit_button = QPushButton("編集")
        prompt_edit_button.setMaximumHeight(28)
        prompt_edit_button.setMaximumWidth(40)
        prompt_edit_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 2px 6px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #FFB74D;
            }
            QPushButton:pressed {
                background-color: #F57C00;
            }
        """)
        prompt_edit_button.clicked.connect(self.edit_prompt)
        
        prompt_controls.addWidget(self.prompt_combo)
        prompt_controls.addWidget(prompt_edit_button)
        prompt_layout.addLayout(prompt_controls)
        
        # 自動送信設定（コンパクト）
        auto_send_layout = QVBoxLayout()
        auto_send_layout.setSpacing(2)
        auto_send_label = QLabel("自動送信:")
        auto_send_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        auto_send_layout.addWidget(auto_send_label)
        
        self.auto_send_checkbox = QCheckBox("有効")
        self.auto_send_checkbox.setChecked(True)  # デフォルトで有効に設定
        self.auto_send_checkbox.setMaximumHeight(28)
        self.auto_send_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 1px solid #4CAF50;
                border-radius: 3px;
            }
        """)
        self.auto_send_checkbox.stateChanged.connect(self.toggle_auto_send)
        auto_send_layout.addWidget(self.auto_send_checkbox)
        
        # 沈黙検出設定（コンパクト）
        silence_layout = QVBoxLayout()
        silence_layout.setSpacing(2)
        silence_label = QLabel("沈黙検出:")
        silence_label.setStyleSheet("color: #ffffff; font-weight: bold; font-size: 12px;")
        silence_layout.addWidget(silence_label)
        
        self.silence_checkbox = QCheckBox("有効")
        self.silence_checkbox.setChecked(True)  # デフォルトで有効
        self.silence_checkbox.setMaximumHeight(28)
        self.silence_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 1px solid #555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #2196F3;
                border: 1px solid #2196F3;
                border-radius: 3px;
            }
        """)
        self.silence_checkbox.stateChanged.connect(self.toggle_silence_detection)
        silence_layout.addWidget(self.silence_checkbox)
        
        # すべての設定を水平に配置
        settings_layout.addLayout(expression_layout)
        settings_layout.addLayout(whisper_layout)
        settings_layout.addLayout(mic_layout)
        settings_layout.addLayout(model_layout)
        settings_layout.addLayout(prompt_layout)
        settings_layout.addLayout(auto_send_layout)
        settings_layout.addLayout(silence_layout)
        settings_layout.addStretch()  # 右側に余白を追加
        
        settings_group.setLayout(settings_layout)
        
        # ボタンエリア（コンパクト化）
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.send_button = QPushButton("送信")
        self.send_button.setMinimumHeight(32)  # 40から32に縮小
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;  
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #424242;
                color: #757575;
            }
        """)
        self.send_button.clicked.connect(self.send_message_clicked)
        
        # 音声入力ボタン
        self.voice_button = QPushButton("🎤 音声入力開始")
        self.voice_button.setMinimumHeight(32)
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #FF7043;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
            QPushButton:disabled {
                background-color: #424242;
                color: #757575;
            }
        """)
        self.voice_button.clicked.connect(self.toggle_voice_recording)
        
        self.clear_button = QPushButton("履歴クリア")
        self.clear_button.setMinimumHeight(32)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #42A5F5;
            }
            QPushButton:pressed {
                background-color: #1976D2;
            }
        """)
        self.clear_button.clicked.connect(self.clear_conversation)
        
        # リアルタイム監視ボタン
        self.monitoring_button = QPushButton("🔊 監視開始")
        self.monitoring_button.setMinimumHeight(32)
        self.monitoring_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #FFB74D;
            }
            QPushButton:pressed {
                background-color: #F57C00;
            }
        """)
        self.monitoring_button.clicked.connect(self.toggle_real_time_monitoring)
        
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.voice_button)
        button_layout.addWidget(self.monitoring_button)
        button_layout.addWidget(self.clear_button)
        
        # レイアウト組み立て
        layout.addWidget(input_group)
        layout.addWidget(settings_group)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def eventFilter(self, obj, event):
        """イベントフィルター（Enterキー処理）"""
        if obj == self.message_input and event.type() == event.Type.KeyPress:
            # 複数のキーボードショートカットに対応
            if event.key() == Qt.Key.Key_Return:
                modifiers = event.modifiers()
                # Cmd+Shift+Enter (macOS)
                if modifiers == (Qt.KeyboardModifier.MetaModifier | Qt.KeyboardModifier.ShiftModifier):
                    self.send_message_clicked()
                    return True
                # Cmd+Enter (macOS)
                elif modifiers == Qt.KeyboardModifier.MetaModifier:
                    self.send_message_clicked()
                    return True
                # Ctrl+Enter (Windows/Linux)
                elif modifiers == Qt.KeyboardModifier.ControlModifier:
                    self.send_message_clicked()
                    return True
            # Escキーで入力クリア
            elif event.key() == Qt.Key.Key_Escape:
                self.clear_input()
                return True
            # Vキーで音声入力開始/停止
            elif event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                self.toggle_voice_recording()
                return True
        return super().eventFilter(obj, event)
    
    def show_input_context_menu(self, position):
        """入力欄の右クリックメニューを表示"""
        menu = QMenu(self)
        
        # 標準のコンテキストメニューアクション
        menu.addAction("切り取り", self.message_input.cut)
        menu.addAction("コピー", self.message_input.copy)
        menu.addAction("貼り付け", self.message_input.paste)
        menu.addSeparator()
        menu.addAction("すべて選択", self.message_input.selectAll)
        menu.addSeparator()
        menu.addAction("入力をクリア", self.clear_input)
        
        # メニューを表示
        global_pos = self.message_input.mapToGlobal(position)
        menu.exec(global_pos)
    
    def send_message_clicked(self):
        """送信ボタンクリック処理"""
        message = self.message_input.toPlainText().strip()
        print(f"📤 send_message_clicked() 実行:")
        print(f"  - 入力欄の内容: '{message}'")
        print(f"  - 長さ: {len(message)}")
        
        if message:
            expression = self.expression_combo.currentText()
            model_setting = self.model_combo.currentText()
            prompt = self.prompt_combo.currentText()
            
            print(f"  - 表情: {expression}")
            print(f"  - モデル: {model_setting}")  
            print(f"  - プロンプト: {prompt}")
            print("📤 send_messageシグナルを送信します")
            
            self.send_message.emit(message, expression, model_setting, prompt)
            self.clear_input()  # 送信後に入力欄をクリア
            print("✅ メッセージ送信完了、入力欄クリア")
        else:
            print("❌ 送信失敗: 入力欄が空です")
    
    def clear_input(self):
        """入力クリア"""
        self.message_input.clear()
    
    def clear_conversation(self):
        """会話履歴クリア（確認ダイアログ付き）"""
        reply = QMessageBox.question(
            self, 
            "確認", 
            "会話履歴をクリアしますか？\n（この操作は元に戻せません）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 親ウィンドウの会話表示をクリア
            main_window = self.parent().parent().parent()
            if hasattr(main_window, 'conversation_display'):
                main_window.conversation_display.clear_conversation()
                main_window.conversation_display.add_system_message("会話履歴をクリアしました", "info")
            
            # コントローラーの会話履歴もクリア
            if hasattr(main_window, 'controller') and main_window.controller:
                main_window.controller.clear_conversation_history()
    
    def set_enabled(self, enabled: bool):
        """入力欄の有効/無効を設定"""
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.voice_button.setEnabled(enabled)
        self.expression_combo.setEnabled(enabled)
        self.whisper_combo.setEnabled(enabled)
        self.mic_combo.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)
        self.prompt_combo.setEnabled(enabled)
    
    def edit_prompt(self):
        """プロンプト編集ダイアログを開く"""
        self.parent().parent().parent().edit_prompt_dialog()
    
    def update_prompt_list(self, prompts: list):
        """プロンプト一覧を更新"""
        current = self.prompt_combo.currentText()
        self.prompt_combo.clear()
        self.prompt_combo.addItems(prompts)
        if current in prompts:
            self.prompt_combo.setCurrentText(current)
    
    def change_whisper_model(self):
        """Whisperモデルを変更"""
        new_model = self.whisper_combo.currentText()
        if new_model != self.current_whisper_model:
            # 現在の録音が実行中なら停止
            if self.voice_recorder.is_recording:
                self.voice_recorder.stop_recording()
                self.voice_recorder.wait(2000)  # 停止を待つ
            
            # 新しいモデルでVoiceRecorderを再作成
            self.current_whisper_model = new_model
            old_recorder = self.voice_recorder
            
            # 新しいレコーダーを作成
            self.voice_recorder = VoiceRecorder(new_model, self.current_device_index)
            self.voice_recorder.recording_started.connect(self.on_recording_started)
            self.voice_recorder.recording_stopped.connect(self.on_recording_stopped)
            self.voice_recorder.transcription_ready.connect(self.on_transcription_ready)
            self.voice_recorder.transcription_with_confidence.connect(self.on_transcription_with_confidence)
            self.voice_recorder.error_occurred.connect(self.on_voice_error)
            
            # 沈黙検出設定を引き継ぎ
            self.voice_recorder.silence_detection_enabled = self.silence_checkbox.isChecked()
            
            # 古いレコーダーをクリーンアップ
            if old_recorder.isRunning():
                old_recorder.quit()
                old_recorder.wait(1000)
            
            # 親ウィンドウの会話表示にメッセージを追加
            main_window = self.parent().parent().parent()
            if hasattr(main_window, 'conversation_display'):
                main_window.conversation_display.add_system_message(f"Faster-Whisperモデルを {new_model} に変更しました", "info")
                main_window.add_log(f"Faster-Whisperモデル変更: {self.current_whisper_model} → {new_model}", "info")
    
    def change_microphone(self):
        """マイクデバイスを変更"""
        selected_index = self.mic_combo.currentIndex()
        new_device_index = self.mic_combo.itemData(selected_index)
        
        if new_device_index != self.current_device_index:
            # 現在の録音が実行中なら停止
            if self.voice_recorder.is_recording:
                self.voice_recorder.stop_recording()
                self.voice_recorder.wait(2000)  # 停止を待つ
            
            # 新しいデバイスでVoiceRecorderを再作成
            self.current_device_index = new_device_index
            old_recorder = self.voice_recorder
            
            # 新しいレコーダーを作成
            self.voice_recorder = VoiceRecorder(self.current_whisper_model, new_device_index)
            self.voice_recorder.recording_started.connect(self.on_recording_started)
            self.voice_recorder.recording_stopped.connect(self.on_recording_stopped)
            self.voice_recorder.transcription_ready.connect(self.on_transcription_ready)
            self.voice_recorder.transcription_with_confidence.connect(self.on_transcription_with_confidence)
            self.voice_recorder.error_occurred.connect(self.on_voice_error)
            
            # 沈黙検出設定を引き継ぎ
            self.voice_recorder.silence_detection_enabled = self.silence_checkbox.isChecked()
            
            # 古いレコーダーをクリーンアップ
            if old_recorder.isRunning():
                old_recorder.quit()
                old_recorder.wait(1000)
            
            # 親ウィンドウの会話表示にメッセージを追加
            main_window = self.parent().parent().parent()
            if hasattr(main_window, 'conversation_display'):
                device_name = self.mic_combo.currentText()
                main_window.conversation_display.add_system_message(f"マイクデバイスを {device_name} に変更しました", "info")
                main_window.add_log(f"マイクデバイス変更: {device_name} (インデックス: {new_device_index})", "info")
    
    def toggle_voice_recording(self):
        """音声録音の開始/停止を切り替え"""
        if not self.voice_recorder.is_recording:
            # 録音開始
            self.voice_recorder.start_recording()
        else:
            # 録音停止
            self.voice_recorder.stop_recording()
    
    def on_recording_started(self):
        """録音開始時の処理"""
        self.voice_button.setText("⏹️ 音声入力停止")
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #FF5722;
            }
            QPushButton:hover {
                background-color: #EF5350;
                border: 2px solid #FF7043;
            }
            QPushButton:pressed {
                background-color: #C62828;
                border: 2px solid #D84315;
            }
        """)
        
        # 親ウィンドウの会話表示にメッセージを追加
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            main_window.conversation_display.add_system_message("🎤 音声録音中... 話してください（Vキーで停止）", "info")
            main_window.add_log("音声録音開始 (Vキーショートカット対応)", "info")
    
    def on_recording_stopped(self):
        """録音停止時の処理"""
        self.voice_button.setText("🎤 音声入力開始")
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #FF7043;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
        """)
        
        # 親ウィンドウの会話表示にメッセージを追加
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            main_window.conversation_display.add_system_message("🔄 音声を認識中...", "warning")
            silence_status = "有効" if self.voice_recorder.silence_detection_enabled else "無効"
            main_window.add_log(f"音声録音停止 - 認識処理開始 (沈黙検出: {silence_status})", "info")
    
    def on_transcription_ready(self, text: str):
        """音声認識完了時の処理"""
        # メッセージ入力欄に認識されたテキストを設定
        self.message_input.setText(text)
        
        # 親ウィンドウの会話表示にメッセージを追加
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            main_window.conversation_display.add_system_message(f"✅ 音声認識完了: {text}", "success")
            main_window.add_log(f"音声認識成功: {text}", "success")
    
    def on_transcription_with_confidence(self, text: str, confidence_info: dict):
        """信頼度付き音声認識完了時の処理"""
        print(f"🎤 音声認識結果受信: '{text}' (信頼度: {confidence_info['overall_confidence']:.1f}%)")
        
        # 基本的な処理は通常の transcription_ready と同じ
        self.message_input.setPlainText(text)  # setTextではなくsetPlainTextを使用
        print(f"📝 入力欄にテキスト設定完了: '{self.message_input.toPlainText()}'")
        
        # 信頼度情報を含む詳細なログ出力
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            # 信頼度に基づいてメッセージの色を変更
            if confidence_info['overall_confidence'] >= 80:
                confidence_color = "success"
                confidence_icon = "✅"
            elif confidence_info['overall_confidence'] >= 60:
                confidence_color = "warning"
                confidence_icon = "⚠️"
            else:
                confidence_color = "error"
                confidence_icon = "❌"
            
            # 詳細な信頼度情報を表示
            confidence_msg = (f"{confidence_icon} 音声認識完了: {text} "
                            f"(精度: {confidence_info['overall_confidence']:.1f}%, "
                            f"単語数: {confidence_info['word_count']}, "
                            f"時間: {confidence_info['audio_duration']:.1f}s)")
            
            main_window.conversation_display.add_system_message(confidence_msg, confidence_color)
            
            # ログには統計情報も含める
            stats, history = self.voice_recorder.get_recognition_stats()
            detailed_log = (f"音声認識: {text} | "
                          f"精度: {confidence_info['overall_confidence']:.1f}% "
                          f"(範囲: {confidence_info['min_confidence']:.1f}%-{confidence_info['max_confidence']:.1f}%) | "
                          f"平均精度: {stats['avg_confidence']:.1f}%")
            main_window.add_log(detailed_log, "success")
        
        # 高精度の場合は自動送信
        self.auto_send_if_high_confidence(text, confidence_info)
    
    def on_voice_error(self, error_message: str):
        """音声エラー時の処理"""
        # 親ウィンドウの会話表示にエラーメッセージを追加
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            main_window.conversation_display.add_system_message(f"❌ {error_message}", "error")
            main_window.add_log(f"音声エラー: {error_message}", "error")
        
        # ボタンを元の状態に戻す
        self.voice_button.setText("🎤 音声入力開始")
        self.voice_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #FF7043;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
        """)
    
    def auto_send_if_high_confidence(self, text: str, confidence_info: dict):
        """高精度の場合に自動送信を実行"""
        print(f"🔍 自動送信判定開始:")
        print(f"  - 自動送信有効: {self.auto_send_enabled}")
        print(f"  - 認識精度: {confidence_info['overall_confidence']:.1f}% (閾値: {self.auto_send_threshold}%)")
        print(f"  - 単語数: {confidence_info['word_count']} (最小: {self.auto_send_min_words})")
        print(f"  - テキスト: '{text.strip()}' (長さ: {len(text.strip())})")
        
        # 設定状況をメインウィンドウのログにも出力
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'add_log'):
            main_window.add_log(f"🔍 自動送信判定: 有効={self.auto_send_enabled}, 精度={confidence_info['overall_confidence']:.1f}%/{self.auto_send_threshold}%", "debug")
        
        if not self.auto_send_enabled:
            print("❌ 自動送信が無効のため送信しません")
            if hasattr(main_window, 'add_log'):
                main_window.add_log("❌ 自動送信無効", "warning")
            return
        
        # 自動送信の条件をチェック
        confidence_ok = confidence_info['overall_confidence'] >= self.auto_send_threshold
        word_count_ok = confidence_info['word_count'] >= self.auto_send_min_words
        text_ok = len(text.strip()) > 1  # 最小文字数チェック
        
        print(f"📊 条件チェック結果:")
        print(f"  - 精度OK: {confidence_ok} ({confidence_info['overall_confidence']:.1f}% >= {self.auto_send_threshold}%)")
        print(f"  - 単語数OK: {word_count_ok} ({confidence_info['word_count']} >= {self.auto_send_min_words})")
        print(f"  - テキストOK: {text_ok} (長さ {len(text.strip())} > 1)")
        
        # ログにも条件チェック結果を出力
        if hasattr(main_window, 'add_log'):
            main_window.add_log(f"📊 条件: 精度{confidence_ok}, 単語数{word_count_ok}, 文字{text_ok}", "debug")
        
        if confidence_ok and word_count_ok and text_ok:
            print("✅ 自動送信条件をすべて満たしました - 送信実行中...")
            if hasattr(main_window, 'add_log'):
                # 沈黙検出による自動終了の場合のメッセージ
                if hasattr(self.voice_recorder, 'auto_stopped_by_silence') and self.voice_recorder.auto_stopped_by_silence:
                    main_window.add_log(f"🔇→📤 沈黙検出による自動送信 ({confidence_info['overall_confidence']:.1f}%)", "success")
                else:
                    main_window.add_log(f"📤 高精度認識による自動送信 ({confidence_info['overall_confidence']:.1f}%)", "success")
            
            # より確実な自動送信の実行
            print("📤 send_message_clicked()を実行します")
            
            # 入力欄の内容を確認
            current_text = self.message_input.toPlainText().strip()
            print(f"📝 送信前の入力欄確認: '{current_text}'")
            
            if current_text:
                self.send_message_clicked()
                print("✅ 自動送信処理完了")
                if hasattr(main_window, 'add_log'):
                    main_window.add_log("✅ 自動送信実行完了", "success")
            else:
                print("❌ 入力欄が空のため送信できません")
                if hasattr(main_window, 'add_log'):
                    main_window.add_log("❌ 自動送信失敗: 入力欄が空", "error")
        else:
            # 自動送信の条件を満たさない場合の理由表示
            reason = []
            if not confidence_ok:
                reason.append(f"精度不足({confidence_info['overall_confidence']:.1f}% < {self.auto_send_threshold}%)")
            if not word_count_ok:
                reason.append(f"単語数不足({confidence_info['word_count']} < {self.auto_send_min_words})")
            if not text_ok:
                reason.append("テキスト長不足")
            
            print(f"❌ 自動送信見送り: {', '.join(reason)}")
            
            if hasattr(main_window, 'add_log'):
                main_window.add_log(f"❌ 自動送信見送り: {', '.join(reason)}", "warning")
    
    def execute_auto_send(self):
        """自動送信を実行（即座送信のため基本的に使用されない）"""
        # 即座送信に変更したため、このメソッドは基本的に使用されない
        pass
    
    def cancel_auto_send(self):
        """自動送信をキャンセル（即座送信のため基本的に使用されない）"""
        # 即座送信に変更したため、このメソッドは基本的に使用されない
        pass
    
    def toggle_auto_send(self, state):
        """自動送信機能の有効/無効を切り替え"""
        self.auto_send_enabled = bool(state)
        
        # 設定変更をログに記録
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            status = "有効" if self.auto_send_enabled else "無効"
            main_window.add_log(f"自動送信機能を{status}にしました", "info")
            main_window.conversation_display.add_system_message(
                f"🔧 自動送信機能: {status} (精度閾値: {self.auto_send_threshold}%以上)", 
                "info"
            )
    
    def toggle_silence_detection(self, state):
        """沈黙検出機能の有効/無効を切り替え"""
        enabled = bool(state)
        self.voice_recorder.silence_detection_enabled = enabled
        
        # 設定変更をログに記録
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            status = "有効" if enabled else "無効"
            main_window.add_log(f"沈黙検出機能を{status}にしました", "info")
            main_window.conversation_display.add_system_message(
                f"🔇 沈黙検出機能: {status} (閾値: {self.voice_recorder.silence_threshold}秒)", 
                "info"
            )
    
    def toggle_real_time_monitoring(self):
        """リアルタイム監視の開始・停止を切り替え"""
        print("🔘 リアルタイム監視ボタンがクリックされました")
        
        if not hasattr(self, 'voice_recorder') or not self.voice_recorder:
            print("❌ VoiceRecorderが利用できません")
            return
            
        print(f"📊 現在の監視状態: {self.voice_recorder.real_time_enabled}")
        
        if self.voice_recorder.real_time_enabled:
            # 監視停止
            print("🔇 リアルタイム監視を停止します")
            self.voice_recorder.stop_real_time_monitoring()
            self.monitoring_button.setText("🔊 監視開始")
            self.monitoring_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #FFB74D;
                }
                QPushButton:pressed {
                    background-color: #F57C00;
                }
            """)
            
            # メインウィンドウにログ表示
            main_window = self.parent().parent().parent()
            if hasattr(main_window, 'add_log'):
                main_window.add_log("🔇 リアルタイム監視を停止しました", "info")
        else:
            # 監視開始
            print("🔊 リアルタイム監視を開始します")
            self.voice_recorder.start_real_time_monitoring()
            self.monitoring_button.setText("🔇 監視停止")
            self.monitoring_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
            """)
            
            # メインウィンドウにログ表示
            main_window = self.parent().parent().parent()
            if hasattr(main_window, 'add_log'):
                main_window.add_log("🔊 リアルタイム監視を開始しました - 「シリウスくん」と呼んでください", "success")
                # 監視状態の詳細情報も表示
                main_window.add_log(f"🎯 検出対象: {', '.join(self.voice_recorder.wake_words)}", "info")
                main_window.add_log("💡 音声レベルが表示されれば監視は正常に動作中です", "info")
    
    def start_voice_input(self):
        """音声入力を開始（ウェイクワード検出後の自動開始用）"""
        if not self.voice_recorder.is_recording:
            self.toggle_voice_recording()

class StatusPanel(QWidget):
    """ステータスパネルウィジェット"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 3, 10, 3)  # マージンを縮小
        layout.setSpacing(8)  # 間隔を調整
        
        # ステータス表示
        self.status_label = QLabel("準備完了")
        self.status_label.setStyleSheet("""
            QLabel {
                color: #81C784;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        
        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                text-align: center;
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        
        # 精度表示ラベル
        self.confidence_label = QLabel("精度: --")
        self.confidence_label.setStyleSheet("""
            QLabel {
                color: #64B5F6;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 6px;
                border: 1px solid #444;
                border-radius: 3px;
                background-color: #333;
            }
        """)
        self.confidence_label.setVisible(False)
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.confidence_label)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_status(self, message: str, progress: bool = False):
        """ステータスを設定"""
        self.status_label.setText(message)
        self.progress_bar.setVisible(progress)
        if progress:
            self.progress_bar.setRange(0, 0)  # 無限プログレス
    
    def update_confidence(self, confidence: float, show: bool = True):
        """認識精度を更新"""
        if show and confidence > 0:
            self.confidence_label.setText(f"精度: {confidence:.1f}%")
            
            # 精度に応じて色を変更
            if confidence >= 80:
                color = "#4CAF50"  # 緑
            elif confidence >= 60:
                color = "#FF9800"  # オレンジ
            else:
                color = "#F44336"  # 赤
            
            self.confidence_label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    font-weight: bold;
                    font-size: 11px;
                    padding: 2px 6px;
                    border: 1px solid {color};
                    border-radius: 3px;
                    background-color: #333;
                }}
            """)
            self.confidence_label.setVisible(True)
        else:
            self.confidence_label.setVisible(False)

class SiriusFaceAnimUI(QMainWindow):
    """メインUIウィンドウ"""
    
    def __init__(self):
        super().__init__()
        self.controller = None
        self.conversation_worker = None
        self.init_controller()
        self.init_ui()
        self.init_connections()
    
    def init_controller(self):
        """コントローラーを初期化"""
        try:
            self.controller = LLMFaceController()
            if not self.controller.is_initialized:
                QMessageBox.critical(self, "エラー", "LLMFaceControllerの初期化に失敗しました")
                sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"システム初期化エラー: {e}")
            sys.exit(1)
    
    def init_ui(self):
        """UIを初期化"""
        self.setWindowTitle("おしゃべりシリウスくん")
        self.setGeometry(100, 100, 800, 500)  # 600から500に縮小
        
        # メインウィジェット
        main_widget = QWidget()
        main_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)
        self.setCentralWidget(main_widget)
        
        # メインレイアウト（マージン調整）
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)  # マージンを縮小
        main_layout.setSpacing(5)  # 間隔を縮小
        
        # ヘッダー（コンパクト化）
        header = QLabel("🤖 おしゃべりシリウスくん")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                font-size: 16px;  
                font-weight: bold;
                color: #64B5F6;
                padding: 8px;  
                background-color: #1e1e1e;
                border-bottom: 1px solid #424242;  
            }
        """)
        
        # スプリッター（上下分割）
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # タブウィジェット作成
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #1e1e1e;
            }
            QTabWidget::tab-bar {
                alignment: left;
            }
            QTabBar::tab {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #424242;
            }
        """)
        
        # 会話表示タブ
        self.conversation_display = ConversationDisplay()
        tab_widget.addTab(self.conversation_display, "💬 会話")
        
        # ログ表示タブ
        self.log_display = LogDisplay()
        tab_widget.addTab(self.log_display, "📋 ログ")
        
        splitter.addWidget(tab_widget)
        
        # 入力部分
        self.input_panel = InputPanel()
        splitter.addWidget(self.input_panel)
        
        # スプリッター比率設定（会話表示エリアを大きく保ちつつ、入力エリアをコンパクトに）
        splitter.setStretchFactor(0, 4)  # 会話表示部分
        splitter.setStretchFactor(1, 1)  # 入力部分をさらに小さく
        
        # ステータスパネル
        self.status_panel = StatusPanel()
        
        # レイアウト組み立て
        main_layout.addWidget(header)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.status_panel)
        
        main_widget.setLayout(main_layout)
        
        # 初期メッセージ
        self.conversation_display.add_system_message("おしゃべりシリウスくんが起動しました", "success")
        self.conversation_display.add_system_message("💡 使い方:\n• Cmd+Enter (macOS) / Ctrl+Enter (Windows) で送信\n• Vキーで音声入力開始/停止\n• 2秒間の沈黙で自動録音終了（設定で切替可能）\n• Escキーで入力欄をクリア\n• 「履歴クリア」ボタンで会話履歴をクリア\n• ログタブで詳細な処理状況を確認", "info")
        
        # 自動送信設定を表示
        auto_send_status = "有効" if self.input_panel.auto_send_enabled else "無効"
        self.conversation_display.add_system_message(f"🔧 自動送信機能: {auto_send_status} (精度閾値: {self.input_panel.auto_send_threshold}%以上、単語数: {self.input_panel.auto_send_min_words}語以上)", "info")
        
        # 初期ログ
        self.add_log("おしゃべり起動完了", "success")
        self.add_log("LLMFaceController初期化完了", "info")
        self.add_log(f"自動送信設定: {auto_send_status}, 精度閾値={self.input_panel.auto_send_threshold}%, 最小単語数={self.input_panel.auto_send_min_words}", "info")
        
        # プロンプト一覧を初期化
        self.update_prompt_list()
        
        # 緊急停止キーボードショートカット（Ctrl+Alt+R）
        self.emergency_stop_shortcut = QShortcut(QKeySequence("Ctrl+Alt+R"), self)
        self.emergency_stop_shortcut.activated.connect(self.emergency_reset)
        
        # 緊急停止の説明をシステムメッセージに追加
        self.conversation_display.add_system_message("🚨 緊急停止: システムが応答しない場合は Ctrl+Alt+R キーを押してください", "warning")
    
    def update_prompt_list(self):
        """プロンプト一覧を更新"""
        try:
            prompts = self.controller.get_available_prompts()
            self.input_panel.update_prompt_list(prompts)
        except Exception as e:
            print(f"プロンプト一覧更新エラー: {e}")
    
    def edit_prompt_dialog(self):
        """プロンプト編集ダイアログを開く"""
        dialog = PromptEditDialog(self.controller, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # プロンプト一覧を更新
            self.update_prompt_list()
    
    def init_connections(self):
        """シグナル・スロット接続を初期化"""
        self.input_panel.send_message.connect(self.handle_user_message)
        # 音声認識の信頼度情報を処理
        self.input_panel.voice_recorder.transcription_with_confidence.connect(self.handle_confidence_update)
        # リアルタイム監視とウェイクワード検出
        self.input_panel.voice_recorder.wake_word_detected.connect(self.handle_wake_word_detected)
        self.input_panel.voice_recorder.real_time_monitoring.connect(self.handle_real_time_monitoring_state)
    
    def add_log(self, message: str, log_type: str = "info"):
        """ログメッセージを追加"""
        if hasattr(self, 'log_display'):
            self.log_display.add_log(message, log_type)
    
    def handle_confidence_update(self, text: str, confidence_info: dict):
        """音声認識の信頼度情報を処理"""
        # ステータスパネルに精度を表示
        if hasattr(self, 'status_panel'):
            self.status_panel.update_confidence(confidence_info['overall_confidence'], True)
        
        # 詳細ログに統計情報を追加
        self.add_log(f"認識精度詳細: 全体={confidence_info['overall_confidence']:.1f}%, "
                    f"範囲={confidence_info['min_confidence']:.1f}%-{confidence_info['max_confidence']:.1f}%, "
                    f"標準偏差={confidence_info['std_confidence']:.1f}%, "
                    f"言語確率={confidence_info['language_probability']:.1f}%", "debug")
    
    def handle_wake_word_detected(self, wake_word: str):
        """ウェイクワード検出時の処理"""
        self.add_log(f"✅ ウェイクワード検出: '{wake_word}'", "success")
        
        # 「はい、なんですか」の応答を生成
        self.respond_to_wake_word()
        
        # 音声入力を自動開始
        QTimer.singleShot(2000, self.start_voice_input_after_wake_word)  # 2秒後に音声入力開始
    
    def handle_real_time_monitoring_state(self, is_active: bool):
        """リアルタイム監視状態の変更を処理"""
        status = "有効" if is_active else "無効"
        self.add_log(f"🔊 リアルタイム音声監視: {status}", "info")
        
        # UIの状態表示を更新
        if hasattr(self, 'status_panel'):
            self.status_panel.update_monitoring_status(is_active)
    
    def respond_to_wake_word(self):
        """ウェイクワード検出時の自動応答"""
        try:
            # 「はい、なんですか」を音声合成で再生
            response_text = "はい、なんですか"
            self.add_log(f"🤖 自動応答: {response_text}", "success")
            
            # 会話表示にAIの応答として追加
            self.conversation_display.add_ai_message(response_text, None)
            
            # VOICEVOX で音声合成（非同期）
            if self.controller and self.controller.voicevox_controller:
                import threading
                threading.Thread(
                    target=self.controller.voicevox_controller.speak,
                    args=(response_text,),
                    daemon=True
                ).start()
                
        except Exception as e:
            self.add_log(f"❌ 自動応答エラー: {e}", "error")
    
    def start_voice_input_after_wake_word(self):
        """ウェイクワード検出後の音声入力開始"""
        try:
            self.add_log("🎤 ウェイクワード応答後、音声入力を開始します", "info")
            # 音声入力パネルの録音開始
            if hasattr(self.input_panel, 'start_voice_input'):
                self.input_panel.start_voice_input()
            else:
                # フォールバック: 音声録音ボタンをプログラム的にクリック
                if hasattr(self.input_panel, 'voice_button'):
                    self.input_panel.voice_button.click()
        except Exception as e:
            self.add_log(f"❌ 音声入力開始エラー: {e}", "error")
    
    def handle_user_message(self, message: str, expression: str, model_setting: str, prompt: str):
        """ユーザーメッセージを処理"""
        # ログ追加
        self.add_log(f"ユーザー入力: {message}", "info")
        self.add_log(f"設定 - 表情: {expression}, モデル: {model_setting}, プロンプト: {prompt}", "debug")
        
        # UI更新
        self.conversation_display.add_user_message(message)
        self.conversation_display.add_system_message(f"モデル: {model_setting} | プロンプト: {prompt}", "info")
        self.input_panel.set_enabled(False)
        self.status_panel.set_status("処理中...", True)
        
        # ワーカースレッドで処理
        self.conversation_worker = ConversationWorker(self.controller, message, expression, model_setting, prompt)
        self.conversation_worker.conversation_finished.connect(self.handle_conversation_result)
        self.conversation_worker.progress_update.connect(self.handle_progress_update)
        self.conversation_worker.start()
        
        self.add_log("会話処理ワーカースレッドを開始", "info")
    
    def handle_progress_update(self, message: str):
        """進行状況更新を処理"""
        self.status_panel.set_status(message, True)
        self.add_log(f"進行状況: {message}", "debug")
    
    def handle_conversation_result(self, result: Dict[str, Any]):
        """会話処理結果を処理"""
        try:
            if result.get("success", False):
                # 成功時の処理
                llm_response = result.get("llm_response", "")
                self.conversation_display.add_ai_message(llm_response)
                self.add_log(f"LLM応答: {llm_response}", "success")
                
                # 各処理の成功/失敗をログに記録
                if result.get("voice_success", False):
                    self.add_log("音声合成: 成功", "success")
                else:
                    self.add_log("音声合成: 失敗", "warning")
                    
                if result.get("expression_success", False):
                    self.add_log("表情制御: 成功", "success")
                else:
                    self.add_log("表情制御: 失敗", "warning")
                
                # ステータス更新
                if result.get("voice_success", False):
                    self.status_panel.set_status("音声再生中...")
                    self.add_log("音声再生開始", "info")
                    # 音声再生完了を待つタイマー（実際の実装では音声再生完了イベントを使用）
                    QTimer.singleShot(8000, lambda: self.status_panel.set_status("準備完了"))  # 8秒に延長
                    QTimer.singleShot(8000, lambda: self.add_log("音声再生完了（推定）", "info"))
                else:
                    self.conversation_display.add_system_message("音声再生に失敗しました", "warning")
                    self.status_panel.set_status("準備完了")
                
            else:
                # エラー時の処理
                error_msg = result.get("error", "不明なエラー")
                self.conversation_display.add_system_message(f"エラー: {error_msg}", "error")
                self.add_log(f"エラー: {error_msg}", "error")
                self.status_panel.set_status("エラー発生")
                
        except Exception as e:
            self.conversation_display.add_system_message(f"結果処理エラー: {e}", "error")
            self.add_log(f"結果処理エラー: {e}", "error")
            self.status_panel.set_status("エラー発生")
        
        finally:
            # UI復元
            self.input_panel.set_enabled(True)
            self.add_log("UI復元完了", "info")
            # ワーカースレッドのクリーンアップ
            self.cleanup_worker_thread()
    
    def cleanup_worker_thread(self):
        """ワーカースレッドのクリーンアップ"""
        if self.conversation_worker:
            self.add_log("ワーカースレッドをクリーンアップ中", "debug")
            
            # シグナル切断
            try:
                self.conversation_worker.conversation_finished.disconnect()
                self.conversation_worker.progress_update.disconnect()
            except:
                pass
            
            # スレッドが実行中の場合は優雅に停止
            if self.conversation_worker.isRunning():
                self.conversation_worker.stop_gracefully()
                # 少し待ってから強制終了
                if not self.conversation_worker.wait(2000):  # 2秒待機
                    self.add_log("ワーカースレッド強制終了", "warning")
                    self.conversation_worker.quit()
                    self.conversation_worker.wait(1000)  # さらに1秒待機
            
            # オブジェクトを削除予約
            self.conversation_worker.deleteLater()
            self.conversation_worker = None
            self.add_log("ワーカースレッドクリーンアップ完了", "debug")
        
        # 音声録音スレッドのクリーンアップ
        if hasattr(self.input_panel, 'voice_recorder'):
            voice_recorder = self.input_panel.voice_recorder
            if voice_recorder.isRunning():
                voice_recorder.stop_recording()
                voice_recorder.wait(2000)  # 2秒待機
                if voice_recorder.isRunning():
                    voice_recorder.quit()
                    voice_recorder.wait(1000)  # さらに1秒待機
    
    def emergency_reset(self):
        """緊急停止・リセット機能"""
        try:
            self.add_log("🚨 緊急停止が実行されました", "warning")
            self.conversation_display.add_system_message("🚨 緊急停止実行中...", "warning")
            
            # 1. 音声合成を強制停止
            if self.controller and hasattr(self.controller, 'voice_controller'):
                try:
                    if hasattr(self.controller.voice_controller, 'stop_speaking'):
                        self.controller.voice_controller.stop_speaking()
                    self.add_log("音声合成を強制停止", "info")
                except Exception as e:
                    self.add_log(f"音声合成停止エラー: {e}", "error")
            
            # 2. is_speakingフラグを強制リセット
            if self.controller:
                try:
                    self.controller.is_speaking = False
                    self.add_log("is_speakingフラグを強制リセット", "info")
                except Exception as e:
                    self.add_log(f"is_speakingリセットエラー: {e}", "error")
            
            # 3. ワーカースレッドを強制終了
            self.cleanup_worker_thread()
            
            # 4. UIを復元
            self.input_panel.set_enabled(True)
            self.status_panel.set_status("緊急停止完了 - 準備完了")
            
            # 5. 音声録音を停止
            if hasattr(self.input_panel, 'voice_recorder'):
                try:
                    voice_recorder = self.input_panel.voice_recorder
                    if voice_recorder.is_recording:
                        voice_recorder.stop_recording()
                    self.add_log("音声録音を停止", "info")
                except Exception as e:
                    self.add_log(f"音声録音停止エラー: {e}", "error")
            
            self.conversation_display.add_system_message("✅ 緊急停止完了 - システムをリセットしました", "success")
            self.add_log("緊急停止・リセット完了", "success")
            
        except Exception as e:
            error_msg = f"緊急停止処理でエラーが発生しました: {e}"
            print(error_msg)
            try:
                self.add_log(error_msg, "error")
                self.conversation_display.add_system_message(f"❌ {error_msg}", "error")
            except:
                pass  # ログ出力も失敗した場合は何もしない
    
    def keyPressEvent(self, event):
        """キーボードイベント処理"""
        # Vキーで音声入力開始/停止（フォーカスに関係なく動作）
        if event.key() == Qt.Key.Key_V and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            # 入力フィールドにフォーカスがない場合のみ処理
            if not self.input_panel.message_input.hasFocus():
                self.input_panel.toggle_voice_recording()
                event.accept()
                return
        
        # その他のキーイベントは親クラスに委譲
        super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """ウィンドウクローズ時の処理"""
        try:
            # ワーカースレッドのクリーンアップ
            self.cleanup_worker_thread()
            
            # コントローラーのクリーンアップ
            if self.controller:
                try:
                    self.controller.stop_speaking()
                    self.controller.cleanup()
                except Exception as e:
                    print(f"コントローラークリーンアップエラー: {e}")
            
            event.accept()
            
        except Exception as e:
            print(f"ウィンドウクローズ時エラー: {e}")
            event.accept()

def main():
    """メイン関数"""
    # PySide6アプリケーション作成
    app = QApplication(sys.argv)
    
    # アプリケーション設定
    app.setApplicationName("おしゃべりシリウス")
    app.setApplicationVersion("1.0.0")
    
    # スタイル設定
    app.setStyle("Fusion")
    
    # ダークテーマ設定
    palette = QPalette()
    # ウィンドウ背景
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    # ボタン背景
    palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 60))
    # テキスト色
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    # 入力フィールド背景
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    # ハイライト色
    palette.setColor(QPalette.ColorRole.Highlight, QColor(100, 181, 246))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)
    
    window = None
    try:
        # メインウィンドウ作成
        window = SiriusFaceAnimUI()
        window.show()
        
        # アプリケーション実行
        result = app.exec()
        
        # 明示的なクリーンアップ
        if window:
            window.cleanup_worker_thread()
            window = None
        
        # アプリケーション終了
        app.quit()
        sys.exit(result)
        
    except Exception as e:
        QMessageBox.critical(None, "重大なエラー", f"アプリケーション起動エラー: {e}")
        
        # エラー時のクリーンアップ
        if window:
            try:
                window.cleanup_worker_thread()
            except:
                pass
        
        app.quit()
        sys.exit(1)

if __name__ == "__main__":
    main()
