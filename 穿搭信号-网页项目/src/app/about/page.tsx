import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { DEVELOPER_PROFILE_URL, PRODUCT_PAGE_URL } from "@/lib/public-site";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "WearCue 天气穿搭助手｜根据天气与场景推荐穿什么",
  description: "WearCue 是独立开发者圆号开发的天气与场景穿搭 Web 应用，提供通勤、约会、旅行出行建议，支持穿搭图片识别、个人库及官方穿搭收藏。通过小红书私信申请邀请码。",
  alternates: { canonical: PRODUCT_PAGE_URL },
  robots: { index: true, follow: true },
};

const features = [
  { title: "把天气翻译成能穿的衣服", image: "today-outfit", alt: "WearCue 今日穿搭界面：天气、体感温度与通勤、约会、出行场景", text: "不只看一个温度数字。结合天气、体感温度和当天场景，查看短袖、长袖、裤装或外套等衣物的厚薄与搭配建议。通勤是优先打磨的场景，也保留约会和旅行出行需求。" },
  { title: "把图片里的灵感留下来", image: "photo-recognition", alt: "WearCue 穿搭照片上传与识别入口", text: "上传自己的穿搭照或有权使用的图片，AI 识别服装款式、颜色、薄厚及适用温度。确认或修改结果后保存到个人库，并选择是否参与首页推荐，在天气与场景匹配时再次看到。" },
  { title: "从穿什么，再到怎么搭", image: "outfit-guide", alt: "WearCue 穿搭方案：单品、穿搭步骤与温度调整说明", text: "查看官方穿搭推荐，点赞或收藏喜欢的搭配；通过 AI 分析和穿搭步骤了解单品如何组合。图里的衣服不一定就在自己的衣柜里，可以结合手边的衣物选择或替换。" },
];

export default function AboutPage() {
  return (
    <main className={styles.page}>
      <header className={styles.intro}>
        <p className={styles.eyebrow}>WearCue · 天气与场景穿搭助手</p>
        <h1>天气说 30℃，<br />今天到底穿什么？</h1>
        <p className={styles.lead}>把天气、体感温度和今天的安排，翻译成具体的穿衣建议。</p>
        <p>WearCue 是独立开发者圆号（GitHub：yuanhao667）开发的穿搭 Web 应用。先解决衣物厚薄与场景选择，再结合官方推荐和个人穿搭灵感，帮你决定今天怎么穿。</p>
        <div className={styles.actions}>
          <a className={styles.primary} href={DEVELOPER_PROFILE_URL} target="_blank" rel="noreferrer">小红书私信申请邀请码</a>
          <Link className={styles.secondary} href="/login" prefetch={false}>已有邀请码，进入体验</Link>
        </div>
        <p className={styles.note}>本页无需登录。实际使用仍需账号与邀请码；电脑、平板和手机浏览器均可访问，现阶段推荐优先在电脑上体验。</p>
      </header>

      <section aria-labelledby="features-heading">
        <h2 id="features-heading" className={styles.sectionTitle}>WearCue 现在能做什么</h2>
        {features.map((feature, i) => (
          <article className={styles.feature} key={feature.image}>
            <div>
              <p className={styles.number}>0{i + 1}</p>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </div>
            <figure>
              <Image src={`/product/${feature.image}.png`} alt={feature.alt} width={1440} height={1000} className={styles.screenshot} sizes="(max-width: 760px) 100vw, 640px" unoptimized />
              <figcaption>WearCue 实际界面示例；具体天气与推荐随使用条件变化。</figcaption>
            </figure>
          </article>
        ))}
      </section>

      <section className={styles.contexts} aria-labelledby="contexts-heading">
        <h2 id="contexts-heading">通勤、约会、旅行，问题不只有一种</h2>
        <dl>
          <div><dt>上班每天不知道穿什么？</dt><dd>先结合天气判断衣物厚薄，再选择通勤场景，参考搭配建议。早晚温差与办公室环境仍需按自己的体感调整。</dd></div>
          <div><dt>30℃约会，或者明天出去旅行？</dt><dd>相同温度下，不同安排需要不同搭配。WearCue 支持约会、出行等场景，不把所有穿搭都当作办公室着装。</dd></div>
          <div><dt>想找户外徒步穿搭？</dt><dd>可以查看出行场景的衣物和造型参考。但专业徒步还涉及路线、海拔、降雨和装备性能，不能只凭 App 推荐判断户外安全。</dd></div>
        </dl>
      </section>

      <section className={styles.faq} aria-labelledby="faq-heading">
        <h2 id="faq-heading">试用前，先说明白</h2>
        <h3>WearCue 是手机 App，还是网页工具？</h3>
        <p>这里介绍的是由圆号 / yuanhao667 开发、通过本网站访问的 Web 应用，不需要从应用商店下载。本项目的代码与产品说明可在 <a href="https://github.com/yuanhao667/wearcue" target="_blank" rel="noreferrer">GitHub 仓库</a>核对。</p>
        <h3>邀请码怎么申请？收费吗？</h3>
        <p>请私信<a href={DEVELOPER_PROFILE_URL} target="_blank" rel="noreferrer">开发者圆号的小红书个人账号</a>申请。计划招募 30 名免费试用者，AI 调用成本由开发者承担，因此保留邀请制，不承诺永久免费或无限使用。通过邮箱完成验证与账号登录；邮箱不是申请邀请码的渠道。</p>
        <h3>能收藏其他用户的穿搭、购买衣服吗？</h3>
        <p>目前支持点赞收藏官方推荐、保存个人穿搭；尚未开放用户社区和商城，不能收藏其他用户的社区穿搭，也不能直接购买推荐中的衣服。</p>
        <h3>AI 的识别与建议可以直接照单全收吗？</h3>
        <p>不能。图片识别可能有误，保存前可以确认或修改；衣物是否适合还需要结合体感、手边的衣服和实际活动判断。上传第三方图片前，请确认具有使用权限。</p>
      </section>

      <footer className={styles.footer}>
        <p>由独立开发者圆号持续迭代。当前已有朋友参与试用，部分反馈已融入改版；尚不以此宣称规模化留存或穿搭效果。</p>
        <p><a href="https://github.com/yuanhao667/wearcue" target="_blank" rel="noreferrer">查看项目与更新</a> · <a href={DEVELOPER_PROFILE_URL} target="_blank" rel="noreferrer">联系开发者</a> · <Link href="/login" prefetch={false}>登录 WearCue</Link></p>
        <p>产品说明更新于 2026 年 9 月 11 日。</p>
      </footer>
    </main>
  );
}
