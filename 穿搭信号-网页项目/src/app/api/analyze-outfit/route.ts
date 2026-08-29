import { NextResponse } from "next/server";
import { z } from "zod";
import { GARMENT_ICON_BY_KEY, GARMENT_ICON_MAP } from "@/config/garment-icon-map";
import type { ExtractedGarment, ImageAnalysisResult } from "@/domain/inspiration";

export const runtime = "nodejs";

const requestSchema = z.object({
  imageDataUrl: z.string().regex(/^data:image\/(jpeg|png|webp);base64,/).max(5_500_000),
  collection: z.enum(["mens", "womens"]),
  dominantColor: z.string().regex(/^#[0-9a-fA-F]{6}$/),
  fileName: z.string().max(160).optional().default(""),
});

const modelResultSchema = z.object({
  summary: z.string().max(180),
  items: z.array(z.object({
    iconKey: z.string(),
    colorName: z.string().max(20),
    colorHex: z.string(),
    thickness: z.enum(["thin", "regular", "thick"]),
    confidence: z.number().min(0).max(1),
    note: z.string().max(80).optional(),
  })).min(1).max(8),
});

export async function POST(request: Request) {
  const input = requestSchema.safeParse(await request.json().catch(() => null));
  if (!input.success) {
    return NextResponse.json({ error: "图片数据无效或体积过大，请换一张图片" }, { status: 400 });
  }

  if (!process.env.OPENAI_API_KEY) {
    return NextResponse.json(buildDemoResult(input.data));
  }

  try {
    const allowed = GARMENT_ICON_MAP.filter((item) => item.collection === input.data.collection || item.collection === "accessory");
    const keyList = allowed.map((item) => `${item.iconKey}:${item.label}`).join("\n");
    const response = await fetch("https://api.openai.com/v1/responses", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.OPENAI_VISION_MODEL ?? "gpt-5.4",
        store: false,
        input: [{
          role: "user",
          content: [
            {
              type: "input_text",
              text: `识别照片中清晰可见、实际穿着或用于搭配的服装、鞋履和饰品。只允许从下列 ${input.data.collection === "mens" ? "男性" : "女性"}衣物库输出 iconKey，不要推断人物性别，不要输出人体或背景物品。相同衣物不要重复。颜色使用中文基础色名和十六进制色值；厚度根据视觉材料判断，不确定时用 regular。\n\n可用 iconKey：\n${keyList}`,
            },
            { type: "input_image", image_url: input.data.imageDataUrl, detail: "high" },
          ],
        }],
        text: {
          format: {
            type: "json_schema",
            name: "garment_analysis",
            strict: true,
            schema: {
              type: "object",
              additionalProperties: false,
              required: ["summary", "items"],
              properties: {
                summary: { type: "string" },
                items: {
                  type: "array",
                  minItems: 1,
                  maxItems: 8,
                  items: {
                    type: "object",
                    additionalProperties: false,
                    required: ["iconKey", "colorName", "colorHex", "thickness", "confidence", "note"],
                    properties: {
                      iconKey: { type: "string", enum: allowed.map((item) => item.iconKey) },
                      colorName: { type: "string" },
                      colorHex: { type: "string", pattern: "^#[0-9A-Fa-f]{6}$" },
                      thickness: { type: "string", enum: ["thin", "regular", "thick"] },
                      confidence: { type: "number", minimum: 0, maximum: 1 },
                      note: { type: "string" },
                    },
                  },
                },
              },
            },
          },
        },
      }),
    });

    if (!response.ok) {
      const detail = await response.text();
      console.error("Vision analysis failed", response.status, detail.slice(0, 500));
      return NextResponse.json({ error: "图片识别服务暂时不可用，请稍后重试" }, { status: 502 });
    }

    const payload = await response.json() as OpenAIResponse;
    const outputText = payload.output
      ?.flatMap((item) => item.content ?? [])
      .find((content) => content.type === "output_text")?.text;
    const parsed = modelResultSchema.safeParse(outputText ? JSON.parse(outputText) : null);
    if (!parsed.success) throw new Error("Model result did not match schema");
    return NextResponse.json(toResult("ai", parsed.data.summary, parsed.data.items, input.data.collection));
  } catch (error) {
    console.error("Unable to analyse outfit", error);
    return NextResponse.json({ error: "没有得到可用的识别结果，请重试或手动添加衣物" }, { status: 502 });
  }
}

interface OpenAIResponse {
  output?: Array<{ content?: Array<{ type: string; text?: string }> }>;
}

function toResult(
  mode: ImageAnalysisResult["mode"],
  summary: string,
  items: Array<{ iconKey: string; colorName: string; colorHex: string; thickness: "thin" | "regular" | "thick"; confidence: number; note?: string }>,
  collection: "mens" | "womens",
): ImageAnalysisResult {
  const allowed = items.filter((item) => {
    const definition = GARMENT_ICON_BY_KEY.get(item.iconKey);
    return definition && (definition.collection === collection || definition.collection === "accessory");
  });
  return {
    mode,
    summary,
    items: allowed.map<ExtractedGarment>((item) => {
      const definition = GARMENT_ICON_BY_KEY.get(item.iconKey)!;
      return {
        id: crypto.randomUUID(),
        iconKey: definition.iconKey,
        label: definition.label,
        category: definition.category,
        colorName: item.colorName || "未命名颜色",
        colorHex: normaliseHex(item.colorHex),
        thickness: item.thickness,
        confidence: item.confidence,
        note: item.note,
      };
    }),
  };
}

function buildDemoResult(input: z.infer<typeof requestSchema>): ImageAnalysisResult {
  const lowerName = input.fileName.toLowerCase();
  const hasDress = input.collection === "womens" && /dress|裙|连衣/.test(lowerName);
  const keys = hasDress
    ? ["womens_onepiece_dress", "womens_shoe_pump", "acc_baseball_cap"]
    : input.collection === "mens"
      ? ["mens_top_tshirt_short", "mens_bottom_casual_pants", "mens_shoe_sneaker"]
      : ["womens_top_shirt", "womens_bottom_casual_pants", "womens_shoe_sneaker"];
  return toResult("demo", "已完成本地演示识别，请确认品类、颜色和薄厚后再保存。", keys.map((iconKey, index) => ({
    iconKey,
    colorName: index === 0 ? "图片取色" : index === 1 ? "深灰" : "黑色",
    colorHex: index === 0 ? input.dominantColor : index === 1 ? "#555b5e" : "#171918",
    thickness: index === 0 ? "thin" as const : "regular" as const,
    confidence: Number((0.72 - index * 0.06).toFixed(2)),
    note: "演示结果，可手动修正",
  })), input.collection);
}

function normaliseHex(value: string) {
  return /^#[0-9a-fA-F]{6}$/.test(value) ? value.toLowerCase() : "#777b78";
}
