# Design QA — 穿搭灵感页最终走查

- Source visual truth: user-provided desktop layout and portrait-card references in this thread
- Implementation capture: active Chrome local walkthrough page
- Viewport: 1728 × 813 CSS px, desktop
- Tested states: 春秋默认列表、冬季男装首卡、自定义季节菜单、旧版首卡详情页

## Layout and interaction

- Desktop grid resolves to four equal 288 px columns; existing 1100 px and 700 px breakpoints retain three and two columns.
- Global header spans the viewport edges and keeps its scroll-direction hide/show behavior.
- “全部穿搭／我的穿搭” stays centered and sticky without a visible backing panel; filters remain in normal document flow.
- Season and scene use WearCue custom listboxes instead of native selects. The selected option uses the product lime accent.
- Season choice is remembered in `sessionStorage`: a fresh tab starts from the current season, while detail-page navigation and return preserve the user's latest choice, including “全部季节”.
- Top upload action is removed. The bottom-right upload control links to `/inspiration`, shows the “上传穿搭灵感” bubble on hover, and uses staged elastic-circle then plus-wiggle motion.
- Settings keeps account actions inside the same card system: “退出登录” now sits in its own “账号管理” card instead of floating below the grid.
- The entry form now separates registration and login in a lightweight white “注册／登录” tab control. Registration is first and selected by default; its selected background reuses the same `#eef0f1` gray as the gender-icon circles.
- Home cards enter only after weather and recommendation data are ready. The left weather card rises first; the right recommendation card follows 120 ms later, using the same upward easing without changing layout dimensions.
- The home-card entrance animates only transform and opacity. Reduced-motion preference disables the animation and shows both cards immediately.

## Card fidelity

- All 12 visible cards render a real image; browser verification reports `complete: true` and non-zero `naturalWidth` for every card. Outer-card garment icon groups are absent.
- The legacy male and female cards reuse the existing `example_mens_ai.png` and `example_womens_ai.png` assets. No replacement image was generated.
- The outer card and its detail-page left image share the same backend image URL.
- The optimized existing male/female example images are also bundled as local static fallbacks. A missing image URL or failed backend image request switches to the matching audience image instead of exposing an empty card shell.
- Default state shows source and title only. Title-block bottom padding is 8 px, removing the empty semi-transparent strip below the title.
- Default overlay background blur computes to `none`; hover alone enables the masked background blur.
- Hover scales the image to 110% inside the clipped frame, reveals secondary metadata and actions, and does not add a black outline.
- Scene/style primary tags remain at the upper right. Season/gender/temperature stay between the two light divider lines in the expanded state.
- Like/home and delete are equal circular auxiliary actions; “查看详情” remains the wider action. Card-body click and the explicit detail link both open the detail page.
- Detail layout matches the production structure: the photo and its garment icons share the left visual card, with icons in one vertical column immediately to the photo's right.
- The separate right content card contains the complete preset analysis, structure points, dressing steps, layering notes, weather adjustment, and substitute guidance.
- Detail steps match abbreviated AI wording back to the correct garment before adding color and thickness, so visual-order sorting cannot attach hat or accessory attributes to a top.
- Detail icons and steps use the same head-to-foot order: headwear, tops, outer layers, bottoms, shoes, then utility accessories. Six legacy clothing records incorrectly stored in the accessory slot were repaired, removing false duplicate hat icons.
- No generated placeholder icons remain in the runtime library. The temporary short-boot and sandal SVGs were removed; legacy boot keys reuse the user-supplied high-top shoe asset, legacy sandal keys reuse the original sneaker asset, and all component slots are validated against their existing asset category.
- Unsupported accessories stay iconless instead of borrowing an unrelated fallback. The three legwear records (leg warmers, scrunched socks, knee socks) retain their labels and steps but no longer reuse the scarf icon; genuine scarves and shoulder wraps continue using it.
- The newly supplied backpack and glasses SVGs are registered as `acc_backpack` and `acc_glasses` without redrawing. Existing explicit backpack components now use the backpack icon; glasses, sunglasses, and common Chinese aliases resolve to the shared glasses icon.
- All 46 system photos were visually reviewed for eyewear. The 21 photos that visibly contain glasses now include exactly one `acc_glasses` detail component; eyewear appears after headwear and before clothing, including glasses worn on the eyes, cap brim, or head.
- Detail-icon optical sizing is calibrated globally by asset key: the oversized shorts/pants silhouettes are reduced, while the visually light leather-shoe and crossbody-bag silhouettes are enlarged. The supplied SVG paths remain unchanged.
- Eyewear, sunscreen, and umbrellas are regular-only accessories: they never show or persist “薄款／厚款”. Existing outfit and recognition records are migrated, system presets are cleaned, and cached/model output is normalized in both backend and UI rendering.

## Data and compatibility checks

- The male legacy sample is restored as winter with `outdoor + minimal`; the female legacy sample is summer with `sport`.
- Saved recommendations now persist season and style tags instead of falling back to spring/autumn.
- Every library source is filtered by the active role's audience. Switching to womens hides prior mens personal outfits as well as mens system presets; the stray `都市层次出行` personal record was deleted from the local walkthrough account.
- Registration is the only flow that accepts nickname and audience. Login accepts only the already-registered invite code and always restores the canonical saved nickname/audience; duplicate registration and unregistered login return distinct errors without changing existing account data.
- Historical detail records missing `steps`, `structure_points`, `completion_advice`, or other guide arrays render with safe defaults rather than crashing.
- Existing cached detail images are returned to the library without regeneration; legacy cards without an upload reuse the existing audience sample image.
- Image identity is used to merge duplicate cards after personal-first sorting. The legacy personal card wins over the system example, so the same photo appears only once while preserving the user-owned record.
- The male padded-jacket example now inherits its photo-bound winter metadata and content: winter, 2–12℃, outdoor + minimal, with the matching preset item breakdown and analysis.
- The no-photo compatibility merge is restricted to the two known legacy icon-only titles; newly created image-less outfits keep their own season, scene, style, and text.
- Photo-bound system recommendations preserve their reviewed component list after weather matching. Weather rules may add reminders or notes, but may not invent visible garments such as “天气适配上装” or “可脱穿薄外层”. Detail pages also prefer the loaded system record over a matching stale home-recommendation cache.
- All 46 packaged system images are content-ready: every entry has a non-empty component list, outfit analysis, replication formula and steps, outfit DNA, signature features, and locked features.

## Validation

- Browser DOM/visual check: 25 unique cards under “全部季节”; one visible copy of the male example image; 4 desktop columns; no default backdrop blur
- Custom dropdown open/select behavior: passed
- Outer card → detail page image reuse: passed; padded-jacket card is labeled winter
- Production comparison: online icon column measured at x767 beside the photo ending at x755; local visual match confirms the same photo-right vertical placement, passed
- Detail content: spring/autumn, summer, and winter system pages sampled in Chrome; each shows its original image, matching icon column, complete analysis, steps, layering notes, weather note, and substitute guidance, passed
- `夏季简约通勤 02` detail regression: only the five photographed components remain (glasses, striped T-shirt, crossbody bag, Bermuda shorts, loafers); no invented weather top/outerwear/bottom, passed
- `冬季运动出行 02` detail regression: leg-warmer copy and step remain, while the unrelated scarf icon is absent, passed
- Settings page DOM check: “账号管理” card contains the “退出登录” button, passed
- System detail manifest completeness: 46/46 passed; incomplete IDs: 0
- Home entrance capture at 40 ms, 180 ms, and 740 ms: left-to-right stagger and settled final state, passed
- Frontend Vitest: 16 files, 58 tests passed
- Backend pytest: 96 tests passed (1 existing Starlette deprecation warning)
- Runtime asset review: 50 SVGs total; 11 accessories, including “双肩包” and “眼镜 / 墨镜”, passed
- TypeScript: passed
- ESLint: passed
- Next.js production build: passed
- Browser flow “全部季节 → 详情页 → 返回穿搭灵感”: returned with “全部季节” and 23 matching cards, passed
- `git diff --check`: passed

final result: passed
