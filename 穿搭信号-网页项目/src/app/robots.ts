import type { MetadataRoute } from "next";
import { PUBLIC_SITE_URL } from "@/lib/public-site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/about", disallow: ["/api/", "/login", "/closet", "/inspiration", "/settings", "/outfit/"] },
    sitemap: `${PUBLIC_SITE_URL}/sitemap.xml`,
  };
}
