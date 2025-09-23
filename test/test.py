import httpx
import base64
from io import BytesIO
from PIL import Image
import asyncio
import json
import os

# --- 配置 ---
# 确保 'test_input_image.png' 文件存在于脚本同级目录，或者提供完整路径。
images = ["test_input_image.png"]
prompt = "Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it."
gemini_api = "https://xxxx/v1/chat/completions"
gemini_model = "gemini-2.5-flash-image-preview"
gemini_key = "sk-xxxxxxxxxxxxx"


async def call_openai_compatible_api_test():
    """
    调用一个兼容 OpenAI 接口的 API，传入文本和图片输入，
    处理错误，并保存任何返回的图片。

    返回:
        tuple: (text_output: str, image_filepath: str, error_message: str)
               如果发生错误或数据不存在，则返回 None。
    """
    text_out = None
    img_filepath = None
    error_message = None

    for img_filename in images:
        try:
            with Image.open(img_filename) as img:
                buf = BytesIO()
                img.save(buf, format="PNG")
                img_b64 = base64.b64encode(buf.getvalue()).decode()
            content_parts = [
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}"
                    }
                }
            ]
        except FileNotFoundError:
            error_message = f"错误：输入图片文件未找到: {img_filename}"
            print(error_message)
            return None, None, error_message
        except Exception as e:
            error_message = f"处理图片 {img_filename} 时发生错误: {e}"
            print(error_message)
            return None, None, error_message

    payload = {
        "model": gemini_model,
        "messages": [
            {
                "role": "user",
                "content": content_parts
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {gemini_key}",
        "Content-Type": "application/json"
    }

    resp = None
    try:
        timeout_config = httpx.Timeout(
            60.0,
            connect=5.0,
            read=60.0,
            write=5.0
        )
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            resp = await client.post(gemini_api, headers=headers, json=payload)
            resp.raise_for_status()
    except httpx.RequestError as e:
        error_message = f"请求过程中发生网络或HTTP错误: {e}"
        print(error_message)
        return None, None, error_message
    except httpx.HTTPStatusError as e:
        error_message = f"API 返回错误状态码 {e.response.status_code}: {e.response.text}"
        print(error_message)
        return None, None, error_message
    except Exception as e:
        error_message = f"HTTP 请求过程中发生未知错误: {e}"
        print(error_message)
        return None, None, error_message

    try:
        result = resp.json()
    except json.JSONDecodeError as e:
        error_message = f"API 响应 JSON 解析失败: {e}。响应文本: {resp.text}"
        print(error_message)
        return None, None, error_message
    except Exception as e:
        error_message = f"解析 JSON 时发生未知错误: {e}。响应文本: {resp.text}"
        print(error_message)
        return None, None, error_message

    # 检查响应体中的 API 级别错误
    if "error" in result:
        error_message = f"API 错误: {result.get('error', {}).get('message', '未知 API 错误')}"
        print(error_message)
        return None, None, error_message

    choices = result.get("choices")

    if not isinstance(choices, list) or not choices:
        error_message = "API 响应中未包含有效的 'choices' 字段。"
        print(error_message)
        return None, None, error_message

    msg = choices[0].get("message", {})

    # 获取文本内容
    text_out = msg.get("content")
    if isinstance(text_out, str):
        text_out = text_out.strip()
    else:
        text_out = None
        print("API 调用成功但未返回文本内容。")

    # 获取并保存图片内容
    images_list = msg.get("images")
    if isinstance(images_list, list) and images_list:
        first_image = images_list[0]
        if isinstance(first_image, dict):
            image_url_data = first_image.get("image_url")
            if isinstance(image_url_data, dict):
                img_b64_data = image_url_data.get("url")
                if img_b64_data and img_b64_data.startswith("data:image/png;base64,"):
                    try:
                        # 提取 base64 部分并解码
                        base64_string = img_b64_data.split(",")[1]
                        image_bytes = base64.b64decode(base64_string)

                        # 定义输出文件名
                        output_filename = "generated_image.png"
                        img_filepath = output_filename

                        # 保存图片
                        with open(output_filename, "wb") as f:
                            f.write(image_bytes)
                        print(f"成功将生成的图片保存到 {output_filename}")
                    except Exception as e:
                        error_message = f"解码或保存返回图片时发生错误: {e}"
                        print(error_message)
                else:
                    print("API 调用成功但返回的图片 URL 不是有效的 base64 PNG 数据 URL。")
            else:
                print("API 调用成功但 'image_url' 数据格式不正确。")
        else:
            print("API 调用成功但第一个图片对象格式不正确。")
    else:
        print("API 调用成功但未返回任何图片。")

    return text_out, img_filepath, error_message


async def main():
    print("开始调用 API...")
    text_result, image_path, error = await call_openai_compatible_api_test()

    if error:
        print(f"\n--- 操作失败 ---")
        print(f"错误: {error}")
    else:
        print(f"\n--- 操作成功 ---")
        if text_result:
            print(f"生成的文本:\n{text_result}")
        else:
            print("未生成文本内容。")

        if image_path:
            print(f"生成的图片已保存到: {image_path}")
        else:
            print("未生成或保存图片。")

    print("\n--- 流程结束 ---")

if __name__ == "__main__":
    # 如果 'test_input_image.png' 不存在，则创建一个占位图片用于演示
    if not os.path.exists("test_input_image.png"):
        print("正在创建占位图片 'test_input_image.png' 用于演示。")
        try:
            img = Image.new('RGB', (60, 30), color = 'red')
            img.save('test_input_image.png')
            print("占位图片已创建。你可以将其替换为你的实际图片。")
        except Exception as e:
            print(f"无法创建占位图片: {e}。请确保已安装 Pillow 库并提供 'test_input_image.png'。")
            exit()

    asyncio.run(main())
