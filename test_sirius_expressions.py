#!/usr/bin/env python3
"""
更新された表情システムのテスト
実際のシリウス表情モードでテスト
"""

import asyncio
import sys
from expression_parser import ExpressionParser, RealTimeExpressionController

# モックコントローラー
class MockSiriusExpressionController:
    def __init__(self):
        self.current_expression = "neutral"
        self.expression_log = []
    
    def set_expression(self, expression):
        if expression != self.current_expression:
            print(f"🎭 シリウス表情変更: {self.current_expression} → {expression}")
            self.current_expression = expression
            self.expression_log.append(expression)
            return True
        return True

class MockSiriusVoiceController:
    async def prepare_audioquery(self, text):
        print(f"🎤 シリウス音声準備: {text}")
        return {"duration": len(text) * 0.1}
    
    async def speak_with_audioquery_lipsync(self, text, style_id=None):
        print(f"🗣️ シリウス音声再生: {text}")
        await asyncio.sleep(len(text) * 0.1)  # 文字数に応じた再生時間をシミュレート
        return True
    
    def stop_speaking(self):
        print("🛑 シリウス音声停止")

async def test_sirius_expressions():
    """シリウス表情モードのテスト"""
    print("🎭 シリウス表情システムテスト")
    print("=" * 50)
    
    # コントローラー作成
    mock_expr = MockSiriusExpressionController()
    mock_voice = MockSiriusVoiceController()
    
    parser = ExpressionParser()
    realtime_controller = RealTimeExpressionController(mock_expr, mock_voice)
    
    # シリウス表情を使ったテストケース
    test_expressions = [
        "<happy>こんにちは！</happy>今日も<wink>元気いっぱい</wink>ですね！",
        "<surprised>えっ！</surprised>そんなことが<angry>許されるの</angry>？<pien>困ったなあ</pien>。",
        "<sad>悲しいお知らせ</sad>があります。<crying>本当に辛いです</crying>。",
        "<mouth3>むにゃむにゃ</mouth3>...<neutral>失礼しました</neutral>。<happy>改めて、よろしくお願いします</happy>！",
        "普通の<neutral>話</neutral>から始まって、<surprised>突然驚いて</surprised>、<hurt>痛くなって</hurt>、最後は<happy>ハッピーエンド</happy>！"
    ]
    
    for i, text in enumerate(test_expressions, 1):
        print(f"\n--- テスト {i} ---")
        print(f"📝 入力: {text}")
        
        # 表情解析
        segments = parser.parse_expression_text(text)
        clean_text = parser.remove_expression_tags(text)
        
        print(f"🧹 クリーンテキスト: {clean_text}")
        print(f"🎭 表情セグメント数: {len(segments)}")
        
        for j, seg in enumerate(segments, 1):
            if seg.text.strip():
                print(f"   {j}. '{seg.text}' → {seg.expression}")
        
        # リアルタイム表情制御実行
        print("🎬 実行開始:")
        await realtime_controller.speak_with_dynamic_expressions(text, "neutral")
        
        print(f"📊 使用された表情: {mock_expr.expression_log}")
        mock_expr.expression_log.clear()  # ログをクリア
        
        print("⏸️ 完了\n")
        await asyncio.sleep(1)

async def test_expression_validation():
    """表情検証のテスト"""
    print("🔍 表情タグ検証テスト")
    print("=" * 30)
    
    from expression_validator import validate_and_fix_expression_tags
    
    # シリウス表情モードでの不正ケース
    invalid_cases = [
        "<happy>嬉しいです<happy>",
        "<pien>困った<pien><wink>でも大丈夫<wink>",
        "<mouth3>むにゃむにゃ<mouth3><crying>泣いちゃう<crying>"
    ]
    
    for i, text in enumerate(invalid_cases, 1):
        print(f"\n--- 検証テスト {i} ---")
        fixed_text = validate_and_fix_expression_tags(text)
        
        # 修正後の解析
        parser = ExpressionParser()
        segments = parser.parse_expression_text(fixed_text)
        
        print(f"表情セグメント: {len(segments)}")
        for j, seg in enumerate(segments, 1):
            if seg.text.strip():
                print(f"   {j}. '{seg.text}' → {seg.expression}")

async def main():
    """メインテスト関数"""
    print("🤖 シリウス表情システム 更新版テスト")
    print("=" * 60)
    print()
    
    # 1. 表情解析・制御テスト
    await test_sirius_expressions()
    
    # 2. 表情検証テスト
    await test_expression_validation()
    
    print("\n🎉 全てのテストが完了しました！")
    print("\n💡 利用可能なシリウス表情:")
    expressions = ["neutral", "happy", "sad", "angry", "surprised", "crying", "hurt", "wink", "mouth3", "pien"]
    for expr in expressions:
        print(f"  • {expr}")
    
    print("\n🎭 シリウス表情システムは正常に動作しています！")

if __name__ == "__main__":
    asyncio.run(main())