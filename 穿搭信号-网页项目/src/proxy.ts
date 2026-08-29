import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "wearcue_session";

export function proxy(request: NextRequest) {
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  if (!hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/closet/:path*", "/inspiration/:path*", "/settings/:path*", "/outfit/:path*"],
};

