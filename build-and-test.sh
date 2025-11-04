#!/bin/bash

set -eox pipefail

echo "🚀 Building wan22 container locally"

if ! nvidia-smi > /dev/null 2>&1; then
    echo "⚠️  No GPU detected. Build will still work, but testing requires GPU."
else
    echo "✅ GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
fi

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build the container
echo "🔨 Building Docker container..."
docker build -t wan22:local .

echo "✅ Container built successfully as 'wan22:local'"
echo ""
echo "To test locally, you can run:"
echo "  docker run --gpus all --rm -it wan22:local"
echo ""
echo "To test with RunPod handler:"
echo "  docker run --gpus all --rm -e RUNPOD_POD_ID=test wan22:local"

