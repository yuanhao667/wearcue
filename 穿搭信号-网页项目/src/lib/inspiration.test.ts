import { beforeEach, describe, expect, it } from "vitest";
import type { InspirationLook } from "@/domain/inspiration";
import { deleteInspirationLook, INSPIRATION_STORAGE_KEY, loadInspirationLooks, saveInspirationLook } from "./inspiration";

function look(id: string, updatedAt = "2026-08-24T00:00:00.000Z"): InspirationLook {
  return {
    id,
    title: `方案 ${id}`,
    note: "",
    imageDataUrl: "data:image/jpeg;base64,test",
    collection: "mens",
    createdAt: updatedAt,
    updatedAt,
    items: [{
      id: `${id}-item`,
      iconKey: "mens_top_tshirt_short",
      label: "短袖 T 恤",
      category: "top",
      colorName: "黑色",
      colorHex: "#171918",
      thickness: "thin",
      confidence: 0.9,
    }],
  };
}

describe("inspiration library storage", () => {
  beforeEach(() => window.localStorage.clear());

  it("saves newest looks first and overwrites an edited look", () => {
    saveInspirationLook(look("one", "2026-08-24T00:00:00.000Z"));
    saveInspirationLook(look("two", "2026-08-24T01:00:00.000Z"));
    saveInspirationLook({ ...look("one", "2026-08-24T02:00:00.000Z"), title: "更新后的方案" });

    expect(loadInspirationLooks().map((item) => item.id)).toEqual(["one", "two"]);
    expect(loadInspirationLooks()[0].title).toBe("更新后的方案");
  });

  it("deletes one look without affecting the others", () => {
    saveInspirationLook(look("one"));
    saveInspirationLook(look("two"));
    expect(deleteInspirationLook("one").map((item) => item.id)).toEqual(["two"]);
  });

  it("recovers from invalid browser data", () => {
    window.localStorage.setItem(INSPIRATION_STORAGE_KEY, "not-json");
    expect(loadInspirationLooks()).toEqual([]);
  });

  it("persists whether a look participates in daily recommendations", () => {
    saveInspirationLook({ ...look("daily"), recommendationEnabled: true });
    expect(loadInspirationLooks()[0].recommendationEnabled).toBe(true);
  });
});
