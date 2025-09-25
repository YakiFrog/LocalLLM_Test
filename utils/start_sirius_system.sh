#!/bin/bash
# シリウス統合システム起動スクリプト

# LocalLLM_Testディレクトリに移動
cd /Users/kotaniryota/NLAB/LocalLLM_Test

# Python仮想環境をアクティベート
source bin/activate

# 統合起動スクリプトを実行
echo "🎭 シリウス統合システムを起動中..."
python utils/launch_sirius_system.py