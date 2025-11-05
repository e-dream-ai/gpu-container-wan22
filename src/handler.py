import runpod
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import subprocess
import time
import boto3
from botocore.config import Config as BotoConfig
from pathlib import Path

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())

def to_nearest_multiple_of_16(value):
    """Round value to nearest multiple of 16, minimum 16."""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height value is not numeric: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted

def process_input(input_data, temp_dir, output_filename, input_type):
    """Process input data and return file path."""
    if input_type == "path":
        logger.info(f"📁 Processing path input: {input_data}")
        return input_data
    elif input_type == "url":
        logger.info(f"🌐 Processing URL input: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        logger.info(f"🔢 Processing Base64 input")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"Unsupported input type: {input_type}")

def download_file_from_url(url, output_path):
    """Download file from URL using wget."""
    try:
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"✅ Successfully downloaded file from URL: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget download failed: {result.stderr}")
            raise Exception(f"URL download failed: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ Download timeout")
        raise Exception("Download timeout")
    except Exception as e:
        logger.error(f"❌ Download error: {e}")
        raise Exception(f"Download error: {e}")

def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Save Base64 data to file."""
    try:
        decoded_data = base64.b64decode(base64_data)
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        logger.info(f"✅ Saved Base64 input to file: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"❌ Base64 decode failed: {e}")
        raise Exception(f"Base64 decode failed: {e}")

def queue_prompt(prompt):
    """Queue prompt to ComfyUI."""
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_history(prompt_id):
    """Get history from ComfyUI."""
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_videos(ws, prompt):
    """Get generated videos from ComfyUI via websocket."""
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_videos = {}
    
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        videos_output = []
        if 'gifs' in node_output:
            for video in node_output['gifs']:
                # Read video file and encode as base64
                with open(video['fullpath'], 'rb') as f:
                    video_data = base64.b64encode(f.read()).decode('utf-8')
                videos_output.append(video_data)
        output_videos[node_id] = videos_output

    return output_videos

def load_workflow(workflow_path):
    """Load workflow JSON file."""
    with open(workflow_path, 'r') as file:
        return json.load(file)

def upload_output_video(video_base64: str) -> str:
    """Upload video to R2 and return presigned URL."""
    logger.info("Preparing upload to R2")
    
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
    
    # Decode base64 video and upload
    video_data = base64.b64decode(video_base64)
    object_key = f"{upload_directory}/{uuid.uuid4()}.mp4"
    
    logger.info(f"Uploading to r2://{bucket_name}/{object_key}")
    s3.put_object(Bucket=bucket_name, Key=object_key, Body=video_data)
    
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

def handler(job):
    """RunPod serverless handler."""
    job_input = job.get("input", {})
    logger.info(f"Received job input: {job_input}")
    
    task_id = f"task_{uuid.uuid4()}"

    # Handle image input for I2V (image_path, image_url, image_base64)
    image_path = None
    task = job_input.get("task", "t2v")
    
    if task == "i2v":
        if "image_path" in job_input:
            image_path = process_input(job_input["image_path"], task_id, "input_image.jpg", "path")
        elif "image_url" in job_input:
            image_path = process_input(job_input["image_url"], task_id, "input_image.jpg", "url")
        elif "image_base64" in job_input:
            image_path = process_input(job_input["image_base64"], task_id, "input_image.jpg", "base64")
        else:
            raise Exception("For I2V task, provide one of: image_path, image_url, or image_base64")
        logger.info(f"Using input image: {image_path}")
    
    # Load workflow
    workflow_file = "/workflows/wan22_api.json"
    logger.info(f"Using workflow: {workflow_file}")
    prompt = load_workflow(workflow_file)
    
    # Apply parameters to workflow
    length = job_input.get("num_frames", 81)
    steps = job_input.get("steps", 10)
    seed = job_input.get("seed", 42)
    cfg = job_input.get("cfg", 2.0)
    
    # Set image if I2V
    if task == "i2v" and image_path:
        prompt["244"]["inputs"]["image"] = image_path
    
    # Set parameters in workflow
    prompt["541"]["inputs"]["num_frames"] = length
    prompt["135"]["inputs"]["positive_prompt"] = job_input.get("prompt", "A beautiful video")
    prompt["220"]["inputs"]["seed"] = seed
    prompt["540"]["inputs"]["seed"] = seed
    prompt["540"]["inputs"]["cfg"] = cfg
    
    # Handle resolution (adjust to nearest 16 multiple)
    original_width = job_input.get("width", 480)
    original_height = job_input.get("height", 832)
    adjusted_width = to_nearest_multiple_of_16(original_width)
    adjusted_height = to_nearest_multiple_of_16(original_height)
    
    if adjusted_width != original_width:
        logger.info(f"Width adjusted to nearest multiple of 16: {original_width} -> {adjusted_width}")
    if adjusted_height != original_height:
        logger.info(f"Height adjusted to nearest multiple of 16: {original_height} -> {adjusted_height}")
    
    prompt["235"]["inputs"]["value"] = adjusted_width
    prompt["236"]["inputs"]["value"] = adjusted_height
    prompt["498"]["inputs"]["context_overlap"] = job_input.get("context_overlap", 48)
    
    # Set steps
    if "834" in prompt:
        prompt["834"]["inputs"]["steps"] = steps
        logger.info(f"Steps set to: {steps}")
        lowsteps = int(steps * 0.6)
        prompt["829"]["inputs"]["step"] = lowsteps
        logger.info(f"LowSteps set to: {lowsteps}")
    
    # Handle LoRA pairs if provided
    lora_pairs = job_input.get("lora_pairs", [])
    if lora_pairs:
        high_lora_node_id = "279"
        low_lora_node_id = "553"
        
        for i, lora_pair in enumerate(lora_pairs[:4]):
            lora_high = lora_pair.get("high")
            lora_low = lora_pair.get("low")
            lora_high_weight = lora_pair.get("high_weight", 1.0)
            lora_low_weight = lora_pair.get("low_weight", 1.0)
            
            if lora_high:
                prompt[high_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_high
                prompt[high_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_high_weight
                logger.info(f"LoRA {i+1} HIGH applied: {lora_high} with weight {lora_high_weight}")
            
            if lora_low:
                prompt[low_lora_node_id]["inputs"][f"lora_{i+1}"] = lora_low
                prompt[low_lora_node_id]["inputs"][f"strength_{i+1}"] = lora_low_weight
                logger.info(f"LoRA {i+1} LOW applied: {lora_low} with weight {lora_low_weight}")

    # Connect to ComfyUI websocket
    ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
    logger.info(f"Connecting to WebSocket: {ws_url}")
    
    # Check HTTP connection first
    http_url = f"http://{server_address}:8188/"
    logger.info(f"Checking HTTP connection to: {http_url}")
    
    max_http_attempts = 180
    for http_attempt in range(max_http_attempts):
        try:
            logger.info(f"HTTP connection successful (attempt {http_attempt+1})")
            break
        except Exception as e:
            logger.warning(f"HTTP connection failed (attempt {http_attempt+1}/{max_http_attempts}): {e}")
            if http_attempt == max_http_attempts - 1:
                raise Exception("Cannot connect to ComfyUI server. Check if server is running.")
            time.sleep(1)
    
    ws = websocket.WebSocket()
    max_attempts = int(180/5)  # 3 minutes
    for attempt in range(max_attempts):
        try:
            ws.connect(ws_url)
            logger.info(f"Websocket connected successfully (attempt {attempt+1})")
            break
        except Exception as e:
            logger.warning(f"Websocket connection failed (attempt {attempt+1}/{max_attempts}): {e}")
            if attempt == max_attempts - 1:
                raise Exception("Websocket connection timeout (3 minutes)")
            time.sleep(5)
    
    # Generate video
    videos = get_videos(ws, prompt)
    ws.close()

    # Find and return video
    for node_id in videos:
        if videos[node_id]:
            video_base64 = videos[node_id][0]
            
            # Upload to R2 if configured
            download_url = upload_output_video(video_base64)
            
            result = {
                "status": "success",
                "video": video_base64,
                "task": task,
                "resolution": f"{adjusted_width}x{adjusted_height}",
                "num_frames": length,
                "steps": steps,
            }
            
            if download_url:
                result["download_url"] = download_url
            
            return result
    
    return {"error": "Video not found in output"}

runpod.serverless.start({"handler": handler})
