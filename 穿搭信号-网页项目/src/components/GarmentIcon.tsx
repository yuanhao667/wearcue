import type { GarmentItem } from "@/domain/types";

export function GarmentIcon({ icon }: { icon: GarmentItem["icon"] }) {
  if (["pants", "shorts", "skirt"].includes(icon)) {
    return (
      <svg viewBox="0 0 96 96" aria-hidden="true">
        <path d={icon === "skirt" ? "M37 24h22l11 53H26l11-53Z" : icon === "shorts" ? "M27 25h42l-2 36-18-5-2 18H31l-4-49Z" : "M29 22h38l-5 60H48l-2-38-5 38H27l2-60Z"} />
        <path className="detail" d="M31 31h34M48 24v20" />
      </svg>
    );
  }
  if (["sneaker", "boot"].includes(icon)) {
    return (
      <svg viewBox="0 0 96 96" aria-hidden="true">
        <path d={icon === "boot" ? "M31 20h28v37l13 7c6 3 5 12-2 12H25c-5 0-7-5-4-9l10-11V20Z" : "M21 57l15-6 8-23 12 3 5 19 17 10c6 4 3 14-4 14H25c-11 0-14-13-4-17Z"} />
        <path className="detail" d="M27 66h44M43 43l15 4" />
      </svg>
    );
  }
  if (["umbrella", "cap"].includes(icon)) {
    return (
      <svg viewBox="0 0 96 96" aria-hidden="true">
        {icon === "umbrella" ? (
          <>
            <path d="M16 48a32 32 0 0 1 64 0c-8-5-13-5-21 0-8-5-14-5-22 0-8-5-13-5-21 0Z" />
            <path className="detail" d="M48 22v50c0 8 12 9 13 0" />
          </>
        ) : (
          <path d="M23 53c0-22 11-33 27-33s26 13 26 34c-19 0-38 1-55 11-8 5-16-2 2-12Z" />
        )}
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 96 96" aria-hidden="true">
      <path d={icon === "down" || icon === "coat" ? "M32 19l16 8 16-8 17 18-10 11-6-6 7 42H24l7-42-6 6-10-11 17-18Z" : "M34 20l14 8 14-8 20 17-11 13-8-7v40H33V43l-8 7-11-13 20-17Z"} />
      <path className="detail" d={icon === "jacket" || icon === "down" || icon === "coat" ? "M48 28v54M34 54h28M38 31l10 8 10-8" : "M38 27c2 8 18 8 20 0"} />
    </svg>
  );
}
