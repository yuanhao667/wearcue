export default function IconLabPage() {
  return (
    <main className="page-shell icon-lab-page">
      <section className="page-intro icon-lab-intro">
        <span className="eyebrow">SVG ASSET HANDOFF</span>
        <h1>图标由你定稿，<br />我来负责接入。</h1>
        <p>此前自动生成的样稿不再作为正式资产。男性衣物、女性衣物和配件是三套独立清单；厚薄仍由页面标签表达，不增加图标版本。</p>
      </section>

      <section className="sample-grid">
        <article className="sample-card"><div className="sample-card-title"><span>01</span><div><strong>男性衣物库</strong><small>/icons/garments/mens/&#123;base_icon_key&#125;.svg</small></div></div></article>
        <article className="sample-card"><div className="sample-card-title"><span>02</span><div><strong>女性衣物库</strong><small>/icons/garments/womens/&#123;base_icon_key&#125;.svg</small></div></div></article>
        <article className="sample-card"><div className="sample-card-title"><span>03</span><div><strong>独立配件库</strong><small>/icons/garments/accessories/&#123;icon_key&#125;.svg</small></div></div></article>
      </section>

      <section className="icon-rule-strip">
        <span>SVG VECTOR</span><span>统一 VIEWBOX</span><span>透明背景</span><span>文件名＝ICON_KEY</span>
      </section>
    </main>
  );
}
