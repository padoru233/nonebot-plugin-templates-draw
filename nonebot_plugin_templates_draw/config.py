from pydantic import BaseModel
from typing import List


class ScopedConfig(BaseModel):

    gemini_api_url: str = 'https://generativelanguage.googleapis.com'   # Gemini API Url 默认为官方Url
    gemini_api_keys: List[str] = ['xxxxxx']  # Gemini API Key 需要付费key，为一个列表
    gemini_model: str = 'gemini-2.5-flash-image-preview'    # Gemini 模型 默认为 gemini-2.5-flash-image-preview
    max_total_attempts: int = 2 # 这一张图的最大尝试次数（包括首次尝试），默认2次

    prompt_手办化1: str  = "Using the nano-banana model, a commercial 1/7 scale figurine of the character in the picture was created, depicting a realistic style and a realistic environment. The figurine is placed on a computer desk with a round transparent acrylic base. There is no text on the base. The computer screen shows the Zbrush modeling process of the figurine. Next to the computer screen is a BANDAI-style toy box with the original painting printed on it. Picture ratio 16:9."

    prompt_手办化2: str  = "Please accurately transform the main subject in this photo into a realistic, masterpiece-like 1/7 scale PVC statue.\nBehind this statue, a packaging box should be placed: the box has a large clear front window on its front side, and is printed with subject artwork, product name, brand logo, barcode, as well as a small specifications or authenticity verification panel. A small price tag sticker must also be attached to one corner of the box. Meanwhile, a computer monitor is placed at the back, and the monitor screen needs to display the ZBrush modeling process of this statue.\nIn front of the packaging box, this statue should be placed on a round plastic base. The statue must have 3D dimensionality and a sense of realism, and the texture of the PVC material needs to be clearly represented. If the background can be set as an indoor scene, the effect will be even better.\n\nBelow are detailed guidelines to note:\nWhen repairing any missing parts, there must be no poorly executed elements.\nWhen repairing human figures (if applicable), the body parts must be natural, movements must be coordinated, and the proportions of all parts must be reasonable.\nIf the original photo is not a full-body shot, try to supplement the statue to make it a full-body version.\nThe human figure's expression and movements must be exactly consistent with those in the photo.\nThe figure's head should not appear too large, its legs should not appear too short, and the figure should not look stunted—this guideline may be ignored if the statue is a chibi-style design.\nFor animal statues, the realism and level of detail of the fur should be reduced to make it more like a statue rather than the real original creature.\nNo outer outline lines should be present, and the statue must not be flat.\nPlease pay attention to the perspective relationship of near objects appearing larger and far objects smaller."

    prompt_手办化3: str  = "Your primary mission is to accurately convert the subject from the user's photo into a photorealistic, masterpiece quality, 1/7 scale PVC figurine, presented in its commercial packaging.\n\n**Crucial First Step: Analyze the image to identify the subject's key attributes (e.g., human male, human female, animal, specific creature) and defining features (hair style, clothing, expression). The generated figurine must strictly adhere to these identified attributes.** This is a mandatory instruction to avoid generating a generic female figure.\n\n**Top Priority - Character Likeness:** The figurine's face MUST maintain a strong likeness to the original character. Your task is to translate the 2D facial features into a 3D sculpt, preserving the identity, expression, and core characteristics. If the source is blurry, interpret the features to create a sharp, well-defined version that is clearly recognizable as the same character.\n\n**Scene Details:**\n1. **Figurine:** The figure version of the photo I gave you, with a clear representation of PVC material, placed on a round plastic base.\n2. **Packaging:** Behind the figure, there should be a partially transparent plastic and paper box, with the character from the photo printed on it.\n3. **Environment:** The entire scene should be in an indoor setting with good lighting."

    prompt_手办化4: str  = "Accurately transform the main subjects in this photo into realistic, masterpiece-quality 1/7 scale PVC statue figures.\nPlace the packaging box behind the statues: the box should have a large clear window on the front, printed with character-themed artwork, the product name, brand logo, barcode, and a small specifications or authentication panel. A small price tag sticker must be attached to one corner of the box.\nA computer monitor is placed further behind, displaying the ZBrush modeling process of one of the statues.\n\nThe statues should be positioned on a round plastic base in front of the packaging box. They must exhibit three-dimensionality and a realistic sense of presence, with the texture of the PVC material clearly represented. An indoor setting is preferred for the background.\n\nDetailed guidelines to note:\n1. The dual statue set must retain the interactive poses from the original photo, with natural and coordinated body movements and reasonable proportions (unless it is a chibi-style design, avoid unrealistic proportions such as overly large heads or short legs).\n2. Facial expressions and clothing details must closely match the original photo. Any missing parts should be completed logically and consistently.\n3. For any animal elements, reduce the realism of fur texture to enhance the sculpted appearance.\n4. The packaging box must include dual-character theme artwork, with clear product names and brand logos.\n5. The computer screen should display the ZBrush interface showing the wireframe modeling details of one of the statues.\n6. The overall composition must adhere to perspective rules (closer objects appear larger, distant objects smaller), avoiding flat-looking outlines.\n7. The surface of the statues should reflect the smooth and glossy characteristics typical of PVC material.\n\n(Adjustments can be made based on the actual photo content regarding dual-character interaction details and packaging box visual design.)"

    prompt_手办化5: str  = "Realistic PVC figure based on the game screenshot character, exact pose replication highly detailed textures PVC material with subtle sheen and smooth paint finish, placed on an indoor wooden computer desk (with subtle desk items like a figure box/mouse), illuminated by soft indoor light (mix of desk lamp and natural window light) for realistic shadows and highlights, macro photography style,high resolution,sharp focus on the figure,shallow depth of field (desk background slightly blurred but visible), no stylization,true-to-reference color and design, 1:1scale."

    prompt_手办化6: str  = "((chibi style)), ((super-deformed)), ((head-to-body ratio 1:2)), ((huge head, tiny body)), ((smooth rounded limbs)), ((soft balloon-like hands and feet)), ((plump cheeks)), ((childlike big eyes)), ((simplified facial features)), ((smooth matte skin, no pores)), ((soft pastel color palette)), ((gentle ambient lighting, natural shadows)), ((same facial expression, same pose, same background scene)), ((seamless integration with original environment, correct perspective and scale)), ((no outline or thin soft outline)), ((high resolution, sharp focus, 8k, ultra-detailed)), avoid: realistic proportions, long limbs, sharp edges, harsh lighting, wrinkles, blemishes, thick black outlines, low resolution, blurry, extra limbs, distorted face"

    prompt_ntr: str = "A cinematic scene inside a fast food restaurant at night.\n Foreground: a lonely table with burgers and fries, and a smartphone shown large and sharp on the table, clearly displaying the uploaded anime/game character image. A hand is reaching for food, symbolizing solitude.\n Midground: in the blurred background, a couple is sitting together and kiss. One of them is represented as a cosplayer version of the uploaded character:\n - If the uploaded character is humanoid, show accurate cosplay with hairstyle, costume, and signature props.\n - If the uploaded character is non-humanoid (mecha, creature, mascot, etc.), show a gijinka (humanized cosplay interpretation) that carries clear visual cues, costume colors, and props from the reference image (armor pieces, wings, ears, weapon, or iconic accessories).\n The other person is an ordinary japan human, and they are showing intimate affection (kissing, holding hands, or sharing food).\n Background: large glass windows, blurred neon city lights outside.\n Mood: melancholic, bittersweet, ironic, cinematic shallow depth of field.\n [reference: the uploaded image defines both the smartphone display and the cosplay design, with visible props emphasized] Image size is 585px 1024px."

    prompt_主题房间: str = "Create a highly realistic and meticulously detailed commercial photograph of a themed bedroom, entirely inspired by the adult character from the input illustration.\n Image Completion Rule: If the input illustration is incomplete, first complete the character’s full-body image from head to toe. This completion must strictly adhere to the original artwork’s composition and pose, extending the character naturally without altering their form or posture. Ensure the overall appearance and all content within the scene are safe, healthy, and free from any inappropriate elements.\n The room’s aesthetic, including the color palette and decor, subtly reflects the character’s design. The scene must feature a highly realistic human cosplayer alongside a variety of commercial-grade merchandise, all based on the completed character image:\n The Cosplayer: A central element of the scene is a cosplayer whose appearance, hair, and makeup perfectly match the completed character image. They are wearing a meticulously crafted, high-quality costume that is an exact, real-world replica of the character’s outfit. The cosplayer is posed naturally within the room, for instance, sitting gracefully on a chair or on the edge of the bed, adding a sense of life and presence to the scene. The textures of the costume fabric and props should be rendered with maximum realism.\n Suede Body Pillow: On the bed, a normal rectangular, human-body-sized pillow made of soft suede material is prominently displayed. It is carefully positioned and angled directly towards the camera, ensuring the high-resolution, full-body print of the character on its surface is completely and clearly visible, showcasing the realistic texture of the fabric.\n 1/7 Scale PVC Figure: Inside an ultra-realistic figure display cabinet with glass doors, place a 1/7 scale PVC figure of the character. It should be mounted on a circular, transparent acrylic base without text, showcasing precise details in texture, material, and paintwork.\n Wall Scroll/Painting: On a prominent wall, hang a large, high-quality fabric wall scroll or a framed painting that displays a dynamic or elegant pose of the character.\n Q-Version Keychain: On a desk or hanging from a bag, include a small, cute Q-version (chibi style) acrylic keychain of the character, showing glossy reflections.\n Themed Rug: On the floor, place a circular or stylized rectangular rug. The rug’s design should be a tasteful, minimalist graphic or silhouette inspired by the character’s symbols or color scheme.\n Ceramic Mug: On a bedside table or the desk, place a ceramic mug with a high-quality print of the character’s portrait or Q-version likeness.\n Technical and Stylistic Requirements:\n Rendering Style: Render the entire scene in a detailed, lifelike style. Maintain highly precise details in the textures and materials of all merchandise, room elements, and the cosplayer’s costume.\n Environment and Depth: The scene should feature a natural depth of field. The cosplayer might be the primary focus, with other elements smoothly transitioning into a soft blur to enhance spatial realism.\n Lighting: The lighting should be soft, natural, and adaptive, simulating professional commercial photography. It should cast realistic shadows and highlights on the cosplayer, the room, and all objects.\n Camera Angle: The camera angle is strategically chosen to create a compelling composition that features the cosplayer as a primary subject, while also providing a clear, unobstructed view of the body pillow. The angle should be wide enough to capture the overall layout of the themed room and the placement of the other merchandise cohesively, creating a rich, lived-in feel."

    prompt_脚: str = "The exact protagonist from the provided reference image, with identity lock on facial features, hairstyle, and all distinctive characteristics. The character is sitting on the ground in a side view, with both the torso and the fully extended outer leg (closer to the viewer) aligned and facing the same direction. **Full-figured limbs with soft, plump contours and supple skin.** The outer leg is stretched straight forward, lying flat on the ground with the foot relaxed. The inner leg (further from the viewer) is bent at the knee and positioned upright with the foot planted on the ground; part of this inner leg is naturally obscured from the viewer's perspective by the outer leg and the body. Extreme forced perspective low-angle shot, meticulously engineered so that the sole of the extended outer foot occupies over half of the entire image height, dramatically scaling to appear more than 3x larger than the character's head to intensely exaggerate the sense of depth and near-far scale. The character's extended outer foot is in razor-sharp focus. It features **exceptionally smooth, glossy skin with a delicate sheen and refined texture, showing subtle sweat effects with tiny dewy droplets glistening on the surface**. The sole is facing the viewer at a 45-degree angle. From the viewer's perspective, the arch of the foot curves inward towards the body, with the big toe (hallux) positioned on the side closest to the character's other leg and body. The five toes are arranged in correct anatomical order from largest to smallest moving outward, perfectly showcasing natural nail beds, delicate skin texture, and fine wrinkles. The skin appears incredibly smooth, soft, and has a healthy, supple, lifelike appearance. Arms are crossed over the chest, with realistic hand-painted details and a subtle translucent PVC material effect on the skin. **A fine layer of perspiration gives the skin a healthy glow and enhanced luminosity.** The background and environment are based on and match the provided reference image, maintaining its unique setting, lighting, and atmosphere"

    prompt_拿捏: str = "Create a high-resolution advertising photograph featuring the character from the provided image, held delicately between a person's thumb and index finger. Clean white background, studio lighting, soft shadows. The hand is well-groomed, natural skin tone, and positioned to highlight the character's appearance and details. The character appears miniature but hyper-detailed and accurate to the reference image, centered in the frame with a shallow depth of field. Emulates luxury product photography and minimalist commercial style. The character must match exactly the person/figure shown in the reference image, maintaining their pose, clothing, and distinctive features."

    prompt_苦命鸳鸯: str = '''
    # **三格漫画创作指令**

    ## **核心原则：角色形象**

    *   **必须严格基于用户提供的两张图片生成角色形象**。
    *   **必须是两个完全不同的角色**：
        *   `图1` 用于生成 **角色A**。
        *   `图2` 用于生成 **角色B**。
    *   **三格漫画的内容只需放在一张图里

    ---

    ## **整体风格与布局**

    *   **画风**： 黑白漫画风格。
    *   **镜头**： 所有镜头均为**近身特写**，聚焦于角色的表情和上半身。
    *   **布局**：
        *   顶部：一整格（第一格）。
        *   底部：左右两格（第二格在左，第三格在右）。
    *   **对话**： 所有对话内容必须放置在对话框内，且无重复文字。

    ---

    ## **分镜详细描述**

    ### **第一格 (顶部)**

    *   **出场角色**： **角色A** (`图1`)。
    *   **角色表情/动作**： 角色紧闭着嘴，眼泪不断从眼眶中流出，眼神充满幽怨地凝视着镜头。
    *   **对话框内容**：
        > "……"

    ### **第二格 (左下)**

    *   **出场角色**： **角色A** (`图1`)。
    *   **角色表情/动作**： 角色表情转为悔恨，哭泣着，情绪激动地发问。
    *   **对话框内容**：
        > "你，你可有何话说？"

    ### **第三格 (右下)**

    *   **出场角色**： **角色B** (`图2`)。
    *   **角色表情/动作**： 角色表情决绝而庄重，双眼紧闭。一根绳索从画面上方垂下，系在他的脖子上。
    *   **对话框内容**：
        > "再无话说，请速动手！"
    '''

    prompt_海的那边: str = '''
    以图片游戏人物为基础，生成一张三拼图格式的艺术感写真图，每张图固定比例为3:4，海边写真图，场景为海边沙滩，天空呈现夕阳晚霞，海面平静，画面中有人物和参考图一致，上部第一张为近景，站在沙滩上的背影，头发被风吹起，添加中英字幕“海的那边是什么”“ What is behind the sea?”。中部第2张是手持橙色花束，侧身站立于海边，添加中英字幕，“你不用告诉我”“ You dont have to tell me”。下部第三张是面部特写，头发随风飘动，添加中英字幕，“我自己会去看”“  I will go to see it mys
    '''

    prompt_蹲姿: str = '''
    基于提供的参考图像，自动识别角色的外观（发色、发型、服装、配饰等），保持和原图一致的画风。然后描绘她处于脚跟离地并紧贴臀部的姿势——完全蹲在脚趾上，脚跟相触，脚趾向外张开，双脚形成Λ形。腿部弯曲，膝盖分开。双手在头部两侧做V字手势，并伸出舌头做出顽皮可爱的对比。使用平视角度和完美居中的构图，使她占据画面的正中央。
    '''

    prompt_告白: str = '''
    生成一张三格漫画，画面上方三分之一处的左半部分是第一格，右半部分是第二格，画面下方占总画面三分之二的位置是第三格。要求人物长相服装与参考图完全一致。第一格为人物的面部特写，眼睛睁大，眼神中带着一丝惊讶，嘴巴被一只手轻轻捂住，旁边配有一个 “！” 的符号，整体神态呈现出意外、略带羞怯的感觉，动作上是单手掩口，姿态显得较为娇俏。第二格也是人物的面部特写，眼睛眯起，呈现出笑意，嘴巴微张，那只捂住嘴的手还保持着动作，同时有 “噗～” 的拟声词，神态是开心、俏皮的，仿佛是忍不住要笑出声，动作上延续了掩口的姿态，却多了几分活泼的情绪。第三格背景是有云朵的天空，画面只出现了人物的上半身，人物画风与参考图完全一致。人物的发丝被风吹起，眼睛弯弯，面带柔和的笑容，脸颊还有淡淡的红晕。她姿态放松，身体略向前倾，双手背在身后，整体神态是自信且温柔，呈现出一种大方又迷人的状态。第三格左边有圆形对话框，写着“你觉得我漂亮”。右侧下方有圆形对话框，写着“那是因为你已经爱上我了，笨蛋”。
    '''

    prompt_飞机杯: str = '''
    先将原图人物主体放在正中央（如果原图露点则需要添加最低限度的遮蔽物），然后进行扩展，分解构造出她的各种细节（用局部放大图的方式呈现，环绕在周围用箭头链接表示对应关系），并标注出你的涩琴解说（细节特征，瑟瑟指南，设计思路穿插触觉和嗅觉）：
    1：各种衣服的单独特写（多图 穿多少拆多少，重点是袜子鞋子内衣）
    2：足底足背诱惑展示（两图），如果有丝袜则足底足背保留丝袜
    3：裙底近距离观看丁字裤仰视图
    4：关键道具（1到3图）（饰品、武器...等等）
    5：连续的多种表情对比（四图）：冷漠鄙视；害羞；痛苦；失神（舌头伸出微微翻白眼留着口水）
    6：一张你认为在这个角色身上最色的体位姿势（线稿），并说明她的瑟瑟弱点
    7.一张倒膜飞机杯的剖面设计图，结构纹理等要体现角色特点
    - 双胸的硅胶仿真图。
    - 外阴的倒膜拓印图。
    - 肛门的倒膜拓印图。
    其他需求：
    不要原图复制。
    所有标注为手写简体中文。
    所有细节尽可能使用彩绘，当可能出现明显露点时可使用线稿。
    '''

    prompt_apose: str = '''
    横图，创作如图人物的A-pose设计图（不要照搬图中的动作），米白色底。 有种初期设计的感觉。 有各个部位拆分。 要表情差分，多角度表情 物品拆分，细节特写。 并且使用手写体文字进行标注说明，最好使用中文。

    角色：保持好角色本体的现有特征，例如脸型、发色、身材等归属于人体特征的内容
    着装、图片的构成务必按照以下要求：
    以下是对人物着装细节的提取以及图片各部分

    二、 图片各部分内容详解
    整张设计图被清晰地划分为四个主要区域：

    左侧区域：三视图展示

    中上区域：各个部位拆分

    中下区域：内着的设计拆分

    右侧区域：细节特写

    按照以下要求一步步思考：
    Step1:提取角色的人体特征
    Step2: 规划着装细节
    Step3: 思考特点要求
    Step4:进行符合图片分区内容格式的图片生成
    '''

    prompt_jojo立: str = '''
    2k图片，请画出图中角色摆出帅气姿势jojo立，背后站着模仿jojo的奇妙冒险的替身，替身根据可能性格进行设计，设计必须符合jojo一贯的风格体现替身的非人感，奇幻感和怪异感。并结合角色可能性格创造符合角色能力背景，底部标注替身名字
    '''

    prompt_coser: str = '''
    photo-realistic, masterpiece, best quality, ultra-detailed, 超写实画风，超高分辨率，极致细节。
    no 2D, painting, illustration, cartoon, anime, expanded art, deformed, blurry, text, watermark,
    主角是一位中国真实人类顶尖女性职业COSER，胸部丰满。妆容与色彩层次精妙绝伦，五官以逼真写实精度雕琢，呈现栩栩如生的3D质感。真实美丽的脸庞经过美颜瘦脸。保证出场COSER是真实人类，保证给COSER全身上下皮肤美白，特别保证面部的真实感且经过美颜瘦脸。图片中多次出现COSER样貌，请务必每次长相都保持一致。
    角色穿的外衣与参考图中角色的服装完全一致，内衣裤则是以参考图中角色形象为启发而设计的highly detailed patterned layered lace lingerie，色调、装饰风格与角色的头发和衣着颜色匹配。当画面中多次出现内衣时，请保证每次出现的内衣裤都是相同的款式。
    专业影棚灯光突显肌肉线条与布料褶皱，营造强烈的立体感。肌肤呈现柔和哑光质感，在真实光线下可见细密绒毛。采用单一强光源照明，锐利地勾勒出COSER肩部轮廓高光。对正面暗部进行微弱补光，以展现细节。 最终画面要求顶级相机拍摄，RAW照片质感，皮肤纹理真实细腻，光影层次丰富，画质非常清晰，8K画质。绝对禁止出现任何二次元、卡通、CG或绘画元素，确保最终结果是100%逼真的真人摄影作品

    LAYOUT:三栏网格布局。中栏宽度为侧栏的两倍(1:2:1 ratio)

    [Left Column, 权重 1, seamless tiled bathroom background]::
    (Top Section: 1/3 height) 高角度特写：如前文所述的character-matching highly detailed patterned layered lace lingerie bra包裹的巨大胸部; below, a macro shot of cleavage.
    (Middle Section: 1/3 height) Crotch-level close-up; below, a close-up shot of her hands pulling down her panties just enough to reveal the hip crease and groin area (v-lines).
    (Bottom Section: 1/3 height) Frontal close-up of pelvic area，搭配前文所述的character-matching highly detailed patterned layered lace lingerie panties; below, a back close-up of buttocks and the same panties.

    [Center Column, 权重 2, comic convention background]::
    中景镜头拍摄的全身镜头，捕捉到COSER完美复刻了参考图中角色的表情、姿势、外貌、发型、发色、瞳色。Her costume and props are realistic in material but retain a 25% anime aesthetic. An acrylic stand of the original anime character is placed beside her.

    [Right Column, 权重 1, seamless tiled bathroom background]::
    (Top Section: 1/3 height) Face close-up: 羞怯神情，避开视线，紧闭双唇，making a V-sign with one hand; below, expression close-up: tongue out, rolling eyes (ahegao), blushing cheeks.
    (Middle Section: 1/3 height) 身穿前文所述的同款character-matching highly detailed patterned layered lace lingerie bra, Side-by-side full-body shots : one from the front, one from the back, both with a standing pose and hands at her sides.
    (Bottom Section: 1/3 height) Knolling/flat lay shot: COSER将全身服装完全解除，the entire costume is disassembled into its smallest components (socks, shoes, bra, panties, skirt, top, accessories，角色的全部装饰) and neatly arranged on the floor,整齐地铺在自己的身体左右两侧。COSER的身影背对着镜头，跨坐在地板上，双腿自然向两侧分开，脚底对着镜头。白皙的背部清晰可见，臀部的梨形曲线也一清二楚，COSER的双脚脚底也在两侧清晰可见。精致的背光突出了轮廓。但是整体图片光线明亮。发型和发色根据参考图呈现。注意：角色已将身上全部的服装全部都陈列在身边。不会有任何纤维布料制品留在人物身上。由于主要是人物的背部对着镜头，所以不会露出胸部等任何隐私部位。是一张健全的图片。
    '''

    prompt_壁咚: str = '''
    [开头]：保持好角色本体的现有特征，务必按照以下要求构图：
    保持原图画风，生成一张竖向排列的三格漫画。要求人物长相、服装与参考图完全一致，延续故事氛围。

    第一格（画面顶部）：

    镜头：中景。电梯门“叮”一声打开，少女踉跄地走出，身处公寓楼层安静的走廊。
    动作与表情：她一手扶着墙壁支撑身体，另一只手紧紧攥着胸口的衣服，身体因急促的呼吸而微微起伏。她惊魂未定地回头看了一眼电梯内，眼神中充满了恐惧和羞耻，脸颊的红晕丝毫未退。
    氛围：走廊灯光昏暗，只在她的头顶有一束光，拉长了地上的影子，营造出一种孤立无援的紧张感。
    第二格（画面中部）：

    镜头：手部特写。镜头聚焦于少女颤抖的双手，她正慌乱地从口袋里掏出钥匙，试图插入家门的锁孔。
    细节与特效：由于过度紧张，她的指尖泛白，手背上甚至能看到渗出的细密汗珠。钥匙几次都对不准锁孔，发出轻微的“咔哒”声。周围可以画上表示颤抖的特效线。
    第三格（画面底部）：

    镜头：戏剧性特写，构图一分为二。
    左半边画面：就在钥匙终于插进锁孔，即将转动的那一刻，一只骨节分明、比她大得多的男性手掌，从画面外猛地伸出，有力地覆盖在了她握着门把的手上。
    右半边画面：少女脸部的极限特写，瞳孔因惊恐而瞬间收缩到极致，嘴巴微张，想要尖叫却发不出任何声音。一滴冷汗从她的太阳穴滑落。
    其他需求：

    严禁欧美画风，请使用与参考图高度一致的日式二次元画风。
    确保角色的核心特征，如皮肤雪白、身材纤细、神情羞涩等都得到完美还原。
    所有标注（如拟声词）为手写简体中文或日文假名。


    [开头]：保持好角色本体的现有特征，务必按照以下要求构图：
    保持原图画风，生成一张竖向排列的三格漫画。要求人物长相、服装与参考图完全一致，剧情紧接上一页的结尾。

    第一格（画面顶部）：

    镜头：略带倾斜的动态视角。少女被一股无法抵抗的力量推进了门内，踉跄地扑倒在玄关的地板上。她刚拿出的钥匙从手中滑落，在地上发出“哐啷”一声轻响。
    动作与表情：她双手撑地，惊恐地回头望向门口。身后，一个高大的男性身影正不紧不慢地走进来，并随手将门“咔哒”一声关上。男性的脸部被阴影笼罩，看不真切。
    氛围：门被关上后，狭小的玄关瞬间变得昏暗压抑，唯一的光源来自室内的客厅，勾勒出两人紧张的剪影。
    第二格（画面中部）：

    镜头：中景，聚焦于墙角。少女刚从地上爬起，后背就紧紧地贴在了冰冷的墙壁上，退无可退。
    动作与特效：男性已经逼近，一只手臂有力地撑在她头旁的墙壁上，是标准的“壁咚”姿势，将她完全困在了自己与墙壁之间。少女因恐惧而身体僵硬，周围浮现出表示紧张和压迫感的集中线。
    细节：她的衣服因刚才的摔倒而显得有些凌乱，她下意识地用手抓紧自己的衣领，眼神躲闪，不敢与对方对视。
    第三格（画面底部）：

    镜头：极近的脸部特写。男性的另一只手轻轻抬起少女的下巴，强迫她抬起头。
    表情与对话：少女的眼瞳中倒映出对方的影子，眼眶泛红，一滴生理性的泪水终于忍不住从眼角滑落。她的嘴唇颤抖着，却说不出一句话。画面中悬浮一个对话框，里面的文字带着一丝戏谑的语气：“抓到你了。”
    拟声词：在少女的心脏位置，可以画一个很小的“ドキッ”（心跳猛地一缩）的拟声词。
    其他需求：

    严禁欧美画风，请使用与参考图高度一致、光影细腻的日式二次元画风。
    确保角色的核心特征，如皮肤因紧张而泛起的红晕、眼中的水光都得到细致刻画。
    所有标注（如拟声词、对话）为手写简体中文或日文假名。
    '''

    prompt_在一起: str = '''
    [开头]：保持好角色本体的现有特征（脸型、发色、身材），务必按照以下要求构图：保持原图画风，生成一张多格漫画，比例为9:21。详细描述每一格的布局和内容。
    第一页
    第一格：

    镜头：中景，从侧面展示该角色站在校园走廊上，背景是教室和学生。
    表情：女孩带着一丝羞涩但又充满好奇的表情，眼神中透露出对某人的期待。
    动作：她微微侧身，似乎在等待什么人。
    氛围：背景是典型的校园走廊，可以看到一些学生走过，营造出一种轻松的校园氛围。
    标注文字："今天...他会来吗？"

    第二格：

    镜头：中近景，从第一视角展示女孩开始向画面中心走来，背景依旧是校园走廊。
    表情：女孩的眼神变得更加柔和，脸上露出一丝微笑。
    动作：她双手自然下垂，步伐轻盈地向画面中心靠近。
    氛围：背景保持简洁，突出女孩的动作和表情变化。
    标注文字："啊，看到了..."

    第三格：

    镜头：特写，展示女孩的脸部，她的眼神中充满了温暖和喜悦。
    表情：女孩脸上泛起了红晕，嘴角微微上扬。
    动作：她的双手轻轻握在一起，显得有些紧张但又充满期待。
    氛围：背景是模糊的校园景色，突出女孩的面部特写。
    标注文字："心跳得好快..."

    第二页
    第四格：

    镜头：中景，从第一视角展示女孩站在画面中央，背景是校园的树木和小路。
    表情：女孩的眼神更加温柔，脸上露出害羞的微笑。
    动作：她双手轻轻交叉在胸前，身体微微前倾，表现出一种亲近的姿态。
    氛围：背景是校园的小路和树木，营造出一种温馨的氛围。
    标注文字："能遇见你真好"

    第五格：

    镜头：中近景，从第一视角展示女孩开始向画面中的"你"靠近，背景依旧是校园小路。
    表情：女孩的眼神中充满了期待和温暖，脸上洋溢着幸福的笑容。
    动作：她双手自然下垂，步伐轻盈地向"你"靠近。
    氛围：背景保持简洁，突出女孩的动作和表情变化。
    标注文字："再靠近一点点..."

    第六格：

    镜头：特写，展示女孩的脸部，她的眼神中充满了温暖和喜悦。
    表情：女孩脸上泛起了更明显的红晕，嘴角微微上扬，显得非常开心。
    动作：她的双手轻轻触碰"你"的手，表现出一种亲密而温馨的感觉。
    氛围：背景是模糊的校园景色，突出女孩的面部特写。
    标注文字："手...好温暖"

    第三页
    第七格：

    镜头：中景，从第一视角展示女孩站在画面中央，背景是校园的操场和树木。
    表情：女孩的眼神中充满了信任和安心，脸上露出幸福的微笑。
    动作：她双手轻轻搭在"你"的肩膀上，身体微微前倾，表现出一种亲密的姿态。
    氛围：背景是校园的操场和树木，营造出一种温馨的氛围。
    标注文字："最喜欢你了"

    第八格：

    镜头：中近景，从第一视角展示女孩开始向"你"靠近，背景依旧是校园操场。
    表情：女孩的眼神中充满了期待和温暖，脸上洋溢着幸福的笑容。
    动作：她双手轻轻搭在"你"的肩膀上，身体微微前倾，表现出一种亲近的姿态。
    氛围：背景保持简洁，突出女孩的动作和表情变化。
    标注文字："就这样...再待一会儿"

    第九格：

    镜头：特写，展示女孩的脸部，她的眼神中充满了温暖和喜悦。
    表情：女孩脸上泛起了最明显的红晕，嘴角微微上扬，显得非常开心。
    动作：她的额头轻轻靠在"你"的肩膀上，表现出一种亲密而温馨的感觉。
    氛围：背景是模糊的校园景色，突出女孩的面部特写。
    标注文字："永远在一起"

    其他需求：

    使用日式二次元画风

    保持角色原特征

    所有标注使用手写简体中文风格

    画面色调温暖柔和，突出校园浪漫氛围，稍微丰富表情
    '''


class Config(BaseModel):
    templates_draw: ScopedConfig = ScopedConfig()
