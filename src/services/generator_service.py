import subprocess
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Wan22Generator:
    """Wrapper service for Wan2.2 TI2V-5B generate.py script."""
    
    def __init__(self, model_dir: str = "/opt/models/wan22-ti2v-5b"):
        self.model_dir = Path(model_dir)
        self.generate_script = Path("/opt/wan22/generate.py")
        self.wan22_dir = Path("/opt/wan22")
        
        if not self.generate_script.exists():
            raise FileNotFoundError(f"generate.py not found at {self.generate_script}")
        
        if not self.model_dir.exists():
            raise FileNotFoundError(f"Model directory not found at {self.model_dir}")
    
    def generate(
        self,
        prompt: str,
        task: str = 't2v',  # 't2v' or 'i2v'
        image_path: Optional[Path] = None,
        width: int = 1280,
        height: int = 704,
        num_frames: int = 120,
        steps: int = 10,
        seed: Optional[int] = None,
    ) -> Path:
        """
        Generate video using Wan2.2 TI2V-5B model.
        
        Args:
            prompt: Text prompt for generation
            task: 't2v' for text-to-video or 'i2v' for image-to-video
            image_path: Path to input image (required for I2V)
            width: Video width (720P: 1280 or 704)
            height: Video height (720P: 704 or 1280)
            num_frames: Number of frames to generate
            steps: Number of denoising steps
            seed: Random seed (optional)
        
        Returns:
            Path to generated video file
        """
        if task == 'i2v' and not image_path:
            raise ValueError("image_path is required for I2V task")
        
        if task == 'i2v' and not image_path.exists():
            raise FileNotFoundError(f"Input image not found: {image_path}")
        
        # Build command
        cmd = [
            "python",
            str(self.generate_script),
            "--task", "ti2v-5B",
            "--size", f"{width}*{height}",
            "--ckpt_dir", str(self.model_dir),
            "--prompt", prompt,
        ]
        
        if num_frames is not None:
            cmd.extend(["--num_frames", str(num_frames)])
        if steps is not None:
            cmd.extend(["--steps", str(steps)])
        if seed is not None:
            cmd.extend(["--seed", str(seed)])
        
        if task == 'i2v' and image_path:
            cmd.extend(["--image", str(image_path)])
        
        logger.info(f"Executing: {' '.join(cmd)}")
        logger.info(f"Working directory: {self.wan22_dir}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.wan22_dir),
                capture_output=True,
                text=True,
                check=True,
                timeout=10800,  # 3 hour timeout
            )
            
            logger.info(f"Generation completed successfully")
            logger.debug(f"stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"stderr: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            logger.error("Generation timed out after 30 minutes")
            raise RuntimeError("Video generation timed out")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Generation failed with return code {e.returncode}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            raise RuntimeError(f"Video generation failed: {e.stderr}")
        
        # Find output video
        output_video = self._find_output_video()
        
        if not output_video.exists():
            raise FileNotFoundError(f"Generated video not found at {output_video}")
        
        logger.info(f"Video generated at: {output_video}")
        return output_video
    
    def _find_output_video(self) -> Path:
        """
        Find the generated video file.
        
        generate.py typically outputs to /opt/wan22/output/ or the current directory.
        """
        possible_locations = [
            Path("/opt/wan22/output"),
            Path("/opt/wan22"),
            Path("/opt/app/output"),
        ]
        
        video_extensions = ['.mp4', '.webm', '.avi', '.mov']
        
        for location in possible_locations:
            if location.exists():
                for ext in video_extensions:
                    videos = list(location.rglob(f"*{ext}"))
                    if videos:
                        videos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        logger.info(f"Found video at: {videos[0]}")
                        return videos[0]
        
        raise FileNotFoundError(
            f"Could not find generated video. Checked locations: {possible_locations}"
        )

