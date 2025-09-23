#!/usr/bin/env python3
"""
プロンプト設定統合型LLMFaceController
プロンプトチューニング機能を統合したバージョン
"""

import asyncio
import sys
import os
import json
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

# 既存のLLMFaceControllerをインポート
from llm_face_controller import LLMFaceController
from prompt_tuning import PromptTuner

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedLLMFaceController(LLMFaceController):
    """プロンプトチューニング機能統合型LLMFaceController"""
    
    def __init__(self, 
                 lm_studio_url="http://127.0.0.1:1234",
                 face_server_url="http://localhost:8080",
                 voicevox_config=None,
                 prompt_config_name="default"):
        """
        初期化
        
        Args:
            lm_studio_url: LM StudioのURL
            face_server_url: シリウス表情サーバーのURL
            voicevox_config: VOICEVOX設定辞書
            prompt_config_name: 使用するプロンプト設定名
        """
        # 親クラスの初期化
        super().__init__(lm_studio_url, face_server_url, voicevox_config)
        
        # プロンプトチューナーを初期化
        self.prompt_tuner = PromptTuner(lm_studio_url)
        
        # プロンプト設定を読み込み
        self.current_prompt_config = prompt_config_name
        self.load_prompt_configuration(prompt_config_name)
        
        logger.info(f"✅ AdvancedLLMFaceController初期化完了 (プロンプト設定: {prompt_config_name})")
    
    def load_prompt_configuration(self, config_name: str):
        """プロンプト設定をロード"""
        try:
            configs = self.prompt_tuner.configs
            
            # システムメッセージを設定
            if config_name in configs["system_messages"]:
                self.system_message = configs["system_messages"][config_name]
                logger.info(f"システムメッセージを設定: {config_name}")
            else:
                logger.warning(f"プロンプト設定 '{config_name}' が見つかりません。デフォルトを使用します。")
                self.system_message = configs["system_messages"]["default"]
            
            # LLM設定を適用
            if config_name in configs["llm_settings"]:
                self.llm_settings = configs["llm_settings"][config_name]
                logger.info(f"LLM設定を適用: {config_name}")
            else:
                logger.warning(f"LLM設定 '{config_name}' が見つかりません。デフォルトを使用します。")
                self.llm_settings = configs["llm_settings"]["default"]
            
            self.current_prompt_config = config_name
            
        except Exception as e:
            logger.error(f"プロンプト設定ロードエラー: {e}")
            # フォールバック
            self.system_message = "あなたは親切で知的なAIアシスタント「シリウス」です。自然で親しみやすい日本語で答えてください。"
            self.llm_settings = {
                "model": "openai/gpt-oss-20b",
                "temperature": 0.7,
                "max_tokens": -1
            }
    
    def switch_prompt_configuration(self, config_name: str) -> bool:
        """プロンプト設定を切り替え"""
        try:
            old_config = self.current_prompt_config
            self.load_prompt_configuration(config_name)
            logger.info(f"プロンプト設定を切り替え: {old_config} → {config_name}")
            return True
        except Exception as e:
            logger.error(f"プロンプト設定切り替えエラー: {e}")
            return False
    
    def get_llm_response(self, user_message: str) -> Optional[str]:
        """
        LLMから応答を取得（プロンプト設定適用版）
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            LLMの応答テキスト
        """
        try:
            # 会話履歴を構築
            messages = [{"role": "system", "content": self.system_message}]
            
            # 過去の会話履歴を追加
            for history_item in self.conversation_history[-self.max_history_length:]:
                messages.append({"role": "user", "content": history_item["user"]})
                messages.append({"role": "assistant", "content": history_item["assistant"]})
            
            # 現在のユーザーメッセージを追加
            messages.append({"role": "user", "content": user_message})
            
            # プロンプト設定を適用してLLMに送信
            response = self.llm_client.chat_completion(
                messages=messages,
                model=self.llm_settings["model"],
                temperature=self.llm_settings["temperature"],
                max_tokens=self.llm_settings["max_tokens"]
            )
            
            if response and "choices" in response:
                ai_response = response["choices"][0]["message"]["content"]
                
                # 会話履歴に追加
                self.conversation_history.append({
                    "user": user_message,
                    "assistant": ai_response
                })
                
                # 履歴長制限
                if len(self.conversation_history) > self.max_history_length:
                    self.conversation_history = self.conversation_history[-self.max_history_length:]
                
                logger.info(f"LLM応答取得成功 (設定: {self.current_prompt_config}): {ai_response[:50]}...")
                return ai_response
            else:
                logger.error("LLMから有効な応答が得られませんでした")
                return None
                
        except Exception as e:
            logger.error(f"LLM応答取得エラー: {e}")
            return None
    
    def get_available_prompt_configurations(self) -> Dict[str, List[str]]:
        """利用可能なプロンプト設定一覧を取得"""
        try:
            configs = self.prompt_tuner.configs
            return {
                "system_messages": list(configs["system_messages"].keys()),
                "llm_settings": list(configs["llm_settings"].keys())
            }
        except Exception as e:
            logger.error(f"プロンプト設定一覧取得エラー: {e}")
            return {"system_messages": [], "llm_settings": []}
    
    def test_current_configuration(self, test_message: str) -> Dict[str, Any]:
        """現在の設定でテストを実行"""
        try:
            result = self.prompt_tuner.test_prompt_combination(
                system_message_name=self.current_prompt_config,
                llm_setting_name=self.current_prompt_config,
                user_message=test_message,
                scenario_name="current_config_test"
            )
            
            logger.info(f"設定テスト完了: {self.current_prompt_config}")
            return result
            
        except Exception as e:
            logger.error(f"設定テストエラー: {e}")
            return {
                "success": False,
                "error": str(e),
                "user_message": test_message
            }
    
    def optimize_for_scenario(self, scenario_name: str) -> bool:
        """特定のシナリオに最適化された設定に切り替え"""
        try:
            # テスト結果を分析
            analysis = self.prompt_tuner.analyze_results(scenario_name)
            
            if "error" in analysis or not analysis["best_performing_settings"]:
                logger.warning(f"シナリオ '{scenario_name}' の最適化データが不足しています")
                return False
            
            # 最高性能の設定を取得
            best_setting = analysis["best_performing_settings"][0][0]
            
            # 設定名を解析 (format: "system_message_name × llm_setting_name")
            if " × " in best_setting:
                sys_msg_name, llm_setting_name = best_setting.split(" × ", 1)
                
                # システムメッセージとLLM設定を個別に適用
                configs = self.prompt_tuner.configs
                if sys_msg_name in configs["system_messages"]:
                    self.system_message = configs["system_messages"][sys_msg_name]
                
                if llm_setting_name in configs["llm_settings"]:
                    self.llm_settings = configs["llm_settings"][llm_setting_name]
                
                logger.info(f"シナリオ '{scenario_name}' に最適化: {best_setting}")
                return True
            else:
                logger.error(f"設定名の解析に失敗: {best_setting}")
                return False
                
        except Exception as e:
            logger.error(f"シナリオ最適化エラー: {e}")
            return False
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """現在の設定の性能統計を取得"""
        try:
            # 現在の設定に関連するテスト結果を抽出
            current_setting_key = f"{self.current_prompt_config} × {self.current_prompt_config}"
            
            related_results = [
                result for result in self.prompt_tuner.test_results
                if f"{result['system_message_name']} × {result['llm_setting_name']}" == current_setting_key
            ]
            
            if not related_results:
                return {"error": "現在の設定に関するテスト結果がありません"}
            
            successful_results = [r for r in related_results if r["success"]]
            
            stats = {
                "configuration": current_setting_key,
                "total_tests": len(related_results),
                "successful_tests": len(successful_results),
                "success_rate_percent": len(successful_results) / len(related_results) * 100,
                "average_response_time": sum(r["response_time_seconds"] for r in successful_results) / len(successful_results) if successful_results else 0,
                "recent_tests": related_results[-5:]  # 最新5件
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"性能統計取得エラー: {e}")
            return {"error": str(e)}
    
    async def process_user_input_with_optimization(self, 
                                                   user_message: str, 
                                                   expression: str = "happy",
                                                   auto_optimize: bool = False,
                                                   scenario_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        ユーザー入力処理（自動最適化機能付き）
        
        Args:
            user_message: ユーザーメッセージ
            expression: 設定する表情
            auto_optimize: 自動最適化を有効にするか
            scenario_hint: シナリオのヒント（最適化用）
            
        Returns:
            処理結果辞書
        """
        # 自動最適化が有効な場合
        if auto_optimize and scenario_hint:
            logger.info(f"自動最適化を実行: {scenario_hint}")
            self.optimize_for_scenario(scenario_hint)
        
        # 通常の処理を実行
        return await self.process_user_input(user_message, expression)

# 使用例とテスト関数
async def test_advanced_controller():
    """AdvancedLLMFaceControllerのテスト"""
    print("🧪 AdvancedLLMFaceControllerテスト開始")
    
    # コントローラー初期化
    controller = AdvancedLLMFaceController(prompt_config_name="default")
    
    if not controller.is_initialized:
        print("❌ コントローラーの初期化に失敗")
        return
    
    # 利用可能な設定を確認
    available_configs = controller.get_available_prompt_configurations()
    print(f"📋 利用可能な設定: {available_configs}")
    
    # テストメッセージ
    test_messages = [
        "こんにちは！",
        "Pythonの基本的な使い方を教えてください",
        "短い物語を作ってください"
    ]
    
    # 各設定でテスト
    for sys_msg_name in available_configs["system_messages"][:3]:  # 最初の3つの設定をテスト
        print(f"\n🔧 設定切り替え: {sys_msg_name}")
        
        success = controller.switch_prompt_configuration(sys_msg_name)
        if not success:
            print(f"❌ 設定切り替え失敗: {sys_msg_name}")
            continue
        
        # テストメッセージで実行
        for message in test_messages[:1]:  # 簡略化のため1つのメッセージのみ
            print(f"📝 テスト: {message}")
            
            result = await controller.process_user_input_with_optimization(
                user_message=message,
                expression="happy",
                auto_optimize=False
            )
            
            if result["success"]:
                print(f"✅ 成功: {result['llm_response'][:100]}...")
            else:
                print(f"❌ 失敗: {result.get('error', '不明なエラー')}")
    
    # 性能統計を表示
    stats = controller.get_performance_stats()
    print(f"\n📊 現在の設定の性能統計: {stats}")
    
    # クリーンアップ
    controller.cleanup()
    print("\n🎉 テスト完了")

def main():
    """メイン関数"""
    print("🚀 Advanced LLMFaceController")
    print("=" * 50)
    
    # テスト実行
    asyncio.run(test_advanced_controller())

if __name__ == "__main__":
    main()