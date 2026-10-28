"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

const navItems = [
  { href: "/", label: "今日穿搭", icon: "○" },
  { href: "/closet", label: "穿搭灵感", icon: "□" },
];

type UserProfile = { id?: string; nickname: string; avatar: string; gender?: "mens" | "womens"; invited?: boolean };
const emptyProfile: UserProfile = { nickname: "", avatar: "" };

export function subscribeProfile(callback: () => void) {
  window.addEventListener("wearcue-profile", callback);
  return () => window.removeEventListener("wearcue-profile", callback);
}

export function profileSnapshot() {
  return localStorage.getItem("wearcue_profile_v1") || "";
}

export function AppNav() {
  const pathname = usePathname();
  const router = useRouter();
  const [headerCollapsed, setHeaderCollapsed] = useState(false);
  const activeNavIndex = navItems.findIndex((item) => item.href === pathname);
  useEffect(() => {
    if (pathname === "/closet") router.prefetch("/");
  }, [pathname, router]);
  useEffect(() => {
    let lastY = window.scrollY;
    let frame = 0;

    function updateHeader() {
      const currentY = window.scrollY;
      if (currentY <= 12) {
        setHeaderCollapsed(false);
      } else if (currentY > lastY + 1) {
        setHeaderCollapsed(true);
      } else if (currentY < lastY - 1) {
        setHeaderCollapsed(false);
      }
      lastY = currentY;
      frame = 0;
    }
    function handleScroll() {
      if (!frame) frame = window.requestAnimationFrame(updateHeader);
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [pathname]);
  const savedProfile = useSyncExternalStore(subscribeProfile, profileSnapshot, () => "");
  let profile: UserProfile = emptyProfile;
  try { profile = savedProfile ? JSON.parse(savedProfile) : emptyProfile; } catch { profile = emptyProfile; }

  const avatarLetter = profile.nickname.trim().charAt(0) || "我";
  return (
    <>
      <header className={`paper-header${headerCollapsed ? " is-collapsed" : ""}`} style={{ backdropFilter: "blur(18px) saturate(135%)", WebkitBackdropFilter: "blur(18px) saturate(135%)" }}>
        <Link href="/" className="paper-wordmark" aria-label="WearCue 首页">
          <Image src="/brand/wearcue-logo-20260828.png" alt="WearCue" width={1774} height={887} priority />
        </Link>
        <nav aria-label="主导航" data-active={activeNavIndex >= 0 ? activeNavIndex : undefined}>
          {navItems.map((item, index) => (
            <Link className={activeNavIndex === index ? "active" : ""} href={item.href} key={item.href} prefetch>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="account-menu">
          <button
            className="account-avatar"
            id="home-tour-profile"
            onClick={() => router.push("/settings")}
            aria-label="设置"
            title="设置"
          >
            {profile.avatar ? <span className="avatar-photo" style={{ backgroundImage: `url(${profile.avatar})` }} /> : avatarLetter}
          </button>

        </div>
      </header>
      <nav className="paper-mobile-nav" aria-label="移动端主导航">
        {navItems.map((item) => (
          <Link className={pathname === item.href ? "active" : ""} href={item.href} key={item.href} prefetch>
            <span aria-hidden="true">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </>
  );
}
