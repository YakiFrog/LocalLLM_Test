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
    
    # 有効な表情タグ
    valid_expressions = {
        'neutral', 'happy', 'sad', 'angry', 'surprised', 
        'crying', 'hurt', 'wink', 'mouth3', 'pien'
    }
    
    # 無効な表情タグ（削除対象）
    invalid_expressions = {
        'thinking', 'excited', 'confused', 'sleepy'
    }
    
    fixed_text = text
    
    # 1. 無効なタグを削除してコンテンツのみを残す
    for invalid_expr in invalid_expressions:
        # <thinking>...</thinking> 形式を削除
        invalid_pattern = re.compile(f'<{invalid_expr}>(.*?)</{invalid_expr}>', re.DOTALL)
        matches = invalid_pattern.findall(fixed_text)
        if matches:
            print(f"❌ 無効なタグを検出: <{invalid_expr}>...</{invalid_expr}>")
            fixed_text = invalid_pattern.sub(r'\1', fixed_text)
            print(f"🔧 削除: <{invalid_expr}>タグを除去してコンテンツのみを保持")
        
        # <thinking>...<thinking> 形式も削除
        malformed_pattern = re.compile(f'<{invalid_expr}>(.*?)<{invalid_expr}>', re.DOTALL)
        malformed_matches = malformed_pattern.findall(fixed_text)
        if malformed_matches:
            print(f"❌ 不正なタグを検出: <{invalid_expr}>...<{invalid_expr}>")
            fixed_text = malformed_pattern.sub(r'\1', fixed_text)
            print(f"🔧 修正: 不正なタグを除去")
        
        # 残った開始タグのみも削除（ネストケース対応）
        start_tag_pattern = re.compile(f'<{invalid_expr}>')
        if start_tag_pattern.search(fixed_text):
            print(f"❌ 残った開始タグを検出: <{invalid_expr}>")
            fixed_text = start_tag_pattern.sub('', fixed_text)
            print(f"🔧 削除: 開始タグのみを除去")
    
    # 2. 有効なタグの不正な形式を修正（<happy>text<happy> → <happy>text</happy>）
    for valid_expr in valid_expressions:
        # 不正なタグパターンを検出（例: <happy>text<happy>）
        invalid_pattern = re.compile(f'<{valid_expr}>(.*?)<{valid_expr}>')
        invalid_matches = invalid_pattern.findall(fixed_text)
        if invalid_matches:
            print(f"❌ 不正なタグを検出: <{valid_expr}>...<{valid_expr}>")
            
            # 不正なタグを正しい形式に修正
            for content in invalid_matches:
                invalid_format = f"<{valid_expr}>{content}<{valid_expr}>"
                correct_format = f"<{valid_expr}>{content}</{valid_expr}>"
                fixed_text = fixed_text.replace(invalid_format, correct_format)
                print(f"🔧 修正: {invalid_format} → {correct_format}")
    
    # 3. 正しいタグを確認
    valid_pattern = re.compile(r'<(\w+)>(.*?)</\1>')
    valid_matches = valid_pattern.findall(fixed_text)
    if valid_matches:
        valid_tags = [tag for tag, content in valid_matches if tag in valid_expressions]
        if valid_tags:
            print(f"✅ 正しいタグを確認: {valid_tags}")
    
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
        "<thinking>考え中</thinking>...<wink>わかった！</wink>",
        
        # 実際の問題ケース
        "<happy><excited>もちろん！</happy>\n<neutral>30日間、人が多くてビックリしたり<hurt>疲れたりも</hurt>したけど…<thinking><happy>全体的に楽しかったよ！</happy></thinking>\n<wink>特に、子どもたちが喜んでくれるのがうれしかったかな</wink>"
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