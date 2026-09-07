# voice_assistant

> 语音合成（TTS）和语音识别（STT）助手

## 概览

- **文件数**: 1
- **类数**: 1
- **方法数**: 16
- **函数数**: 1

## 技能描述

语音合成（TTS）和语音识别（STT）助手

## 依赖

```bash
pip install edge-tts
pip install openai-whisper
pip install pydub
pip install sounddevice
pip install numpy
pip install scipy
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `action` | string | `` | 操作类型 (tts/stt/list_voices) (必填) |
| `text` | string | `` | 要合成的文本 (tts 操作需要) |
| `audio_file` | string | `` | 要识别的音频文件路径 (stt 操作需要) |
| `voice` | string | `` | 语音类型 (zh-CN-XiaoxiaoNeural/zh-CN-YunxiNeural/en-US-JennyNeural)，默认 zh-CN-XiaoxiaoNeural |
| `speed` | float | `` | 语速 0.5-2.0，默认 1.0 |
| `pitch` | string | `` | 音调 (default/high/low)，默认 default |
| `output_file` | string | `` | 输出文件路径，默认 ./output/audio_{timestamp}.mp3 |
| `language` | string | `` | 识别语言 (zh-CN/en-US)，默认 zh-CN |
| `sample_rate` | integer | `` | 采样率，默认 16000 |
| `silence_threshold` | float | `` | 静音检测阈值，默认 1.0 |

## 输出

| 字段 | 说明 |
|------|------|
| `audio_path` | 合成的音频路径 (tts) |
| `transcript` | 识别的文本内容 (stt) |
| `duration` | 音频时长(秒) |
| `voices` | 可用语音列表 (list_voices) |
| `processing_time` | 处理耗时 |

## 使用方法

```bash
python -m markflow.cli.commands execute voice_assistant [参数]
```

### 示例

```bash
# TTS 文本转语音
python -m markflow.cli.commands execute voice_assistant action="tts" text="你好，欢迎使用 MarkFlow"

# STT 语音识别
python -m markflow.cli.commands execute voice_assistant action="stt" audio_file="./audio.mp3"

# 列出可用语音
python -m markflow.cli.commands execute voice_assistant action="list_voices"
```

查看完整参数说明：

```bash
python -m markflow.cli.commands info voice_assistant
```

## 输出位置

生成的输出保存在 `skills/voice_assistant/output/` 目录下。

---

*文档自动生成于 2026-08-23 17:13:23*