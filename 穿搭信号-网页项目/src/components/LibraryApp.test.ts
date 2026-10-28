import { describe, expect, it } from "vitest";
import { storedDiscoverySeason } from "./LibraryApp";

describe("library season session", () => {
  it("restores every valid season choice, including all seasons", () => {
    expect(storedDiscoverySeason({ getItem: () => "all" }, "spring-autumn")).toBe("all");
    expect(storedDiscoverySeason({ getItem: () => "summer" }, "spring-autumn")).toBe("summer");
  });

  it("uses the current-season fallback for a fresh or invalid session", () => {
    expect(storedDiscoverySeason({ getItem: () => null }, "winter")).toBe("winter");
    expect(storedDiscoverySeason({ getItem: () => "invalid" }, "spring-autumn")).toBe("spring-autumn");
  });
});
