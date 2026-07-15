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

    def load(self, device: str = "cpu") -> bool:
        if not _transformers_available:
            self._load_error = "transformers library not installed"
            return False

        try:
            logger.info(f"Loading AI model: {self.model_name} (device: {device})")
            if os.environ.get("HF_ENDPOINT"):
                logger.info(f"Using HuggingFace mirror: {os.environ['HF_ENDPOINT']}")

            import torch
            self.processor = BlipProcessor.from_pretrained(self.model_name)
            self.model = BlipForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32 if device == "cpu" else torch.float16,
                device_map=device
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