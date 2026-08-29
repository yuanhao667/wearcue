import { authenticatedBackendFetch } from "@/lib/server-auth";

export async function GET() {
  const response = await authenticatedBackendFetch("/auth/me");
  return new Response(response.body, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
  });
}

