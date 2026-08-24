# HTMLレポートのフォーマット

アーキテクチャレビューは、OSの一時ディレクトリ内の単一の自己完結型HTMLファイルとして描画される。TailwindとMermaidはどちらもCDNから読み込む。Mermaidはグラフ状の図を確実に扱い、手作りのdivとインラインSVGはよりエディトリアルなビジュアル(質量図、断面図)を扱う。両方を組み合わせること: すべてをMermaidに頼ると、ありきたりな見た目になってしまう。

## スキャフォールド

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{{repo name}}のアーキテクチャレビュー</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      /* Tailwindではきれいにカバーできないもの向けの小さなカスタムレイヤー:
         破線のシーム線、手描き風の矢印の先端など */
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

## ヘッダー

リポジトリ名、日付、そしてコンパクトな凡例: 実線の箱 = モジュール、破線 = シーム、赤い矢印 = 漏れ、太い濃色の箱 = 深いモジュール。導入段落は不要。すぐに候補に入る。

## 候補カード

図が重みを担う。文章は簡潔で平易であり、(`/codebase-design`スキルの)用語集の言葉を気取らず使う。

各候補は1つの`<article>`とする:

- **Title**: 深化の内容を短く名付ける(例: "Order intakeパイプラインを畳み込む")。
- **Badge row**: 推奨度(`Strong` = emerald、`Worth exploring` = amber、`Speculative` = slate)、および依存カテゴリのタグ(`in-process`、`local-substitutable`、`ports & adapters`、`mock`)。
- **Files**: 等幅フォントのリスト、`font-mono text-sm`。
- **Before / After diagram**: 中心となる要素。2カラムを並べて配置。パターンは後述。
- **Problem**: 一文で。何が痛いか。
- **Solution**: 一文で。何が変わるか。
- **Wins**: 箇条書き、各項目6語以内。例: "テストが1つのインターフェースだけを叩く"、"Pricingロジックの漏れが止まる"、"浅いラッパーを4つ削除"。
- **ADR callout**(該当する場合): amber色の背景ボックスに1行。

説明の段落は書かない。図を理解するのに段落が必要なら、図を描き直す。

## 図のパターン

候補に合ったパターンを選ぶ。組み合わせて使う。すべての図を同じ見た目にしないこと。多様性自体が狙いの一部だ。

### Mermaidグラフ(依存関係・コールフローの主力)

「XがYを呼び、YがZを呼び、見ての通りの混乱」というポイントを示したいときは、Mermaidの`flowchart`か`graph`を使う。唐突な印象にならないよう、Tailwindでスタイリングしたカードで囲む。classDefで漏れているエッジを赤く、深いモジュールを濃色にスタイリングする。「前: 6往復、後: 1往復」のようなケースにはシーケンス図がよく合う。

```html
<div class="rounded-lg border border-slate-200 bg-white p-4">
  <pre class="mermaid">
    flowchart LR
      A[OrderHandler] --> B[OrderValidator]
      B --> C[OrderRepo]
      C -.leak.-> D[PricingClient]
      classDef leak stroke:#dc2626,stroke-width:2px;
      class C,D leak
  </pre>
</div>
```

### 手作りの箱と矢印(Mermaidのレイアウトが噛み合わないとき)

モジュールは枠線とラベル付きの`<div>`として表現する。矢印は、relativeなコンテナの上にabsolute配置したインラインSVGの`<line>`や`<path>`要素として表現する。「後」の図を、内部がグレーアウトした太枠の1つの深いモジュールのように見せたいときはこれを使う。Mermaidではその重みを正しく描画できないからだ。

### 断面図(層状の浅さに向く)

水平なバンド(`h-12 border-l-4`)を積み重ねて、呼び出しが通過する層を示す。前: 何もしていない薄い層が6つ。後: 統合された責務を示す太いバンドが1つ。

### 質量図(「実装と同じ幅のインターフェース」に向く)

モジュールごとに2つの矩形: 1つはインターフェースの表面積、もう1つは実装。前: インターフェースの矩形が実装の矩形とほぼ同じ高さ(浅い)。後: インターフェースの矩形は低く、実装の矩形は高い(深い)。

### コールグラフの折りたたみ

前: 関数呼び出しの木が入れ子の箱として描画されている。後: 同じ木が1つの箱に折りたたまれ、今や内部呼び出しとなったものが、その中に薄く表示される。

## スタイルガイダンス

- コーポレートダッシュボードではなく、エディトリアル寄りに。余白は多めに。見出しにはセリフ体も選択肢(`font-serif`はstone/slateとよく合う)。
- 色は控えめに: アクセント1色(emeraldかindigo)に加え、漏れには赤、警告にはamberを使う。
- 図の高さは~320px程度に抑え、ビフォー/アフターがスクロールなしで並んで無理なく収まるようにする。
- 図中のモジュールラベルには`text-xs uppercase tracking-wider`を使い、UIではなく模式図として読めるようにする。
- スクリプトはTailwindのCDNとMermaidのESMインポートのみ。それ以外レポートは静的である: アプリケーションコードはなく、Mermaid自体の描画以上のインタラクティブ性もない。

## Top recommendationセクション

1つの大きめのカード。候補名、理由を一文、そのカードへのアンカーリンク。それだけだ。

## トーン

平易で簡潔な文章にしつつ、アーキテクチャの名詞・動詞は`/codebase-design`スキルからそのまま持ってくる。簡潔さは逸脱の言い訳にならない。

**そのまま使う用語:** module、interface、implementation、depth、deep、shallow、seam、adapter、leverage、locality。

**言い換えないこと:** component、service、unit(module の代わりに)・API、signature(interface の代わりに)・boundary(seam の代わりに)・layer、wrapper(module を意味する場合の module の代わりに)。

**このスタイルに合う言い回し:**

- "Order intakeモジュールは浅い: インターフェースがほぼ実装と一致している。"
- "Pricingがシームを越えて漏れている。"
- "深化させる: インターフェースは1つ、テストする場所も1つ。"
- "アダプタが2つあることがシームを正当化する: 本番ではHTTP、テストではin-memory。"

**Winsの箇条書き**は、用語集の言葉で利益を語る: *「locality: バグが1つのモジュールに集中する」*、*「leverage: インターフェースは1つ、呼び出し箇所はN個」*、*「interfaceは縮小し、implementationがラッパーを吸収する」*。*「保守しやすくなる」*や*「コードがきれいになる」*とは書かないこと。これらの言葉は用語集になく、使う価値がないからだ。

曖昧なぼかし表現、前置き、「〜ということは注目に値する」のような言葉は書かない。文が箇条書きにできるなら、箇条書きにする。箇条書きが削れるなら、削る。ある用語が`/codebase-design`の用語集にないなら、新しい用語を作る前に、用語集にある言葉を探す。
