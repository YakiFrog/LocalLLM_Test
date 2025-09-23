#!/usr/bin/env python3
"""
Mistral モデルのテストスクリプト
"""

import asyncio
import sys
from main import LMStudioClient

async def test_mistral_model():
    """Mistralモデルのテスト"""
    print("=== Mistral Model Test ===")
    
    # LM Studio クライアント初期化
    client = LMStudioClient()
    
    # テストケース1: 基本的な会話
    print("\n1. 基本的な会話テスト")
    messages = [
        {"role": "system", "content": "あなたは親切で知的なAIアシスタント「シリウス」です。自然で親しみやすい日本語で答えてください。"},
        {"role": "user", "content": "こんにちは！今日はどんな日ですか？"}
    ]
    
    response = client.chat_completion(
        messages=messages,
        model="mistralai/magistral-small-2509",
        temperature=0.7,
        max_tokens=-1
    )
    
    if response and "choices" in response:
        print(f"AI応答: {response['choices'][0]['message']['content']}")
    else:
        print("エラー: 応答を取得できませんでした")
    
    # テストケース2: 韻を踏む応答（元のcurlと同じ）
    print("\n2. 韻を踏む応答テスト")
    messages = [
        {"role": "system", "content": "Always answer in rhymes. Today is Thursday"},
        {"role": "user", "content": "What day is it today?"}
    ]
    
    response = client.chat_completion(
        messages=messages,
        model="mistralai/magistral-small-2509",
        temperature=0.7,
        max_tokens=-1
    )
    
    if response and "choices" in response:
        print(f"AI応答: {response['choices'][0]['message']['content']}")
    else:
        print("エラー: 応答を取得できませんでした")
    
    # テストケース3: 創造性の高い応答
    print("\n3. 創造性テスト（高温度設定）")
    messages = [
        {"role": "system", "content": "あなたは創造的で想像力豊かなAIアシスタント「シリウス」です。"},
        {"role": "user", "content": "宇宙旅行について短い詩を作ってください"}
    ]
    
    response = client.chat_completion(
        messages=messages,
        model="mistralai/magistral-small-2509",
        temperature=0.9,
        max_tokens=200
    )
    
    if response and "choices" in response:
        print(f"AI応答: {response['choices'][0]['message']['content']}")
    else:
        print("エラー: 応答を取得できませんでした")
    
    # テストケース4: 正確性重視（低温度設定）
    print("\n4. 正確性テスト（低温度設定）")
    messages = [
        {"role": "system", "content": "あなたは正確で詳細な情報を提供するAIアシスタントです。"},
        {"role": "user", "content": "Pythonでリストを作成する方法を教えてください"}
    ]
    
    response = client.chat_completion(
        messages=messages,
        model="mistralai/magistral-small-2509",
        temperature=0.1,
        max_tokens=300
    )
    
    if response and "choices" in response:
        print(f"AI応答: {response['choices'][0]['message']['content']}")
    else:
        print("エラー: 応答を取得できませんでした")
    
    print("\n=== テスト完了 ===")

if __name__ == "__main__":
    asyncio.run(test_mistral_model())