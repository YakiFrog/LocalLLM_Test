#!/usr/bin/env python3
"""
プロンプトチューニング統合型シリウス音声対話UIアプリケーション
PySide6 + ローカルLLM + VOICEVOX AudioQuery + プロンプトチューニング統合システム
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QLineEdit, QComboBox, 
    QProgressBar, QScrollArea, QFrame, QSplitter, QGroupBox,
    QCheckBox, QSpinBox, QSlider, QMessageBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextBrowser
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QPalette, QColor

# Advanced LLM Face Controllerのインポート
from advanced_llm_controller import AdvancedLLMFaceController
from prompt_tuning import PromptTuner

# 既存のワーカークラスを継承
from sync_siriusface import ConversationWorker, ConversationDisplay, StatusPanel

class AdvancedConversationWorker(QThread):
    """プロンプトチューニング対応会話処理用ワーカースレッド"""
    conversation_finished = Signal(dict)
    
    def __init__(self, controller: AdvancedLLMFaceController, user_message: str, expression: str, 
                 auto_optimize: bool = False, scenario_hint: Optional[str] = None):
        super().__init__()
        self.controller = controller
        self.user_message = user_message
        self.expression = expression
        self.auto_optimize = auto_optimize
        self.scenario_hint = scenario_hint
    
    def run(self):
        """ワーカースレッドの実行"""
        try:
            # asyncioイベントループを作成
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.controller.process_user_input_with_optimization(
                        self.user_message, 
                        self.expression,
                        self.auto_optimize,
                        self.scenario_hint
                    )
                )
                self.conversation_finished.emit(result)
            finally:
                loop.close()
                
        except Exception as e:
            error_result = {
                "success": False,
                "user_message": self.user_message,
                "llm_response": None,
                "voice_success": False,
                "expression_success": False,
                "error": f"会話処理エラー: {e}"
            }
            self.conversation_finished.emit(error_result)

class PromptConfigurationPanel(QWidget):
    """プロンプト設定パネル"""
    config_changed = Signal(str)  # 設定変更シグナル
    
    def __init__(self, controller: AdvancedLLMFaceController):
        super().__init__()
        self.controller = controller
        self.init_ui()
        self.load_configurations()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # プロンプト設定グループ
        config_group = QGroupBox("プロンプト設定")
        config_group.setStyleSheet("""
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
        config_layout = QVBoxLayout()
        
        # システムメッセージ選択
        sys_msg_layout = QHBoxLayout()
        sys_msg_label = QLabel("システムメッセージ:")
        sys_msg_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.system_message_combo = QComboBox()
        self.system_message_combo.setStyleSheet("""
            QComboBox {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
                min-width: 150px;
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
        self.system_message_combo.currentTextChanged.connect(self.on_config_change)
        
        sys_msg_layout.addWidget(sys_msg_label)
        sys_msg_layout.addWidget(self.system_message_combo)
        sys_msg_layout.addStretch()
        
        # LLM設定選択
        llm_setting_layout = QHBoxLayout()
        llm_setting_label = QLabel("LLM設定:")
        llm_setting_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.llm_setting_combo = QComboBox()
        self.llm_setting_combo.setStyleSheet(self.system_message_combo.styleSheet())
        self.llm_setting_combo.currentTextChanged.connect(self.on_config_change)
        
        llm_setting_layout.addWidget(llm_setting_label)
        llm_setting_layout.addWidget(self.llm_setting_combo)
        llm_setting_layout.addStretch()
        
        # 自動最適化オプション
        optimization_layout = QHBoxLayout()
        self.auto_optimize_checkbox = QCheckBox("自動最適化を有効にする")
        self.auto_optimize_checkbox.setStyleSheet("""
            QCheckBox {
                color: #ffffff;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #2b2b2b;
                border: 2px solid #555;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 3px;
            }
        """)
        
        optimization_layout.addWidget(self.auto_optimize_checkbox)
        optimization_layout.addStretch()
        
        # シナリオヒント入力
        scenario_layout = QHBoxLayout()
        scenario_label = QLabel("シナリオヒント:")
        scenario_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.scenario_input = QLineEdit()
        self.scenario_input.setPlaceholderText("例: 基本挨拶, 技術質問, 創作依頼...")
        self.scenario_input.setStyleSheet("""
            QLineEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:focus {
                border: 2px solid #64B5F6;
            }
        """)
        
        scenario_layout.addWidget(scenario_label)
        scenario_layout.addWidget(self.scenario_input)
        
        # レイアウト組み立て
        config_layout.addLayout(sys_msg_layout)
        config_layout.addLayout(llm_setting_layout)
        config_layout.addLayout(optimization_layout)
        config_layout.addLayout(scenario_layout)
        config_group.setLayout(config_layout)
        
        # 設定変更ボタン
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("設定を適用")
        self.apply_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #42A5F5;
            }
            QPushButton:pressed {
                background-color: #1976D2;
            }
        """)
        self.apply_button.clicked.connect(self.apply_configuration)
        
        button_layout.addWidget(self.apply_button)
        button_layout.addStretch()
        
        # メインレイアウト
        layout.addWidget(config_group)
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def load_configurations(self):
        """利用可能な設定をロード"""
        available_configs = self.controller.get_available_prompt_configurations()
        
        # システムメッセージを設定
        self.system_message_combo.clear()
        self.system_message_combo.addItems(available_configs["system_messages"])
        self.system_message_combo.setCurrentText(self.controller.current_prompt_config)
        
        # LLM設定を設定
        self.llm_setting_combo.clear()
        self.llm_setting_combo.addItems(available_configs["llm_settings"])
        self.llm_setting_combo.setCurrentText(self.controller.current_prompt_config)
    
    def on_config_change(self):
        """設定変更時の処理"""
        current_config = self.system_message_combo.currentText()
        self.config_changed.emit(current_config)
    
    def apply_configuration(self):
        """設定を適用"""
        selected_config = self.system_message_combo.currentText()
        success = self.controller.switch_prompt_configuration(selected_config)
        
        if success:
            QMessageBox.information(self, "設定適用", f"プロンプト設定 '{selected_config}' を適用しました")
        else:
            QMessageBox.warning(self, "設定適用失敗", f"プロンプト設定 '{selected_config}' の適用に失敗しました")
    
    def get_auto_optimize_settings(self):
        """自動最適化設定を取得"""
        return {
            "enabled": self.auto_optimize_checkbox.isChecked(),
            "scenario_hint": self.scenario_input.text().strip() or None
        }

class PerformanceStatsPanel(QWidget):
    """性能統計パネル"""
    
    def __init__(self, controller: AdvancedLLMFaceController):
        super().__init__()
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 統計情報表示
        stats_group = QGroupBox("性能統計")
        stats_group.setStyleSheet("""
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
        stats_layout = QVBoxLayout()
        
        self.stats_display = QTextBrowser()
        self.stats_display.setStyleSheet("""
            QTextBrowser {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Courier New', monospace;
            }
        """)
        self.stats_display.setMaximumHeight(200)
        
        stats_layout.addWidget(self.stats_display)
        stats_group.setLayout(stats_layout)
        
        # 更新ボタン
        button_layout = QHBoxLayout()
        
        self.update_button = QPushButton("統計を更新")
        self.update_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #66BB6A;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
        """)
        self.update_button.clicked.connect(self.update_stats)
        
        button_layout.addWidget(self.update_button)
        button_layout.addStretch()
        
        # レイアウト組み立て
        layout.addWidget(stats_group)
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # 初期統計を表示
        self.update_stats()
    
    def update_stats(self):
        """統計情報を更新"""
        try:
            stats = self.controller.get_performance_stats()
            
            if "error" in stats:
                self.stats_display.setHtml(f"""
                <div style='color: #E57373; font-weight: bold;'>
                    ❌ {stats['error']}
                </div>
                """)
                return
            
            # HTML形式で統計を表示
            html_content = f"""
            <div style='color: #81C784; font-weight: bold; font-size: 14px;'>
                📊 現在の設定: {stats['configuration']}
            </div>
            <br>
            <div style='color: #64B5F6;'>
                <strong>総テスト数:</strong> {stats['total_tests']}<br>
                <strong>成功テスト数:</strong> {stats['successful_tests']}<br>
                <strong>成功率:</strong> {stats['success_rate_percent']:.1f}%<br>
                <strong>平均応答時間:</strong> {stats['average_response_time']:.2f}秒
            </div>
            """
            
            if stats['recent_tests']:
                html_content += f"""
                <br>
                <div style='color: #FFB74D; font-weight: bold;'>
                    📈 最近のテスト結果:
                </div>
                """
                
                for i, test in enumerate(stats['recent_tests'][-3:], 1):  # 最新3件のみ表示
                    status = "✅" if test['success'] else "❌"
                    html_content += f"""
                    <div style='margin-left: 10px; font-size: 12px;'>
                        {status} {test['scenario_name']}: {test['response_time_seconds']:.2f}秒
                    </div>
                    """
            
            self.stats_display.setHtml(html_content)
            
        except Exception as e:
            self.stats_display.setHtml(f"""
            <div style='color: #E57373; font-weight: bold;'>
                ❌ 統計更新エラー: {e}
            </div>
            """)

class AdvancedInputPanel(QWidget):
    """プロンプトチューニング対応入力パネル"""
    send_message = Signal(str, str, dict)  # message, expression, optimization_settings
    
    def __init__(self, controller: AdvancedLLMFaceController):
        super().__init__()
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 既存の入力部分（簡略版）
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
        self.message_input.setMaximumHeight(80)
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
        
        # 表情選択
        controls_layout = QHBoxLayout()
        
        expression_label = QLabel("表情:")
        expression_label.setStyleSheet("color: #ffffff; font-weight: bold;")
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
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555;
                selection-background-color: #64B5F6;
            }
        """)
        
        controls_layout.addWidget(expression_label)
        controls_layout.addWidget(self.expression_combo)
        controls_layout.addStretch()
        
        # 入力エリア組み立て
        input_layout.addWidget(self.message_input)
        input_layout.addLayout(controls_layout)
        input_group.setLayout(input_layout)
        
        # プロンプト設定パネル
        self.prompt_config_panel = PromptConfigurationPanel(self.controller)
        
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
        layout.addWidget(self.prompt_config_panel)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def send_message_clicked(self):
        """送信ボタンクリック処理"""
        message = self.message_input.toPlainText().strip()
        if message:
            expression = self.expression_combo.currentText()
            optimization_settings = self.prompt_config_panel.get_auto_optimize_settings()
            self.send_message.emit(message, expression, optimization_settings)
            self.message_input.clear()
    
    def clear_input(self):
        """入力クリア"""
        self.message_input.clear()
    
    def set_enabled(self, enabled: bool):
        """入力欄の有効/無効を設定"""
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        self.expression_combo.setEnabled(enabled)

class AdvancedSiriusFaceAnimUI(QMainWindow):
    """プロンプトチューニング統合型メインUIウィンドウ"""
    
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
            self.controller = AdvancedLLMFaceController(prompt_config_name="default")
            if not self.controller.is_initialized:
                QMessageBox.critical(self, "エラー", "AdvancedLLMFaceControllerの初期化に失敗しました")
                sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"システム初期化エラー: {e}")
            sys.exit(1)
    
    def init_ui(self):
        """UIを初期化"""
        self.setWindowTitle("シリウス音声対話システム（プロンプトチューニング統合版）")
        self.setGeometry(100, 100, 1000, 700)
        
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
        header = QLabel("🤖 シリウス音声対話システム（プロンプトチューニング統合版）")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #64B5F6;
                padding: 15px;
                background-color: #1e1e1e;
                border-bottom: 2px solid #424242;
            }
        """)
        
        # タブウィジェット
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
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #4CAF50;
            }
            QTabBar::tab:hover {
                background-color: #66BB6A;
            }
        """)
        
        # 会話タブ
        conversation_widget = QWidget()
        conversation_layout = QVBoxLayout()
        
        # スプリッター（上下分割）
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 会話表示部分
        self.conversation_display = ConversationDisplay()
        splitter.addWidget(self.conversation_display)
        
        # 入力部分
        self.input_panel = AdvancedInputPanel(self.controller)
        splitter.addWidget(self.input_panel)
        
        # スプリッター比率設定
        splitter.setStretchFactor(0, 2)  # 会話表示部分
        splitter.setStretchFactor(1, 1)  # 入力部分
        
        conversation_layout.addWidget(splitter)
        conversation_widget.setLayout(conversation_layout)
        
        # 統計タブ
        stats_widget = PerformanceStatsPanel(self.controller)
        
        # タブを追加
        tab_widget.addTab(conversation_widget, "💬 会話")
        tab_widget.addTab(stats_widget, "📊 統計")
        
        # ステータスパネル
        self.status_panel = StatusPanel()
        
        # レイアウト組み立て
        main_layout.addWidget(header)
        main_layout.addWidget(tab_widget)
        main_layout.addWidget(self.status_panel)
        
        main_widget.setLayout(main_layout)
        
        # 初期メッセージ
        self.conversation_display.add_system_message("シリウス音声対話システム（プロンプトチューニング統合版）が起動しました", "success")
        self.conversation_display.add_system_message("プロンプト設定を調整して会話の品質を向上させることができます", "info")
    
    def init_connections(self):
        """シグナル・スロット接続を初期化"""
        self.input_panel.send_message.connect(self.handle_user_message)
    
    def handle_user_message(self, message: str, expression: str, optimization_settings: Dict[str, Any]):
        """ユーザーメッセージを処理"""
        # UI更新
        self.conversation_display.add_user_message(message)
        self.input_panel.set_enabled(False)
        self.status_panel.set_status("処理中...", True)
        
        # 最適化設定を表示
        if optimization_settings["enabled"]:
            opt_msg = f"自動最適化が有効です"
            if optimization_settings["scenario_hint"]:
                opt_msg += f"（シナリオ: {optimization_settings['scenario_hint']}）"
            self.conversation_display.add_system_message(opt_msg, "info")
        
        # ワーカースレッドで処理
        self.conversation_worker = AdvancedConversationWorker(
            self.controller, 
            message, 
            expression,
            optimization_settings["enabled"],
            optimization_settings["scenario_hint"]
        )
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
                    QTimer.singleShot(8000, lambda: self.status_panel.set_status("準備完了"))
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
            if self.conversation_worker:
                self.conversation_worker.deleteLater()
                self.conversation_worker = None
    
    def closeEvent(self, event):
        """ウィンドウクローズ時の処理"""
        # ワーカースレッドが実行中の場合は停止を待つ
        if self.conversation_worker and self.conversation_worker.isRunning():
            self.conversation_worker.conversation_finished.disconnect()
            self.conversation_worker.terminate()
            self.conversation_worker.wait(3000)
            if self.conversation_worker.isRunning():
                self.conversation_worker.quit()
                self.conversation_worker.wait()
        
        # コントローラーのクリーンアップ
        if self.controller:
            try:
                self.controller.stop_speaking()
                self.controller.cleanup()
            except Exception as e:
                print(f"クリーンアップエラー: {e}")
        
        event.accept()

def main():
    """メイン関数"""
    # PySide6アプリケーション作成
    app = QApplication(sys.argv)
    
    # アプリケーション設定
    app.setApplicationName("シリウス音声対話システム（プロンプトチューニング統合版）")
    app.setApplicationVersion("2.0.0")
    
    # スタイル設定
    app.setStyle("Fusion")
    
    # ダークテーマ設定
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(45, 45, 45))
    palette.setColor(QPalette.ColorRole.Button, QColor(60, 60, 60))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(100, 181, 246))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
    app.setPalette(palette)
    
    try:
        # メインウィンドウ作成
        window = AdvancedSiriusFaceAnimUI()
        window.show()
        
        # アプリケーション実行
        sys.exit(app.exec())
        
    except Exception as e:
        QMessageBox.critical(None, "重大なエラー", f"アプリケーション起動エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()