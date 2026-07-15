import os
import logging
from typing import Optional, Union
from PIL import Image

# Configure HuggingFace mirror before importing transformers
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

logger = logging.getLogger(__name__)

try:
    from transformers import BlipProcessor, BlipForConditionalGeneration
    _transformers_available = True
except ImportError:
    _transformers_available = False
    logger.warning("transformers library not installed, AI captioning will be disabled")


class AICaptioner:
    def __init__(self, model_name: str = "Salesforce/blip-image-captioning-base"):
        self.model_name = model_name
        self.processor = None
        self.model = None
        self._is_loaded = False
        self._load_error = None

    def _find_local_cache_path(self) -> Optional[str]:
        """Find local cache path for the model"""
        try:
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            repo_name = self.model_name.replace("/", "--")
            model_cache_dir = os.path.join(cache_dir, f"models--{repo_name}")
            snapshots_dir = os.path.join(model_cache_dir, "snapshots")
            
            if not os.path.exists(snapshots_dir):
                return None
            
            snapshots = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
            if not snapshots:
                return None
            
            snapshots.sort(reverse=True)
            for snapshot in snapshots:
                snapshot_path = os.path.join(snapshots_dir, snapshot)
                model_bin = os.path.join(snapshot_path, "pytorch_model.bin")
                config_json = os.path.join(snapshot_path, "config.json")
                if os.path.exists(model_bin) and os.path.exists(config_json):
                    return snapshot_path
            
            return None
        except Exception:
            return None

    def load(self, device: str = "cpu") -> bool:
        if not _transformers_available:
            self._load_error = "transformers library not installed"
            return False

        try:
            logger.info(f"Loading AI model: {self.model_name} (device: {device})")
            
            local_path = self._find_local_cache_path()
            if local_path:
                logger.info(f"Found local cache: {local_path}")
                model_path = local_path
                use_local = True
            else:
                logger.info("No local cache found, will download from HuggingFace")
                if os.environ.get("HF_ENDPOINT"):
                    logger.info(f"Using HuggingFace mirror: {os.environ['HF_ENDPOINT']}")
                model_path = self.model_name
                use_local = False

            import torch
            
            self.processor = BlipProcessor.from_pretrained(
                model_path,
                local_files_only=use_local
            )
            
            self.model = BlipForConditionalGeneration.from_pretrained(
                model_path,
                torch_dtype=torch.float32 if device == "cpu" else torch.float16,
                device_map=device,
                local_files_only=use_local
            )
            
            self._is_loaded = True
            logger.info("AI model loaded successfully")
            return True
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"Failed to load AI model: {e}")
            return False

    def is_available(self) -> bool:
        return self._is_loaded

    def generate_caption(self, image: Union[Image.Image, str], prompt: Optional[str] = None) -> str:
        if not self._is_loaded:
            return ""

        try:
            if isinstance(image, str):
                image = Image.open(image).convert("RGB")
            elif isinstance(image, Image.Image):
                image = image.convert("RGB")
            else:
                return ""

            if prompt:
                inputs = self.processor(image, prompt, return_tensors="pt").to(self.model.device)
            else:
                inputs = self.processor(image, return_tensors="pt").to(self.model.device)

            output = self.model.generate(
                **inputs,
                max_new_tokens=64,
                num_beams=4,
                early_stopping=True
            )
            caption = self.processor.decode(output[0], skip_special_tokens=True).strip()
            return caption
        except Exception as e:
            logger.error(f"Failed to generate caption: {e}")
            return ""

    def get_load_error(self) -> Optional[str]:
        return self._load_error