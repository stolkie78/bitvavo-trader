#!/bin/bash
IMAGE=${1}
TAG=${2}

git pull || exit 1
git fetch -a || exit 1
git checkout ${2}|| exit 1
docker build -t ${1}:${2} . --no-cache || exit 1
