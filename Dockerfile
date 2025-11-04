FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04
#
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_PREFER_BINARY=1
ENV CMAKE_BUILD_PARALLEL_LEVEL=8
ENV FORCE_CUDA=1
ENV MODEL_CACHE_DIR=/opt/models
ENV TEMP_DIR=/tmp/video_processing

RUN apt-get update && apt-get install -y \
    python3.10 python3-pip python3-dev git git-lfs wget ffmpeg libgl1 libglib2.0-0 \
    build-essential gcc g++ make cmake ninja-build \
    && ln -sf /usr/bin/python3.10 /usr/bin/python \
    && ln -sf /usr/bin/pip3 /usr/bin/pip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN git lfs install

RUN pip install --no-cache-dir --upgrade pip setuptools wheel packaging
RUN pip install --no-cache-dir \
    torch==2.4.0+cu118 \
    torchvision==0.19.0+cu118 \
    --index-url https://download.pytorch.org/whl/cu118

WORKDIR /opt
RUN git clone https://github.com/Wan-Video/Wan2.2.git wan22
WORKDIR /opt/wan22

RUN pip install --no-cache-dir \
    torchaudio \
    "opencv-python>=4.9.0.80" \
    "diffusers>=0.31.0" \
    "transformers>=4.49.0,<=4.51.3" \
    "tokenizers>=0.20.3" \
    "accelerate>=1.1.1" \
    tqdm \
    "imageio[ffmpeg]" \
    easydict \
    ftfy \
    dashscope \
    imageio-ffmpeg \
    "numpy>=1.23.5,<2" \
    einops

RUN pip install --no-cache-dir flash_attn || echo "flash_attn installation failed, continuing without it (optional)"

RUN pip install --no-cache-dir "huggingface_hub"

WORKDIR /opt/models
RUN git lfs install --skip-smudge && \
    git clone https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B wan22-ti2v-5b && \
    cd wan22-ti2v-5b && \
    git lfs pull && \
    git lfs checkout

WORKDIR /opt/app
COPY src/ ./src/
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /opt/app/output

CMD ["python", "-u", "src/handler.py"]