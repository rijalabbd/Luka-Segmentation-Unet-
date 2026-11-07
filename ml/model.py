from pathlib import Path
import sys

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if _BACKEND_DIR.is_dir() and str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.services.unet_model import DecoderBlock, ResNet34UNet  # noqa: E402,F401

__all__ = ["DecoderBlock", "ResNet34UNet"]
