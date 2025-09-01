from pydantic import BaseModel
from typing import List


class ScopedConfig(BaseModel):
    gemini_api_url: str = 'https://generativelanguage.googleapis.com'   # Gemini API Url 默认为官方Url
    gemini_api_keys: List[str] = ['xxxxxx']  # Gemini API Key 需要付费key，可为一个列表
    gemini_model: str = 'gemini-2.5-flash-image-preview'    # Gemini 模型 默认为 gemini-2.5-flash-image-preview
    max_api_key_attempts: int = 3 # 每个API Key的最大尝试次数（包括首次尝试），默认3次
    default_prompt: str  = "Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it."

class Config(BaseModel):
    figurine: ScopedConfig = ScopedConfig()
