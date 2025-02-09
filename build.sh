#!/bin/bash

# Function to display error messages and exit
handle_error() {
    echo "❌ Error: $1"
    exit 1
}

# Validate input arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <image_name> <tag>"
    exit 1
fi

IMAGE=$1
TAG=$2

echo "🚀 Starting build process for Docker image '${IMAGE}:${TAG}'..."
git checkout main
# Update Git repository
echo "🔄 Pulling latest changes..."
git pull || handle_error "Failed to pull latest changes."
git fetch -a || handle_error "Failed to fetch all references."
git checkout "${TAG}" || handle_error "Failed to checkout branch or tag '${TAG}'."

# Build Docker image
echo "🐳 Building Docker image '${IMAGE}:${TAG}'..."
docker build -t "${IMAGE}:${TAG}" . --no-cache || handle_error "Docker build failed."

echo "✅ Successfully built Docker image '${IMAGE}:${TAG}'."