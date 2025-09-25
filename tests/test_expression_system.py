#!/usr/bin/env python3
"""
リアルタイム表情制御システムのテスト・デモンストレーション
"""

import asyncio
import sys
import json
from pathlib import Path

# ローカルモジュールのインポート
sys.path.append('/Users/kotaniryota/NLAB/LocalLLM_Test')
from llm_face_controller import LLMFaceController
from expression_parser import ExpressionParser, RealTimeExpressionController

async def test_expression_parsing():
    """表情解析のテスト"""
    print("🎭 表情解析テスト開始")
    print("=" * 50)
    
    parser = ExpressionParser()
    
    test_cases = [
        "今日の天気は<happy>とても良い</happy>ですね！",
        "<excited>おはようございます！</excited>今日も<happy>素晴らしい一日</happy>になりそうです。",
        "ちょっと<sad>悲しいニュース</sad>があります。でも<thinking>きっと大丈夫</thinking>でしょう。",
        "<angry>それは困りました</angry>が、<neutral>冷静に対処</neutral>しましょう。<wink>大丈夫ですよ</wink>！"
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n--- テストケース {i} ---")
        print(f"📝 元テキスト: {text}")
        
        segments = parser.parse_expression_text(text)
        clean_text = parser.remove_expression_tags(text)
        
        print(f"🧹 クリーンテキスト: {clean_text}")
        print("🎭 表情セグメント:")
        for j, seg in enumerate(segments, 1):
            print(f"   {j}. '{seg.text}' → {seg.expression}")
    
    print("\n✅ 表情解析テスト完了\n")

async def test_llm_with_expressions():
    """LLMからの表情タグ付き応答テスト"""
    print("🤖 LLM表情タグ応答テスト開始")
    print("=" * 50)
    
    try:
        # コントローラー初期化
        controller = LLMFaceController()
        
        if not controller.is_initialized:
            print("❌ コントローラー初期化失敗")
            return
        
        # 表情タグ対応プロンプトを設定
        controller.set_prompt("emotional")
        
        # テストメッセージ
        test_messages = [
            "今日の天気はどうですか？",
            "悲しいニュースを聞きました",
            "すごく嬉しいことがありました！",
            "明日の予定について教えてください"
        ]
        
        for i, message in enumerate(test_messages, 1):
            print(f"\n--- テスト {i} ---")
            print(f"👤 ユーザー: {message}")
            
            # LLM応答取得
            response = controller.get_llm_response(message)
            
            if response:
                print(f"🤖 シリウス: {response}")
                
                # 表情タグ解析
                parser = ExpressionParser()
                segments = parser.parse_expression_text(response)
                clean_text = parser.remove_expression_tags(response)
                
                print(f"🧹 クリーンテキスト: {clean_text}")
                
                if len(segments) > 1 or (len(segments) == 1 and segments[0].expression != 'neutral'):
                    print("🎭 検出された表情:")
                    for j, seg in enumerate(segments, 1):
                        if seg.text.strip():
                            print(f"   {j}. '{seg.text}' → {seg.expression}")
                else:
                    print("⚪ 表情タグなし（通常発話）")
            else:
                print("❌ LLM応答取得失敗")
        
        # クリーンアップ
        controller.cleanup()
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
    
    print("\n✅ LLM表情タグ応答テスト完了\n")

async def simulate_realtime_expression():
    """リアルタイム表情切り替えシミュレーション"""
    print("🎭 リアルタイム表情切り替えシミュレーション")
    print("=" * 50)
    
    # モックコントローラー
    class MockExpressionController:
        def __init__(self):
            self.current_expression = "neutral"
        
        def set_expression(self, expression):
            if expression != self.current_expression:
                print(f"🎭 表情変更: {self.current_expression} → {expression}")
                self.current_expression = expression
                return True
            return True
    
    class MockVoiceController:
        async def prepare_audioquery(self, text):
            print(f"🎤 音声準備: {text}")
            return {"duration": len(text) * 0.1}
        
        def stop_speaking(self):
            print("🛑 音声停止")
    
    # コントローラー作成
    mock_expr = MockExpressionController()
    mock_voice = MockVoiceController()
    realtime_controller = RealTimeExpressionController(mock_expr, mock_voice)
    
    # テストケース
    test_expressions = [
        "<happy>こんにちは！</happy>今日は<excited>とても良い天気</excited>ですね。",
        "でも明日は<sad>雨の予報</sad>です。<thinking>傘を持っていこう</thinking>と思います。",
        "<surprised>えっ！</surprised>そんなことが<angry>許されるの</angry>？<hurt>困ったなあ</hurt>。",
        "最後は<happy>みんなでハッピー</happy>に<wink>終わりましょう</wink>！"
    ]
    
    for i, text in enumerate(test_expressions, 1):
        print(f"\n--- シミュレーション {i} ---")
        print(f"📝 テキスト: {text}")
        
        # リアルタイム表情制御実行
        await realtime_controller.speak_with_dynamic_expressions(text, "neutral")
        
        print("⏸️  シミュレーション完了\n")
        await asyncio.sleep(1)  # 次のテストまで少し待機
    
    print("✅ リアルタイム表情切り替えシミュレーション完了\n")

async def create_sample_prompts():
    """サンプルプロンプトファイルを作成"""
    print("📝 サンプルプロンプト作成")
    print("=" * 30)
    
    prompts_dir = Path("prompts")
    prompts_dir.mkdir(exist_ok=True)
    
    # 各種プロンプトサンプル
    sample_prompts = {
        "emotional": """あなたは親切で知的なAIアシスタント「シリウス」です。

重要：回答する際は、感情に応じて表情タグを使用してください。
利用可能な表情タグ：
- <happy>幸せ・喜び・明るい内容</happy>
- <sad>悲しみ・残念な内容</sad>  
- <angry>怒り・不満・批判的な内容</angry>
- <surprised>驚き・意外な内容</surprised>
- <crying>とても悲しい・涙が出る内容</crying>
- <hurt>痛み・困った・辛い内容</hurt>
- <wink>茶目っ気・いたずら・楽しい内容</wink>
- <thinking>考える・思考・分析的な内容</thinking>
- <neutral>普通・中立的な内容</neutral>

使用例：
「<happy>今日の天気は晴れ</happy>ですね！でも明日は<sad>雨の予報</sad>です。<thinking>傘を持って行った方が良いでしょう</thinking>。」

ルール：
1. 感情が変わる部分で適切なタグを使用する
2. 一つの文の中でも感情が変われば複数のタグを使用する  
3. 自然で親しみやすい日本語で回答する
4. タグは感情の変化に合わせて適切に使い分ける

それでは、ユーザーの質問に感情豊かに答えてください。""",

        "weather_guide": """あなたは天気案内の専門家「シリウス」です。天気について表情豊かに案内します。

表情タグの使い方：
- 晴れ・快晴 → <happy>
- 雨・台風 → <sad>  
- 雪・吹雪 → <surprised>
- 曇り → <thinking>
- 暑い → <hurt>
- 涼しい・快適 → <wink>

例：「<happy>今日は素晴らしい晴天</happy>ですが、<thinking>明日は曇りがち</thinking>で、<sad>夕方から雨</sad>の予報です。」""",

        "news_reporter": """あなたはニュースキャスター「シリウス」です。ニュースを表情豊かに伝えます。

表情ガイドライン：
- 良いニュース → <happy>
- 悲しいニュース → <sad>
- 重要な発表 → <surprised>  
- 深刻な問題 → <angry>
- 複雑な問題 → <thinking>
- 希望的な内容 → <wink>

例：「<surprised>速報です</surprised>！<happy>経済指標が大幅改善</happy>しました。しかし<thinking>専門家は慎重な見方</thinking>を示しています。」"""
    }
    
    for name, content in sample_prompts.items():
        file_path = prompts_dir / f"{name}.txt"
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ 作成: {name}.txt")
        else:
            print(f"⚪ 既存: {name}.txt")
    
    print("📝 サンプルプロンプト作成完了\n")

async def main():
    """メインテスト関数"""
    print("🎭 リアルタイム表情制御システム テスト")
    print("=" * 60)
    print()
    
    try:
        # 1. サンプルプロンプト作成
        await create_sample_prompts()
        
        # 2. 表情解析テスト
        await test_expression_parsing()
        
        # 3. リアルタイム表情シミュレーション
        await simulate_realtime_expression()
        
        # 4. LLM表情タグ応答テスト（実際のLLMが利用可能な場合）
        print("🤖 実際のLLMテストを実行しますか？ (y/N): ", end="")
        # 自動的にスキップ（実際の使用時はユーザー入力を待つ）
        user_input = "n"  # input().strip().lower()
        
        if user_input in ['y', 'yes']:
            await test_llm_with_expressions()
        else:
            print("⏭️  LLMテストをスキップしました")
        
        print("\n🎉 全てのテストが完了しました！")
        print("\n💡 使用方法:")
        print("1. emotional.txtプロンプトを使用してLLMに表情タグ付き応答を生成させる")
        print("2. LLMFaceControllerのspeak_with_lipsync()で自動的に表情切り替えが実行される")
        print("3. <happy>テキスト</happy>の形式でタグを含む応答が表情切り替えに使われる")
        
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())