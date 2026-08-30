"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

const navItems = [
  { href: "/", label: "今日穿搭", icon: "○" },
  { href: "/closet", label: "穿搭灵感", icon: "□" },
];

type UserProfile = { id?: string; nickname: string; avatar: string; gender?: "mens" | "womens"; invited?: boolean };
const emptyProfile: UserProfile = { nickname: "", avatar: "" };

export function nextSettingsNudgeVisit(raw: string | null) {
  const previous = Number.parseInt(raw || "0", 10);
  const visits = (Number.isFinite(previous) && previous > 0 ? previous : 0) + 1;
  return { visits, visible: visits <= 3 };
}

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
  const countedAccount = useRef("");
  const [showSettingsNudge, setShowSettingsNudge] = useState(false);
  const activeNavIndex = navItems.findIndex((item) => item.href === pathname);
  useEffect(() => {
    if (pathname === "/closet") router.prefetch("/");
  }, [pathname, router]);
  const savedProfile = useSyncExternalStore(subscribeProfile, profileSnapshot, () => "");
  let profile: UserProfile = emptyProfile;
  try { profile = savedProfile ? JSON.parse(savedProfile) : emptyProfile; } catch { profile = emptyProfile; }

  const avatarLetter = profile.nickname.trim().charAt(0) || "我";
  const loggedIn = Boolean(profile.invited && profile.nickname && profile.gender);
  const accountKey = profile.id || `${profile.nickname.trim()}:${profile.gender || ""}`;

  useEffect(() => {
    if (pathname === "/login" || !loggedIn || !accountKey || countedAccount.current === accountKey) return;
    countedAccount.current = accountKey;
    try {
      const storageKey = `wearcue_settings_nudge_visits_v1:${accountKey}`;
      const next = nextSettingsNudgeVisit(localStorage.getItem(storageKey));
      localStorage.setItem(storageKey, String(next.visits));
      setShowSettingsNudge(next.visible);
    } catch {
      setShowSettingsNudge(true);
    }
  }, [accountKey, loggedIn, pathname]);

  return (
    <>
      <header className="paper-header">
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
            onClick={() => router.push(loggedIn ? "/settings" : "/login")}
            aria-label={loggedIn ? "设置" : "登录"}
            title={loggedIn ? "设置" : "登录"}
          >
            {profile.avatar ? <span className="avatar-photo" style={{ backgroundImage: `url(${profile.avatar})` }} /> : avatarLetter}
          </button>
          {showSettingsNudge && pathname !== "/settings" && pathname !== "/login" && <button className="settings-nudge" type="button" onClick={() => { setShowSettingsNudge(false); router.push("/settings"); }}>
            <strong>完善个人设置</strong><span>让推荐和人物效果更贴合你</span>
          </button>}
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
