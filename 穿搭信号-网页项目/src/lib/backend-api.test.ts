import { describe, expect, it } from "vitest";
import { parseError } from "./backend-api";

describe("parseError", () => {
  it("reads the backend error envelope instead of rendering an object", async () => {
    const response = new Response(JSON.stringify({ error: { message: "视觉模型响应超时" } }), { status: 503 });
    await expect(parseError(response)).resolves.toBe("视觉模型响应超时");
  });
});
