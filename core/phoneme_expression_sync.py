#!/usr/bin/env python3
"""
音韻ベース表情同期システム
AudioQueryの音韻データと表情タグを組み合わせて精密な同期を実現
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)

@dataclass
class PhonemeSegment:
    """音韻セグメント"""
    phoneme: str
    start_time: float
    end_time: float

@dataclass
class SyncedExpressionSegment:
    """同期済み表情セグメント"""
    text: str
    expression: str
    start_time: float
    end_time: float
    phoneme_segments: List[PhonemeSegment]

class PhonemeBasedExpressionSync:
    """音韻ベース表情同期クラス"""
    
    def __init__(self, expression_controller, voice_controller):
        self.expression_controller = expression_controller
        self.voice_controller = voice_controller
        self.current_expression = "neutral"
        self.is_playing = False
    
    async def create_synced_segments(self, tagged_text: str, audioquery_data: Dict) -> List[SyncedExpressionSegment]:
        """
        表情タグ付きテキストとAudioQueryデータから同期セグメントを作成
        
        Args:
            tagged_text: 表情タグ付きテキスト
            audioquery_data: AudioQueryから取得した音韻データ
            
        Returns:
            同期済み表情セグメントのリスト
        """
        try:
            from expression_parser import ExpressionParser
            parser = ExpressionParser()
            
            # 表情セグメントを解析
            expression_segments = parser.parse_expression_text(tagged_text)
            clean_text = parser.remove_expression_tags(tagged_text)
            
            # AudioQueryから音韻データを取得
            accent_phrases = audioquery_data.get('accent_phrases', [])
            phoneme_data = self._extract_phoneme_timing(accent_phrases)
            
            # 文字位置と音韻タイミングをマッピング
            synced_segments = self._map_expression_to_phonemes(
                expression_segments, phoneme_data, clean_text
            )
            
            return synced_segments
            
        except Exception as e:
            logger.error(f"同期セグメント作成エラー: {e}")
            return []
    
    def _extract_phoneme_timing(self, accent_phrases: List[Dict]) -> List[PhonemeSegment]:
        """アクセント句から音韻タイミングを抽出"""
        phoneme_segments = []
        current_time = 0.0
        
        for phrase in accent_phrases:
            moras = phrase.get('moras', [])
            
            for mora in moras:
                consonant = mora.get('consonant')
                vowel = mora.get('vowel')
                consonant_length = mora.get('consonant_length', 0.0)
                vowel_length = mora.get('vowel_length', 0.0)
                
                if consonant:
                    phoneme_segments.append(PhonemeSegment(
                        phoneme=consonant,
                        start_time=current_time,
                        end_time=current_time + consonant_length
                    ))
                    current_time += consonant_length
                
                if vowel:
                    phoneme_segments.append(PhonemeSegment(
                        phoneme=vowel,
                        start_time=current_time,
                        end_time=current_time + vowel_length
                    ))
                    current_time += vowel_length
            
            # ポーズ時間
            pause_length = phrase.get('pause_mora', {}).get('vowel_length', 0.0)
            if pause_length > 0:
                phoneme_segments.append(PhonemeSegment(
                    phoneme='pau',
                    start_time=current_time,
                    end_time=current_time + pause_length
                ))
                current_time += pause_length
        
        return phoneme_segments
    
    def _map_expression_to_phonemes(self, expression_segments, phoneme_segments, clean_text) -> List[SyncedExpressionSegment]:
        """表情セグメントと音韻セグメントをマッピング"""
        synced_segments = []
        
        # 文字位置から時間位置への変換比率を計算
        total_chars = len(clean_text)
        total_time = phoneme_segments[-1].end_time if phoneme_segments else 1.0
        char_to_time_ratio = total_time / total_chars if total_chars > 0 else 0.1
        
        for expr_seg in expression_segments:
            # 文字位置を時間に変換（簡易的）
            start_time = expr_seg.start_pos * char_to_time_ratio
            end_time = expr_seg.end_pos * char_to_time_ratio
            
            # 該当する音韻セグメントを取得
            related_phonemes = [
                p for p in phoneme_segments 
                if p.start_time < end_time and p.end_time > start_time
            ]
            
            synced_segments.append(SyncedExpressionSegment(
                text=expr_seg.text,
                expression=expr_seg.expression,
                start_time=start_time,
                end_time=end_time,
                phoneme_segments=related_phonemes
            ))
        
        return synced_segments
    
    async def play_with_precise_sync(self, synced_segments: List[SyncedExpressionSegment], audio_file_path: str) -> bool:
        """
        同期済みセグメントで精密同期再生
        
        Args:
            synced_segments: 同期済み表情セグメント
            audio_file_path: 音声ファイルパス
            
        Returns:
            成功/失敗
        """
        try:
            self.is_playing = True
            
            # 音声再生開始
            audio_task = asyncio.create_task(self._play_audio(audio_file_path))
            
            # 表情制御タスク
            expression_task = asyncio.create_task(
                self._control_expressions_precise(synced_segments)
            )
            
            # 両方のタスクを並行実行
            audio_result, expression_result = await asyncio.gather(
                audio_task, expression_task, return_exceptions=True
            )
            
            # 結果チェック
            if isinstance(audio_result, Exception):
                logger.error(f"音声再生エラー: {audio_result}")
                return False
            
            if isinstance(expression_result, Exception):
                logger.error(f"表情制御エラー: {expression_result}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"精密同期再生エラー: {e}")
            return False
        finally:
            self.is_playing = False
    
    async def _control_expressions_precise(self, synced_segments: List[SyncedExpressionSegment]):
        """精密な表情制御"""
        start_time = asyncio.get_event_loop().time()
        
        for segment in synced_segments:
            if not self.is_playing:
                break
            
            # セグメント開始まで待機
            current_time = asyncio.get_event_loop().time() - start_time
            wait_time = segment.start_time - current_time
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            # 表情変更
            await self._set_expression(segment.expression)
            
            logger.info(f"精密同期 - {segment.start_time:.2f}s: '{segment.text}' -> {segment.expression}")
    
    async def _play_audio(self, audio_file_path: str):
        """音声ファイル再生"""
        # 実際の実装では、適切な音声再生ライブラリを使用
        # ここでは簡易的な実装
        if hasattr(self.voice_controller, 'play_audio_file'):
            await self.voice_controller.play_audio_file(audio_file_path)
        else:
            # フォールバック: ファイルサイズから再生時間を推定
            import os
            file_size = os.path.getsize(audio_file_path) if os.path.exists(audio_file_path) else 100000
            estimated_duration = file_size / 16000  # 16kHz想定での簡易計算
            await asyncio.sleep(estimated_duration)
    
    async def _set_expression(self, expression: str):
        """表情設定"""
        if expression != self.current_expression:
            try:
                if hasattr(self.expression_controller, 'set_expression'):
                    result = self.expression_controller.set_expression(expression)
                    if result:
                        self.current_expression = expression
                        logger.info(f"🎭 精密表情変更: {expression}")
            except Exception as e:
                logger.error(f"表情設定エラー: {e}")
    
    def stop_playback(self):
        """再生停止"""
        self.is_playing = False

# 使用例とテスト
async def test_phoneme_sync():
    """音韻同期テスト"""
    # モックデータ
    mock_audioquery = {
        "accent_phrases": [
            {
                "moras": [
                    {
                        "text": "コ",
                        "consonant": "k",
                        "consonant_length": 0.1,
                        "vowel": "o",
                        "vowel_length": 0.2
                    },
                    {
                        "text": "ン",
                        "consonant": None,
                        "consonant_length": 0.0,
                        "vowel": "N",
                        "vowel_length": 0.15
                    }
                ],
                "pause_mora": {"vowel_length": 0.1}
            }
        ]
    }
    
    # テストテキスト
    tagged_text = "<happy>こんにちは</happy>！<excited>今日は良い天気</excited>ですね。"
    
    # モックコントローラー
    class MockController:
        def set_expression(self, expr):
            print(f"🎭 表情: {expr}")
            return True
        
        async def play_audio_file(self, path):
            print(f"🎵 音声再生: {path}")
            await asyncio.sleep(2.0)  # 2秒のダミー再生
    
    mock_expr = MockController()
    mock_voice = MockController()
    
    sync_system = PhonemeBasedExpressionSync(mock_expr, mock_voice)
    
    # 同期セグメント作成
    synced_segments = await sync_system.create_synced_segments(tagged_text, mock_audioquery)
    
    print(f"同期セグメント数: {len(synced_segments)}")
    for i, seg in enumerate(synced_segments):
        print(f"  {i+1}: {seg.start_time:.2f}s-{seg.end_time:.2f}s '{seg.text}' -> {seg.expression}")
    
    # 精密同期再生テスト
    await sync_system.play_with_precise_sync(synced_segments, "dummy_audio.wav")

if __name__ == "__main__":
    asyncio.run(test_phoneme_sync())