import requests
import json

class LMStudioClient:
    def __init__(self, base_url="http://127.0.0.1:1234"):
        self.base_url = base_url
        self.api_url = f"{base_url}/v1/chat/completions"
    
    def chat_completion(self, messages, model="openai/gpt-oss-20b", temperature=0.7, max_tokens=-1, stream=False):
        """
        LMStudioのAPIを使用してチャット補完を実行
        
        Args:
            messages: メッセージのリスト [{"role": "user/system/assistant", "content": "テキスト"}]
            model: 使用するモデル名
            temperature: 創造性のパラメータ (0-1)
            max_tokens: 最大トークン数 (-1で無制限)
            stream: ストリーミングするかどうか
        
        Returns:
            APIレスポンス
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=payload)
            response.raise_for_status()  # HTTPエラーがあれば例外を発生
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"リクエストエラー: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSONデコードエラー: {e}")
            return None

    def simple_chat(self, user_message, system_message=None):
        """
        シンプルなチャット機能
        
        Args:
            user_message: ユーザーのメッセージ
            system_message: システムメッセージ（オプション）
        
        Returns:
            AIの応答テキスト
        """
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
        
        messages.append({"role": "user", "content": user_message})
        
        response = self.chat_completion(messages)
        
        if response and "choices" in response:
            return response["choices"][0]["message"]["content"]
        else:
            return "エラー: 応答を取得できませんでした"

def main():
    # LMStudioクライアントを初期化
    client = LMStudioClient()
    
    # # 例1: 提供されたcurlコマンドと同じリクエスト
    # print("=== 例1: 韻を踏む応答 ===")
    # messages = [
    #     {"role": "system", "content": "Always answer in rhymes. Today is Thursday"},
    #     {"role": "user", "content": "What day is it today?"}
    # ]
    
    # response = client.chat_completion(messages)
    # if response:
    #     print("AI応答:")
    #     print(response["choices"][0]["message"]["content"])
    #     print()
    
    # # 例2: 日本語での会話
    # print("=== 例2: 日本語での会話 ===")
    # japanese_response = client.simple_chat(
    #     user_message="こんにちは！今日の天気について教えてください。",
    #     system_message="あなたは親切で丁寧な日本語のアシスタントです。"
    # )
    # print("AI応答:")
    # print(japanese_response)
    # print()
    
    # 例3: インタラクティブな会話
    print("=== インタラクティブな会話 ===")
    print("openai/gpt-oss-20bと会話を開始します。'quit'と入力して終了してください。")
    
    while True:
        user_input = input("\nあなた: ")
        if user_input.lower() in ['quit', 'exit', '終了']:
            break
        
        ai_response = client.simple_chat(user_input)
        print(f"AI: {ai_response}")

if __name__ == "__main__":
    main()