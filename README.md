<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-figurine

_✨ NoneBot2 一个图片手办化插件 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/padoru233/nonebot-plugin-figurine.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-figurine">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-figurine.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">

</div>


## 📖 介绍

基于Gemini API 的图片手办化插件

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-figurine

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-figurine
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-figurine
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-figurine
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-figurine
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_figurine"]

</details>

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| FIGURINE__GEMINI_API_URL | 是 | https://generativelanguage.googleapis.com | Gemini API Url 默认为官方Url |
| FIGURINE__GEMINI_API_KEYS | 是 | ["xxxxxx"] | 需要付费key，填入你的多个API Key，例如 ['key1', 'key2', 'key3'] |
| FIGURINE__GEMINI_MODEL | 否 | gemini-2.5-flash-image-preview | Gemini 模型 默认为 gemini-2.5-flash-image-preview |
| FIGURINE__MAX_TOTAL_ATTEMPTS | 否 | 3 | 这一张图的最大尝试次数（包括首次尝试），默认3次，建议不小于Key数量，保证每个Key至少轮到1次 |
| FIGURINE_DEFAULT_PROMPT | 否 | 省略 | 可参考下方 |

### 可参考提示词（PROMPT）：

默认："Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it."

"Please accurately transform the main subject in this photo into a realistic, masterpiece-like 1/7 scale PVC statue.\nBehind this statue, a packaging box should be placed: the box has a large clear front window on its front side, and is printed with subject artwork, product name, brand logo, barcode, as well as a small specifications or authenticity verification panel. A small price tag sticker must also be attached to one corner of the box. Meanwhile, a computer monitor is placed at the back, and the monitor screen needs to display the ZBrush modeling process of this statue.\nIn front of the packaging box, this statue should be placed on a round plastic base. The statue must have 3D dimensionality and a sense of realism, and the texture of the PVC material needs to be clearly represented. If the background can be set as an indoor scene, the effect will be even better.\n\nBelow are detailed guidelines to note:\nWhen repairing any missing parts, there must be no poorly executed elements.\nWhen repairing human figures (if applicable), the body parts must be natural, movements must be coordinated, and the proportions of all parts must be reasonable.\nIf the original photo is not a full-body shot, try to supplement the statue to make it a full-body version.\nThe human figure's expression and movements must be exactly consistent with those in the photo.\nThe figure's head should not appear too large, its legs should not appear too short, and the figure should not look stunted—this guideline may be ignored if the statue is a chibi-style design.\nFor animal statues, the realism and level of detail of the fur should be reduced to make it more like a statue rather than the real original creature.\nNo outer outline lines should be present, and the statue must not be flat.\nPlease pay attention to the perspective relationship of near objects appearing larger and far objects smaller."

"Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it. Picture ratio 16:9."

"Your primary mission is to accurately convert the subject from the user's photo into a photorealistic, masterpiece quality, 1/7 scale PVC figurine, presented in its commercial packaging.\n\n**Crucial First Step: Analyze the image to identify the subject's key attributes (e.g., human male, human female, animal, specific creature) and defining features (hair style, clothing, expression). The generated figurine must strictly adhere to these identified attributes.** This is a mandatory instruction to avoid generating a generic female figure.\n\n**Top Priority - Character Likeness:** The figurine's face MUST maintain a strong likeness to the original character. Your task is to translate the 2D facial features into a 3D sculpt, preserving the identity, expression, and core characteristics. If the source is blurry, interpret the features to create a sharp, well-defined version that is clearly recognizable as the same character.\n\n**Scene Details:**\n1. **Figurine:** The figure version of the photo I gave you, with a clear representation of PVC material, placed on a round plastic base.\n2. **Packaging:** Behind the figure, there should be a partially transparent plastic and paper box, with the character from the photo printed on it.\n3. **Environment:** The entire scene should be in an indoor setting with good lighting."

"Accurately transform the main subjects in this photo into realistic, masterpiece-quality 1/7 scale PVC statue figures.\nPlace the packaging box behind the statues: the box should have a large clear window on the front, printed with character-themed artwork, the product name, brand logo, barcode, and a small specifications or authentication panel. A small price tag sticker must be attached to one corner of the box.\nA computer monitor is placed further behind, displaying the ZBrush modeling process of one of the statues.\n\nThe statues should be positioned on a round plastic base in front of the packaging box. They must exhibit three-dimensionality and a realistic sense of presence, with the texture of the PVC material clearly represented. An indoor setting is preferred for the background.\n\nDetailed guidelines to note:\n1. The dual statue set must retain the interactive poses from the original photo, with natural and coordinated body movements and reasonable proportions (unless it is a chibi-style design, avoid unrealistic proportions such as overly large heads or short legs).\n2. Facial expressions and clothing details must closely match the original photo. Any missing parts should be completed logically and consistently.\n3. For any animal elements, reduce the realism of fur texture to enhance the sculpted appearance.\n4. The packaging box must include dual-character theme artwork, with clear product names and brand logos.\n5. The computer screen should display the ZBrush interface showing the wireframe modeling details of one of the statues.\n6. The overall composition must adhere to perspective rules (closer objects appear larger, distant objects smaller), avoiding flat-looking outlines.\n7. The surface of the statues should reflect the smooth and glossy characteristics typical of PVC material.\n\n(Adjustments can be made based on the actual photo content regarding dual-character interaction details and packaging box visual design.)"

"Realistic PVC figure based on the game screenshot character, exact pose replication highly detailed textures PVC material with subtle sheen and smooth paint finish, placed on an indoor wooden computer desk (with subtle desk items like a figure box/mouse), illuminated by soft indoor light (mix of desk lamp and natural window light) for realistic shadows and highlights, macro photography style,high resolution,sharp focus on the figure,shallow depth of field (desk background slightly blurred but visible), no stylization,true-to-reference color and design, 1:1scale."

"((chibi style)), ((super-deformed)), ((head-to-body ratio 1:2)), ((huge head, tiny body)), ((smooth rounded limbs)), ((soft balloon-like hands and feet)), ((plump cheeks)), ((childlike big eyes)), ((simplified facial features)), ((smooth matte skin, no pores)), ((soft pastel color palette)), ((gentle ambient lighting, natural shadows)), ((same facial expression, same pose, same background scene)), ((seamless integration with original environment, correct perspective and scale)), ((no outline or thin soft outline)), ((high resolution, sharp focus, 8k, ultra-detailed)), avoid: realistic proportions, long limbs, sharp edges, harsh lighting, wrinkles, blemishes, thick black outlines, low resolution, blurry, extra limbs, distorted face"

## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| 手办化 | 群员 | 否 | 群聊 | 需要带一张图或回复一张图片 |
| 手办化@xx | 群员 | 是 | 群聊 | 自动获取头像 |
| 手办化 自己 | 群员 | 否 | 群聊 | 自动获取头像 |
### 效果图
如果有效果图的话
