#!/usr/bin/env python3
"""
表情タグ検証・修正スクリプト
LLMからの不正な表情タグを検出・修正する
"""

import re
import asyncio
from expression_parser import ExpressionParser

def validate_and_fix_expression_tags(text: str) -> str:
    """
    表情タグを検証・修正
    
    Args:
        text: 検証するテキスト
        
    Returns:
        修正されたテキスト
    """
    print(f"🔍 検証対象: {text}")
    
    # 不正なタグパターンを検出（例: <happy>text<happy>）
    invalid_pattern = re.compile(r'<(\w+)>(.*?)<\1>')
    
    # 正しいタグパターン（例: <happy>text</happy>）
    valid_pattern = re.compile(r'<(\w+)>(.*?)</\1>')
    
    # 修正処理
    fixed_text = text
    
    # 不正なタグを検出
    invalid_matches = invalid_pattern.findall(text)
    if invalid_matches:
        print(f"❌ 不正なタグを検出: {invalid_matches}")
        
        # 不正なタグを正しい形式に修正
        for tag, content in invalid_matches:
            invalid_format = f"<{tag}>{content}<{tag}>"
            correct_format = f"<{tag}>{content}</{tag}>"
            fixed_text = fixed_text.replace(invalid_format, correct_format)
            print(f"🔧 修正: {invalid_format} → {correct_format}")
    
    # 正しいタグを確認
    valid_matches = valid_pattern.findall(fixed_text)
    if valid_matches:
        print(f"✅ 正しいタグを確認: {valid_matches}")
    
    print(f"🎯 修正結果: {fixed_text}")
    return fixed_text

async def test_expression_parsing():
    """表情解析のテスト"""
    print("🧪 表情タグ解析テスト")
    print("=" * 50)
    
    parser = ExpressionParser()
    
    # テストケース（不正・正しい両方）
    test_cases = [
        # 不正なケース
        "<happy>こんにちは！きみは今日も元気ね？<happy>",
        "<excited>おはよう<excited>今日も<happy>いい日<happy>だね！",
        
        # 正しいケース
        "<happy>こんにちは！</happy>今日も<excited>元気</excited>ですね。",
        "普通のテキストです。",
        "<thinking>考え中</thinking>...<wink>わかった！</wink>"
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n--- テストケース {i} ---")
        
        # 検証・修正
        fixed_text = validate_and_fix_expression_tags(text)
        
        # パース結果確認
        segments = parser.parse_expression_text(fixed_text)
        clean_text = parser.remove_expression_tags(fixed_text)
        
        print(f"📝 クリーンテキスト: {clean_text}")
        print(f"🎭 セグメント数: {len(segments)}")
        for j, seg in enumerate(segments, 1):
            print(f"   {j}. '{seg.text}' → {seg.expression}")

def create_expression_validator():
    """表情タグバリデーター関数を作成"""
    
    def validate_llm_response(response: str) -> str:
        """LLM応答の表情タグを検証・修正"""
        return validate_and_fix_expression_tags(response)
    
    return validate_llm_response

if __name__ == "__main__":
    asyncio.run(test_expression_parsing())