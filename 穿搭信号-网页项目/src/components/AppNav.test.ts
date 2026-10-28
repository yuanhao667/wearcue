import { afterEach, expect, it, vi } from "vitest";
import { profileSnapshot, subscribeProfile } from "./AppNav";

afterEach(() => localStorage.clear());
it("updates the navigation profile when the account changes", () => {
  const callback = vi.fn();
  const unsubscribe = subscribeProfile(callback);
  localStorage.setItem("wearcue_profile_v1", '{"id":"another-user"}');
  window.dispatchEvent(new Event("wearcue-profile"));
  expect(callback).toHaveBeenCalledOnce();
  expect(profileSnapshot()).toContain("another-user");
  unsubscribe();
  window.dispatchEvent(new Event("wearcue-profile"));
  expect(callback).toHaveBeenCalledOnce();
});
