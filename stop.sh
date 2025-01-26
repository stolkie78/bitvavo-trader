#!/bin/bash

# Controleer of er een parameter is opgegeven
if [ $# -eq 1 ]; then
    CONTAINER_NAME="$1"
    echo "Stopping container with name: $CONTAINER_NAME"
    docker ps -q --filter "name=^scalper-v2_${CONTAINER_NAME}$" | xargs -r docker rm -f
else
    echo "Stopping all containers with names starting with 'scalper-v2_'"
    docker ps -q --filter "name=^scalper-v2_" | xargs -r docker rm -f
fi

echo "Done."