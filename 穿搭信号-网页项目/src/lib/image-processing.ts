export interface PreparedImage {
  dataUrl: string;
  dominantColor: string;
  width: number;
  height: number;
}

const MAX_EDGE = 1280;

export async function prepareImage(file: File): Promise<PreparedImage> {
  const source = await readFile(file);
  const image = await loadImage(source);
  const scale = Math.min(1, MAX_EDGE / Math.max(image.naturalWidth, image.naturalHeight));
  const width = Math.max(1, Math.round(image.naturalWidth * scale));
  const height = Math.max(1, Math.round(image.naturalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("当前浏览器无法处理这张图片");
  context.drawImage(image, 0, 0, width, height);
  const dominantColor = sampleDominantColor(context, width, height);
  const mime = file.type === "image/png" && file.size < 650_000 ? "image/png" : "image/jpeg";
  const dataUrl = canvas.toDataURL(mime, mime === "image/jpeg" ? 0.82 : undefined);
  return { dataUrl, dominantColor, width, height };
}

function readFile(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("图片读取失败，请重新选择"));
    reader.readAsDataURL(file);
  });
}

function loadImage(source: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("图片格式无法识别，请换一张 JPEG、PNG 或 WebP"));
    image.src = source;
  });
}

function sampleDominantColor(context: CanvasRenderingContext2D, width: number, height: number) {
  const sampleSize = 48;
  const canvas = document.createElement("canvas");
  canvas.width = sampleSize;
  canvas.height = sampleSize;
  const sample = canvas.getContext("2d", { willReadFrequently: true });
  if (!sample) return "#777b78";
  sample.drawImage(context.canvas, 0, 0, width, height, 0, 0, sampleSize, sampleSize);
  const pixels = sample.getImageData(0, 0, sampleSize, sampleSize).data;
  let red = 0;
  let green = 0;
  let blue = 0;
  let weight = 0;
  for (let index = 0; index < pixels.length; index += 16) {
    const alpha = pixels[index + 3] / 255;
    const brightness = (pixels[index] + pixels[index + 1] + pixels[index + 2]) / 3;
    if (alpha < 0.2 || brightness > 244) continue;
    red += pixels[index] * alpha;
    green += pixels[index + 1] * alpha;
    blue += pixels[index + 2] * alpha;
    weight += alpha;
  }
  if (!weight) return "#777b78";
  return `#${[red, green, blue].map((value) => Math.round(value / weight).toString(16).padStart(2, "0")).join("")}`;
}
