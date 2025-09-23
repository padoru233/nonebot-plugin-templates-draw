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
| FIGURINE__GEMINI_API_URL | 是 | https://generativelanguage.googleapis.com | Gemini API Url 默认为官方Url（调用方式并非Gemini原生而是OpenAI格式） |
| FIGURINE__GEMINI_API_KEYS | 是 | ["xxxxxx"] | 需要付费key，填入你的多个API Key，例如 ['key1', 'key2', 'key3'] |
| FIGURINE__GEMINI_MODEL | 否 | gemini-2.5-flash-image-preview | Gemini 模型 默认为 gemini-2.5-flash-image-preview |
| FIGURINE__MAX_TOTAL_ATTEMPTS | 否 | 3 | 这一张图的最大尝试次数（包括首次尝试），默认3次，建议不小于Key数量，保证每个Key至少轮到1次 |
| FIGURINE__PROMPT_0 | 否 | 默认和预设1一样 | 自定义预设，可参考下方的预设 |

### 推荐API

- https://openrouter.ai/ ~~充值10刀即可每天调用1000次免费模型~~
- 由于Google改变了价格，不再有免费调用：https://ai.google.dev/gemini-api/docs/pricing?hl=zh-cn#gemini-2.5-flash-image-preview
- 1次调用不到4毛CNY，建议配合 [插件管理系统](https://github.com/HibiKier/nonebot-plugin-zxpm) 等设置阻塞、CD、次数
- 自建API：覆盖如下请求参数
```
{
  "modalities": ["text", "image"]
}
```

### 可参考提示词（PROMPT）：

- 手办化1 :生成带包装盒、电脑桌背景的写实手办。
- 手办化2 :生成带包装盒、电脑桌背景的写实手办（风格更加固定）。
- 手办化3 :生成带包装盒的写实手办，更注重面部还原。
- 手办化4 :与 变手办1 类似，细节更加丰富，风格略有差异。
- 手办化5 :基于游戏截图风格，微距摄影效果，带木质电脑桌背景。
- 手办化6 :生成可爱的Q版/粘土人风格手办。
- 手办化ntr :生成一张快餐店构图，手机上展示着上传的图片，背景中一对情侣坐在一起接吻。
- 手办化cos :生成一张主题房间构图，房间中有Cosplayer、抱枕、PVC人物等。
- 手办化jio :生成一张人物将脚伸出，夸大展示脚部的透视图。

<details>
<summary>默认预设1 Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment.</summary>

    Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it. Picture ratio 16:9
</details>

<details>
<summary>预设2 Please accurately transform the main subject in this photo into a realistic, masterpiece-like 1/7 scale PVC statue.</summary>

    Please accurately transform the main subject in this photo into a realistic, masterpiece-like 1/7 scale PVC statue.\nBehind this statue, a packaging box should be placed: the box has a large clear front window on its front side, and is printed with subject artwork, product name, brand logo, barcode, as well as a small specifications or authenticity verification panel. A small price tag sticker must also be attached to one corner of the box. Meanwhile, a computer monitor is placed at the back, and the monitor screen needs to display the ZBrush modeling process of this statue.\nIn front of the packaging box, this statue should be placed on a round plastic base. The statue must have 3D dimensionality and a sense of realism, and the texture of the PVC material needs to be clearly represented. If the background can be set as an indoor scene, the effect will be even better.\n\nBelow are detailed guidelines to note:\nWhen repairing any missing parts, there must be no poorly executed elements.\nWhen repairing human figures (if applicable), the body parts must be natural, movements must be coordinated, and the proportions of all parts must be reasonable.\nIf the original photo is not a full-body shot, try to supplement the statue to make it a full-body version.\nThe human figure's expression and movements must be exactly consistent with those in the photo.\nThe figure's head should not appear too large, its legs should not appear too short, and the figure should not look stunted—this guideline may be ignored if the statue is a chibi-style design.\nFor animal statues, the realism and level of detail of the fur should be reduced to make it more like a statue rather than the real original creature.\nNo outer outline lines should be present, and the statue must not be flat.\nPlease pay attention to the perspective relationship of near objects appearing larger and far objects smaller.
</details>

<details>
<summary>预设3 Your primary mission is to accurately convert the subject from the user's photo into a photorealistic, masterpiece quality, 1/7 scale PVC figurine, presented in its commercial packaging.</summary>

    Your primary mission is to accurately convert the subject from the user's photo into a photorealistic, masterpiece quality, 1/7 scale PVC figurine, presented in its commercial packaging.\n\n**Crucial First Step: Analyze the image to identify the subject's key attributes (e.g., human male, human female, animal, specific creature) and defining features (hair style, clothing, expression). The generated figurine must strictly adhere to these identified attributes.** This is a mandatory instruction to avoid generating a generic female figure.\n\n**Top Priority - Character Likeness:** The figurine's face MUST maintain a strong likeness to the original character. Your task is to translate the 2D facial features into a 3D sculpt, preserving the identity, expression, and core characteristics. If the source is blurry, interpret the features to create a sharp, well-defined version that is clearly recognizable as the same character.\n\n**Scene Details:**\n1. **Figurine:** The figure version of the photo I gave you, with a clear representation of PVC material, placed on a round plastic base.\n2. **Packaging:** Behind the figure, there should be a partially transparent plastic and paper box, with the character from the photo printed on it.\n3. **Environment:** The entire scene should be in an indoor setting with good lighting.
</details>

<details>
<summary>预设4 Accurately transform the main subjects in this photo into realistic, masterpiece-quality 1/7 scale PVC statue figures.</summary>

    Accurately transform the main subjects in this photo into realistic, masterpiece-quality 1/7 scale PVC statue figures.\nPlace the packaging box behind the statues: the box should have a large clear window on the front, printed with character-themed artwork, the product name, brand logo, barcode, and a small specifications or authentication panel. A small price tag sticker must be attached to one corner of the box.\nA computer monitor is placed further behind, displaying the ZBrush modeling process of one of the statues.\n\nThe statues should be positioned on a round plastic base in front of the packaging box. They must exhibit three-dimensionality and a realistic sense of presence, with the texture of the PVC material clearly represented. An indoor setting is preferred for the background.\n\nDetailed guidelines to note:\n1. The dual statue set must retain the interactive poses from the original photo, with natural and coordinated body movements and reasonable proportions (unless it is a chibi-style design, avoid unrealistic proportions such as overly large heads or short legs).\n2. Facial expressions and clothing details must closely match the original photo. Any missing parts should be completed logically and consistently.\n3. For any animal elements, reduce the realism of fur texture to enhance the sculpted appearance.\n4. The packaging box must include dual-character theme artwork, with clear product names and brand logos.\n5. The computer screen should display the ZBrush interface showing the wireframe modeling details of one of the statues.\n6. The overall composition must adhere to perspective rules (closer objects appear larger, distant objects smaller), avoiding flat-looking outlines.\n7. The surface of the statues should reflect the smooth and glossy characteristics typical of PVC material.\n\n(Adjustments can be made based on the actual photo content regarding dual-character interaction details and packaging box visual design.)
</details>

<details>
<summary>预设5 Realistic PVC figure based on the game screenshot character, exact pose replication highly detailed textures PVC material with subtle sheen and smooth paint finish,</summary>

    Realistic PVC figure based on the game screenshot character, exact pose replication highly detailed textures PVC material with subtle sheen and smooth paint finish, placed on an indoor wooden computer desk (with subtle desk items like a figure box/mouse), illuminated by soft indoor light (mix of desk lamp and natural window light) for realistic shadows and highlights, macro photography style,high resolution,sharp focus on the figure,shallow depth of field (desk background slightly blurred but visible), no stylization,true-to-reference color and design, 1:1scale.
</details>

<details>
<summary>预设6 ((chibi style)), ((super-deformed)), ((head-to-body ratio 1:2)), ((huge head, tiny body)), ((smooth rounded limbs)), ((soft balloon-like hands and feet)),</summary>

    ((chibi style)), ((super-deformed)), ((head-to-body ratio 1:2)), ((huge head, tiny body)), ((smooth rounded limbs)), ((soft balloon-like hands and feet)), ((plump cheeks)), ((childlike big eyes)), ((simplified facial features)), ((smooth matte skin, no pores)), ((soft pastel color palette)), ((gentle ambient lighting, natural shadows)), ((same facial expression, same pose, same background scene)), ((seamless integration with original environment, correct perspective and scale)), ((no outline or thin soft outline)), ((high resolution, sharp focus, 8k, ultra-detailed)), avoid: realistic proportions, long limbs, sharp edges, harsh lighting, wrinkles, blemishes, thick black outlines, low resolution, blurry, extra limbs, distorted face
</details>

<details>
<summary>预设ntr A cinematic scene inside a fast food restaurant at night.</summary>

    A cinematic scene inside a fast food restaurant at night.\n Foreground: a lonely table with burgers and fries, and a smartphone shown large and sharp on the table, clearly displaying the uploaded anime/game character image. A hand is reaching for food, symbolizing solitude.\n Midground: in the blurred background, a couple is sitting together and kiss. One of them is represented as a cosplayer version of the uploaded character:\n - If the uploaded character is humanoid, show accurate cosplay with hairstyle, costume, and signature props.\n - If the uploaded character is non-humanoid (mecha, creature, mascot, etc.), show a gijinka (humanized cosplay interpretation) that carries clear visual cues, costume colors, and props from the reference image (armor pieces, wings, ears, weapon, or iconic accessories).\n The other person is an ordinary japan human, and they are showing intimate affection (kissing, holding hands, or sharing food).\n Background: large glass windows, blurred neon city lights outside.\n Mood: melancholic, bittersweet, ironic, cinematic shallow depth of field.\n [reference: the uploaded image defines both the smartphone display and the cosplay design, with visible props emphasized] Image size is 585px 1024px.
</details>

<details>
<summary> 预设cos Create a highly realistic and meticulously detailed commercial photograph of a themed bedroom, entirely inspired by the adult character from the input illustration.</summary>

    Create a highly realistic and meticulously detailed commercial photograph of a themed bedroom, entirely inspired by the adult character from the input illustration.\n Image Completion Rule: If the input illustration is incomplete, first complete the character’s full-body image from head to toe. This completion must strictly adhere to the original artwork’s composition and pose, extending the character naturally without altering their form or posture. Ensure the overall appearance and all content within the scene are safe, healthy, and free from any inappropriate elements.\n The room’s aesthetic, including the color palette and decor, subtly reflects the character’s design. The scene must feature a highly realistic human cosplayer alongside a variety of commercial-grade merchandise, all based on the completed character image:\n The Cosplayer: A central element of the scene is a cosplayer whose appearance, hair, and makeup perfectly match the completed character image. They are wearing a meticulously crafted, high-quality costume that is an exact, real-world replica of the character’s outfit. The cosplayer is posed naturally within the room, for instance, sitting gracefully on a chair or on the edge of the bed, adding a sense of life and presence to the scene. The textures of the costume fabric and props should be rendered with maximum realism.\n Suede Body Pillow: On the bed, a normal rectangular, human-body-sized pillow made of soft suede material is prominently displayed. It is carefully positioned and angled directly towards the camera, ensuring the high-resolution, full-body print of the character on its surface is completely and clearly visible, showcasing the realistic texture of the fabric.\n 1/7 Scale PVC Figure: Inside an ultra-realistic figure display cabinet with glass doors, place a 1/7 scale PVC figure of the character. It should be mounted on a circular, transparent acrylic base without text, showcasing precise details in texture, material, and paintwork.\n Wall Scroll/Painting: On a prominent wall, hang a large, high-quality fabric wall scroll or a framed painting that displays a dynamic or elegant pose of the character.\n Q-Version Keychain: On a desk or hanging from a bag, include a small, cute Q-version (chibi style) acrylic keychain of the character, showing glossy reflections.\n Themed Rug: On the floor, place a circular or stylized rectangular rug. The rug’s design should be a tasteful, minimalist graphic or silhouette inspired by the character’s symbols or color scheme.\n Ceramic Mug: On a bedside table or the desk, place a ceramic mug with a high-quality print of the character’s portrait or Q-version likeness.\n Technical and Stylistic Requirements:\n Rendering Style: Render the entire scene in a detailed, lifelike style. Maintain highly precise details in the textures and materials of all merchandise, room elements, and the cosplayer’s costume.\n Environment and Depth: The scene should feature a natural depth of field. The cosplayer might be the primary focus, with other elements smoothly transitioning into a soft blur to enhance spatial realism.\n Lighting: The lighting should be soft, natural, and adaptive, simulating professional commercial photography. It should cast realistic shadows and highlights on the cosplayer, the room, and all objects.\n Camera Angle: The camera angle is strategically chosen to create a compelling composition that features the cosplayer as a primary subject, while also providing a clear, unobstructed view of the body pillow. The angle should be wide enough to capture the overall layout of the themed room and the placement of the other merchandise cohesively, creating a rich, lived-in feel.
</details>

<details>
<summary>预设jio The exact protagonist from the provided reference image, with identity lock on facial features, hairstyle, and all distinctive characteristics. The character is sitting on the ground in a side view, with both the torso and the fully extended outer leg (closer to the viewer) aligned and facing the same direction.</summary>

    The exact protagonist from the provided reference image, with identity lock on facial features, hairstyle, and all distinctive characteristics. The character is sitting on the ground in a side view, with both the torso and the fully extended outer leg (closer to the viewer) aligned and facing the same direction. **Full-figured limbs with soft, plump contours and supple skin.** The outer leg is stretched straight forward, lying flat on the ground with the foot relaxed. The inner leg (further from the viewer) is bent at the knee and positioned upright with the foot planted on the ground; part of this inner leg is naturally obscured from the viewer's perspective by the outer leg and the body. Extreme forced perspective low-angle shot, meticulously engineered so that the sole of the extended outer foot occupies over half of the entire image height, dramatically scaling to appear more than 3x larger than the character's head to intensely exaggerate the sense of depth and near-far scale. The character's extended outer foot is in razor-sharp focus. It features **exceptionally smooth, glossy skin with a delicate sheen and refined texture, showing subtle sweat effects with tiny dewy droplets glistening on the surface**. The sole is facing the viewer at a 45-degree angle. From the viewer's perspective, the arch of the foot curves inward towards the body, with the big toe (hallux) positioned on the side closest to the character's other leg and body. The five toes are arranged in correct anatomical order from largest to smallest moving outward, perfectly showcasing natural nail beds, delicate skin texture, and fine wrinkles. The skin appears incredibly smooth, soft, and has a healthy, supple, lifelike appearance. Arms are crossed over the chest, with realistic hand-painted details and a subtle translucent PVC material effect on the skin. **A fine layer of perspiration gives the skin a healthy glow and enhanced luminosity.** The background and environment are based on and match the provided reference image, maintaining its unique setting, lighting, and atmosphere
</details>


## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| 手办化 | 群员 | 否 | 群聊 | 使用自定义预设，需要带一张图或回复一张图片 |
| 手办化xx | 群员 | 否 | 群聊 | 同上，使用预设xx |
| 手办化@xxx/自己 | 群员 | 是 | 群聊 | 自动获取头像 |

### 效果图
如果有效果图的话
