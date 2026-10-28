import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
const create = vi.hoisted(() => vi.fn());
vi.mock("./bear-motion-renderer", () => ({ createBearMotionRenderer: create }));
vi.mock("next/image", () => ({ default: ({ priority: _priority, ...props }: Record<string, unknown>) => <img {...props} /> }));
import { TrackingBear } from "./TrackingBear";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.clearAllMocks(); });

it("keeps the static bear initially and loads motion only on the first pointer entry", async () => {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("any-hover"), addEventListener: vi.fn(), removeEventListener: vi.fn() }));
  const observer = class { observe() {} disconnect() {} };
  vi.stubGlobal("ResizeObserver", observer);
  vi.stubGlobal("IntersectionObserver", observer);
  create.mockResolvedValue({ draw: () => false, dispose: vi.fn() });
  const { container } = render(<TrackingBear />);
  expect(container.querySelector("img")).toBeInTheDocument();
  expect(create).not.toHaveBeenCalled();
  await act(async () => fireEvent.pointerEnter(container.firstElementChild!));
  expect(create).toHaveBeenCalledOnce();
  await act(async () => fireEvent.pointerEnter(container.firstElementChild!));
  expect(create).toHaveBeenCalledOnce();
});
