#!/usr/bin/env python3
"""
リアルタイム表情解析システム
LLMからの応答にタグが含まれている場合、リアルタイムで表情を切り替える
"""

import re
import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ExpressionSegment:
    """表情セグメント"""
    text: str
    expression: str
    start_pos: int
    end_pos: int

class ExpressionParser:
    """表情タグ解析クラス"""
    
    def __init__(self):
        # 表情タグパターン（例: <happy>テキスト</happy>）
        self.expression_pattern = re.compile(r'<(\w+)>(.*?)</\1>', re.DOTALL)
        
        # 対応表情リスト（シリウス表情モード）
        self.valid_expressions = {
            'neutral', 'happy', 'sad', 'angry', 'surprised', 
            'crying', 'hurt', 'wink', 'mouth3', 'pien'
        }
    
    def parse_expression_text(self, text: str) -> List[ExpressionSegment]:
        """
        表情タグ付きテキストを解析してセグメントに分割
        
        Args:
            text: 解析するテキスト
            
        Returns:
            ExpressionSegmentのリスト
        """
        segments = []
        current_pos = 0
        
        for match in self.expression_pattern.finditer(text):
            expression = match.group(1).lower()
            content = match.group(2)
            start = match.start()
            end = match.end()
            
            # タグの前のテキスト（通常の表情）
            if start > current_pos:
                before_text = text[current_pos:start]
                if before_text.strip():
                    segments.append(ExpressionSegment(
                        text=before_text,
                        expression='neutral',
                        start_pos=current_pos,
                        end_pos=start
                    ))
            
            # 表情タグ内のテキスト
            if expression in self.valid_expressions:
                segments.append(ExpressionSegment(
                    text=content,
                    expression=expression,
                    start_pos=start,
                    end_pos=end
                ))
            else:
                # 不正な表情タグは通常テキストとして扱う
                segments.append(ExpressionSegment(
                    text=match.group(0),
                    expression='neutral',
                    start_pos=start,
                    end_pos=end
                ))
            
            current_pos = end
        
        # 残りのテキスト
        if current_pos < len(text):
            remaining_text = text[current_pos:]
            if remaining_text.strip():
                segments.append(ExpressionSegment(
                    text=remaining_text,
                    expression='neutral',
                    start_pos=current_pos,
                    end_pos=len(text)
                ))
        
        return segments
    
    def remove_expression_tags(self, text: str) -> str:
        """表情タグを除去してプレーンテキストを取得"""
        return self.expression_pattern.sub(r'\2', text)

class RealTimeExpressionController:
    """リアルタイム表情制御クラス"""
    
    def __init__(self, expression_controller, voice_controller):
        self.expression_controller = expression_controller
        self.voice_controller = voice_controller
        self.parser = ExpressionParser()
        self.current_expression = "neutral"
        self.is_playing = False
    
    async def speak_with_dynamic_expressions(self, tagged_text: str, base_expression: str = "neutral") -> bool:
        """
        表情タグ付きテキストを解析してリアルタイム表情切り替えで発話
        
        Args:
            tagged_text: 表情タグ付きテキスト
            base_expression: ベースとなる表情
            
        Returns:
            成功/失敗
        """
        try:
            self.is_playing = True
            
            # テキストを解析
            segments = self.parser.parse_expression_text(tagged_text)
            clean_text = self.parser.remove_expression_tags(tagged_text)
            
            logger.info(f"表情セグメント数: {len(segments)}")
            for i, segment in enumerate(segments):
                logger.info(f"  セグメント{i+1}: '{segment.text}' -> {segment.expression}")
            
            # ベース表情に設定
            await self._set_expression(base_expression)
            
            # 音声合成の準備
            if hasattr(self.voice_controller, 'prepare_audioquery'):
                audio_info = await self.voice_controller.prepare_audioquery(clean_text)
                if not audio_info:
                    logger.error("AudioQuery準備に失敗")
                    return False
            
            # セグメントごとに表情を切り替えながら再生
            await self._play_segments_with_expressions(segments, clean_text)
            
            # 最後にベース表情に戻す
            await self._set_expression(base_expression)
            
            return True
            
        except Exception as e:
            logger.error(f"動的表情発話エラー: {e}")
            return False
        finally:
            self.is_playing = False
    
    async def _play_segments_with_expressions(self, segments: List[ExpressionSegment], clean_text: str):
        """セグメントごとに表情を切り替えながら再生"""
        
        # 実際の音声合成を実行
        if hasattr(self.voice_controller, 'speak_with_audioquery_lipsync'):
            # 音声合成タスクを開始
            voice_task = asyncio.create_task(
                self.voice_controller.speak_with_audioquery_lipsync(clean_text)
            )
            
            # 表情制御タスクを開始
            expression_task = asyncio.create_task(
                self._control_expressions_with_timing(segments, clean_text)
            )
            
            # 両方のタスクを並行実行
            try:
                voice_result, _ = await asyncio.gather(voice_task, expression_task)
                return voice_result
            except Exception as e:
                logger.error(f"並行実行エラー: {e}")
                return False
        else:
            # フォールバック: シミュレーション
            return await self._simulate_playback_with_expressions(segments, clean_text)
    
    async def _control_expressions_with_timing(self, segments: List[ExpressionSegment], clean_text: str):
        """タイミング制御付き表情変更"""
        total_chars = len(clean_text)
        estimated_duration = total_chars * 0.15  # 1文字約150ms
        
        char_position = 0
        
        for segment in segments:
            if not self.is_playing:
                break
            
            # 表情切り替え
            await self._set_expression(segment.expression)
            
            # このセグメントの再生時間を計算
            segment_chars = len(segment.text.strip())
            if segment_chars > 0:
                segment_duration = segment_chars * 0.15
                
                logger.info(f"セグメント再生: '{segment.text}' ({segment.expression}) - {segment_duration:.1f}秒")
                
                # セグメント時間分待機
                await asyncio.sleep(segment_duration)
                
                char_position += segment_chars
    
    async def _simulate_playback_with_expressions(self, segments: List[ExpressionSegment], clean_text: str):
        """シミュレーション用の再生"""
        for segment in segments:
            if not self.is_playing:
                break
            
            # 表情切り替え
            await self._set_expression(segment.expression)
            
            # このセグメントの再生時間を計算
            segment_chars = len(segment.text.strip())
            if segment_chars > 0:
                segment_duration = segment_chars * 0.15
                
                logger.info(f"セグメント再生: '{segment.text}' ({segment.expression}) - {segment_duration:.1f}秒")
                
                # セグメント時間分待機
                await asyncio.sleep(segment_duration)
        
        return True
    
    async def _set_expression(self, expression: str):
        """表情を設定（非同期）"""
        if expression != self.current_expression:
            try:
                if hasattr(self.expression_controller, 'set_expression'):
                    result = self.expression_controller.set_expression(expression)
                    if result:
                        self.current_expression = expression
                        logger.info(f"表情変更: {expression}")
                    else:
                        logger.warning(f"表情変更失敗: {expression}")
            except Exception as e:
                logger.error(f"表情設定エラー: {e}")
    
    def stop_playback(self):
        """再生停止"""
        self.is_playing = False
        if hasattr(self.voice_controller, 'stop_speaking'):
            self.voice_controller.stop_speaking()

# テスト用の実装例
class MockExpressionController:
    """テスト用モック表情コントローラー"""
    
    def set_expression(self, expression: str) -> bool:
        print(f"🎭 表情変更: {expression}")
        return True

class MockVoiceController:
    """テスト用モック音声コントローラー"""
    
    async def prepare_audioquery(self, text: str):
        print(f"🎤 音声準備: {text}")
        return {"duration": len(text) * 0.15}
    
    def stop_speaking(self):
        print("🛑 音声停止")

# テスト関数
async def test_expression_parser():
    """表情解析のテスト"""
    parser = ExpressionParser()
    
    # テストケース
    test_texts = [
        "今日の天気は<happy>晴れ</happy>です！でも明日は<sad>雨</sad>かもしれません。",
        "<excited>おはようございます！</excited>今日も<happy>素敵な一日</happy>になりそうですね。",
        "普通のテキストです。",
        "<angry>これは怒ってます</angry>が、<neutral>落ち着いて</neutral>話しましょう。"
    ]
    
    for i, text in enumerate(test_texts, 1):
        print(f"\n--- テストケース {i} ---")
        print(f"元テキスト: {text}")
        
        segments = parser.parse_expression_text(text)
        clean_text = parser.remove_expression_tags(text)
        
        print(f"クリーンテキスト: {clean_text}")
        print("セグメント:")
        for j, seg in enumerate(segments):
            print(f"  {j+1}: '{seg.text}' -> {seg.expression}")

async def test_realtime_controller():
    """リアルタイム表情制御のテスト"""
    mock_expression = MockExpressionController()
    mock_voice = MockVoiceController()
    
    controller = RealTimeExpressionController(mock_expression, mock_voice)
    
    test_text = "<happy>こんにちは！</happy>今日は<excited>とても良い天気</excited>ですね。でも明日は<sad>雨</sad>の予報です。<thinking>傘を持って行った方が良いでしょう</thinking>。"
    
    print(f"\nテスト実行: {test_text}")
    await controller.speak_with_dynamic_expressions(test_text, "neutral")

if __name__ == "__main__":
    print("=== 表情パーサーテスト ===")
    asyncio.run(test_expression_parser())
    
    print("\n=== リアルタイム制御テスト ===")
    asyncio.run(test_realtime_controller())