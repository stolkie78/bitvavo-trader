#!/bin/bash
#
# Shell script to run a Docker container with a specified config
#
# Usage: ./run_$[IMAGE}.sh <config_name>
#
IMAGE=${1}
TAG=${2}
CONFIG=${3}

docker volume create ${IMAGE}_volume

docker run --restart=always --name ${IMAGE}_${TAG}_${CONFIG} -d \
  -v $(pwd)/config/bitvavo.json:/app/bitvavo.json \
  -v $(pwd)/config/slack.json:/app/slack.json \
  -v $(pwd)/config/${CONFIG}.json:/config/scalper.json \
  -v ${IMAGE}_volume:/app/data \
  ${IMAGE}:${TAG}
