import logging
from typing import Dict, Any
from pathlib import Path
import validators

logger = logging.getLogger(__name__)


class InputValidator:
    """Validator for Wan22 input parameters."""
    
    @staticmethod
    def validate_prompt(prompt: Any) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        if not prompt or not isinstance(prompt, str):
            result['errors'].append("Prompt is required and must be a string")
            return result
        
        if len(prompt.strip()) == 0:
            result['errors'].append("Prompt cannot be empty")
            return result
        
        if len(prompt) > 1000:
            result['warnings'].append(f"Prompt is very long ({len(prompt)} chars), may affect generation time")
        
        result['valid'] = True
        return result
    
    @staticmethod
    def validate_task(task: Any) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        if not isinstance(task, str):
            result['errors'].append("Task must be a string")
            return result
        
        task_lower = task.lower().strip()
        if task_lower not in ['t2v', 'i2v']:
            result['errors'].append(f"Task must be 't2v' or 'i2v', got: {task}")
            return result
        
        result['valid'] = True
        result['value'] = task_lower
        return result
    
    @staticmethod
    def validate_resolution(width: Any, height: Any) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        try:
            width_int = int(width)
            height_int = int(height)
        except (ValueError, TypeError):
            result['errors'].append("Width and height must be integers")
            return result
        
        # TI2V-5B only supports 720P: 1280x704 or 704x1280
        valid_resolutions = [(1280, 704), (704, 1280)]
        
        if (width_int, height_int) not in valid_resolutions:
            result['errors'].append(
                f"Resolution {width_int}x{height_int} is not supported. "
                f"TI2V-5B only supports 720P: 1280x704 or 704x1280"
            )
            return result
        
        result['valid'] = True
        result['width'] = width_int
        result['height'] = height_int
        return result
    
    @staticmethod
    def validate_num_frames(num_frames: Any) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        try:
            num_frames_int = int(num_frames)
        except (ValueError, TypeError):
            result['errors'].append("num_frames must be an integer")
            return result
        
        if num_frames_int < 1:
            result['errors'].append("num_frames must be at least 1")
            return result
        
        if num_frames_int > 300:
            result['errors'].append("num_frames cannot exceed 300")
            return result
        
        # Estimate duration (assuming 24fps)
        duration_seconds = num_frames_int / 24
        if duration_seconds > 30:
            result['warnings'].append(
                f"Large number of frames ({num_frames_int}) will generate a long video "
                f"(~{duration_seconds:.1f}s) and may take significant time"
            )
        
        result['valid'] = True
        result['value'] = num_frames_int
        return result
    
    @staticmethod
    def validate_steps(steps: Any) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        try:
            steps_int = int(steps)
        except (ValueError, TypeError):
            result['errors'].append("steps must be an integer")
            return result
        
        if steps_int < 1:
            result['errors'].append("steps must be at least 1")
            return result
        
        if steps_int > 50:
            result['errors'].append("steps cannot exceed 50")
            return result
        
        if steps_int < 5:
            result['warnings'].append("Very low step count may result in lower quality")
        
        if steps_int > 20:
            result['warnings'].append("High step count will increase generation time significantly")
        
        result['valid'] = True
        result['value'] = steps_int
        return result
    
    @staticmethod
    def validate_image_url(url: str) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        if not url or not isinstance(url, str):
            result['errors'].append("Image URL is required and must be a string")
            return result
        
        if not validators.url(url):
            result['errors'].append("Invalid URL format")
            return result
        
        supported_protocols = ['http', 'https']
        protocol = url.split('://')[0].lower()
        
        if protocol not in supported_protocols:
            result['errors'].append(f"Unsupported protocol: {protocol}. Supported: {supported_protocols}")
            return result
        
        result['valid'] = True
        return result
    
    @staticmethod
    def validate_image_path(path: str) -> Dict[str, Any]:
        result = {'valid': False, 'errors': [], 'warnings': []}
        
        if not path or not isinstance(path, str):
            result['errors'].append("Image path is required and must be a string")
            return result
        
        path_obj = Path(path)
        if not path_obj.exists():
            result['errors'].append(f"Image file does not exist: {path}")
            return result
        
        if not path_obj.is_file():
            result['errors'].append(f"Path is not a file: {path}")
            return result
        
        # Check if it's an image file
        supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
        if path_obj.suffix.lower() not in supported_extensions:
            result['warnings'].append(
                f"Unusual image extension: {path_obj.suffix}. "
                f"Supported: {supported_extensions}"
            )
        
        result['valid'] = True
        return result

