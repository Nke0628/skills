// @ts-check
// dependency-cruiserによるdeep moduleの強制。
//
// packagesルート配下の各パッケージはDEEP MODULE(深いモジュール)である:
// 小さなインターフェースの裏に多くの振る舞いを持つ。パッケージのPUBLIC
// SURFACE(公開面)はそのENTRY POINTS(エントリーポイント)、つまり
// パッケージルートにあるファイル群である。実装はSUBFOLDERS(サブフォルダ)
// に置かれ、非公開である(慣習として実装は`lib/`、テストは`tests/`に
// 置くが、実際にはどのサブフォルダも非公開扱いになる)。パッケージは
// 複数の小さなエントリーポイント(index.ts、client.ts、server.tsなど)
// を公開してもよい。1つの巨大なバレルindexにまとめるより、そちらを
// 優先すること。
//
// ここで編集する必要があるのはPACKAGES_ROOTだけである。

/** パッケージが置かれている場所。パッケージルート直下の子ディレクトリ1つにつき1パッケージ(フラット、ネストなし)。 */
const PACKAGES_ROOT = "src/packages";

// --- 派生パターン(編集不要) -------------------------------------
const R = PACKAGES_ROOT;
/**
 * パッケージの非公開内部: パッケージのサブフォルダ内にネストされたものすべて。
 * パッケージのルートファイルはそのエントリーポイントであり、ここではマッチ
 * させない: それらは外部からインポート可能なままである。
 */
const PACKAGE_INTERNALS = `^${R}/[^/]+/[^/]+/`;

/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "entrypoint-boundary-from-app",
      comment:
        "App/root code may import a package's entry points (its root files), but nothing inside its subfolders.",
      severity: "error",
      from: { pathNot: `^${R}/` }, // importer is NOT inside any package
      to: { path: PACKAGE_INTERNALS },
    },
    {
      name: "entrypoint-boundary-across-packages",
      comment:
        "A package's own files import each other freely, but may reach OTHER packages only through their entry points, never their internals.",
      severity: "error",
      // importer is inside a package ($1), but is not a test file
      from: { path: `^${R}/([^/]+)/`, pathNot: `^${R}/[^/]+/tests/` },
      to: {
        path: PACKAGE_INTERNALS,
        pathNot: `^${R}/$1/`, // same package → intra-package freedom
      },
    },
    {
      name: "tests-through-entrypoints",
      comment:
        "A package's tests exercise it through its entry points like everyone else: they may import any package's entry points and their own tests/ fixtures, but never any package's internals, not even their own.",
      severity: "error",
      from: { path: `^${R}/([^/]+)/tests/` }, // a test file, in package $1
      to: {
        path: PACKAGE_INTERNALS,
        pathNot: `^${R}/$1/tests/`, // own tests/ fixtures → allowed
      },
    },
    {
      name: "tests-folder-is-private",
      comment:
        "A package's tests/ folder is reachable only from tests: nothing else may import fixtures.",
      severity: "error",
      from: { pathNot: `^${R}/[^/]+/tests/` }, // importer is not itself a test
      to: { path: `^${R}/[^/]+/tests/` },
    },
    {
      name: "no-circular",
      comment: "No dependency cycles. Scope to `^${R}/` if you want to allow cycles outside packages.",
      severity: "error",
      from: {},
      to: { circular: true },
    },

    // --- レイヤリング(オプション、デフォルトで無効) ----------------------------------
    // インターフェース隠蔽は「どうやって」インポートするか(エントリー
    // ポイントを通して)を制御する。レイヤリングは「どのパッケージが
    // どのパッケージに依存してよいか」を制御する。独自のルールをここに
    // 追加する。例:
    //
    // {
    //   name: "ui-may-not-depend-on-billing",
    //   severity: "error",
    //   from: { path: `^${R}/ui/` },
    //   to:   { path: `^${R}/billing/` },
    // },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
    enhancedResolveOptions: {
      extensions: [".ts", ".tsx", ".js", ".jsx", ".json"],
    },
  },
};
