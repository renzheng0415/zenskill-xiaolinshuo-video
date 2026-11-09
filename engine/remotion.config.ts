import { Config } from "@remotion/cli/config";

// 中间片用 JPEG q95 帧序列（scripts/render_parts.py 再用 ffmpeg 编码 crf12），预览/直接 render 时同样生效
Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(95);
Config.setCodec("h264");
Config.setCrf(16);
Config.setPixelFormat("yuv420p");
Config.setEntryPoint("src/index.ts");
