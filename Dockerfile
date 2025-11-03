# Base image with CUDA
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_PREFER_BINARY=1
ENV PYTHONUNBUFFERED=1
ENV CMAKE_BUILD_PARALLEL_LEVEL=8
ENV PYTORCH_CUDA_ALLOC_CONF=backend:cudaMallocAsync
ENV MODEL_CACHE_DIR=/opt/models
ENV TEMP_DIR=/tmp/video_processing

# System packages
RUN apt-get update && apt-get install -y \
    python3.10 python3-pip python3-dev git wget ffmpeg libgl1 libglib2.0-0 \
    build-essential gcc g++ make cmake \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && apt-get autoremove -y && apt-get clean -y && rm -rf /var/lib/apt/lists/*

# Upgrade pip and core build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel packaging


RUN pip install --no-cache-dir \
    torch==2.4.0+cu118 \
    torchvision==0.19.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

# Clone Wan repo (after torch is already installed)
WORKDIR /opt
RUN git clone https://github.com/Wan-Video/Wan2.2.git wan22
WORKDIR /opt/wan22

COPY requirements.txt /opt/wan22/requirements.txt

RUN grep -v "flash_attn" requirements.txt > _reqs.txt

RUN pip install --no-cache-dir -r _reqs.txt

RUN pip install --no-cache-dir flash-attn==2.8.3

RUN pip install --no-cache-dir "huggingface_hub[cli]"

# Download model
RUN mkdir -p /opt/models/wan22-ti2v-5b && \
    huggingface-cli download Wan-AI/Wan2.2-TI2V-5B \
    --local-dir /opt/models/wan22-ti2v-5b \
    --local-dir-use-symlinks False

# Application setup
WORKDIR /opt/app
COPY src/ ./src/
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /opt/app/output

CMD ["python", "-u", "src/handler.py"]