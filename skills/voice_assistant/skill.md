# voice_assistant

## 描述
语音合成（TTS）和语音识别（STT）助手

## 目的


## 输入
- **action**: 操作类型 (tts/stt/list_voices) (必填)
- **text**: 要合成的文本 (tts 操作需要)
- **audio_file**: 要识别的音频文件路径 (stt 操作需要)
- **voice**: 语音类型 (zh-CN-XiaoxiaoNeural/zh-CN-YunxiNeural/en-US-JennyNeural)，默认 zh-CN-XiaoxiaoNeural
- **speed**: 语速 0.5-2.0，默认 1.0
- **pitch**: 音调 (default/high/low)，默认 default
- **output_file**: 输出文件路径，默认 ./output/audio_{timestamp}.mp3
- **language**: 识别语言 (zh-CN/en-US)，默认 zh-CN
- **sample_rate**: 采样率，默认 16000
- **silence_threshold**: 静音检测阈值，默认 1.0

## 输出
- **audio_path**: 合成的音频路径 (tts)
- **transcript**: 识别的文本内容 (stt)
- **duration**: 音频时长(秒)
- **voices**: 可用语音列表 (list_voices)
- **processing_time**: 处理耗时

## 步骤
无

## 依赖
- edge-tts
- openai-whisper
- pydub
- sounddevice
- numpy
- scipy

## 版本
1.0.0
