import { describe, expect, it } from "vitest";
import { nextSettingsNudgeVisit } from "./AppNav";

describe("settings nudge visits", () => {
  it("shows only for the first three product entries", () => {
    expect(nextSettingsNudgeVisit(null)).toEqual({ visits: 1, visible: true });
    expect(nextSettingsNudgeVisit("2")).toEqual({ visits: 3, visible: true });
    expect(nextSettingsNudgeVisit("3")).toEqual({ visits: 4, visible: false });
  });
});
