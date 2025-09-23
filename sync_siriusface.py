#!/usr/bin/env python3
"""
シリウス音声対話UIアプリケーション
PySide6 + ローカルLLM + VOICEVOX AudioQuery統合システム
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QComboBox, 
    QProgressBar, QScrollArea, QFrame, QSplitter, QGroupBox,
    QCheckBox, QSpinBox, QSlider, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QColor

# LLM Face Controllerのインポート
from llm_face_controller import LLMFaceController

class ConversationWorker(QThread):
    """会話処理用ワーカースレッド"""
    conversation_finished = Signal(dict)
    
    def __init__(self, controller: LLMFaceController, user_message: str, expression: str, model_setting: str):
        super().__init__()
        self.controller = controller
        self.user_message = user_message
        self.expression = expression
        self.model_setting = model_setting
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

class ConversationDisplay(QWidget):
    """会話表示ウィジェット"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 会話履歴表示エリア
        self.conversation_area = QTextEdit()
        self.conversation_area.setReadOnly(True)
        self.conversation_area.setMinimumHeight(400)
        
        # フォント設定
        font = QFont("Yu Gothic UI", 10)
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
    send_message = Signal(str, str, str)  # message, expression, model_setting
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # メッセージ入力エリア
        input_group = QGroupBox("メッセージ入力")
        input_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #64B5F6;
            }
        """)
        input_layout = QVBoxLayout()
        
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(100)
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
        
        input_layout.addWidget(self.message_input)
        input_group.setLayout(input_layout)
        
        # 設定パネル
        settings_group = QGroupBox("設定")
        settings_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #ffffff;
                border: 2px solid #555;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #64B5F6;
            }
        """)
        settings_layout = QVBoxLayout()
        
        # 第1行: 表情とLLMモデル
        first_row = QHBoxLayout()
        
        # 表情選択
        expression_layout = QVBoxLayout()
        expression_label = QLabel("表情:")
        expression_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        expression_layout.addWidget(expression_label)
        self.expression_combo = QComboBox()
        self.expression_combo.addItems([
            "neutral", "happy", "sad", "angry", "surprised", 
            "confused", "thinking", "sleepy", "excited"
        ])
        self.expression_combo.setCurrentText("happy")
        self.expression_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #ffffff;
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
        
        # LLMモデル選択
        model_layout = QVBoxLayout()
        model_label = QLabel("LLMモデル:")
        model_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        model_layout.addWidget(model_label)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "mistral_default", "mistral_conservative", "mistral_creative", "mistral_precise",
            "default", "conservative", "creative", "precise"
        ])
        self.model_combo.setCurrentText("mistral_default")
        self.model_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                min-width: 120px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #555;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid #ffffff;
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
        
        first_row.addLayout(expression_layout)
        first_row.addLayout(model_layout)
        
        settings_layout.addLayout(first_row)
        settings_group.setLayout(settings_layout)
        
        # ボタンエリア
        button_layout = QHBoxLayout()
        
        self.send_button = QPushButton("送信")
        self.send_button.setMinimumHeight(40)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
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
        
        self.clear_button = QPushButton("クリア")
        self.clear_button.setMinimumHeight(40)
        self.clear_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #42A5F5;
            }
            QPushButton:pressed {
                background-color: #1976D2;
            }
        """)
        self.clear_button.clicked.connect(self.clear_input)
        
        button_layout.addWidget(self.send_button)
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
        return super().eventFilter(obj, event)
    
    def send_message_clicked(self):
        """送信ボタンクリック処理"""
        message = self.message_input.toPlainText().strip()
        if message:
            expression = self.expression_combo.currentText()
            model_setting = self.model_combo.currentText()
            self.send_message.emit(message, expression, model_setting)
            self.message_input.clear()
    
    def clear_input(self):
        """入力クリア"""
        self.message_input.clear()
    
    def set_enabled(self, enabled: bool):
        """入力欄の有効/無効を設定"""
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.expression_combo.setEnabled(enabled)
        self.model_combo.setEnabled(enabled)

class StatusPanel(QWidget):
    """ステータスパネルウィジェット"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        
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
        self.setGeometry(100, 100, 800, 600)
        
        # メインウィジェット
        main_widget = QWidget()
        main_widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: #ffffff;
            }
        """)
        self.setCentralWidget(main_widget)
        
        # メインレイアウト
        main_layout = QVBoxLayout()
        
        # ヘッダー
        header = QLabel("🤖 シリウス音声対話システム")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #64B5F6;
                padding: 15px;
                background-color: #1e1e1e;
                border-bottom: 2px solid #424242;
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
        
        # スプリッター比率設定
        splitter.setStretchFactor(0, 3)  # 会話表示部分を大きく
        splitter.setStretchFactor(1, 1)  # 入力部分を小さく
        
        # ステータスパネル
        self.status_panel = StatusPanel()
        
        # レイアウト組み立て
        main_layout.addWidget(header)
        main_layout.addWidget(splitter)
        main_layout.addWidget(self.status_panel)
        
        main_widget.setLayout(main_layout)
        
        # 初期メッセージ
        self.conversation_display.add_system_message("シリウス音声対話システムが起動しました", "success")
        self.conversation_display.add_system_message("メッセージを入力して「送信」ボタンを押すか、Cmd+Enter（macOS）またはCtrl+Enter（Windows/Linux）で送信できます", "info")
    
    def init_connections(self):
        """シグナル・スロット接続を初期化"""
        self.input_panel.send_message.connect(self.handle_user_message)
    
    def handle_user_message(self, message: str, expression: str, model_setting: str):
        """ユーザーメッセージを処理"""
        # UI更新
        self.conversation_display.add_user_message(message)
        self.conversation_display.add_system_message(f"モデル: {model_setting}", "info")
        self.input_panel.set_enabled(False)
        self.status_panel.set_status("処理中...", True)
        
        # ワーカースレッドで処理
        self.conversation_worker = ConversationWorker(self.controller, message, expression, model_setting)
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
