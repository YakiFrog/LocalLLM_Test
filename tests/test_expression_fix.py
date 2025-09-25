#!/usr/bin/env python3
"""
表情タグ修正テスト
問題のテキストを実際に修正してテスト
"""

from expression_validator import validate_and_fix_expression_tags
from expression_parser import ExpressionParser

def test_problem_text():
    """実際に問題となったテキストをテスト"""
    print("=== 問題のテキスト修正テスト ===")
    
    # 実際に問題となったテキスト
    problem_text = '<happy><excited>もちろん！</happy>\n<neutral>30日間、人が多くてビックリしたり<hurt>疲れたりも</hurt>したけど…<thinking><happy>全体的に楽しかったよ！</happy></thinking>\n<wink>特に、子どもたちが喜んでくれるのがうれしかったかな</wink>'
    
    print(f"元のテキスト:\n{problem_text}")
    print("\n" + "="*50)
    
    # 修正実行
    fixed_text = validate_and_fix_expression_tags(problem_text)
    
    print("\n" + "="*50)
    print(f"修正後のテキスト:\n{fixed_text}")
    
    # パーサーでセグメント解析
    parser = ExpressionParser()
    clean_text = parser.remove_expression_tags(fixed_text)
    segments = parser.parse_expression_text(fixed_text)
    
    print("\n" + "="*30)
    print(f"クリーンテキスト（読み上げ用）:\n{clean_text}")
    
    print(f"\n表情セグメント:")
    for i, seg in enumerate(segments, 1):
        print(f"  {i}. '{seg.text}' → {seg.expression}")

def test_various_cases():
    """様々なケースをテスト"""
    print("\n\n=== 様々なケースのテスト ===")
    
    test_cases = [
        "<thinking>考え中</thinking>普通のテキスト",
        "<excited>興奮！</excited><happy>嬉しい</happy>",
        "<happy>正しいタグ</happy>と<thinking>削除すべきタグ</thinking>",
        "<neutral>普通</neutral><excited>無効</excited><sad>悲しい</sad>",
    ]
    
    for i, test_text in enumerate(test_cases, 1):
        print(f"\n--- テストケース {i} ---")
        print(f"元: {test_text}")
        fixed = validate_and_fix_expression_tags(test_text)
        
        parser = ExpressionParser()
        clean = parser.remove_expression_tags(fixed)
        print(f"クリーン: {clean}")

if __name__ == "__main__":
    test_problem_text()
    test_various_cases()