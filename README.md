# GPU Container Wan22 (TI2V-5B)

A RunPod serverless container for Wan2.2-TI2V-5B text-to-video and image-to-video generation.

## Model Information

This container uses the **Wan2.2-TI2V-5B** model, which:

- Supports both **Text-to-Video (T2V)** and **Image-to-Video (I2V)** generation
- Generates videos at **720P resolution** (1280×704 or 704×1280)
- Runs on single GPU with **24GB VRAM** (e.g., RTX 4090)
- Generates videos at 24fps (typically 5+ seconds in under 9 minutes)
- Uses high-compression Wan2.2-VAE for efficient generation

**Model Source**: [HuggingFace - Wan-AI/Wan2.2-TI2V-5B](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B)

## Architecture

```
Input (Text/Image) → Wan2.2-TI2V-5B Generator → Video Output → R2 Upload
```

## Usage

### Input Parameters

#### Text-to-Video (T2V)

```json
{
  "input": {
    "prompt": "Two anthropomorphic cats in comfy boxing gear and bright gloves fight intensely on a spotlighted stage",
    "task": "t2v",
    "width": 1280,
    "height": 704,
    "num_frames": 120,
    "steps": 10,
    "seed": 42
  }
}
```

#### Image-to-Video (I2V)

```json
{
  "input": {
    "prompt": "Summer beach vacation style, a white cat wearing sunglasses sits on a surfboard",
    "task": "i2v",
    "image_url": "https://example.com/image.jpg",
    "width": 1280,
    "height": 704,
    "num_frames": 120,
    "steps": 10,
    "seed": 42
  }
}
```

### Parameter Reference

| Parameter    | Type   | Required | Default | Description                            |
| ------------ | ------ | -------- | ------- | -------------------------------------- |
| `prompt`     | string | Yes      | -       | Text prompt for video generation       |
| `task`       | string | No       | `t2v`   | Generation task: `t2v` or `i2v`        |
| `image_url`  | string | No\*     | -       | URL of input image (required for I2V)  |
| `image_path` | string | No\*     | -       | Local path to image (required for I2V) |
| `width`      | int    | No       | 1280    | Video width (720P: 1280 or 704)        |
| `height`     | int    | No       | 704     | Video height (720P: 704 or 1280)       |
| `num_frames` | int    | No       | 120     | Number of frames (~5s at 24fps)        |
| `steps`      | int    | No       | 10      | Number of denoising steps              |
| `seed`       | int    | No       | None    | Random seed for generation             |

\*At least one image input method is required for I2V task.

### Output

```json
{
  "status": "success",
  "task": "t2v",
  "resolution": "1280x704",
  "num_frames": 120,
  "steps": 10,
  "download_url": "https://...presigned-url..."
}
```

## Building and Deployment

### Local Build

```bash
cd gpu-container-wan22
docker build -t wan22-ti2v-5b .
```

### RunPod Deployment

1. **Build and push** to your registry:

   ```bash
   docker build -t your-registry/wan22-ti2v-5b:latest .
   docker push your-registry/wan22-ti2v-5b:latest
   ```

2. **Create Serverless Endpoint**:
   - Container Image: `your-registry/wan22-ti2v-5b:latest`
   - GPU: RTX 4090 or equivalent (24GB+ VRAM)
   - Environment Variables:
     - `R2_BUCKET_NAME`: Cloudflare R2 bucket name
     - `R2_ENDPOINT_URL`: R2 S3 endpoint
     - `R2_ACCESS_KEY_ID`: R2 access key
     - `R2_SECRET_ACCESS_KEY`: R2 secret key
     - `R2_UPLOAD_DIRECTORY`: Upload directory prefix (default: `video-outputs`)
     - `R2_PRESIGNED_EXPIRY`: Presigned URL expiration (default: `86400`)

### Cloudflare R2 Uploads

This container can upload processed videos to Cloudflare R2 and return presigned URLs. Configure these environment variables on your RunPod endpoint:

- `R2_BUCKET_NAME`: Target R2 bucket name
- `R2_ENDPOINT_URL`: R2 S3 endpoint (`https://<account-id>.r2.cloudflarestorage.com`)
- `R2_ACCESS_KEY_ID`: R2 access key
- `R2_SECRET_ACCESS_KEY`: R2 secret key
- `R2_UPLOAD_DIRECTORY` (optional): Prefix for uploaded objects (default: `video-outputs`)
- `R2_PRESIGNED_EXPIRY` (optional): Expiration in seconds for presigned URL (default: `86400`)

## Technical Details

### Model Requirements

- **GPU Memory**: Minimum 24GB VRAM (RTX 4090 recommended)
- **Resolution**: 720P only (1280×704 or 704×1280)
- **Frame Rate**: 24fps
- **Model Size**: ~20GB (downloaded during build)

### Generation Time

- **5-second video**: ~9 minutes on RTX 4090
- **10-second video**: ~18 minutes on RTX 4090

## Example Usage

### Text-to-Video

```python
import requests

endpoint_url = "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run"
headers = {"Authorization": f"Bearer {YOUR_API_KEY}"}

payload = {
    "input": {
        "prompt": "A beautiful sunset over the ocean with waves crashing on the shore",
        "task": "t2v",
        "width": 1280,
        "height": 704,
        "num_frames": 120,
        "steps": 10
    }
}

response = requests.post(endpoint_url, json=payload, headers=headers)
print(response.json())
```

### Image-to-Video

```python
payload = {
    "input": {
        "prompt": "The cat starts walking and exploring the garden",
        "task": "i2v",
        "image_url": "https://example.com/cat.jpg",
        "width": 1280,
        "height": 704,
        "num_frames": 120,
        "steps": 10
    }
}

response = requests.post(endpoint_url, json=payload, headers=headers)
print(response.json())
```

## References

- [Wan2.2 GitHub](https://github.com/Wan-Video/Wan2.2)
- [Wan2.2-TI2V-5B HuggingFace](https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B)
