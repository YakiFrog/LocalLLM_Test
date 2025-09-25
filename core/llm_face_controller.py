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
import time
from typing import Optional, Dict, Any
from pathlib import Path

# LMStudioクライアントのインポート
sys.path.append('/Users/kotaniryota/NLAB/LocalLLM_Test/core')
from main import LMStudioClient

# AudioQuery音韻解析システムのインポート
sys.path.append('/Users/kotaniryota/NLAB/sirius_face_anim/python')
# voicevox_coreパッケージのパスを追加
sys.path.append('/Users/kotaniryota/NLAB/sirius_face_anim/python/lib/python3.13/site-packages')
from audioquery_phoneme import AudioQueryLipSyncSpeaker, TalkingModeController, ExpressionController
from expression_parser import RealTimeExpressionController, ExpressionParser
from expression_validator import validate_and_fix_expression_tags

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMFaceController:
    """LLM統合型音声・表情制御システム"""
    
    def __init__(self, 
                 lm_studio_url="http://127.0.0.1:1234",
                 face_server_url="http://localhost:8080",
                 voicevox_config=None,
                 config_file="prompt_configs.json"):
        """
        初期化
        
        Args:
            lm_studio_url: LM StudioのURL
            face_server_url: シリウス表情サーバーのURL
            voicevox_config: VOICEVOX設定辞書
            config_file: 設定ファイルのパス
        """
        # 設定ファイル読み込み
        self.config = self.load_config(config_file)
        
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
        
        # リアルタイム表情制御クラス初期化
        try:
            self.realtime_expression_controller = RealTimeExpressionController(
                self.expression_controller, 
                self.voice_controller
            )
            logger.info("✅ リアルタイム表情制御システム初期化完了")
        except Exception as e:
            logger.error(f"❌ リアルタイム表情制御システム初期化失敗: {e}")
            self.realtime_expression_controller = None
        
        # 表情パーサー初期化
        self.expression_parser = ExpressionParser()
        
        # システム設定
        self.conversation_history = []  # 会話履歴
        self.max_history_length = 10    # 最大履歴保持数
        self.current_llm_setting = "mistral_default"  # デフォルトをMistralに変更
        self.prompts_dir = Path("prompts")  # プロンプトディレクトリ
        self.current_prompt = "default"  # 現在のプロンプト設定
        self.system_message = self.load_prompt(self.current_prompt)
        
        # ステータス
        self.is_speaking = False
        self.is_initialized = True
    
    def load_config(self, config_file: str) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        try:
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"設定ファイル読み込み完了: {config_file}")
                return config
            else:
                logger.warning(f"設定ファイルが見つかりません: {config_file}")
                return {}
        except Exception as e:
            logger.error(f"設定ファイル読み込みエラー: {e}")
            return {}
    
    def load_prompt(self, prompt_name: str) -> str:
        """プロンプトファイルを読み込み"""
        try:
            prompt_file = self.prompts_dir / f"{prompt_name}.txt"
            if prompt_file.exists():
                with open(prompt_file, 'r', encoding='utf-8') as f:
                    prompt = f.read().strip()
                logger.info(f"プロンプトファイル読み込み完了: {prompt_name}.txt")
                return prompt
            else:
                logger.warning(f"プロンプトファイルが見つかりません: {prompt_file}")
                # フォールバック: 設定ファイルから読み込み
                return self.config.get("system_messages", {}).get(prompt_name, 
                    "あなたは親切で知的なAIアシスタント「シリウス」です。自然で親しみやすい日本語で答えてください。")
        except Exception as e:
            logger.error(f"プロンプトファイル読み込みエラー: {e}")
            return "あなたは親切で知的なAIアシスタント「シリウス」です。自然で親しみやすい日本語で答えてください。"
    
    def get_available_prompts(self) -> list:
        """利用可能なプロンプト一覧を取得"""
        try:
            if not self.prompts_dir.exists():
                self.prompts_dir.mkdir(exist_ok=True)
                return ["default"]
            
            prompt_files = list(self.prompts_dir.glob("*.txt"))
            prompt_names = [f.stem for f in prompt_files]
            
            # 設定ファイルからも追加（後方互換性のため）
            config_prompts = list(self.config.get("system_messages", {}).keys())
            
            # 重複を除去してソート
            all_prompts = sorted(list(set(prompt_names + config_prompts)))
            return all_prompts if all_prompts else ["default"]
            
        except Exception as e:
            logger.error(f"プロンプト一覧取得エラー: {e}")
            return ["default"]
    
    def set_prompt(self, prompt_name: str):
        """プロンプトを変更"""
        try:
            new_prompt = self.load_prompt(prompt_name)
            self.system_message = new_prompt
            self.current_prompt = prompt_name
            logger.info(f"プロンプトを変更: {prompt_name}")
            logger.info(f"新しいシステムメッセージ: {new_prompt[:100]}...")
        except Exception as e:
            logger.error(f"プロンプト変更エラー: {e}")
    
    def save_prompt(self, prompt_name: str, prompt_content: str):
        """新しいプロンプトをファイルに保存"""
        try:
            if not self.prompts_dir.exists():
                self.prompts_dir.mkdir(exist_ok=True)
            
            prompt_file = self.prompts_dir / f"{prompt_name}.txt"
            with open(prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            
            logger.info(f"プロンプトファイル保存完了: {prompt_name}.txt")
            return True
            
        except Exception as e:
            logger.error(f"プロンプトファイル保存エラー: {e}")
            return False
    
    def set_llm_setting(self, setting_name: str):
        """LLM設定を変更"""
        if setting_name in self.config.get("llm_settings", {}):
            self.current_llm_setting = setting_name
            logger.info(f"LLM設定を変更: {setting_name}")
        else:
            logger.error(f"不明なLLM設定: {setting_name}")
    
    def get_available_llm_settings(self) -> list:
        """利用可能なLLM設定一覧を取得"""
        return list(self.config.get("llm_settings", {}).keys())
    
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
            # 現在のLLM設定を取得
            llm_setting = self.config.get("llm_settings", {}).get(self.current_llm_setting, {})
            model = llm_setting.get("model", "mistralai/magistral-small-2509")
            temperature = llm_setting.get("temperature", 0.7)
            max_tokens = llm_setting.get("max_tokens", -1)
            
            # 会話履歴を構築
            messages = [{"role": "system", "content": self.system_message}]
            
            # 過去の会話履歴を追加
            for history_item in self.conversation_history[-self.max_history_length:]:
                messages.append({"role": "user", "content": history_item["user"]})
                messages.append({"role": "assistant", "content": history_item["assistant"]})
            
            # 現在のユーザーメッセージを追加
            messages.append({"role": "user", "content": user_message})
            
            # LLMに送信（設定ファイルのパラメータを使用）
            response = self.llm_client.chat_completion(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if response and "choices" in response:
                ai_response = response["choices"][0]["message"]["content"]
                
                # 表情タグを検証・修正
                ai_response = validate_and_fix_expression_tags(ai_response)
                
                # 会話履歴に追加
                self.conversation_history.append({
                    "user": user_message,
                    "assistant": ai_response
                })
                
                # 履歴長制限
                if len(self.conversation_history) > self.max_history_length:
                    self.conversation_history = self.conversation_history[-self.max_history_length:]
                
                logger.info(f"LLM応答取得成功 (モデル: {model}): {ai_response[:50]}...")
                return ai_response
            else:
                logger.error("LLMから有効な応答が得られませんでした")
                return None
                
        except Exception as e:
            logger.error(f"LLM応答取得エラー: {e}")
            return None
    
    async def speak_with_lipsync(self, text: str, style_id: Optional[int] = None, enable_expression_parsing: bool = True) -> bool:
        """
        AudioQuery音韻解析を使用して音声合成とリップシンクを実行（高速化版）
        
        Args:
            text: 話すテキスト
            style_id: 音声スタイルID
            enable_expression_parsing: 表情タグ解析を有効にするか
            
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
            start_time = time.time()
            self.is_speaking = True
            logger.info(f"🚀 音声合成開始: {text[:30]}...")
            
            # 表情タグが含まれているかチェック
            if enable_expression_parsing and self.realtime_expression_controller:
                has_expression_tags = '<' in text and '>' in text and '</' in text
                
                if has_expression_tags:
                    logger.info("🎭 表情タグを検出、リアルタイム表情制御で発話します")
                    
                    # 表情タグを解析
                    segments = self.expression_parser.parse_expression_text(text)
                    clean_text = self.expression_parser.remove_expression_tags(text)
                    
                    logger.info(f"クリーンテキスト: {clean_text}")
                    logger.info(f"表情セグメント数: {len(segments)}")
                    
                    # ⚡ タイムアウト短縮（30→20秒）とキャンセレーション対応
                    try:
                        success = await asyncio.wait_for(
                            self.realtime_expression_controller.speak_with_dynamic_expressions(
                                text, "neutral"
                            ),
                            timeout=20.0  # 30→20秒に短縮
                        )
                    except asyncio.TimeoutError:
                        logger.error("❌ リアルタイム表情制御がタイムアウトしました（20秒）")
                        success = False
                else:
                    logger.info("🎵 表情タグなし、通常の発話を実行します")
                    # ⚡ タイムアウト短縮（20→15秒）
                    try:
                        success = await asyncio.wait_for(
                            self.voice_controller.speak_with_audioquery_lipsync(text, style_id),
                            timeout=15.0  # 20→15秒に短縮
                        )
                    except asyncio.TimeoutError:
                        logger.error("❌ 音声合成がタイムアウトしました（15秒）")
                        success = False
            else:
                # 通常のAudioQuery音韻解析による発話
                logger.info("🎵 通常の発話を実行します")
                # ⚡ タイムアウト短縮（20→15秒）
                try:
                    success = await asyncio.wait_for(
                        self.voice_controller.speak_with_audioquery_lipsync(text, style_id),
                        timeout=15.0  # 20→15秒に短縮
                    )
                except asyncio.TimeoutError:
                    logger.error("❌ 音声合成がタイムアウトしました（15秒）")
                    success = False
            
            elapsed_time = time.time() - start_time
            if success:
                logger.info(f"✅ 音声合成完了 ({elapsed_time:.2f}秒)")
            else:
                logger.error(f"❌ 音声合成失敗 ({elapsed_time:.2f}秒)")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 音声合成エラー: {e}")
            return False
        finally:
            self.is_speaking = False
            logger.debug("音声合成処理終了、is_speakingフラグをリセット")
    
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
            
            # 2. LLM応答取得（タイムアウト短縮: 30→20秒）
            logger.info(f"🤖 ユーザー入力処理開始: {user_message[:30]}...")
            try:
                # LLM応答取得を非同期化してタイムアウト処理
                loop = asyncio.get_event_loop()
                llm_response = await asyncio.wait_for(
                    loop.run_in_executor(None, self.get_llm_response, user_message),
                    timeout=20.0  # 30→20秒に短縮
                )
            except asyncio.TimeoutError:
                result["error"] = "LLM応答がタイムアウトしました（20秒）"
                logger.error("❌ LLM応答がタイムアウトしました（20秒）")
                return result
            
            if not llm_response:
                result["error"] = "LLMから応答を取得できませんでした"
                return result
            
            result["llm_response"] = llm_response
            
            # 3. 音声合成とリップシンク（既にタイムアウト処理済み）
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
        
        # リアルタイム表情制御も停止
        if self.realtime_expression_controller:
            try:
                self.realtime_expression_controller.stop_playback()
                logger.info("リアルタイム表情制御を停止しました")
            except Exception as e:
                logger.error(f"リアルタイム表情制御停止エラー: {e}")
        
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