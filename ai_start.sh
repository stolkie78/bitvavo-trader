#!/bin/bash
set -e

echo "🚀 Starting retrain_models.py first..."
python ai/retrain_models.py

echo "🤖 Starting AI Trader Bot..."
python bot/ai_trader.py