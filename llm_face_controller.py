#!/usr/bin/env python3
"""
LLM統合型シリウス音声・表情制御システム
ローカルLLM（LM Studio）とVOICEVOX AudioQuery音韻解析を統合
"""

import asyncio
import sys
import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

# LMStudioクライアントのインポート
sys.path.append('/Users/kotaniryota/NLAB/LocalLLM_Test')
from main import LMStudioClient

# AudioQuery音韻解析システムのインポート
sys.path.append('/Users/kotaniryota/NLAB/sirius_face_anim/python')
# voicevox_coreパッケージのパスを追加
sys.path.append('/Users/kotaniryota/NLAB/sirius_face_anim/python/lib/python3.13/site-packages')
from audioquery_phoneme import AudioQueryLipSyncSpeaker, TalkingModeController, ExpressionController

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMFaceController:
    """LLM統合型音声・表情制御システム"""
    
    def __init__(self, 
                 lm_studio_url="http://127.0.0.1:1234",
                 face_server_url="http://localhost:8080",
                 voicevox_config=None):
        """
        初期化
        
        Args:
            lm_studio_url: LM StudioのURL
            face_server_url: シリウス表情サーバーのURL
            voicevox_config: VOICEVOX設定辞書
        """
        # LMStudioクライアント初期化
        self.llm_client = LMStudioClient(base_url=lm_studio_url)
        
        # VOICEVOX設定のデフォルト値
        if voicevox_config is None:
            voicevox_config = {
                "voicevox_onnxruntime_path": "/Users/kotaniryota/NLAB/sirius_face_anim/python/voicevox_core/onnxruntime/lib/libvoicevox_onnxruntime.1.17.3.dylib",
                "open_jtalk_dict_dir": "/Users/kotaniryota/NLAB/sirius_face_anim/python/voicevox_core/dict/open_jtalk_dic_utf_8-1.11",
                "model_path": "/Users/kotaniryota/NLAB/sirius_face_anim/python/voicevox_core/models/vvms/13.vvm",
                "dialogue_file_path": "/Users/kotaniryota/NLAB/sirius_face_anim/python/dialogue_data.json"
            }
        
        self.voicevox_config = voicevox_config
        
        # AudioQuery音韻解析システム初期化
        try:
            self.voice_controller = AudioQueryLipSyncSpeaker(
                server_url=face_server_url,
                **voicevox_config
            )
            logger.info("✅ AudioQuery音韻解析システム初期化完了")
        except Exception as e:
            logger.error(f"❌ AudioQuery音韻解析システム初期化失敗: {e}")
            self.voice_controller = None
        
        # 表情制御クラス初期化
        try:
            self.expression_controller = ExpressionController(server_url=face_server_url)
            logger.info("✅ 表情制御システム初期化完了")
        except Exception as e:
            logger.error(f"❌ 表情制御システム初期化失敗: {e}")
            self.expression_controller = None
        
        # おしゃべりモード制御クラス初期化
        try:
            self.talking_mode_controller = TalkingModeController(server_url=face_server_url)
            logger.info("✅ おしゃべりモード制御システム初期化完了")
        except Exception as e:
            logger.error(f"❌ おしゃべりモード制御システム初期化失敗: {e}")
            self.talking_mode_controller = None
        
        # システム設定
        self.conversation_history = []  # 会話履歴
        self.max_history_length = 10    # 最大履歴保持数
        self.system_message = "あなたは親切で知的なAIアシスタント「シリウス」です。自然で親しみやすい日本語で答えてください。"
        
        # ステータス
        self.is_speaking = False
        self.is_initialized = True
    
    def set_system_message(self, message: str):
        """システムメッセージを設定"""
        self.system_message = message
        logger.info(f"システムメッセージを設定: {message[:50]}...")
    
    def clear_conversation_history(self):
        """会話履歴をクリア"""
        self.conversation_history = []
        logger.info("会話履歴をクリアしました")
    
    def get_llm_response(self, user_message: str) -> Optional[str]:
        """
        LLMから応答を取得
        
        Args:
            user_message: ユーザーメッセージ
            
        Returns:
            LLMの応答テキスト
        """
        try:
            # 会話履歴を構築
            messages = [{"role": "system", "content": self.system_message}]
            
            # 過去の会話履歴を追加
            for history_item in self.conversation_history[-self.max_history_length:]:
                messages.append({"role": "user", "content": history_item["user"]})
                messages.append({"role": "assistant", "content": history_item["assistant"]})
            
            # 現在のユーザーメッセージを追加
            messages.append({"role": "user", "content": user_message})
            
            # LLMに送信
            response = self.llm_client.chat_completion(messages)
            
            if response and "choices" in response:
                ai_response = response["choices"][0]["message"]["content"]
                
                # 会話履歴に追加
                self.conversation_history.append({
                    "user": user_message,
                    "assistant": ai_response
                })
                
                # 履歴長制限
                if len(self.conversation_history) > self.max_history_length:
                    self.conversation_history = self.conversation_history[-self.max_history_length:]
                
                logger.info(f"LLM応答取得成功: {ai_response[:50]}...")
                return ai_response
            else:
                logger.error("LLMから有効な応答が得られませんでした")
                return None
                
        except Exception as e:
            logger.error(f"LLM応答取得エラー: {e}")
            return None
    
    async def speak_with_lipsync(self, text: str, style_id: Optional[int] = None) -> bool:
        """
        AudioQuery音韻解析を使用して音声合成とリップシンクを実行
        
        Args:
            text: 話すテキスト
            style_id: 音声スタイルID
            
        Returns:
            成功/失敗
        """
        if not self.voice_controller:
            logger.error("音声制御システムが初期化されていません")
            return False
        
        if self.is_speaking:
            logger.warning("既に発話中です")
            return False
        
        try:
            self.is_speaking = True
            logger.info(f"音声合成開始: {text[:30]}...")
            
            # AudioQuery音韻解析による発話
            success = await self.voice_controller.speak_with_audioquery_lipsync(text, style_id)
            
            if success:
                logger.info("音声合成完了")
            else:
                logger.error("音声合成失敗")
            
            return success
            
        except Exception as e:
            logger.error(f"音声合成エラー: {e}")
            return False
        finally:
            self.is_speaking = False
    
    def set_expression(self, expression: str) -> bool:
        """
        表情を設定
        
        Args:
            expression: 表情名
            
        Returns:
            成功/失敗
        """
        if not self.expression_controller:
            logger.error("表情制御システムが初期化されていません")
            return False
        
        try:
            return self.expression_controller.set_expression(expression)
        except Exception as e:
            logger.error(f"表情設定エラー: {e}")
            return False
    
    async def process_user_input(self, user_message: str, expression: str = "happy") -> Dict[str, Any]:
        """
        ユーザー入力を処理してLLM応答と音声出力を実行
        
        Args:
            user_message: ユーザーメッセージ
            expression: 設定する表情
            
        Returns:
            処理結果辞書
        """
        result = {
            "success": False,
            "user_message": user_message,
            "llm_response": None,
            "voice_success": False,
            "expression_success": False,
            "error": None
        }
        
        try:
            # 1. 表情設定
            if expression:
                result["expression_success"] = self.set_expression(expression)
            
            # 2. LLM応答取得
            logger.info(f"ユーザー入力処理開始: {user_message[:30]}...")
            llm_response = self.get_llm_response(user_message)
            
            if not llm_response:
                result["error"] = "LLMから応答を取得できませんでした"
                return result
            
            result["llm_response"] = llm_response
            
            # 3. 音声合成とリップシンク
            voice_success = await self.speak_with_lipsync(llm_response)
            result["voice_success"] = voice_success
            
            if voice_success:
                result["success"] = True
                logger.info("ユーザー入力処理完了")
            else:
                result["error"] = "音声合成に失敗しました"
            
        except Exception as e:
            error_msg = f"ユーザー入力処理エラー: {e}"
            logger.error(error_msg)
            result["error"] = error_msg
        
        return result
    
    def stop_speaking(self):
        """発話を停止"""
        if self.voice_controller:
            try:
                self.voice_controller.stop_speaking()
                logger.info("発話を停止しました")
            except Exception as e:
                logger.error(f"発話停止エラー: {e}")
        
        self.is_speaking = False
    
    def cleanup(self):
        """リソースのクリーンアップ"""
        try:
            if self.expression_controller:
                self.expression_controller.cleanup_session()
            
            if self.talking_mode_controller:
                self.talking_mode_controller.cleanup_session()
            
            logger.info("リソースのクリーンアップ完了")
        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")

# テスト用関数
async def test_llm_face_controller():
    """LLMFaceControllerのテスト"""
    controller = LLMFaceController()
    
    if not controller.is_initialized:
        logger.error("コントローラーの初期化に失敗しました")
        return
    
    # テストメッセージ
    test_message = "こんにちは！今日はどんな日ですか？"
    
    # 処理実行
    result = await controller.process_user_input(test_message, "happy")
    
    print(f"処理結果: {result}")
    
    # クリーンアップ
    controller.cleanup()

if __name__ == "__main__":
    asyncio.run(test_llm_face_controller())