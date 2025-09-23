#!/bin/bash
# シリウス統合システム起動スクリプト

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# Python仮想環境をアクティベート
source bin/activate

# 統合起動スクリプトを実行
echo "🎭 シリウス統合システムを起動中..."
python launch_sirius_system.py