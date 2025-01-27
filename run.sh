#!/bin/bash

# Function to display error messages and exit
handle_error() {
  echo "❌ Error: $1"
  exit 1
}

# Validate input arguments
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <image_name> <tag> <config_name>"
  echo "Example: $0 bitvavo-scalper 0.1.0 top5_config"
  exit 1
fi

IMAGE=$1
TAG=$2
CONFIG=$3

echo "🚀 Starting Docker container '${IMAGE}:${TAG}' with config '${CONFIG}'..."

# Create Docker volume
VOLUME_NAME="${IMAGE}_volume"
echo "🔄 Creating Docker volume '${VOLUME_NAME}' (if not exists)..."
docker volume create "${VOLUME_NAME}" || handle_error "Failed to create Docker volume '${VOLUME_NAME}'."

# Run the Docker container
echo "🐳 Running Docker container '${IMAGE}_${TAG}_${CONFIG}'..."
docker run --restart=always --name "${IMAGE}_${TAG}_${CONFIG}" -d \
  -v "$(pwd)/config/bitvavo.json:/app/bitvavo.json" \
  -v "$(pwd)/config/slack.json:/app/slack.json" \
  -v "$(pwd)/config/:/app/config" \
  -v "${VOLUME_NAME}:/app/data" \
  "${IMAGE}:${TAG}" --config config/${CONFIG}.json|| handle_error "Failed to start Docker container '${IMAGE}_${TAG}_${CONFIG}'."

echo "✅ Docker container '${IMAGE}_${TAG}_${CONFIG}' is running successfully."