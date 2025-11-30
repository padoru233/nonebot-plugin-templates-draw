<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/nbp_logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <p><img src="https://github.com/A-kirami/nonebot-plugin-template/blob/resources/NoneBotPlugin.svg" width="240" alt="NoneBotPluginText"></p>
</div>

<div align="center">

# nonebot-plugin-templates-draw

_✨ NoneBot2 一个模板绘图插件 ✨_


<a href="./LICENSE">
    <img src="https://img.shields.io/github/license/padoru233/nonebot-plugin-templates-draw.svg" alt="license">
</a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-templates-draw">
    <img src="https://img.shields.io/pypi/v/nonebot-plugin-templates-draw.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="python">

</div>

> [!IMPORTANT]
> **收藏项目**，你的每一个Star⭐都是作者更新的动力～️

## 📖 介绍

基于Gemini API 的模板绘图插件
前身是 nonebot-plugin-figurine 进行了全面升级

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>
在 nonebot2 项目的根目录下打开命令行, 输入以下指令即可安装

    nb plugin install nonebot-plugin-templates-draw

</details>

<details>
<summary>使用包管理器安装</summary>
在 nonebot2 项目的插件目录下, 打开命令行, 根据你使用的包管理器, 输入相应的安装命令

<details>
<summary>pip</summary>

    pip install nonebot-plugin-templates-draw
</details>
<details>
<summary>pdm</summary>

    pdm add nonebot-plugin-templates-draw
</details>
<details>
<summary>poetry</summary>

    poetry add nonebot-plugin-templates-draw
</details>
<details>
<summary>conda</summary>

    conda install nonebot-plugin-templates-draw
</details>

打开 nonebot2 项目根目录下的 `pyproject.toml` 文件, 在 `[tool.nonebot]` 部分追加写入

    plugins = ["nonebot_plugin_templates_draw"]

</details>

## ⚙️ 配置

在 nonebot2 项目的`.env`文件中添加下表中的必填配置

| 配置项 | 必填 | 默认值 | 说明 |
|:-----:|:----:|:----:|:----:|
| TEMPLATES_DRAW__GEMINI_API_URL | 是 | - | 看下方注释 |
| TEMPLATES_DRAW__GEMINI_API_KEYS | 是 | ["xxxxxx"] | 需要付费key，填入你的多个API Key，例如 ['key1', 'key2', 'key3'] |
| TEMPLATES_DRAW__GEMINI_MODEL | 否 | gemini-2.5-flash-image-preview | Gemini 模型 默认为 gemini-2.5-flash-image-preview |
| TEMPLATES_DRAW__MAX_TOTAL_ATTEMPTS | 否 | 2 | 这一张图的最大尝试次数（包括首次尝试），默认2次，建议不小于Key数量，保证每个Key至少轮到1次 |
| TEMPLATES_DRAW__SEND_FORWARD_MSG | 否 | True | 使用合并转发来发图，默认开启 |
| TEMPLATES_DRAW__JAILBREAK_PROMPT | 否 | - | 看下方注释 |

- Gemini API Url 默认为官方完整 Url `https://generativelanguage.googleapis.com/v1beta`，可以替换为中转 `https://xxxxx.xxx/v1beta` 如果想使用 OpenAI 兼容层（不推荐），可以替换为 `https://generativelanguage.googleapis.com/v1beta/openai` 或者中转 `https://xxxxx.xxx/v1/chat/completions`
- ~~默认使用了很长的文本破限词，如果破限效果不好或者花费太高可以自定义JAILBREAK_PROMPT~~
- 放弃了JAILBREAK_PROMPT，使用上下文破限

### 推荐API

- https://openrouter.ai/ ~~充值10刀即可每天调用1000次免费模型~~
- 由于Google改变了价格，不再有免费调用：https://ai.google.dev/gemini-api/docs/pricing?hl=zh-cn#gemini-2.5-flash-image-preview
- 1次调用不到4毛CNY，建议配合 [插件管理系统](https://github.com/HibiKier/nonebot-plugin-zxpm) 等设置阻塞、CD、次数
- 自建API：覆盖如下请求参数
```
{
  "modalities": [
    "image",
    "text"
  ]
}
```

- 最新API：柏拉图AI

## 🎉 使用
### 指令表
| 指令 | 权限 | 需要@ | 范围 | 说明 |
|:-----:|:----:|:----:|:----:|:----:|
| 画图 | 群员 | 否 | 群聊 | 需要带图或回复图片或@某人 |
| 查看模板 | 群员 | 否 | 群聊 | 查看模板 或者 查看模板 <模板标识> |
| 添加/删除模板 | 群员 | 是 | 群聊 | 格式：添加模板 <模板标识> <提示词> |

- 默认提示词已经写入config，不可修改，可以通过用户模板覆盖同名模板

## 鸣谢
感谢真寻以及真寻群友提供的灵感

[![:name](https://count.getloli.com/@:nonebot-plugin-templates-draw?theme=gelbooru)](https://count.getloli.com/@nonebot-plugin-templates-draw?name=nonebot-plugin-templates-draw&theme=booru-qualityhentais&padding=7&offset=0&align=center&scale=1&pixelated=1&darkmode=auto)
