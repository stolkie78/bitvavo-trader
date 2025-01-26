#!/bin/bash
#
# Shell script to run a Docker container with a specified config
#
# Usage: ./run_$[IMAGE}.sh <config_name>
#
IMAGE=${1}
CONFIG=${2}
TAG=${3}

if [ -z "$CONFIG" <image> <config> <tag> ]; then
  echo "Usage: $0 <config_name>"
  exit 1
fi

echo "Running Docker container with configuration: $CONFIG"
docker volume create ${IMAGE}_volume

docker run --restart=always --name ${IMAGE}_${CONFIG} -d \
  -v $(pwd)/config/config.json:/app/config.json \
  -v $(pwd)/config/${CONFIG}.json:/app/${IMAGE}.json \
  -v $(pwd)/config/slack.json:/app/slack.json \
  -v $[IMAGE}_volume:/app/data \
  bitvavo-${IMAGE}:${TAG}
docker logs ${IMAGE}_${CONFIG}
