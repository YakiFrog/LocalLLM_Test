#!/usr/bin/env python3
"""
プロンプトシステムのテストスクリプト
"""

import asyncio
import sys
from llm_face_controller import LLMFaceController

async def test_prompt_system():
    """プロンプトシステムのテスト"""
    print("=== プロンプトシステムテスト ===")
    
    # コントローラー初期化
    controller = LLMFaceController()
    
    if not controller.is_initialized:
        print("エラー: コントローラーの初期化に失敗しました")
        return
    
    # 利用可能なプロンプト一覧を表示
    print("\n利用可能なプロンプト:")
    prompts = controller.get_available_prompts()
    for i, prompt in enumerate(prompts, 1):
        print(f"{i}. {prompt}")
    
    # 各プロンプトでテスト
    test_message = "こんにちは！今日はどんな日ですか？"
    
    for prompt_name in prompts[:3]:  # 最初の3つのプロンプトでテスト
        print(f"\n{'='*50}")
        print(f"プロンプト: {prompt_name}")
        print(f"{'='*50}")
        
        # プロンプトを設定
        controller.set_prompt(prompt_name)
        
        # 現在のシステムメッセージを表示
        print(f"システムメッセージ: {controller.system_message[:100]}...")
        
        # LLM応答を取得（音声は無効化）
        try:
            response = controller.get_llm_response(test_message)
            if response:
                print(f"AI応答: {response}")
            else:
                print("エラー: 応答を取得できませんでした")
        except Exception as e:
            print(f"エラー: {e}")
        
        print("\n" + "-"*30)
    
    # カスタムプロンプトのテスト
    print(f"\n{'='*50}")
    print("カスタムプロンプトテスト")
    print(f"{'='*50}")
    
    custom_prompt = "あなたは関西弁で話すAIアシスタント「シリウス」です。関西弁で親しみやすく返答してください。"
    
    # カスタムプロンプトを保存
    success = controller.save_prompt("kansai", custom_prompt)
    if success:
        print("カスタムプロンプト 'kansai' を保存しました")
        
        # カスタムプロンプトを適用
        controller.set_prompt("kansai")
        
        try:
            response = controller.get_llm_response("今日はええ天気やなあ")
            if response:
                print(f"AI応答（関西弁）: {response}")
            else:
                print("エラー: 応答を取得できませんでした")
        except Exception as e:
            print(f"エラー: {e}")
    else:
        print("カスタムプロンプトの保存に失敗しました")
    
    # クリーンアップ
    controller.cleanup()
    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    asyncio.run(test_prompt_system())