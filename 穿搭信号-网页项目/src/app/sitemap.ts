import type { MetadataRoute } from "next";
import { PRODUCT_PAGE_URL } from "@/lib/public-site";

export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: PRODUCT_PAGE_URL, lastModified: "2026-09-11" }];
}
