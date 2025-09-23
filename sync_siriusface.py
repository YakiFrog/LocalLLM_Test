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

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QComboBox, 
    QProgressBar, QScrollArea, QFrame, QSplitter, QGroupBox,
    QCheckBox, QSpinBox, QSlider, QMessageBox, QDialog, QDialogButtonBox, QMenu
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QColor

# 音声関連のインポート
import speech_recognition as sr
import pyaudio
import wave
import whisper

# LLM Face Controllerのインポート
from llm_face_controller import LLMFaceController

class VoiceRecorder(QThread):
    """音声録音・認識処理用スレッド"""
    recording_started = Signal()
    recording_stopped = Signal()
    transcription_ready = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, model_name="medium"):
        super().__init__()
        self.is_recording = False
        self.audio_data = []
        # 音声品質設定（日本語音声認識に最適化・高品質）
        self.sample_rate = 16000        # Whisper推奨サンプルレート
        self.chunk_size = 1024          # バッファサイズ
        self.channels = 1               # モノラル録音
        self.format = pyaudio.paInt16   # 16bit PCM
        self.record_seconds_min = 1.0   # 最小録音時間（秒）
        
        # Whisperモデル（選択されたモデルを使用）
        self.load_whisper_model(model_name)
    
    def load_whisper_model(self, model_name):
        """Whisperモデルをロード"""
        try:
            # 警告を抑制
            import warnings
            warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
            
            print(f"🔄 Whisperモデル（{model_name}）をロード中...")
            self.whisper_model = whisper.load_model(model_name)
            print(f"✅ Whisperモデル（{model_name}）が正常にロードされました")
        except Exception as e:
            print(f"❌ Whisper {model_name}モデル読み込み失敗: {e}")
            self.whisper_model = None
    
    def start_recording(self):
        """録音開始"""
        if not self.is_recording:
            self.is_recording = True
            self.audio_data = []
            self.start()
    
    def stop_recording(self):
        """録音停止"""
        self.is_recording = False
    
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
                frames_per_buffer=self.chunk_size
            )
            
            self.recording_started.emit()
            
            # 録音ループ
            while self.is_recording:
                try:
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    self.audio_data.append(data)
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
            
            # Whisperで音声認識（高精度日本語設定）
            if self.whisper_model:
                try:
                    print("🎤 音声認識処理開始...")
                    # 日本語に特化した高精度設定でWhisperを実行
                    result = self.whisper_model.transcribe(
                        temp_filename, 
                        language="ja",              # 日本語指定
                        fp16=False,                 # CPUではFP16を無効化
                        verbose=False,              # 詳細ログを無効化
                        temperature=0.0,            # 決定論的出力（精度向上）
                        compression_ratio_threshold=2.4,  # 圧縮率閾値（ノイズ除去）
                        logprob_threshold=-1.0,     # 確率閾値（低信頼度フィルタ）
                        no_speech_threshold=0.6,    # 無音判定閾値
                        condition_on_previous_text=False,  # 前のテキストに依存しない
                        initial_prompt="以下は日本語の音声です。",  # 日本語コンテキスト
                        word_timestamps=False       # 単語レベルのタイムスタンプは不要
                    )
                    transcribed_text = result["text"].strip()
                    
                    # 結果の後処理（日本語特有の問題を修正）
                    if transcribed_text:
                        # 不要な空白や記号を除去
                        transcribed_text = transcribed_text.replace("。", "").replace("、", "").strip()
                        print(f"🎤 音声認識結果: '{transcribed_text}'")
                        self.transcription_ready.emit(transcribed_text)
                    else:
                        print("⚠️ 音声が認識できませんでした（空の結果）")
                        self.error_occurred.emit("音声が認識できませんでした。もう一度お試しください。")
                except Exception as e:
                    print(f"❌ Whisper音声認識エラー: {e}")
                    self.error_occurred.emit(f"音声認識処理エラー: {str(e)}")
            else:
                self.error_occurred.emit("Whisperモデルが利用できません")
            
            # 一時ファイルを削除
            os.unlink(temp_filename)
            
        except Exception as e:
            self.error_occurred.emit(f"音声認識エラー: {str(e)}")

class ConversationWorker(QThread):
    """会話処理用ワーカースレッド"""
    conversation_finished = Signal(dict)
    
    def __init__(self, controller: LLMFaceController, user_message: str, expression: str, model_setting: str, prompt: str):
        super().__init__()
        self.controller = controller
        self.user_message = user_message
        self.expression = expression
        self.model_setting = model_setting
        self.prompt = prompt
        self._is_running = False
    
    def run(self):
        """ワーカースレッドの実行"""
        self._is_running = True
        try:
            # スレッドが中断されていないかチェック
            if not self._is_running:
                return
                
            # asyncioイベントループを作成
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # スレッドが中断されていないかチェック
                if not self._is_running:
                    return
                
                # LLMモデル設定を変更
                self.controller.set_llm_setting(self.model_setting)
                
                # プロンプト設定を変更
                self.controller.set_prompt(self.prompt)
                    
                result = loop.run_until_complete(
                    self.controller.process_user_input(self.user_message, self.expression)
                )
                
                # スレッドが中断されていないかチェック
                if self._is_running:
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
        self.voice_recorder = VoiceRecorder(self.current_whisper_model)
        self.voice_recorder.recording_started.connect(self.on_recording_started)
        self.voice_recorder.recording_stopped.connect(self.on_recording_stopped)
        self.voice_recorder.transcription_ready.connect(self.on_transcription_ready)
        self.voice_recorder.error_occurred.connect(self.on_voice_error)
        
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
        
        # すべての設定を水平に配置
        settings_layout.addLayout(expression_layout)
        settings_layout.addLayout(whisper_layout)
        settings_layout.addLayout(model_layout)
        settings_layout.addLayout(prompt_layout)
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
        
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.voice_button)
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
        if message:
            expression = self.expression_combo.currentText()
            model_setting = self.model_combo.currentText()
            prompt = self.prompt_combo.currentText()
            self.send_message.emit(message, expression, model_setting, prompt)
            self.clear_input()  # 送信後に入力欄をクリア
    
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
            self.voice_recorder = VoiceRecorder(new_model)
            self.voice_recorder.recording_started.connect(self.on_recording_started)
            self.voice_recorder.recording_stopped.connect(self.on_recording_stopped)
            self.voice_recorder.transcription_ready.connect(self.on_transcription_ready)
            self.voice_recorder.error_occurred.connect(self.on_voice_error)
            
            # 古いレコーダーをクリーンアップ
            if old_recorder.isRunning():
                old_recorder.quit()
                old_recorder.wait(1000)
            
            # 親ウィンドウの会話表示にメッセージを追加
            main_window = self.parent().parent().parent()
            if hasattr(main_window, 'conversation_display'):
                main_window.conversation_display.add_system_message(f"Whisperモデルを {new_model} に変更しました", "info")
    
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
            main_window.conversation_display.add_system_message("🎤 音声録音中... 話してください", "info")
    
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
    
    def on_transcription_ready(self, text: str):
        """音声認識完了時の処理"""
        # メッセージ入力欄に認識されたテキストを設定
        self.message_input.setText(text)
        
        # 親ウィンドウの会話表示にメッセージを追加
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            main_window.conversation_display.add_system_message(f"✅ 音声認識完了: {text}", "success")
    
    def on_voice_error(self, error_message: str):
        """音声エラー時の処理"""
        # 親ウィンドウの会話表示にエラーメッセージを追加
        main_window = self.parent().parent().parent()
        if hasattr(main_window, 'conversation_display'):
            main_window.conversation_display.add_system_message(f"❌ {error_message}", "error")
        
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
        
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def set_status(self, message: str, progress: bool = False):
        """ステータスを設定"""
        self.status_label.setText(message)
        self.progress_bar.setVisible(progress)
        if progress:
            self.progress_bar.setRange(0, 0)  # 無限プログレス

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
        self.setWindowTitle("シリウス音声対話システム")
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
        header = QLabel("🤖 シリウス音声対話システム")
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
        
        # 会話表示部分
        self.conversation_display = ConversationDisplay()
        splitter.addWidget(self.conversation_display)
        
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
        self.conversation_display.add_system_message("シリウス音声対話システムが起動しました", "success")
        self.conversation_display.add_system_message("💡 使い方:\n• Cmd+Enter (macOS) / Ctrl+Enter (Windows) で送信\n• Escキーで入力欄をクリア\n• 「履歴クリア」ボタンで会話履歴をクリア", "info")
        
        # プロンプト一覧を初期化
        self.update_prompt_list()
    
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
    
    def handle_user_message(self, message: str, expression: str, model_setting: str, prompt: str):
        """ユーザーメッセージを処理"""
        # UI更新
        self.conversation_display.add_user_message(message)
        self.conversation_display.add_system_message(f"モデル: {model_setting} | プロンプト: {prompt}", "info")
        self.input_panel.set_enabled(False)
        self.status_panel.set_status("処理中...", True)
        
        # ワーカースレッドで処理
        self.conversation_worker = ConversationWorker(self.controller, message, expression, model_setting, prompt)
        self.conversation_worker.conversation_finished.connect(self.handle_conversation_result)
        self.conversation_worker.start()
    
    def handle_conversation_result(self, result: Dict[str, Any]):
        """会話処理結果を処理"""
        try:
            if result.get("success", False):
                # 成功時の処理
                llm_response = result.get("llm_response", "")
                self.conversation_display.add_ai_message(llm_response)
                
                # ステータス更新
                if result.get("voice_success", False):
                    self.status_panel.set_status("音声再生中...")
                    # 音声再生完了を待つタイマー（実際の実装では音声再生完了イベントを使用）
                    QTimer.singleShot(8000, lambda: self.status_panel.set_status("準備完了"))  # 8秒に延長
                else:
                    self.conversation_display.add_system_message("音声再生に失敗しました", "warning")
                    self.status_panel.set_status("準備完了")
                
            else:
                # エラー時の処理
                error_msg = result.get("error", "不明なエラー")
                self.conversation_display.add_system_message(f"エラー: {error_msg}", "error")
                self.status_panel.set_status("エラー発生")
                
        except Exception as e:
            self.conversation_display.add_system_message(f"結果処理エラー: {e}", "error")
            self.status_panel.set_status("エラー発生")
        
        finally:
            # UI復元
            self.input_panel.set_enabled(True)
            # ワーカースレッドのクリーンアップ
            self.cleanup_worker_thread()
    
    def cleanup_worker_thread(self):
        """ワーカースレッドのクリーンアップ"""
        if self.conversation_worker:
            # シグナル切断
            try:
                self.conversation_worker.conversation_finished.disconnect()
            except:
                pass
            
            # スレッドが実行中の場合は優雅に停止
            if self.conversation_worker.isRunning():
                self.conversation_worker.stop_gracefully()
                # 少し待ってから強制終了
                if not self.conversation_worker.wait(2000):  # 2秒待機
                    self.conversation_worker.quit()
                    self.conversation_worker.wait(1000)  # さらに1秒待機
            
            # オブジェクトを削除予約
            self.conversation_worker.deleteLater()
            self.conversation_worker = None
        
        # 音声録音スレッドのクリーンアップ
        if hasattr(self.input_panel, 'voice_recorder'):
            voice_recorder = self.input_panel.voice_recorder
            if voice_recorder.isRunning():
                voice_recorder.stop_recording()
                voice_recorder.wait(2000)  # 2秒待機
                if voice_recorder.isRunning():
                    voice_recorder.quit()
                    voice_recorder.wait(1000)  # さらに1秒待機
    
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
    app.setApplicationName("シリウス音声対話システム")
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
