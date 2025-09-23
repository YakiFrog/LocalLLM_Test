#!/usr/bin/env python3
"""
プロンプトチューニング機能
LLMのシステムメッセージや設定をテストおよび調整するためのツール
"""

import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import datetime

from main import LMStudioClient

class PromptTuner:
    """プロンプトチューニングクラス"""
    
    def __init__(self, base_url="http://127.0.0.1:1234"):
        """
        初期化
        
        Args:
            base_url: LM StudioのベースURL
        """
        self.client = LMStudioClient(base_url)
        self.config_file = Path("prompt_configs.json")
        self.test_results_file = Path("prompt_test_results.json")
        
        # 設定ファイルをロード
        self.configs = self.load_configs()
        
        # テスト結果履歴をロード
        self.test_results = self.load_test_results()
    
    def load_configs(self) -> Dict[str, Any]:
        """設定ファイルをロード"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # デフォルト設定を作成
            default_configs = {
                "system_messages": {
                    "default": "あなたは親切で知的なAIアシスタント「シリウス」です。自然で親しみやすい日本語で答えてください。",
                    "formal": "あなたは専門的で正確な情報を提供するAIアシスタント「シリウス」です。丁寧で詳細な日本語で回答してください。",
                    "casual": "あなたは親しみやすくフレンドリーなAIアシスタント「シリウス」です。くだけた日本語で楽しく会話してください。",
                    "technical": "あなたは技術的な専門知識を持つAIアシスタント「シリウス」です。正確で詳細な技術情報を提供してください。",
                    "creative": "あなたは創造的で想像力豊かなAIアシスタント「シリウス」です。アイデアやストーリーを考えるのが得意です。"
                },
                "llm_settings": {
                    "default": {
                        "model": "openai/gpt-oss-20b",
                        "temperature": 0.7,
                        "max_tokens": -1
                    },
                    "conservative": {
                        "model": "openai/gpt-oss-20b",
                        "temperature": 0.3,
                        "max_tokens": 500
                    },
                    "creative": {
                        "model": "openai/gpt-oss-20b",
                        "temperature": 0.9,
                        "max_tokens": 1000
                    },
                    "precise": {
                        "model": "openai/gpt-oss-20b",
                        "temperature": 0.1,
                        "max_tokens": 300
                    }
                },
                "test_scenarios": [
                    {
                        "name": "基本挨拶",
                        "user_message": "こんにちは！",
                        "expected_style": "親しみやすい挨拶"
                    },
                    {
                        "name": "技術質問",
                        "user_message": "Pythonの基本的な使い方を教えてください",
                        "expected_style": "技術的で正確な説明"
                    },
                    {
                        "name": "創作依頼",
                        "user_message": "短い物語を作ってください",
                        "expected_style": "創造的で魅力的な内容"
                    },
                    {
                        "name": "感情的な相談",
                        "user_message": "最近疲れていて元気が出ません",
                        "expected_style": "共感的で励ましのある返答"
                    }
                ]
            }
            self.save_configs(default_configs)
            return default_configs
    
    def save_configs(self, configs: Dict[str, Any]):
        """設定をファイルに保存"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)
        self.configs = configs
    
    def load_test_results(self) -> List[Dict[str, Any]]:
        """テスト結果履歴をロード"""
        if self.test_results_file.exists():
            with open(self.test_results_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def save_test_results(self):
        """テスト結果をファイルに保存"""
        with open(self.test_results_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
    
    def add_system_message(self, name: str, message: str):
        """新しいシステムメッセージを追加"""
        self.configs["system_messages"][name] = message
        self.save_configs(self.configs)
        print(f"✅ システムメッセージ '{name}' を追加しました")
    
    def add_llm_setting(self, name: str, model: str, temperature: float, max_tokens: int):
        """新しいLLM設定を追加"""
        self.configs["llm_settings"][name] = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        self.save_configs(self.configs)
        print(f"✅ LLM設定 '{name}' を追加しました")
    
    def test_prompt_combination(self, 
                               system_message_name: str, 
                               llm_setting_name: str, 
                               user_message: str,
                               scenario_name: str = "manual_test") -> Dict[str, Any]:
        """
        特定のプロンプト組み合わせをテスト
        
        Args:
            system_message_name: システムメッセージ名
            llm_setting_name: LLM設定名
            user_message: テスト用ユーザーメッセージ
            scenario_name: シナリオ名
            
        Returns:
            テスト結果
        """
        if system_message_name not in self.configs["system_messages"]:
            raise ValueError(f"システムメッセージ '{system_message_name}' が見つかりません")
        
        if llm_setting_name not in self.configs["llm_settings"]:
            raise ValueError(f"LLM設定 '{llm_setting_name}' が見つかりません")
        
        # 設定を取得
        system_message = self.configs["system_messages"][system_message_name]
        llm_setting = self.configs["llm_settings"][llm_setting_name]
        
        # メッセージを構築
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        # LLMに送信
        try:
            start_time = datetime.now()
            response = self.client.chat_completion(
                messages=messages,
                model=llm_setting["model"],
                temperature=llm_setting["temperature"],
                max_tokens=llm_setting["max_tokens"]
            )
            end_time = datetime.now()
            
            if response and "choices" in response:
                ai_response = response["choices"][0]["message"]["content"]
                
                # テスト結果を記録
                test_result = {
                    "timestamp": start_time.isoformat(),
                    "scenario_name": scenario_name,
                    "system_message_name": system_message_name,
                    "llm_setting_name": llm_setting_name,
                    "user_message": user_message,
                    "ai_response": ai_response,
                    "response_time_seconds": (end_time - start_time).total_seconds(),
                    "success": True,
                    "token_count": response.get("usage", {}).get("total_tokens", 0) if "usage" in response else 0
                }
                
                self.test_results.append(test_result)
                self.save_test_results()
                
                return test_result
            else:
                error_result = {
                    "timestamp": start_time.isoformat(),
                    "scenario_name": scenario_name,
                    "system_message_name": system_message_name,
                    "llm_setting_name": llm_setting_name,
                    "user_message": user_message,
                    "ai_response": None,
                    "response_time_seconds": (end_time - start_time).total_seconds(),
                    "success": False,
                    "error": "無効な応答"
                }
                
                self.test_results.append(error_result)
                self.save_test_results()
                
                return error_result
                
        except Exception as e:
            error_result = {
                "timestamp": datetime.now().isoformat(),
                "scenario_name": scenario_name,
                "system_message_name": system_message_name,
                "llm_setting_name": llm_setting_name,
                "user_message": user_message,
                "ai_response": None,
                "response_time_seconds": 0,
                "success": False,
                "error": str(e)
            }
            
            self.test_results.append(error_result)
            self.save_test_results()
            
            return error_result
    
    def run_full_test_suite(self) -> List[Dict[str, Any]]:
        """全テストシナリオを実行"""
        print("🚀 フルテストスイート開始...")
        
        results = []
        total_tests = len(self.configs["test_scenarios"]) * len(self.configs["system_messages"]) * len(self.configs["llm_settings"])
        current_test = 0
        
        for scenario in self.configs["test_scenarios"]:
            for sys_msg_name in self.configs["system_messages"]:
                for llm_setting_name in self.configs["llm_settings"]:
                    current_test += 1
                    print(f"📊 テスト {current_test}/{total_tests}: {scenario['name']} × {sys_msg_name} × {llm_setting_name}")
                    
                    result = self.test_prompt_combination(
                        system_message_name=sys_msg_name,
                        llm_setting_name=llm_setting_name,
                        user_message=scenario["user_message"],
                        scenario_name=scenario["name"]
                    )
                    
                    results.append(result)
                    
                    if result["success"]:
                        print(f"  ✅ 成功 ({result['response_time_seconds']:.2f}秒)")
                        print(f"  📝 応答: {result['ai_response'][:100]}...")
                    else:
                        print(f"  ❌ 失敗: {result.get('error', '不明なエラー')}")
                    
                    print()
        
        print(f"🎉 フルテストスイート完了！ {len(results)}件のテストを実行しました")
        return results
    
    def analyze_results(self, scenario_name: Optional[str] = None) -> Dict[str, Any]:
        """テスト結果を分析"""
        # フィルタリング
        if scenario_name:
            filtered_results = [r for r in self.test_results if r["scenario_name"] == scenario_name]
        else:
            filtered_results = self.test_results
        
        if not filtered_results:
            return {"error": "分析対象のテスト結果がありません"}
        
        # 成功率計算
        successful_results = [r for r in filtered_results if r["success"]]
        success_rate = len(successful_results) / len(filtered_results) * 100
        
        # 平均応答時間計算
        avg_response_time = sum(r["response_time_seconds"] for r in successful_results) / len(successful_results) if successful_results else 0
        
        # 設定別成功率
        setting_stats = {}
        for result in filtered_results:
            key = f"{result['system_message_name']} × {result['llm_setting_name']}"
            if key not in setting_stats:
                setting_stats[key] = {"total": 0, "success": 0}
            setting_stats[key]["total"] += 1
            if result["success"]:
                setting_stats[key]["success"] += 1
        
        # 成功率でソート
        sorted_settings = sorted(
            setting_stats.items(),
            key=lambda x: x[1]["success"] / x[1]["total"],
            reverse=True
        )
        
        analysis = {
            "total_tests": len(filtered_results),
            "successful_tests": len(successful_results),
            "success_rate_percent": success_rate,
            "average_response_time_seconds": avg_response_time,
            "best_performing_settings": sorted_settings[:5],
            "worst_performing_settings": sorted_settings[-5:] if len(sorted_settings) > 5 else []
        }
        
        return analysis
    
    def interactive_tuning(self):
        """インタラクティブなプロンプトチューニング"""
        print("🎛️  インタラクティブプロンプトチューニング開始")
        print("利用可能なコマンド:")
        print("  1. test - プロンプトをテスト")
        print("  2. add_system - システムメッセージを追加")
        print("  3. add_setting - LLM設定を追加")
        print("  4. run_suite - フルテストスイート実行")
        print("  5. analyze - 結果分析")
        print("  6. list - 設定一覧表示")
        print("  7. quit - 終了")
        print()
        
        while True:
            command = input("コマンドを入力してください: ").strip().lower()
            
            if command == "quit" or command == "q":
                break
            elif command == "test" or command == "1":
                self._interactive_test()
            elif command == "add_system" or command == "2":
                self._interactive_add_system_message()
            elif command == "add_setting" or command == "3":
                self._interactive_add_llm_setting()
            elif command == "run_suite" or command == "4":
                self.run_full_test_suite()
            elif command == "analyze" or command == "5":
                self._interactive_analyze()
            elif command == "list" or command == "6":
                self._list_configurations()
            else:
                print("❌ 無効なコマンドです")
    
    def _interactive_test(self):
        """インタラクティブテスト"""
        print("\n--- プロンプトテスト ---")
        
        # システムメッセージ選択
        print("利用可能なシステムメッセージ:")
        for name in self.configs["system_messages"]:
            print(f"  - {name}")
        sys_msg_name = input("システムメッセージ名を入力: ").strip()
        
        if sys_msg_name not in self.configs["system_messages"]:
            print(f"❌ システムメッセージ '{sys_msg_name}' が見つかりません")
            return
        
        # LLM設定選択
        print("利用可能なLLM設定:")
        for name in self.configs["llm_settings"]:
            print(f"  - {name}")
        llm_setting_name = input("LLM設定名を入力: ").strip()
        
        if llm_setting_name not in self.configs["llm_settings"]:
            print(f"❌ LLM設定 '{llm_setting_name}' が見つかりません")
            return
        
        # ユーザーメッセージ入力
        user_message = input("テスト用メッセージを入力: ").strip()
        
        if not user_message:
            print("❌ メッセージが入力されていません")
            return
        
        # テスト実行
        print("🔄 テスト実行中...")
        result = self.test_prompt_combination(sys_msg_name, llm_setting_name, user_message)
        
        if result["success"]:
            print(f"✅ テスト成功 ({result['response_time_seconds']:.2f}秒)")
            print(f"📝 AI応答:\n{result['ai_response']}")
        else:
            print(f"❌ テスト失敗: {result.get('error', '不明なエラー')}")
        print()
    
    def _interactive_add_system_message(self):
        """インタラクティブシステムメッセージ追加"""
        print("\n--- システムメッセージ追加 ---")
        
        name = input("メッセージ名を入力: ").strip()
        if not name:
            print("❌ 名前が入力されていません")
            return
        
        message = input("システムメッセージを入力: ").strip()
        if not message:
            print("❌ メッセージが入力されていません")
            return
        
        self.add_system_message(name, message)
        print()
    
    def _interactive_add_llm_setting(self):
        """インタラクティブLLM設定追加"""
        print("\n--- LLM設定追加 ---")
        
        name = input("設定名を入力: ").strip()
        if not name:
            print("❌ 名前が入力されていません")
            return
        
        model = input("モデル名を入力 (デフォルト: openai/gpt-oss-20b): ").strip()
        if not model:
            model = "openai/gpt-oss-20b"
        
        try:
            temperature = float(input("Temperature (0-1, デフォルト: 0.7): ").strip() or "0.7")
            max_tokens = int(input("最大トークン数 (-1で無制限, デフォルト: -1): ").strip() or "-1")
        except ValueError:
            print("❌ 数値の入力が不正です")
            return
        
        self.add_llm_setting(name, model, temperature, max_tokens)
        print()
    
    def _interactive_analyze(self):
        """インタラクティブ結果分析"""
        print("\n--- 結果分析 ---")
        
        scenario = input("分析対象シナリオ名 (空白で全体分析): ").strip()
        if not scenario:
            scenario = None
        
        analysis = self.analyze_results(scenario)
        
        if "error" in analysis:
            print(f"❌ {analysis['error']}")
            return
        
        print(f"📊 分析結果:")
        print(f"  総テスト数: {analysis['total_tests']}")
        print(f"  成功テスト数: {analysis['successful_tests']}")
        print(f"  成功率: {analysis['success_rate_percent']:.1f}%")
        print(f"  平均応答時間: {analysis['average_response_time_seconds']:.2f}秒")
        
        print(f"\n🏆 最高性能設定 (上位5位):")
        for i, (setting, stats) in enumerate(analysis['best_performing_settings'], 1):
            success_rate = stats['success'] / stats['total'] * 100
            print(f"  {i}. {setting}: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
        
        if analysis['worst_performing_settings']:
            print(f"\n⚠️  低性能設定 (下位5位):")
            for i, (setting, stats) in enumerate(analysis['worst_performing_settings'], 1):
                success_rate = stats['success'] / stats['total'] * 100
                print(f"  {i}. {setting}: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
        
        print()
    
    def _list_configurations(self):
        """設定一覧表示"""
        print("\n--- 設定一覧 ---")
        
        print("📝 システムメッセージ:")
        for name, message in self.configs["system_messages"].items():
            print(f"  - {name}: {message[:50]}...")
        
        print("\n⚙️  LLM設定:")
        for name, setting in self.configs["llm_settings"].items():
            print(f"  - {name}: model={setting['model']}, temp={setting['temperature']}, tokens={setting['max_tokens']}")
        
        print(f"\n🧪 テストシナリオ ({len(self.configs['test_scenarios'])}件):")
        for scenario in self.configs["test_scenarios"]:
            print(f"  - {scenario['name']}: {scenario['user_message'][:30]}...")
        
        print()

def main():
    """メイン関数"""
    print("🎛️  プロンプトチューニングツール")
    print("=" * 50)
    
    tuner = PromptTuner()
    tuner.interactive_tuning()
    
    print("👋 プロンプトチューニングツールを終了しました")

if __name__ == "__main__":
    main()