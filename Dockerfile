FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_PREFER_BINARY=1
ENV PYTHONUNBUFFERED=1
ENV CMAKE_BUILD_PARALLEL_LEVEL=8
ENV PYTORCH_CUDA_ALLOC_CONF=backend:cudaMallocAsync
ENV MODEL_CACHE_DIR=/opt/models
ENV TEMP_DIR=/tmp/video_processing

# System dependencies
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip git wget ffmpeg libgl1 libglib2.0-0 \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

RUN pip install --default-timeout=100 --no-cache-dir \
    torch>=2.4.0 \
    torchvision \
    --extra-index-url https://download.pytorch.org/whl/cu118

# Clone Wan2.2 repository
WORKDIR /opt
RUN git clone https://github.com/Wan-Video/Wan2.2.git wan22
WORKDIR /opt/wan22

# Install Wan2.2 dependencies
RUN pip install --default-timeout=100 --no-cache-dir -r requirements.txt

# Install huggingface-cli for model download
RUN pip install --default-timeout=100 --no-cache-dir "huggingface_hub[cli]"

# Create model directory
RUN mkdir -p /opt/models/wan22-ti2v-5b

RUN huggingface-cli download Wan-AI/Wan2.2-TI2V-5B \
    --local-dir /opt/models/wan22-ti2v-5b \
    --local-dir-use-symlinks False

# Set working directory for application
WORKDIR /opt/app

# Copy application code
COPY src/ ./src/
COPY requirements.txt ./

# Install application dependencies
RUN pip install --default-timeout=100 --no-cache-dir -r requirements.txt

RUN mkdir -p /opt/app/output

# Set entrypoint
CMD ["python", "-u", "src/handler.py"]

