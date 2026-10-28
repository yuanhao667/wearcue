import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { TypingHeadline } from "./TypingHeadline";

afterEach(cleanup);

it("shows the full headline immediately and only underlines the outfit name", () => {
  const { container, rerender } = render(<TypingHeadline firstLine="圆号，今天穿什么" secondLine="看看今天的穿搭建议" secondLineHighlight="" />);
  expect(container.querySelectorAll(".typing-line")[1].textContent).toBe("看看今天的穿搭建议");
  rerender(<TypingHeadline firstLine="圆号，今日有雨" secondLine="试试这套浅灰工装日常" secondLineHighlight="浅灰工装日常" />);
  const lines = container.querySelectorAll<HTMLElement>(".typing-line");
  expect(lines[0].textContent).toBe("圆号，今日有雨");
  expect(lines[1].textContent).toBe("试试这套浅灰工装日常");
  expect(lines[0].style.fontSize).toBe(lines[1].style.fontSize);
  expect(container.querySelector(".headline-accent")?.textContent).toBe("浅灰工装日常");
  expect(container.querySelector(".typing-caret")).toBeNull();
});
