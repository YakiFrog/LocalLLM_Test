#!/usr/bin/env python3
"""
シリウスくん ウェイクワード検出GUI
PySide6を使用したユーザーフレンドリーなインターフェース
"""

import sys
import pyaudio
import tempfile
import wave
import os
import time
from threading import Thread, Event
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QPushButton, QLabel, QTextEdit, QProgressBar,
                               QComboBox, QSpinBox, QGroupBox, QGridLayout, QCheckBox)
from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap, QIcon
from faster_whisper import WhisperModel
import numpy as np

class WakeWordThread(QThread):
    # シグナル定義
    status_update = Signal(str)
    volume_update = Signal(float)
    recognition_result = Signal(str)
    wake_word_detected = Signal(str)
    error_occurred = Signal(str)
    model_loaded = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.running = False
        self.whisper_model = None
        self.audio_buffer = []
        self.last_check = 0
        self.last_recognition_text = ""  # 前回の認識結果を記録
        self.same_text_count = 0  # 同じテキストの連続回数
        
    def run(self):
        """メインの監視ループ"""
        try:
            self.load_whisper_model()
            self.start_audio_monitoring()
        except Exception as e:
            self.error_occurred.emit(f"監視エラー: {str(e)}")
    
    def load_whisper_model(self):
        """Whisperモデルの読み込み"""
        self.status_update.emit("🔄 Whisperモデルを読み込み中...")
        self.whisper_model = WhisperModel("medium", device="cpu", compute_type="int8")
        self.model_loaded.emit()
        self.status_update.emit("✅ モデル読み込み完了")
    
    def start_audio_monitoring(self):
        """音声監視の開始（エラーハンドリング強化版）"""
        self.running = True
        self.status_update.emit("🎤 音声監視を開始しました")
        
        # PyAudio初期化
        p = pyaudio.PyAudio()
        stream = None
        
        try:
            stream = p.open(
                format=self.config['format'],
                channels=self.config['channels'],
                rate=self.config['sample_rate'],
                input=True,
                input_device_index=self.config['device_index'],
                frames_per_buffer=self.config['chunk_size']
            )
            
            buffer_frames = int(self.config['buffer_duration'] * self.config['sample_rate'] / self.config['chunk_size'])
            error_count = 0  # エラーカウンター
            
            while self.running:
                try:
                    # 音声データ読み取り
                    data = stream.read(self.config['chunk_size'], exception_on_overflow=False)
                    self.audio_buffer.append(data)
                    
                    # バッファサイズ制限
                    if len(self.audio_buffer) > buffer_frames:
                        self.audio_buffer.pop(0)
                    
                    # 音声レベル更新（頻度を下げてCPU負荷軽減）
                    if len(self.audio_buffer) % 20 == 0:  # 20フレームに1回に削減
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        volume = np.sqrt(np.mean(audio_data**2))
                        self.volume_update.emit(volume)
                    
                    # 定期的にウェイクワード検出
                    current_time = time.time()
                    if (current_time - self.last_check >= self.config['check_interval'] and 
                        len(self.audio_buffer) >= buffer_frames // 2):
                        
                        self.last_check = current_time
                        
                        # 音声レベルをチェック
                        recent_audio = b''.join(self.audio_buffer[-10:])
                        audio_data = np.frombuffer(recent_audio, dtype=np.int16)
                        volume = np.sqrt(np.mean(audio_data**2)) if len(audio_data) > 0 else 0
                        
                        if volume > self.config['volume_threshold']:
                            self.status_update.emit(f"🔍 認識処理中... [音声レベル:{volume:.0f}]")
                            result = self.check_wake_word()
                            if result:
                                self.wake_word_detected.emit("シリウスくん")
                                break
                    
                    error_count = 0  # 正常時はエラーカウンターリセット
                            
                except Exception as e:
                    error_count += 1
                    if error_count > 10:  # 連続エラーが多い場合は停止
                        self.error_occurred.emit(f"連続エラーが発生しました: {str(e)}")
                        break
                        
        except Exception as e:
            self.error_occurred.emit(f"音声監視エラー: {str(e)}")
        finally:
            if stream:
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
                    wf.setnchannels(self.config['channels'])
                    wf.setsampwidth(pyaudio.get_sample_size(self.config['format']))
                    wf.setframerate(self.config['sample_rate'])
                    wf.writeframes(b''.join(self.audio_buffer))
            
            # 音声認識実行（精度向上設定）
            segments, info = self.whisper_model.transcribe(
                temp_filename,
                language="ja",
                beam_size=5,  # ビームサイズを増加
                temperature=0.1,  # 少し温度を上げて多様性確保
                no_speech_threshold=0.4,  # 閾値を上げて無音判定を厳しく
                condition_on_previous_text=False,
                word_timestamps=False,
                initial_prompt="シリウスくん、しりうすくん、シリウス君"  # 候補語彙を提示
            )
            
            # 認識結果を取得
            full_text = ""
            for segment in segments:
                full_text += segment.text.strip()
            
            if full_text.strip():
                self.recognition_result.emit(full_text)
                
                # ウェイクワード検出チェック（詳細ログ付き）
                if "シリウスくん" in full_text:
                    self.recognition_result.emit(f"✅ 完全一致: {full_text}")
                    return True
                elif self.flexible_match("シリウスくん", full_text):
                    self.recognition_result.emit(f"✅ 柔軟一致: {full_text}")
                    return True
                else:
                    self.recognition_result.emit(f"❌ 不一致: {full_text}")
            
            # 一時ファイル削除
            try:
                os.unlink(temp_filename)
            except:
                pass
                
        except Exception as e:
            self.error_occurred.emit(f"認識エラー: {str(e)}")
        
        return False
    
    def flexible_match(self, wake_word, text):
        """高精度柔軟マッチング（音韻類似性も考慮）"""
        # 基本パターン
        basic_patterns = [
            "シリウス", "しりうす", "シリウス君", "しりうす君",
            "シリウスくん", "しりうすくん"
        ]
        
        # 音韻類似パターン（よくある認識ミス）
        phonetic_patterns = [
            "シリーズ",      # 今回の問題！一時的に許可
            "シリース",      # よくある認識ミス
            "シリュース",    # 別の認識ミス
            "シリュースくん", # フル版
            "シリウース",    # 長音違い
            "シリエス",      # 短縮認識ミス
            "シリユース",    # 別のパターン
        ]
        
        # すべてのパターンをチェック
        all_patterns = basic_patterns + phonetic_patterns
        for pattern in all_patterns:
            if pattern in text:
                return True
                
        # 部分マッチング（コア部分 + 敬語）
        core_patterns = ["シリ", "しり"]
        for core in core_patterns:
            if core in text and ("くん" in text or "君" in text or "さん" in text):
                return True
                
        return False
    
    def stop_monitoring(self):
        """監視停止"""
        self.running = False
        self.status_update.emit("⏹️ 監視を停止しました")

class WakeWordGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.wake_word_thread = None
        self.setup_ui()
        self.setup_config()
        
    def setup_ui(self):
        """UIセットアップ"""
        self.setWindowTitle("シリウスくん ウェイクワード検出システム")
        self.setGeometry(100, 100, 800, 600)
        
        # メインウィジェット
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # タイトル
        title = QLabel("🎤 シリウスくん ウェイクワード検出システム")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #4FC3F7; margin: 10px;")
        layout.addWidget(title)
        
        # 設定グループ
        self.setup_settings_group(layout)
        
        # ステータスグループ
        self.setup_status_group(layout)
        
        # コントロールボタン
        self.setup_control_buttons(layout)
        
        # ログエリア
        self.setup_log_area(layout)
        
    def setup_settings_group(self, parent_layout):
        """設定グループの作成"""
        settings_group = QGroupBox("🔧 設定")
        settings_layout = QGridLayout(settings_group)
        
        # デバイス設定
        settings_layout.addWidget(QLabel("マイクデバイス:"), 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["MacBook Air内蔵マイク (1)", "外部マイク (0)", "USB マイク (2)"])
        settings_layout.addWidget(self.device_combo, 0, 1)
        
        # 音量閾値
        settings_layout.addWidget(QLabel("音量閾値:"), 0, 2)
        self.volume_threshold_spin = QSpinBox()
        self.volume_threshold_spin.setRange(1, 100)
        self.volume_threshold_spin.setValue(25)  # 15→25に上げて不要認識を削減
        settings_layout.addWidget(self.volume_threshold_spin, 0, 3)
        
        # チェック間隔
        settings_layout.addWidget(QLabel("チェック間隔(秒):"), 1, 0)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 10)
        self.interval_spin.setValue(2)  # 1→2に戻してパフォーマンス改善
        settings_layout.addWidget(self.interval_spin, 1, 1)
        
        # 詳細ログ
        self.detailed_log_check = QCheckBox("詳細ログ表示")
        self.detailed_log_check.setChecked(True)
        settings_layout.addWidget(self.detailed_log_check, 1, 2)
        
        parent_layout.addWidget(settings_group)
    
    def setup_status_group(self, parent_layout):
        """ステータスグループの作成"""
        status_group = QGroupBox("📊 ステータス")
        status_layout = QGridLayout(status_group)
        
        # ステータス表示
        status_layout.addWidget(QLabel("システム状態:"), 0, 0)
        self.status_label = QLabel("🔴 停止中")
        self.status_label.setStyleSheet("font-weight: bold; color: #FF5252;")
        status_layout.addWidget(self.status_label, 0, 1)
        
        # 音声レベル
        status_layout.addWidget(QLabel("音声レベル:"), 1, 0)
        self.volume_progress = QProgressBar()
        self.volume_progress.setRange(0, 100)
        status_layout.addWidget(self.volume_progress, 1, 1, 1, 2)
        
        # 最後の認識結果
        status_layout.addWidget(QLabel("最後の認識:"), 2, 0)
        self.last_recognition = QLabel("まだありません")
        self.last_recognition.setStyleSheet("font-style: italic; color: #BDBDBD;")
        status_layout.addWidget(self.last_recognition, 2, 1, 1, 2)
        
        parent_layout.addWidget(status_group)
    
    def setup_control_buttons(self, parent_layout):
        """コントロールボタンの作成"""
        button_layout = QHBoxLayout()
        
        # 開始ボタン
        self.start_button = QPushButton("🎤 監視開始")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45A049;
            }
        """)
        self.start_button.clicked.connect(self.start_monitoring)
        button_layout.addWidget(self.start_button)
        
        # 停止ボタン
        self.stop_button = QPushButton("⏹️ 監視停止")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        # ログクリア
        clear_button = QPushButton("🗑️ ログクリア")
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        clear_button.clicked.connect(self.clear_logs)
        button_layout.addWidget(clear_button)
        
        # 詳細分析ボタン（手動実行用）
        analyze_button = QPushButton("🔍 詳細分析")
        analyze_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-size: 14px;
                padding: 10px 20px;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        analyze_button.clicked.connect(self.manual_analyze)
        button_layout.addWidget(analyze_button)
        
        parent_layout.addLayout(button_layout)
    
    def setup_log_area(self, parent_layout):
        """ログエリアの作成"""
        log_group = QGroupBox("📝 ログ")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #212121;
                color: #FFFFFF;
                border: 1px solid #424242;
                font-family: 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        parent_layout.addWidget(log_group)
    
    def setup_config(self):
        """設定の初期化"""
        self.config = {
            'sample_rate': 48000,
            'chunk_size': 1024,
            'channels': 1,
            'format': pyaudio.paInt16,
            'device_index': 1,
            'buffer_duration': 3.0,  # バッファを長くして安定性向上
            'check_interval': 2.0,   # チェック間隔を延長してCPU負荷軽減
            'volume_threshold': 25   # 閾値を上げて不要な認識を減らす
        }
    
    def start_monitoring(self):
        """監視開始"""
        if self.wake_word_thread and self.wake_word_thread.isRunning():
            return
        
        # 設定を更新
        self.update_config()
        
        # スレッド作成と開始
        self.wake_word_thread = WakeWordThread(self.config)
        self.wake_word_thread.status_update.connect(self.update_status)
        self.wake_word_thread.volume_update.connect(self.update_volume)
        self.wake_word_thread.recognition_result.connect(self.update_recognition)
        self.wake_word_thread.wake_word_detected.connect(self.on_wake_word_detected)
        self.wake_word_thread.error_occurred.connect(self.on_error)
        self.wake_word_thread.model_loaded.connect(self.on_model_loaded)
        
        self.wake_word_thread.start()
        
        # UIの状態を更新
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("🟡 初期化中...")
        self.status_label.setStyleSheet("font-weight: bold; color: #FFC107;")
        
        self.add_log("システム開始処理を開始しました")
    
    def stop_monitoring(self):
        """監視停止"""
        if self.wake_word_thread:
            self.wake_word_thread.stop_monitoring()
            self.wake_word_thread.wait()
        
        # UIの状態を更新
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_label.setText("🔴 停止中")
        self.status_label.setStyleSheet("font-weight: bold; color: #FF5252;")
        self.volume_progress.setValue(0)
        
        self.add_log("システムを停止しました")
    
    def update_config(self):
        """設定を更新"""
        device_map = {"MacBook Air内蔵マイク (1)": 1, "外部マイク (0)": 0, "USB マイク (2)": 2}
        device_text = self.device_combo.currentText()
        self.config['device_index'] = device_map.get(device_text, 1)
        self.config['volume_threshold'] = self.volume_threshold_spin.value()
        self.config['check_interval'] = self.interval_spin.value()
    
    def update_status(self, status):
        """ステータス更新"""
        if "監視を開始" in status:
            self.status_label.setText("🟢 監視中")
            self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        elif "停止" in status:
            self.status_label.setText("🔴 停止中")
            self.status_label.setStyleSheet("font-weight: bold; color: #FF5252;")
        
        if self.detailed_log_check.isChecked():
            self.add_log(status)
    
    def update_volume(self, volume):
        """音量レベル更新"""
        progress_value = min(int(volume), 100)
        self.volume_progress.setValue(progress_value)
        
        # 色の変更
        if volume > self.config['volume_threshold']:
            self.volume_progress.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #4CAF50;
                }
            """)
        else:
            self.volume_progress.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #FFC107;
                }
            """)
    
    def update_recognition(self, text):
        """認識結果更新（軽量版 + フィルタリング）"""
        self.last_recognition.setText(f"'{text}'")
        
        # 認識結果の簡潔な表示
        if "✅" in text:
            self.last_recognition.setStyleSheet("font-style: normal; color: #4CAF50; font-weight: bold;")
            self.add_log(f"🎉 {text}")
        elif "❌ 簡易" in text:
            # 短い単語は表示のみ（ログには残さない）
            self.last_recognition.setStyleSheet("font-style: normal; color: #FFC107;")
            # ログは出さない（spam防止）
        elif "❌" in text:
            self.last_recognition.setStyleSheet("font-style: normal; color: #FF5252;")
            # 簡潔なログのみ（重い分析処理は省略）
            actual_text = text.replace("❌ 不一致: ", "")
            self.add_log(f"📝 認識結果: '{actual_text}' (不一致)")
        else:
            self.last_recognition.setStyleSheet("font-style: normal; color: #FFFFFF;")
            self.add_log(f"📝 認識結果: '{text}'")
    
    def on_wake_word_detected(self, word):
        """ウェイクワード検出時の処理"""
        self.add_log(f"🎉 ウェイクワード検出成功: '{word}'")
        self.status_label.setText("🎉 検出成功！")
        self.status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        
        # 自動的に停止
        QTimer.singleShot(3000, self.stop_monitoring)  # 3秒後に停止
    
    def on_error(self, error):
        """エラー発生時の処理"""
        self.add_log(f"❌ エラー: {error}")
        self.status_label.setText("❌ エラー")
        self.status_label.setStyleSheet("font-weight: bold; color: #FF5252;")
    
    def on_model_loaded(self):
        """モデル読み込み完了時の処理"""
        self.status_label.setText("🟡 準備完了")
        self.status_label.setStyleSheet("font-weight: bold; color: #FF9800;")
    
    def add_log(self, message):
        """ログ追加"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def clear_logs(self):
        """ログクリア"""
        self.log_text.clear()
        self.add_log("ログをクリアしました")
    
    def manual_analyze(self):
        """手動で詳細分析を実行"""
        last_text = self.last_recognition.text()
        if last_text and last_text != "まだありません":
            # クォートを除去
            clean_text = last_text.strip("'\"❌✅")
            if "不一致:" in clean_text:
                clean_text = clean_text.replace("不一致:", "").strip()
            elif "柔軟一致:" in clean_text:
                clean_text = clean_text.replace("柔軟一致:", "").strip()
            elif "完全一致:" in clean_text:
                clean_text = clean_text.replace("完全一致:", "").strip()
            
            self.add_log("🔬 手動詳細分析を開始...")
            self.analyze_matching(clean_text)
        else:
            self.add_log("❌ 分析対象となる認識結果がありません")
    
    def analyze_matching(self, text):
        """マッチング分析（デバッグ用）"""
        self.add_log(f"🔍 マッチング分析: '{text}'")
        
        # 文字レベルでの類似性チェック
        target = "シリウスくん"
        similarity_score = 0
        for char in target:
            if char in text:
                similarity_score += 1
        
        similarity_percent = (similarity_score / len(target)) * 100
        self.add_log(f"   文字類似度: {similarity_percent:.1f}% ({similarity_score}/{len(target)}文字一致)")
        
        # 具体的なパターンマッチング結果
        patterns_found = []
        all_patterns = [
            "シリウス", "しりうす", "シリウス君", "しりうす君", "シリウスくん", "しりうすくん",
            "シリーズ", "シリース", "シリュース", "シリュースくん", "シリウース", "シリエス"
        ]
        
        for pattern in all_patterns:
            if pattern in text:
                patterns_found.append(pattern)
        
        if patterns_found:
            self.add_log(f"   発見パターン: {', '.join(patterns_found)}")
        else:
            self.add_log(f"   発見パターン: なし")
        
        # 推奨される改善点
        if "シリーズ" in text:
            self.add_log(f"   💡 ヒント: 'シリーズ' → 'シリウス' に近い！より明確に発音してみてください")
        elif "シリ" in text:
            self.add_log(f"   💡 ヒント: 'シリ' 部分は認識されています。'ウスくん' 部分を明確に")

def main():
    app = QApplication(sys.argv)
    
    # アプリケーションスタイル設定
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1E1E1E;
            color: #FFFFFF;
        }
        QWidget {
            background-color: #1E1E1E;
            color: #FFFFFF;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #424242;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            color: #FFFFFF;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #4FC3F7;
        }
        QLabel {
            color: #FFFFFF;
        }
        QComboBox {
            background-color: #2D2D30;
            color: #FFFFFF;
            border: 1px solid #424242;
            padding: 5px;
            border-radius: 3px;
        }
        QComboBox::drop-down {
            border: none;
        }
        QComboBox QAbstractItemView {
            background-color: #2D2D30;
            color: #FFFFFF;
            border: 1px solid #424242;
        }
        QSpinBox {
            background-color: #2D2D30;
            color: #FFFFFF;
            border: 1px solid #424242;
            padding: 5px;
            border-radius: 3px;
        }
        QCheckBox {
            color: #FFFFFF;
        }
        QProgressBar {
            border: 1px solid #424242;
            border-radius: 5px;
            text-align: center;
            background-color: #2D2D30;
            color: #FFFFFF;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 5px;
        }
    """)
    
    window = WakeWordGUI()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()