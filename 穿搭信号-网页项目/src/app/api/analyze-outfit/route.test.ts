import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

const onePixelPng = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";

describe("outfit image analysis route", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("returns an explicitly labelled demo result without an API key", async () => {
    vi.stubEnv("OPENAI_API_KEY", "");
    const response = await POST(new Request("http://localhost/api/analyze-outfit", {
      method: "POST",
      body: JSON.stringify({ imageDataUrl: onePixelPng, collection: "womens", dominantColor: "#7898aa", fileName: "look.png" }),
    }));
    const result = await response.json();

    expect(response.status).toBe(200);
    expect(result.mode).toBe("demo");
    expect(result.items).toHaveLength(3);
    expect(result.items.every((item: { iconKey: string }) => item.iconKey.startsWith("womens_") || item.iconKey.startsWith("acc_"))).toBe(true);
  });

  it("rejects unsupported image data", async () => {
    const response = await POST(new Request("http://localhost/api/analyze-outfit", {
      method: "POST",
      body: JSON.stringify({ imageDataUrl: "not-an-image", collection: "mens", dominantColor: "#111111" }),
    }));
    expect(response.status).toBe(400);
  });
});
