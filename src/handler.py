import os
import json
import tempfile
import logging
import argparse
from typing import Dict, Any
from pathlib import Path
import uuid
import boto3
from botocore.config import Config as BotoConfig
from services.generator_service import Wan22Generator
from utils.cleanup_manager import CleanupManager
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and set default parameters."""
    validated = {}
    
    # Required
    if 'prompt' not in params or not params['prompt']:
        raise ValueError("'prompt' is required")
    validated['prompt'] = str(params['prompt'])
    
    # Optional with defaults
    validated['task'] = params.get('task', 't2v')
    if validated['task'] not in ['t2v', 'i2v']:
        raise ValueError(f"task must be 't2v' or 'i2v', got: {validated['task']}")
    
    validated['width'] = params.get('width', 1280)
    validated['height'] = params.get('height', 704)
    if not ((validated['width'] == 1280 and validated['height'] == 704) or 
            (validated['width'] == 704 and validated['height'] == 1280)):
        logger.warning(f"Resolution {validated['width']}x{validated['height']} is not standard 720P. Adjusting to 1280x704")
        validated['width'] = 1280
        validated['height'] = 704
    
    validated['num_frames'] = params.get('num_frames', 120)
    if not (1 <= validated['num_frames'] <= 300):
        raise ValueError(f"num_frames must be between 1 and 300, got: {validated['num_frames']}")
    
    validated['steps'] = params.get('steps', 10)
    if not (1 <= validated['steps'] <= 50):
        raise ValueError(f"steps must be between 1 and 50, got: {validated['steps']}")
    
    validated['seed'] = params.get('seed')
    
    # Image inputs for I2V
    validated['image_url'] = params.get('image_url')
    validated['image_path'] = params.get('image_path')
    
    if validated['task'] == 'i2v':
        provided = [validated['image_url'], validated['image_path']]
        provided = [p for p in provided if p]
        if len(provided) == 0:
            raise ValueError("For I2V task, provide one of 'image_url' or 'image_path'")
        if len(provided) > 1:
            raise ValueError("Provide only one of 'image_url' or 'image_path'")
    
    return validated


def download_input_image(image_url: str, temp_dir: Path) -> Path:
    """Download image from URL to temporary directory."""
    from urllib.parse import urlparse
    
    parsed = urlparse(image_url)
    file_ext = Path(parsed.path).suffix or '.jpg'
    input_path = temp_dir / f"input_image{file_ext}"
    
    logger.info(f"Downloading image from: {image_url}")
    
    try:
        response = requests.get(image_url, timeout=60, stream=True)
        response.raise_for_status()
        
        with open(input_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Image downloaded successfully: {input_path}")
        return input_path
    
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        raise RuntimeError(f"Image download failed: {e}")


def upload_output_video(video_path: Path) -> str:
    """Upload processed video to R2 and return a presigned download URL."""
    logger.info(f"Preparing upload for: {video_path}")
    
    bucket_name = os.environ.get("R2_BUCKET_NAME")
    endpoint_url = os.environ.get("R2_ENDPOINT_URL")
    r2_key = os.environ.get("R2_ACCESS_KEY_ID")
    r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")
    upload_directory = os.environ.get("R2_UPLOAD_DIRECTORY", "video-outputs")
    expiration_seconds = int(os.environ.get("R2_PRESIGNED_EXPIRY", "86400"))
    
    if not all([bucket_name, endpoint_url, r2_key, r2_secret]):
        logger.warning("R2 not configured, skipping upload")
        return None
    
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=r2_key,
        aws_secret_access_key=r2_secret,
        region_name="auto",
        config=BotoConfig(s3={"addressing_style": "path"})
    )
    
    object_key = f"{upload_directory}/{uuid.uuid4()}{video_path.suffix or '.mp4'}"
    logger.info(f"Uploading to r2://{bucket_name}/{object_key}")
    s3.upload_file(str(video_path), bucket_name, object_key)
    
    try:
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=expiration_seconds
        )
        logger.info("Generated presigned URL for download")
        return presigned_url
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        return f"{endpoint_url}/{bucket_name}/{object_key}"


def get_input_image_path(params: Dict[str, Any], temp_dir: Path) -> Path:
    """Get input image path from image_url or image_path."""
    image_url = (params.get('image_url') or '').strip() if params.get('image_url') else None
    image_path = (params.get('image_path') or '').strip() if params.get('image_path') else None
    
    provided = [p for p in [image_url, image_path] if p]
    if len(provided) == 0:
        raise ValueError("For I2V task, provide one of 'image_url' or 'image_path'")
    if len(provided) > 1:
        raise ValueError("Provide only one of 'image_url' or 'image_path'")
    
    if image_url:
        return download_input_image(image_url, temp_dir)
    
    if image_path:
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            raise FileNotFoundError(f"Image file not found: {image_path_obj}")
        return image_path_obj


def process_video_generation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Process video generation with given parameters."""
    cleanup_manager = CleanupManager()
    
    try:
        validated = validate_params(params)
        logger.info(f"Processing video generation with parameters: {validated}")
        
        temp_dir = Path(tempfile.mkdtemp(prefix='wan22_'))
        cleanup_manager.add_directory(temp_dir)
        
        # Get input image if I2V task
        image_path = None
        if validated['task'] == 'i2v':
            image_path = get_input_image_path(validated, temp_dir)
            logger.info(f"Using input image: {image_path}")
        
        generator = Wan22Generator()
        
        # Generate video
        output_video_path = generator.generate(
            prompt=validated['prompt'],
            task=validated['task'],
            image_path=image_path,
            width=validated['width'],
            height=validated['height'],
            num_frames=validated['num_frames'],
            steps=validated['steps'],
            seed=validated['seed'],
        )
        
        logger.info(f"Video generated: {output_video_path}")
        
        # Upload to R2 (optional)
        download_url = upload_output_video(output_video_path)
        
        result = {
            'status': 'success',
            'task': validated['task'],
            'resolution': f"{validated['width']}x{validated['height']}",
            'num_frames': validated['num_frames'],
            'steps': validated['steps'],
            'output_path': str(output_video_path),
        }
        
        if download_url:
            result['download_url'] = download_url
        
        return result
        
    except Exception as e:
        logger.error(f"Processing failed: {e}", exc_info=True)
        raise
    
    finally:
        cleanup_manager.cleanup_all()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Wan2.2-TI2V-5B Video Generation')
    parser.add_argument('--input', type=str, help='JSON input file path')
    parser.add_argument('--prompt', type=str, help='Text prompt for generation')
    parser.add_argument('--task', type=str, default='t2v', choices=['t2v', 'i2v'], help='Generation task')
    parser.add_argument('--image-url', type=str, help='Image URL for I2V')
    parser.add_argument('--image-path', type=str, help='Image file path for I2V')
    parser.add_argument('--width', type=int, default=1280, help='Video width')
    parser.add_argument('--height', type=int, default=704, help='Video height')
    parser.add_argument('--num-frames', type=int, default=120, help='Number of frames')
    parser.add_argument('--steps', type=int, default=10, help='Number of denoising steps')
    parser.add_argument('--seed', type=int, help='Random seed')
    
    args = parser.parse_args()
    
    # Build params dict
    if args.input:
        # Load from JSON file
        with open(args.input, 'r') as f:
            params = json.load(f)
            # Handle nested 'input' key if present
            if 'input' in params:
                params = params['input']
    else:
        # Build from command line args
        if not args.prompt:
            parser.error("--prompt is required when not using --input")
        
        params = {
            'prompt': args.prompt,
            'task': args.task,
            'width': args.width,
            'height': args.height,
            'num_frames': args.num_frames,
            'steps': args.steps,
        }
        if args.image_url:
            params['image_url'] = args.image_url
        if args.image_path:
            params['image_path'] = args.image_path
        if args.seed is not None:
            params['seed'] = args.seed
    
    # Process generation
    result = process_video_generation(params)
    
    # Output result as JSON
    print(json.dumps(result, indent=2))
    
    return result


if __name__ == "__main__":
    main()

