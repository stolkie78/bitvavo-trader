#!/bin/bash

# Function to display error messages and exit
handle_error() {
    echo "❌ Error: $1"
    exit 1
}

# Validate input arguments
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <type hodl or trader> <tag>"
    exit 1
fi

TYPE=$1
TAG=$2
IMAGE=bitvavo-${TYPE}

echo "🚀 Starting build process for Docker image '${IMAGE}:${TAG}'..."
git checkout main
# Update Git repository
echo "🔄 Pulling latest changes..."
git pull || handle_error "Failed to pull latest changes."
git fetch -a || handle_error "Failed to fetch all references."
git checkout "${TAG}" || handle_error "Failed to checkout branch or tag '${TAG}'."

# Build Docker image
echo "🐳 Building Docker image '${IMAGE}:${TAG}'..."
docker build -t "${IMAGE}:${TAG}" --file Dockerfile_${TYPE} . --no-cache || handle_error "Docker build failed."

echo "✅ Successfully built Docker image '${IMAGE}:${TAG}'."