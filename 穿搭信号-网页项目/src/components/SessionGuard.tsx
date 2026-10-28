"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { apiJson } from "@/lib/backend-api";
import { clearClientSession } from "@/lib/client-auth";

export function SessionGuard() {
  const pathname = usePathname();
  useEffect(() => {
    // Product information is public and must never start an auth request.
    if (pathname === "/about") return;
    if (pathname === "/login") {
      clearClientSession();
      return;
    }
    let checking = false;
    const controller = new AbortController();
    const checkSession = async () => {
      if (checking || document.visibilityState === "hidden") return;
      checking = true;
      try {
        await apiJson("/auth/me", {
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]),
        });
      } catch { /* Only a confirmed 401 triggers recovery in apiJson. */ }
      finally { checking = false; }
    };
    void checkSession();
    window.addEventListener("focus", checkSession);
    window.addEventListener("pageshow", checkSession);
    document.addEventListener("visibilitychange", checkSession);
    return () => {
      controller.abort();
      window.removeEventListener("focus", checkSession);
      window.removeEventListener("pageshow", checkSession);
      document.removeEventListener("visibilitychange", checkSession);
    };
  }, [pathname]);
  return null;
}
