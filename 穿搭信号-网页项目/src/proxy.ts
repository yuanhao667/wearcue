import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "wearcue_session";
const PROFILE_PENDING_COOKIE = "wearcue_profile_pending";

export function proxy(request: NextRequest) {
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  const profilePending = Boolean(request.cookies.get(PROFILE_PENDING_COOKIE)?.value);
  if (!hasSession || profilePending) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/closet/:path*", "/inspiration/:path*", "/settings/:path*", "/outfit/:path*"],
};
