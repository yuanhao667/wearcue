"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

const navItems = [
  { href: "/", label: "今日穿搭", icon: "○" },
  { href: "/closet", label: "穿搭灵感", icon: "□" },
];

type UserProfile = { nickname: string; avatar: string; gender?: "mens" | "womens"; invited?: boolean };
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
  const activeNavIndex = navItems.findIndex((item) => item.href === pathname);
  useEffect(() => {
    if (pathname === "/closet") router.prefetch("/");
  }, [pathname, router]);
  const savedProfile = useSyncExternalStore(subscribeProfile, profileSnapshot, () => "");
  let profile: UserProfile = emptyProfile;
  try { profile = savedProfile ? JSON.parse(savedProfile) : emptyProfile; } catch { profile = emptyProfile; }
  const [draft, setDraft] = useState({ nickname: "", avatar: "" });
  const [profileOpen, setProfileOpen] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!profileOpen) return;
    const closeMenu = (event: PointerEvent) => { if (!accountMenuRef.current?.contains(event.target as Node)) setProfileOpen(false); };
    document.addEventListener("pointerdown", closeMenu);
    return () => document.removeEventListener("pointerdown", closeMenu);
  }, [profileOpen]);

  async function chooseAvatar(file?: File) {
    if (!file || !file.type.startsWith("image/")) return;
    const source = URL.createObjectURL(file);
    const image = document.createElement("img");
    image.src = source;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 256;
    const context = canvas.getContext("2d");
    if (context) {
      const side = Math.min(image.naturalWidth, image.naturalHeight);
      context.drawImage(image, (image.naturalWidth - side) / 2, (image.naturalHeight - side) / 2, side, side, 0, 0, 256, 256);
      const avatar = canvas.toDataURL("image/jpeg", .82);
      const nextDraft = { ...draft, avatar };
      setDraft(nextDraft);
      saveProfile(nextDraft);
    }
    URL.revokeObjectURL(source);
  }

  function saveProfile(nextDraft = draft) {
    const nickname = nextDraft.nickname.trim().slice(0, 5);
    if (!nickname) return;
    const next = { ...profile, nickname, avatar: nextDraft.avatar };
    localStorage.setItem("wearcue_profile_v1", JSON.stringify(next));
    window.dispatchEvent(new Event("wearcue-profile"));
    setDraft({ nickname: next.nickname, avatar: next.avatar });
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    localStorage.removeItem("wearcue_profile_v1");
    window.dispatchEvent(new Event("wearcue-profile"));
    setProfileOpen(false);
    router.replace("/login");
  }

  const avatarLetter = profile.nickname.trim().charAt(0) || "我";
  const loggedIn = Boolean(profile.invited && profile.nickname && profile.gender);
  const nickname = draft.nickname.trim() || profile.nickname.trim() || "我";

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
        <div className="account-menu" ref={accountMenuRef}>
          <button className="account-avatar" onClick={() => { if (!loggedIn) { router.push("/login"); return; } if (!profileOpen) setDraft({ nickname: profile.nickname, avatar: profile.avatar }); setProfileOpen((current) => !current); }} aria-expanded={profileOpen} aria-haspopup="dialog" aria-label={loggedIn ? "查看个人资料" : "登录"} title={loggedIn ? "查看个人资料" : "登录"}>
            {profile.avatar ? <span className="avatar-photo" style={{ backgroundImage: `url(${profile.avatar})` }} /> : avatarLetter}
          </button>
          {profileOpen && <section className="profile-dialog" role="dialog" aria-label="个人资料">
            <div className="profile-menu-info">
              <div className="profile-menu-row"><span>昵称：<strong>{nickname}</strong></span></div>
              <div className="profile-menu-row"><span>性别：<strong>{profile.gender === "womens" ? "女" : "男"}</strong></span></div>
            </div>
            <label className="profile-upload"><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => void chooseAvatar(event.target.files?.[0])} />{draft.avatar ? "更换头像" : "上传头像"}</label>
            <button className="profile-logout" onClick={() => void logout()}>退出登录</button>
          </section>}
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
