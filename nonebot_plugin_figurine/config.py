from pydantic import BaseModel


class ScopedConfig(BaseModel):
    gemini_api_url: str = 'https://generativelanguage.googleapis.com'   # Gemini API Url 默认为官方Url
    gemini_api_key: str = 'xxxxxx'  # Gemini API Key 需要付费key
    gemini_model: str = 'gemini-2.5-flash-image-preview'    # Gemini 模型 默认为 gemini-2.5-flash-image-preview
    default_prompt: str  = "Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it."

class Config(BaseModel):
    figurine: ScopedConfig = ScopedConfig()
