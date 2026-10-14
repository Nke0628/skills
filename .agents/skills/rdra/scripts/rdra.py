#!/usr/bin/env python3
"""RDRA要件定義スキルの機械処理(標準ライブラリのみ)。

使い方: python3 .agents/skills/rdra/scripts/rdra.py <command> [--dir docs/rdra]

  init            docs/rdra を作成し、テンプレートと空の表を置く(既存ファイルは上書きしない)
  check [--json]  構造・参照・出典のチェック結果を出す
  gate {1,2,done} 判定条件を満たすか(満たせば終了コード0)
  set-phase N [--force 理由]  現在のフェーズを記録する(今より小さい番号には戻さない)
  accept KEY 理由  チェック指摘を「許容」として記録する
  reopen 理由     完成の記録を外す(完成後に表・質問を変えるとき)
  lint-request [--draft]  初期要望.txt(または初期要望.draft.txt)の形を点検する(致命があれば終了コード1)
  adopt [--replace]  人が見直した初期要望.draft.txt を初期要望.txt にする(印を消し、下書きを削除)
  next-qid        次の質問IDを出す
  html            questions.md から questions.html を生成する
  merge-answers   answers.json を questions.md に取り込む
  diagrams        表から diagrams.md を生成する
  analysis        analysis.md(チェック結果・重要UC・PIVOT)を生成する
  status          status.md を生成し、要約を出す
  prd             表と質問から関係者向けの prd.html を生成する
  mock            画面・UC・情報の属性から画面モック mock.html を生成する
"""
import argparse
import datetime
import itertools
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

TABLES = {
    "00_ゴール.md": {"ゴール": ["ID", "ゴール", "達成の判断基準", "説明"]},
    "01_要求.md": {"要求": ["ID", "種別", "要求", "説明", "ゴールID"]},
    "02_アクター.md": {"アクター": ["アクター", "説明"], "外部システム": ["外部システム", "説明"]},
    "03_BUC.md": {"BUC": ["業務", "BUC", "要求ID", "先", "アクティビティ", "次", "アクター", "UC", "画面",
                          "イベント", "外部システム", "情報", "条件"]},
    "04_情報.md": {"情報": ["コンテキスト", "情報", "説明", "属性", "状態モデル", "バリエーション"], "情報関連": ["情報", "関連先", "多重度"]},
    "05_状態.md": {"状態": ["コンテキスト", "状態モデル", "状態", "遷移先", "遷移UC"]},
    "06_条件.md": {"条件": ["コンテキスト", "条件", "説明", "バリエーション", "状態モデル"],
                  "バリエーション": ["コンテキスト", "バリエーション", "値"],
                  "条件の表": ["条件", "値", "結果"]},
}
TABLE_FILE = {t: f for f, ts in TABLES.items() for t in ts}
TAIL = ["出典", "質問"]
PRIORITIES = ["高", "中", "低"]
Q_STATES = ["未回答", "回答済", "反映済", "許容"]
UNRESOLVED = {"未回答", "回答済"}
SEVERITIES = ["致命", "警告", "情報"]
ANY_VALUE = "すべて"  # 条件の表で、軸の値を問わないことを表す
FLOW_DOWN = "↓"  # 03_BUC の次の列で、下の行のアクティビティへ進むことを表す


# ---------------------------------------------------------------- 読み込み

def split_cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", s)]


def parse_md_tables(path):
    """`## 見出し` の直後にある最初の表を {見出し: (列, [(セル, 行番号)])} で返す。"""
    tables = {}
    heading = None
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^##\s+(.+?)\s*$", lines[i])
        if m:
            heading = m.group(1)
            i += 1
            continue
        if lines[i].strip().startswith("|") and heading is not None and heading not in tables:
            header = split_cells(lines[i])
            rows = []
            j = i + 1
            if j < len(lines) and re.match(r"^\s*\|?\s*:?-", lines[j]):
                j += 1
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append((split_cells(lines[j]), j + 1))
                j += 1
            tables[heading] = (header, rows)
            i = j
            continue
        i += 1
    return tables


def multi(value):
    return [v.strip() for v in re.split(r"[、,]", value or "") if v.strip()]


def is_hyp(row):
    return row.get("出典", "") == "仮説"


NAME_COLS = {"ゴール": ["ID"], "要求": ["ID"], "アクター": ["アクター"], "外部システム": ["外部システム"],
             "BUC": ["BUC", "アクティビティ", "UC"], "情報": ["情報"], "情報関連": ["情報", "関連先"],
             "状態": ["状態モデル", "状態"], "条件": ["条件"], "バリエーション": ["バリエーション"],
             "条件の表": ["条件", "値"]}


def row_label(r):
    return f"{r['_table']}:" + "/".join(r[c] for c in NAME_COLS[r["_table"]] if r.get(c))


class Model:
    def __init__(self, d):
        self.dir = d
        self.format_issues = []
        self.t = {}
        for fname, tdefs in TABLES.items():
            p = d / fname
            parsed = parse_md_tables(p) if p.exists() else {}
            for tname, cols in tdefs.items():
                expect = cols + TAIL
                rows = []
                if tname not in parsed:
                    self.format_issues.append(
                        (f"{fname}#{tname}", f"表「{tname}」がない(`## {tname}` の直後に表を置く)", fname))
                else:
                    header, raw = parsed[tname]
                    if header != expect:
                        self.format_issues.append(
                            (f"{fname}#{tname}", f"列構成が違う。期待: {' | '.join(expect)}", fname))
                    else:
                        for cells, ln in raw:
                            if not any(cells):
                                continue
                            cells = (cells + [""] * len(expect))[:len(expect)]
                            r = dict(zip(expect, cells))
                            r["_loc"] = f"{fname}:{ln}"
                            r["_table"] = tname
                            rows.append(r)
                self.t[tname] = rows

        self.goals = {r["ID"]: r for r in self.t["ゴール"] if r["ID"]}
        self.reqs = {r["ID"]: r for r in self.t["要求"] if r["ID"]}
        self.actors = {r["アクター"]: r for r in self.t["アクター"] if r["アクター"]}
        self.exts = {r["外部システム"]: r for r in self.t["外部システム"] if r["外部システム"]}
        self.buc_rows = self.t["BUC"]
        self.infos = {r["情報"]: r for r in self.t["情報"] if r["情報"]}
        self.conds = {r["条件"]: r for r in self.t["条件"] if r["条件"]}
        self.vars = {r["バリエーション"]: r for r in self.t["バリエーション"] if r["バリエーション"]}
        self.cond_cells = {}  # 条件 -> 条件の表の行(順序保持)
        for r in self.t["条件の表"]:
            if r["条件"]:
                self.cond_cells.setdefault(r["条件"], []).append(r)

        self.bucs = {}  # (業務, BUC) -> rows(順序保持)
        for r in self.buc_rows:
            if r["BUC"]:
                self.bucs.setdefault((r["業務"], r["BUC"]), []).append(r)
        self.ucs = {}  # UC -> rows
        for r in self.buc_rows:
            if r["UC"]:
                self.ucs.setdefault(r["UC"], []).append(r)
        self.state_models = {}  # 状態モデル -> rows
        for r in self.t["状態"]:
            if r["状態モデル"]:
                self.state_models.setdefault(r["状態モデル"], []).append(r)

    def flow(self, group):
        """業務の中のアクティビティのつながり。先・次の列から作る。
        nodes: (BUC, アクティビティ) -> 行(表の順)。edges: [(元, 先)](元・先は nodes のキー)。
        issues: [(コード, 対象, 内容, 場所)] 次のラベルの参照切れ・先のラベルの重複など。"""
        nodes = {}
        for r in self.buc_rows:
            if r["業務"] == group and r["BUC"] and r["アクティビティ"]:
                nodes.setdefault((r["BUC"], r["アクティビティ"]), []).append(r)
        keys = list(nodes)
        labels, issues = {}, []
        for k, rows in nodes.items():
            for lb in dict.fromkeys(x for r in rows for x in multi(r["先"])):
                if lb == FLOW_DOWN:
                    issues.append(("R17", f"{k[0]}/{k[1]}", f"先に「{FLOW_DOWN}」は書けない(ラベルを書く)", rows[0]["_loc"]))
                elif lb in labels:
                    issues.append(("S08", f"{k[0]}/{k[1]}", f"先のラベル「{lb}」が「{labels[lb][1]}」と重複している", rows[0]["_loc"]))
                else:
                    labels[lb] = k
        edges, used = [], set()
        for idx, (k, rows) in enumerate(nodes.items()):
            for t in dict.fromkeys(x for r in rows for x in multi(r["次"])):
                if t == FLOW_DOWN:
                    if idx + 1 < len(keys):
                        edges.append((k, keys[idx + 1]))
                    else:
                        issues.append(("R16", f"{k[0]}/{k[1]}", f"次が「{FLOW_DOWN}」だが、業務「{group}」の下の行にアクティビティがない", rows[0]["_loc"]))
                elif t in labels:
                    edges.append((k, labels[t]))
                    used.add(t)
                else:
                    issues.append(("R16", f"{k[0]}/{k[1]}", f"次のラベル「{t}」が業務「{group}」の先の列にない", rows[0]["_loc"]))
        for lb, k in labels.items():
            if lb not in used:
                issues.append(("S09", f"{k[0]}/{k[1]}", f"先のラベル「{lb}」を次で指しているアクティビティがない", nodes[k][0]["_loc"]))
        return nodes, edges, issues

    def groups(self):
        return list(dict.fromkeys(g for g, _ in self.bucs))

    def all_rows(self):
        for rows in self.t.values():
            yield from rows

    def states_of(self, model):
        names = []
        for r in self.state_models.get(model, []):
            for s in [r["状態"]] + multi(r["遷移先"]):
                if s and s not in names:
                    names.append(s)
        return names

    def cond_axes(self, cond):
        """条件の軸を [(名前, 値の一覧)] で返す。バリエーション列の順、状態モデル列の順。"""
        r = self.conds.get(cond)
        if not r:
            return []
        return ([(v, multi(self.vars[v]["値"]) if v in self.vars else []) for v in multi(r["バリエーション"])]
                + [(sm, self.states_of(sm)) for sm in multi(r["状態モデル"])])

    def cell_combos(self, cond, row):
        """条件の表の1行が当てはまる値の組合せ。「すべて」は軸の値すべて、「/」はどれか。
        値の数が軸の数と違う、または軸にない値があれば None。"""
        axes = self.cond_axes(cond)
        vals = multi(row["値"])
        if len(vals) != len(axes):
            return None
        choices = []
        for (_, allowed), v in zip(axes, vals):
            vs = allowed if v == ANY_VALUE else [x.strip() for x in v.split("/")]
            if any(x not in allowed for x in vs):
                return None
            choices.append(vs)
        return list(itertools.product(*choices))

    def sm_holders(self, sm):
        """状態モデルを持つ情報。情報の状態モデル列で決める。"""
        return sorted(i for i, r in self.infos.items() if sm in multi(r["状態モデル"]))

    def uc_infos(self, uc):
        return sorted({i for r in self.ucs.get(uc, []) for i in multi(r["情報"])})

    def uc_state_models(self, uc):
        return sorted({m for m, rows in self.state_models.items()
                       for r in rows if uc in multi(r["遷移UC"])})


Q_HEAD = re.compile(r"^###\s+(Q-\d+)\s+\[(.+?)\]\s+\[フェーズ(\d)\]\s*(.*)$")
Q_FIELD = re.compile(r"^(対象|提案|根拠|観点|回答|状態):\s?(.*)$")
Q_CHOICE = re.compile(r"^\s+([A-Z])\)\s*(.*)$")


def parse_questions(path):
    qs = {}
    if not path.exists():
        return qs, []
    lines = path.read_text(encoding="utf-8").splitlines()
    cur = None
    for idx, line in enumerate(lines):
        m = Q_HEAD.match(line)
        if m:
            cur = {"id": m.group(1), "priority": m.group(2), "phase": int(m.group(3)),
                   "title": m.group(4).strip(), "fields": {}, "lines": {}, "choices": [],
                   "head_line": idx}
            qs[cur["id"]] = cur
            continue
        if line.startswith("#"):
            cur = None
            continue
        if cur is None:
            continue
        m = Q_FIELD.match(line)
        if m:
            cur["fields"][m.group(1)] = m.group(2).strip()
            cur["lines"][m.group(1)] = idx
            continue
        m = Q_CHOICE.match(line)
        if m:
            cur["choices"].append({"key": m.group(1), "text": m.group(2).strip()})
    return qs, lines


def q_status(q):
    return q["fields"].get("状態", "")


# ---------------------------------------------------------------- 状態ファイル

def load_state(d):
    p = d / ".state.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"phase": 0, "force": [], "accepted": {}, "done": False}


def save_state(d, st):
    (d / ".state.json").write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- チェック

class Issue:
    def __init__(self, code, phase, severity, target, msg, loc=""):
        self.code, self.phase, self.severity = code, phase, severity
        self.target, self.msg, self.loc = target, msg, loc

    @property
    def key(self):
        return f"{self.code}:{self.target}"

    def to_dict(self):
        return {"key": self.key, "code": self.code, "phase": self.phase, "severity": self.severity,
                "target": self.target, "message": self.msg, "location": self.loc}


def run_checks(m, qs, phase):
    out = []

    def add(code, ph, sev, target, msg, loc="", max_phase=9):
        if ph <= phase <= max_phase or ph == 0:
            out.append(Issue(code, ph, sev, target, msg, loc))

    # 書式
    for target, msg, loc in m.format_issues:
        add("F01", 0, "致命", target, msg, loc)
    for q in qs.values():
        if q["priority"] not in PRIORITIES:
            add("Q01", 0, "致命", q["id"], f"優先度が不正: {q['priority']}")
        if q_status(q) not in Q_STATES:
            add("Q02", 0, "致命", q["id"], f"状態が不正: {q_status(q)!r}({'/'.join(Q_STATES)})")
        for f in ("提案", "根拠"):
            if not q["fields"].get(f):
                add("Q03", 0, "致命", q["id"], f"{f}がない")

    # 出典・質問の紐付け
    for r in m.all_rows():
        src, qref = r.get("出典", ""), multi(r.get("質問", ""))
        target = row_label(r)
        if not (src in ("要望", "回答", "仮説") or re.match(r"^資料:.+", src)):
            add("S01", 0, "致命", target, f"出典が不正: {src!r}(要望/資料:<ファイル名>/回答/仮説)", r["_loc"])
        if src == "仮説" and not qref:
            add("S02", 0, "致命", target, "仮説の行に質問IDがない", r["_loc"])
        for qid in qref:
            if qid not in qs:
                add("S03", 0, "致命", target, f"存在しない質問ID: {qid}", r["_loc"])
        if src == "仮説" and qref and all(qid in qs and q_status(qs[qid]) in ("反映済", "許容") for qid in qref):
            add("S04", 0, "警告", target, "質問は解決済みだが行が仮説のまま(反映漏れ)", r["_loc"])

    # 重複
    for tname, col in (("ゴール", "ID"), ("要求", "ID"), ("アクター", "アクター"), ("外部システム", "外部システム"),
                       ("情報", "情報"), ("条件", "条件"), ("バリエーション", "バリエーション")):
        seen = set()
        for r in m.t[tname]:
            if r[col] in seen:
                add("S05", 0, "致命", f"{tname}:{r[col]}", "同じ名前が重複している", r["_loc"])
            seen.add(r[col])
    for a in m.actors:
        if a in m.exts:
            add("S06", 0, "警告", a, "アクターと外部システムに同じ名前がある")

    # 参照切れ
    for r in m.buc_rows:
        for col, pool, code in (("アクター", m.actors, "R01"), ("外部システム", m.exts, "R02"),
                                ("情報", m.infos, "R03"), ("条件", m.conds, "R04"), ("要求ID", m.reqs, "R05")):
            for v in multi(r[col]):
                if v not in pool:
                    add(code, 0, "致命", f"BUC:{v}", f"{col}「{v}」が定義されていない", r["_loc"])
    for g in m.groups():
        nodes, edges, issues = m.flow(g)
        for code, target, msg, loc in issues:
            add(code, 0, "警告" if code == "S09" else "致命", target, msg, loc)
        outs = {a for a, _ in edges}
        for (gg, buc), rows in m.bucs.items():
            if gg != g:
                continue
            acts = [k for k in nodes if k[0] == buc]
            for k in acts[:-1]:
                if k not in outs:
                    add("P113", 1, "警告", f"{k[0]}/{k[1]}",
                        f"BUCの途中のアクティビティに次がない(下へ進むなら「{FLOW_DOWN}」、飛ぶならラベル)", nodes[k][0]["_loc"])
    for r in m.t["要求"]:
        for g in multi(r["ゴールID"]):
            if g not in m.goals:
                add("R11", 0, "致命", f"要求:{r['ID']}", f"ゴールID「{g}」が定義されていない", r["_loc"])
    for r in m.t["情報関連"]:
        for col in ("情報", "関連先"):
            if r[col] and r[col] not in m.infos:
                add("R06", 0, "致命", f"情報関連:{r[col]}", f"情報「{r[col]}」が定義されていない", r["_loc"])
    for r in m.t["状態"]:
        for uc in multi(r["遷移UC"]):
            if uc not in m.ucs:
                add("R07", 0, "致命", f"状態:{uc}", f"遷移UC「{uc}」が03_BUCにない", r["_loc"])
        if multi(r["遷移UC"]) and not multi(r["遷移先"]):
            add("R08", 0, "致命", f"状態:{r['状態モデル']}/{r['状態']}", "遷移UCがあるのに遷移先がない", r["_loc"])
    for i, r in m.infos.items():
        for sm in multi(r["状態モデル"]):
            if sm not in m.state_models:
                add("R12", 0, "致命", f"情報:{i}", f"状態モデル「{sm}」が05_状態にない", r["_loc"])
        for v in multi(r["バリエーション"]):
            if v not in m.vars:
                add("R13", 0, "致命", f"情報:{i}", f"バリエーション「{v}」が06_条件にない", r["_loc"])
    for r in m.t["条件"]:
        for v in multi(r["バリエーション"]):
            if v not in m.vars:
                add("R09", 0, "致命", f"条件:{v}", f"バリエーション「{v}」が定義されていない", r["_loc"])
        for sm in multi(r["状態モデル"]):
            if sm not in m.state_models:
                add("R10", 0, "致命", f"条件:{sm}", f"状態モデル「{sm}」が定義されていない", r["_loc"])
    for c, rows in m.cond_cells.items():
        if c not in m.conds:
            add("R14", 0, "致命", f"条件の表:{c}", f"条件「{c}」が 06_条件 の条件にない", rows[0]["_loc"])
            continue
        axes = m.cond_axes(c)
        if not axes:
            add("R15", 0, "致命", f"条件の表:{c}", "条件に軸(バリエーション・状態モデル)がないのに条件の表がある", rows[0]["_loc"])
            continue
        seen = {}
        for r in rows:
            combos = m.cell_combos(c, r)
            if combos is None:
                names = "、".join(a for a, _ in axes)
                add("R15", 0, "致命", row_label(r),
                    f"値が軸({names})に合わない。軸の順に1つずつ、軸の値・「{ANY_VALUE}」・「/」区切りで書く", r["_loc"])
                continue
            dup = [x for x in combos if x in seen]
            if dup:
                add("S07", 0, "致命", row_label(r),
                    f"組合せ「{'、'.join(dup[0])}」が {seen[dup[0]]} と重複している", r["_loc"])
            for x in combos:
                seen.setdefault(x, r["_loc"])
        missing = [x for x in itertools.product(*(vs for _, vs in axes)) if x not in seen]
        if missing:
            more = f" ほか{len(missing) - 3}件" if len(missing) > 3 else ""
            add("P307", 3, "警告", f"条件の表:{c}",
                f"組合せが抜けている: {' / '.join('、'.join(x) for x in missing[:3])}{more}", rows[0]["_loc"])

    # フェーズ1
    if not m.goals:
        add("P112", 1, "致命", "ゴール", "ゴールがない(最重要要求・背景から作る)", "00_ゴール.md")
    goal_reqs = {g for r in m.t["要求"] for g in multi(r["ゴールID"])}
    for g, r in m.goals.items():
        if g not in goal_reqs:
            add("P110", 1, "致命", g, "ゴールにつながる要求がない", r["_loc"])
        if not r["達成の判断基準"]:
            add("P111", 1, "警告", g, "ゴールの達成の判断基準がない", r["_loc"])
    for q, r in m.reqs.items():
        if r["種別"] in ("機能", "非機能") and not multi(r["ゴールID"]):
            add("P109", 1, "警告", q, "要求がどのゴールにもつながっていない", r["_loc"])
    for (gyomu, buc), rows in m.bucs.items():
        if not any(r["アクティビティ"] for r in rows):
            add("P101", 1, "致命", buc, "BUCにアクティビティがない", rows[0]["_loc"])
        if not any(multi(r["要求ID"]) for r in rows):
            add("P106", 1, "警告", buc, "BUCがどの要求にもつながっていない", rows[0]["_loc"])
    for r in m.buc_rows:
        if r["アクティビティ"] and not multi(r["アクター"]) and not multi(r["外部システム"]):
            add("P102", 1, "致命", f"{r['BUC']}/{r['アクティビティ']}", "アクティビティにアクター(または外部システム)がない", r["_loc"])
    used_actors = {a for r in m.buc_rows for a in multi(r["アクター"])}
    used_exts = {e for r in m.buc_rows for e in multi(r["外部システム"])}
    used_reqs = {q for r in m.buc_rows for q in multi(r["要求ID"])}
    for a, r in m.actors.items():
        if a not in used_actors:
            add("P103", 1, "警告", a, "アクターがどのBUCにも登場しない", r["_loc"])
    for e, r in m.exts.items():
        if e not in used_exts:
            add("P104", 1, "警告", e, "外部システムがどのBUCにも登場しない", r["_loc"])
    for q, r in m.reqs.items():
        if q not in used_reqs:
            add("P105", 1, "警告", q, "要求がどのBUCにもつながっていない", r["_loc"])
    used_infos_any = {i for r in m.buc_rows for i in multi(r["情報"])}
    for i, r in m.infos.items():
        if i not in used_infos_any:
            add("P107", 1, "警告", i, "情報がどのアクティビティでも扱われていない", r["_loc"], max_phase=1)
    for sm in m.state_models:
        if len(m.states_of(sm)) < 2:
            add("P108", 1, "警告", sm, "状態モデルの状態が1つしかない")

    # フェーズ2
    used_infos_uc = {i for r in m.buc_rows if r["UC"] for i in multi(r["情報"])}
    for i, r in m.infos.items():
        if i not in used_infos_uc:
            add("P201", 2, "致命", i, "情報がどのUCにもつながっていない(登録・参照するUCがない)", r["_loc"])
        if not r["属性"]:
            add("P206", 2, "警告", i, "情報に属性がない", r["_loc"])
        if not r["コンテキスト"]:
            add("P210", 2, "警告", i, "情報のコンテキストが空", r["_loc"])
    for sm, rows in m.state_models.items():
        if not any(multi(r["遷移UC"]) for r in rows):
            add("P202", 2, "致命", sm, "状態モデルに遷移させるUCがない", rows[0]["_loc"])
        outgoing = {r["状態"] for r in rows if multi(r["遷移先"])}
        for s in m.states_of(sm):
            if s not in outgoing:
                add("P208", 2, "情報", f"{sm}/{s}", "遷移先のない状態(終端で正しいか確認)")
        holders = set(m.sm_holders(sm))
        if not holders:
            add("P211", 2, "警告", sm, "状態モデルを持つ情報がない(04_情報の状態モデル列)", rows[0]["_loc"])
        for uc in dict.fromkeys(u for r in rows for u in multi(r["遷移UC"])):
            if holders and uc in m.ucs and not holders & set(m.uc_infos(uc)):
                add("P209", 2, "警告", f"{sm}/{uc}",
                    f"状態を変えるUCが、状態を持つ情報({'、'.join(sorted(holders))})を扱っていない", m.ucs[uc][0]["_loc"])
    for uc, rows in m.ucs.items():
        if not any(multi(r["画面"]) or multi(r["イベント"]) for r in rows):
            add("P203", 2, "致命", uc, "UCに画面もイベントもない(タイマー起動はイベントに「タイマー」)", rows[0]["_loc"])
        if not m.uc_infos(uc):
            add("P205", 2, "警告", uc, "UCがどの情報も扱っていない", rows[0]["_loc"])
        for r in rows:
            if multi(r["画面"]) and not multi(r["アクター"]):
                add("P204", 2, "警告", f"{uc}/画面", "画面があるのにアクターがない", r["_loc"])
            evs = [e for e in multi(r["イベント"]) if not e.startswith("タイマー")]
            if evs and not multi(r["外部システム"]):
                add("P204", 2, "警告", f"{uc}/イベント", "イベントがあるのに外部システムがない", r["_loc"])
    if len(m.infos) > 1:
        related = {r[c] for r in m.t["情報関連"] for c in ("情報", "関連先")}
        for i, r in m.infos.items():
            if i not in related:
                add("P207", 2, "警告", i, "情報が他のどの情報とも関連していない", r["_loc"])

    # フェーズ3
    used_conds = {c for r in m.buc_rows for c in multi(r["条件"])}
    used_vars = {v for r in m.t["条件"] for v in multi(r["バリエーション"])}
    held_vars = {v for r in m.infos.values() for v in multi(r["バリエーション"])}
    for c, r in m.conds.items():
        if c not in used_conds:
            add("P301", 3, "警告", c, "条件がどのアクティビティ・UCにもつながっていない", r["_loc"])
        if not multi(r["バリエーション"]) and not multi(r["状態モデル"]):
            add("P302", 3, "警告", c, "条件の軸(バリエーション・状態モデル)がない", r["_loc"])
        if not r["コンテキスト"]:
            add("P305", 3, "警告", c, "条件のコンテキストが空", r["_loc"])
    for v, r in m.vars.items():
        if len(multi(r["値"])) < 2:
            add("P303", 3, "警告", v, "バリエーションの値が2つ未満", r["_loc"])
        if v not in used_vars:
            add("P304", 3, "警告", v, "バリエーションがどの条件にも使われていない", r["_loc"])
        if v not in held_vars:
            add("P306", 3, "情報", v, "バリエーションをどの情報も持っていない(ルールの区分なら問題ない)", r["_loc"])
    return out


def unresolved(qs, priorities):
    return [q for q in qs.values() if q["priority"] in priorities and q_status(q) in UNRESOLVED]


def evaluate_gate(d, gate):
    st = load_state(d)
    m = Model(d)
    qs, _ = parse_questions(d / "questions.md")
    phase = st["phase"]
    issues = [i for i in run_checks(m, qs, phase) if i.key not in st["accepted"]]
    reasons = []
    if gate in ("1", "2"):
        need = int(gate)
        if phase < need:
            reasons.append(f"現在のフェーズは{phase}。フェーズ{need}の生成が先")
        hi = unresolved(qs, ["高"])
        if hi:
            reasons.append(f"優先度・高の未解決: {', '.join(q['id'] for q in hi)}")
        for i in issues:
            if i.severity == "致命" and i.phase <= need:
                reasons.append(f"[{i.key}] {i.msg} ({i.loc})")
    else:
        if phase < 3:
            reasons.append(f"現在のフェーズは{phase}。フェーズ3の生成が先")
        hm = unresolved(qs, ["高", "中"])
        if hm:
            reasons.append(f"優先度・高・中の未解決: {', '.join(q['id'] for q in hm)}")
        hyp = {}
        for r in m.all_rows():
            if is_hyp(r):
                hyp.setdefault(TABLE_FILE[r["_table"]], []).append(r["_loc"].rsplit(":", 1)[1])
        if hyp:
            reasons.append("仮説の行が残っている: " + "、".join(
                f"{f} {len(ls)}行(L{','.join(ls)})" for f, ls in hyp.items()))
        for i in issues:
            if i.severity in ("致命", "警告"):
                reasons.append(f"[{i.key}] {i.msg} ({i.loc})")
    return reasons


# ---------------------------------------------------------------- 図

class Ids:
    def __init__(self):
        self.m = {}

    def __call__(self, kind, name):
        k = (kind, name)
        if k not in self.m:
            self.m[k] = f"{kind}{len(self.m) + 1}"
        return self.m[k]


def ql(s):
    return '"' + str(s).replace('"', "#quot;") + '"'


HYP_STYLE = "classDef hyp stroke-dasharray:5 5,stroke:#d97706,color:#92400e"


def system_name(d):
    p = d / "初期要望.txt"
    if p.exists():
        lines = p.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("# システム名"):
                for nxt in lines[i + 1:]:
                    if nxt.strip().startswith("#"):
                        break
                    if nxt.strip():
                        return nxt.strip()
    return "対象システム"


def mermaid(body):
    return "```mermaid\n" + "\n".join(body) + "\n```\n"


def diagram_context(m, sysname):
    ids = Ids()
    b = ["flowchart LR", f"  sys([{ql(sysname)}])"]
    hyps = []
    for a, r in m.actors.items():
        n = ids("a", a)
        b.append(f"  {n}[{kl('アクター', a)}] --- sys")
        if is_hyp(r):
            hyps.append(n)
    for e, r in m.exts.items():
        n = ids("e", e)
        b.append(f"  sys --- {n}[[{kl('外部システム', e)}]]")
        if is_hyp(r):
            hyps.append(n)
    b += kind_classes(ids)
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def diagram_requirements(m):
    ids = Ids()
    b = ["flowchart LR"]
    hyps = []
    for g, r in m.goals.items():
        n = ids("g", g)
        b.append(f"  {n}{{{{{ql(f'{g} {r['ゴール']}')}}}}}")
        if is_hyp(r):
            hyps.append(n)
    for q, r in m.reqs.items():
        n = ids("r", q)
        b.append(f"  {n}[{ql(f'{q} [{r['種別']}] {r['要求']}')}]")
        if is_hyp(r):
            hyps.append(n)
        for g in multi(r["ゴールID"]):
            if g in m.goals:
                arrow = "-.->" if is_hyp(r) else "-->"
                b.append(f"  {ids('g', g)} {arrow} {n}")
    seen = set()
    for (g, buc), rows in m.bucs.items():
        bn = ids("b", buc)
        b.append(f"  {bn}([{ql(buc)}])")
        for r in rows:
            for q in multi(r["要求ID"]):
                if q in m.reqs and (q, buc) not in seen:
                    seen.add((q, buc))
                    arrow = "-.->" if is_hyp(r) else "-->"
                    b.append(f"  {ids('r', q)} {arrow} {bn}")
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def diagram_business_context(m):
    """業務の枠の中にBUCを置き、関わるアクター・外部システムとつなぐ。"""
    ids = Ids()
    b = ["flowchart LR"]
    hyps, links = [], []
    by_g = {}
    for (g, buc), rows in m.bucs.items():
        by_g.setdefault(g, []).append((buc, rows))
    for g, bucs in by_g.items():
        b.append(f"  subgraph {ids('g', g)}[{ql(g)}]")
        for buc, rows in bucs:
            bn = ids("b", buc)
            b.append(f"    {bn}([{ql(buc)}])")
            if rows and all(is_hyp(r) for r in rows):
                hyps.append(bn)
            for w, kind in [(a, "a") for r in rows for a in multi(r["アクター"])] + \
                           [(e, "e") for r in rows for e in multi(r["外部システム"])]:
                hyp = all(is_hyp(r) for r in rows
                          if w in multi(r["アクター"]) + multi(r["外部システム"]))
                link = (kind, w, bn, hyp)
                if not any(l[:3] == link[:3] for l in links):
                    links.append(link)
        b.append("  end")
    for kind, w, bn, hyp in links:
        arrow = "-.-" if hyp else "---"
        if kind == "a":
            b.append(f"  {ids('a', w)}[{kl('アクター', w)}] {arrow} {bn}")
        else:
            b.append(f"  {bn} {arrow} {ids('e', w)}[[{kl('外部システム', w)}]]")
    b += kind_classes(ids)
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def activities(rows):
    acts = {}
    for r in rows:
        if r["アクティビティ"]:
            acts.setdefault(r["アクティビティ"], []).append(r)
    return acts


def diagram_flow(m, group, buc=None, wrap=None):
    """アクティビティをアクターのレーンに置き、先・次の列のとおりに矢印でつなぐ。
    buc を渡すとそのBUCだけを描き、ほかのBUCとのつながりは「BUC「X」へ/から」で示す。
    wrap: アクティビティがこの数を超えたらレーンの中を縦に並べる(PRD用)"""
    ids = Ids()
    nodes, edges, _ = m.flow(group)
    acts = {k: rs for k, rs in nodes.items() if buc is None or k[0] == buc}
    lanes = {}
    for k, rs in acts.items():
        who = multi(rs[0]["アクター"]) or multi(rs[0]["外部システム"]) or ["(未定)"]
        lanes.setdefault(who[0], []).append(k)
    b = ["flowchart TB"]
    hyps = []
    for lane, acts_in in lanes.items():
        b.append(f"  subgraph {ids('l', lane)}[{ql(lane)}]")
        if wrap and len(acts) > wrap:
            b.append("    direction TB")
        for k in acts_in:
            n = ids("act", k)
            b.append(f"    {n}[{ql(k[1])}]")
            if all(is_hyp(r) for r in acts[k]):
                hyps.append(n)
        b.append("  end")
    lines = []
    for a, z in edges:
        if a in acts and z in acts:
            lines.append(f"  {ids('act', a)} --> {ids('act', z)}")
        elif a in acts:
            lines.append(f"  {ids('act', a)} --> {ids('to', z[0])}([{ql(f'BUC「{z[0]}」へ')}])")
        elif z in acts:
            lines.append(f"  {ids('from', a[0])}([{ql(f'BUC「{a[0]}」から')}]) --> {ids('act', z)}")
    b += dict.fromkeys(lines)
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def kl(kind, name):
    """図形だけでは種類が分からないので、名前の上に種類を小さく書く。"""
    return ql(f"<small>{kind}</small><br/>{name}")


# UC複合図の種類ごとの色(diagrams.md 用の明るい色)。PRD はこの classDef を外し、
# ページ側の色(ダークモードで切り替わる)で同じクラスを塗る
KIND_STYLES = {
    "kActor": "fill:#e6eefa,stroke:#3b6fb6",
    "kScreen": "fill:#e3f3f6,stroke:#2a8199",
    "kUc": "fill:#e2f0ee,stroke:#0d6b67",
    "kExt": "fill:#efe8f8,stroke:#7a52b3",
    "kInfo": "fill:#fbf1d9,stroke:#a87410",
    "kCond": "fill:#fbe7ea,stroke:#b54a5e",
    "kState": "fill:#ebedf0,stroke:#5a6773",
}


def kind_classes(ids):
    """Ids の種類(先頭の記号)ごとに class 行を作る。"""
    by = {}
    cls = {"a": "kActor", "s": "kScreen", "uc": "kUc", "ev": "kExt", "e": "kExt",
           "i": "kInfo", "c": "kCond", "sm": "kState"}
    for (kind, _), node in ids.m.items():
        if kind in cls:
            by.setdefault(cls[kind], []).append(node)
    out = [f"  classDef {k} {KIND_STYLES[k]}" for k in KIND_STYLES if k in by]
    out += [f"  class {','.join(v)} {k}" for k, v in by.items()]
    return out


def diagram_uc(m, uc, ids=None):
    ids = ids or Ids()
    un = ids("uc", uc)
    b = ["flowchart LR", f"  {un}([{kl('UC', uc)}])"]
    seen = set()

    def edge(line):
        if line not in seen:
            seen.add(line)
            b.append(line)

    for r in m.ucs[uc]:
        arrow = "-.-" if is_hyp(r) else "---"
        for s in multi(r["画面"]):
            sn = ids("s", s)
            edge(f"  {sn}[/{kl('画面', s)}/] {arrow} {un}")
            for a in multi(r["アクター"]):
                edge(f"  {ids('a', a)}[{kl('アクター', a)}] {arrow} {sn}")
        for ev in multi(r["イベント"]):
            en = ids("ev", ev)
            edge(f"  {un} {arrow} {en}>{kl('イベント', ev)}]")
            for e in multi(r["外部システム"]):
                edge(f"  {en} {arrow} {ids('e', e)}[[{kl('外部システム', e)}]]")
        for i in multi(r["情報"]):
            edge(f"  {un} {arrow} {ids('i', i)}[({kl('情報', i)})]")
        for c in multi(r["条件"]):
            edge(f"  {ids('c', c)}{{{kl('条件', c)}}} {arrow} {un}")
    # 状態モデルは持ち主の情報にだけつなぎ、線にはこのUCで起きる遷移を書く。
    # 持ち主の情報をUCが扱っていなければ描かない(P209 で指摘する)
    for sm in m.uc_state_models(uc):
        holders = [i for i in m.sm_holders(sm) if i in m.uc_infos(uc)]
        if not holders:
            continue
        sn = ids("sm", sm)
        trans = "、".join(dict.fromkeys(f"{r['状態']}→{t}" for r in m.state_models[sm]
                                        if uc in multi(r["遷移UC"]) for t in multi(r["遷移先"])))
        for i in holders:
            link = f"-->|{ql(trans)}|" if trans else "-->"
            edge(f"  {ids('i', i)} {link} {sn}[{kl('状態モデル', sm)}]")
    b += kind_classes(ids)
    if all(is_hyp(r) for r in m.ucs[uc]):
        b += ["  " + HYP_STYLE, f"  class {un} hyp"]
    return mermaid(b)


def er_card(text):
    t = (text or "").replace(" ", "").replace(":", "対").replace("N", "多").replace("n", "多").replace("*", "多")
    if t in ("1対1",):
        return "||--||"
    if t in ("1対多", "1対0..多", "1対0..*"):
        return "||--o{"
    if t in ("多対1",):
        return "}o--||"
    if t in ("多対多",):
        return "}o--o{"
    return "}o--o{"


def diagram_info(m):
    ids = Ids()
    b = ["erDiagram"]
    by_ctx = {}
    for i, r in m.infos.items():
        by_ctx.setdefault(r["コンテキスト"] or "(未分類)", []).append((i, r))
    for ctx, items in by_ctx.items():
        b.append(f"  %% コンテキスト: {ctx}")
        for i, r in items:
            label = f"{i}(仮説)" if is_hyp(r) else i
            b.append(f"  {ids('i', i)}[{ql(label)}]")
    for r in m.t["情報関連"]:
        if r["情報"] in m.infos and r["関連先"] in m.infos:
            card = er_card(r["多重度"])
            if is_hyp(r):
                card = card.replace("--", "..")
            b.append(f"  {ids('i', r['情報'])} {card} {ids('i', r['関連先'])} : {ql(r['多重度'] or '未定')}")
    return mermaid(b)


def diagram_state(m, sm, max_ucs=None):
    ids = Ids()
    b = ["stateDiagram-v2"]
    rows = m.state_models[sm]
    hyps = set()
    for s in m.states_of(sm):
        b.append(f"  state {ql(s)} as {ids('s', s)}")
        own = [r for r in rows if r["状態"] == s]
        if own and all(is_hyp(r) for r in own):
            hyps.add(ids("s", s))
    for r in rows:
        ucs = multi(r["遷移UC"])
        for nxt in multi(r["遷移先"]):
            shown = ucs if not max_ucs or len(ucs) <= max_ucs else ucs[:1]
            label = "、".join(shown) + (f" など{len(ucs)}件" if len(shown) < len(ucs) else "") if ucs else "(遷移UC未定)"
            if is_hyp(r):
                label += "(仮説)"
            label = label.replace(":", "：")
            b.append(f"  {ids('s', r['状態'])} --> {ids('s', nxt)} : {label}")
    if hyps:
        b.append("  " + HYP_STYLE)
        b.append(f"  class {','.join(sorted(hyps))} hyp")
    return mermaid(b)


def diagram_conditions(m):
    ids = Ids()
    b = ["flowchart LR"]
    hyps = []
    for c, r in m.conds.items():
        cn = ids("c", c)
        b.append(f"  {cn}{{{ql(c)}}}")
        if is_hyp(r):
            hyps.append(cn)
        for v in multi(r["バリエーション"]):
            vals = m.vars.get(v, {}).get("値", "")
            b.append(f"  {cn} --> {ids('v', v)}[{ql(f'{v}: {vals}' if vals else v)}]")
        for sm in multi(r["状態モデル"]):
            b.append(f"  {cn} --> {ids('sm', sm)}[{ql('状態: ' + sm)}]")
    for uc, rows in m.ucs.items():
        for c in sorted({c for r in rows for c in multi(r["条件"])}):
            b.append(f"  {ids('uc', uc)}([{ql(uc)}]) --- {ids('c', c)}")
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def build_diagrams(d):
    m = Model(d)
    out = ["# RDRA ダイアグラム", "",
           "> `rdra.py diagrams` で表から生成。手で編集しない。点線・橙色は仮説。", ""]
    out += ["## システムコンテキスト", "", diagram_context(m, system_name(d))]
    if m.goals or m.reqs:
        out += ["## 要求モデル", "", diagram_requirements(m)]
    if m.bucs:
        out += ["## ビジネスコンテキスト", "", diagram_business_context(m)]
        out += ["## 業務フロー", ""]
        for g in m.groups():
            out += [f"### {g}", ""]
            out += [diagram_flow(m, g)] if m.flow(g)[0] else ["アクティビティがまだない。", ""]
        out += ["## BUCごとのアクティビティ", ""]
        for (g, buc), rows in m.bucs.items():
            out += [f"### {g} / {buc}", ""]
            out += [diagram_flow(m, g, buc)] if activities(rows) else ["アクティビティがまだない。", ""]
    if m.ucs:
        out += ["## UC複合図", ""]
        for uc in m.ucs:
            out += [f"### {uc}", "", diagram_uc(m, uc)]
    if m.infos:
        out += ["## 情報モデル", "", diagram_info(m)]
    if m.state_models:
        out += ["## 状態モデル", ""]
        for sm in m.state_models:
            out += [f"### {sm}", "", diagram_state(m, sm)]
    if m.conds:
        out += ["## バリエーション・条件", "", diagram_conditions(m)]
    (d / "diagrams.md").write_text("\n".join(out), encoding="utf-8")


# ---------------------------------------------------------------- analysis / status

def important_ucs(m):
    res = []
    for uc in m.ucs:
        ctxs = sorted({m.infos[i]["コンテキスト"] for i in m.uc_infos(uc)
                       if i in m.infos and m.infos[i]["コンテキスト"]})
        sms = m.uc_state_models(uc)
        if len(ctxs) >= 2 or len(sms) >= 2:
            res.append((uc, ctxs, sms))
    return res


def build_trace(m, phase):
    """各要素から根(ゴール、またはゴールを持たないポリシー)までのつながりをたどる。

    根へは機能要求・ポリシーを通ってたどる。非機能要求は「なぜ」にならないので通らない
    (要求ごとの実現の表には、付いている行をそのまま出す)。

    根ごとに「仮説の行を通らずに届くか(firm)」を持つ。上り(なぜ)と下り(どう実現するか)を返す。
    """
    def req_roots(rid):
        r = m.reqs.get(rid)
        if not r or r["種別"] == "非機能":
            return {}  # 非機能要求は品質の制約で、要素が存在する理由(なぜ)にはならない
        gs = [g for g in multi(r["ゴールID"]) if g in m.goals]
        if gs:
            return {g: not is_hyp(r) and not is_hyp(m.goals[g]) for g in gs}
        if r["種別"] == "ポリシー":
            return {f"ポリシー {rid}": not is_hyp(r)}
        return {}

    def merge(dst, src, firm=True):
        for k, v in src.items():
            dst[k] = dst.get(k, False) or (v and firm)
        return dst

    buc_reqs = {k: [q for r in rows for q in multi(r["要求ID"])] for k, rows in m.bucs.items()}

    def row_reqs(r):
        return multi(r["要求ID"]) or buc_reqs.get((r["業務"], r["BUC"]), [])

    def rows_roots(rows):
        res = {}
        for r in rows:
            for q in row_reqs(r):
                merge(res, req_roots(q), not is_hyp(r))
        return res

    def rows_break(rows):
        if not rows:
            return "03_BUCのどの行にも現れない"
        reqs = sorted({q for r in rows for q in row_reqs(r)})
        if not reqs:
            return "行に要求IDがなく、BUCのどの行にもない"
        if all(m.reqs.get(q, {}).get("種別") == "非機能" for q in reqs):
            return "非機能要求 " + "、".join(reqs) + " にしかつながらない(非機能は「なぜ」にならない)"
        return "要求 " + "、".join(reqs) + " がゴールにもポリシーにもつながらない"

    up = []

    def add(kind, name, roots, brk, loc, self_row=None):
        if self_row is not None and is_hyp(self_row):
            roots = {k: False for k in roots}
        up.append({"kind": kind, "name": name, "loc": loc,
                   "roots": [{"root": k, "firm": v} for k, v in sorted(roots.items())],
                   "break": "" if roots else brk})

    for q, r in m.reqs.items():
        if r["種別"] != "非機能":
            add("要求", q, req_roots(q), "ゴールIDがない(ポリシー以外はゴールが要る)", r["_loc"])
    for (gyomu, buc), rows in m.bucs.items():
        add("BUC", buc, rows_roots(rows), rows_break(rows), rows[0]["_loc"])
        for act in activities(rows):
            ar = [r for r in rows if r["アクティビティ"] == act]
            add("アクティビティ", f"{buc}/{act}", rows_roots(ar), rows_break(ar), ar[0]["_loc"])
    for uc, rows in m.ucs.items():
        add("UC", uc, rows_roots(rows), rows_break(rows), rows[0]["_loc"])
    for col in ("画面", "イベント"):
        names = dict.fromkeys(v for r in m.buc_rows for v in multi(r[col]))
        for n in names:
            rows = [r for r in m.buc_rows if n in multi(r[col])]
            add(col, n, rows_roots(rows), rows_break(rows), rows[0]["_loc"])
    for kind, pool, col in (("アクター", m.actors, "アクター"), ("外部システム", m.exts, "外部システム"),
                            ("情報", m.infos, "情報"), ("条件", m.conds, "条件")):
        for n, r in pool.items():
            rows = [b for b in m.buc_rows if n in multi(b[col])]
            if kind == "情報" and phase >= 2:
                rows = [b for b in rows if b["UC"]] or rows
            add(kind, n, rows_roots(rows), rows_break(rows), r["_loc"], r)
    for sm, srows in m.state_models.items():
        ucs = sorted({u for r in srows for u in multi(r["遷移UC"])})
        rows = [b for u in ucs for b in m.ucs.get(u, [])]
        add("状態モデル", sm, rows_roots(rows), "遷移UCがない" if not ucs else rows_break(rows), srows[0]["_loc"])
    cond_roots = {e["name"]: e for e in up if e["kind"] == "条件"}
    for v, r in m.vars.items():
        cs = [c for c, cr in m.conds.items() if v in multi(cr["バリエーション"])]
        roots = {}
        for c in cs:
            merge(roots, {x["root"]: x["firm"] for x in cond_roots[c]["roots"]}, not is_hyp(m.conds[c]))
        add("バリエーション", v, roots, "どの条件にも使われていない" if not cs else "使う条件が根につながらない", r["_loc"], r)

    down = []
    for g in m.goals:
        reqs = [q for q, r in m.reqs.items() if g in multi(r["ゴールID"])]
        rows = [r for r in m.buc_rows if set(row_reqs(r)) & set(reqs)]
        ucs = list(dict.fromkeys(r["UC"] for r in rows if r["UC"]))
        down.append({"goal": g, "reqs": reqs,
                     "bucs": list(dict.fromkeys(r["BUC"] for r in rows)), "ucs": ucs,
                     "infos": list(dict.fromkeys(i for r in rows for i in multi(r["情報"]))),
                     "state_models": sorted({s for u in ucs for s in m.uc_state_models(u)}),
                     "conds": list(dict.fromkeys(c for r in rows for c in multi(r["条件"])))})
    realize = []
    for q, r in m.reqs.items():
        rows = [b for b in m.buc_rows if q in multi(b["要求ID"])]
        ucs = list(dict.fromkeys(b["UC"] for b in rows if b["UC"]))
        conds = list(dict.fromkeys(c for b in rows for c in multi(b["条件"])))
        gap = ""
        if not rows:
            gap = "BUCにつながらない"
        elif r["種別"] == "機能" and phase >= 2 and not ucs:
            gap = "機能要求なのにUCがない"
        elif r["種別"] == "ポリシー" and phase >= 3 and not conds:
            gap = "ポリシーなのに条件がない"
        realize.append({"req": q, "type": r["種別"], "bucs": list(dict.fromkeys(b["BUC"] for b in rows)),
                        "ucs": ucs, "conds": conds, "gap": gap, "loc": r["_loc"]})
    return {"up": up, "down": down, "realize": realize}


def trace_markdown(tr, heading="##"):
    h = heading
    out = []
    broken = [e for e in tr["up"] if not e["roots"]]
    out += [f"{h} 根につながらない要素", "",
            "ゴール、またはゴールを持たないポリシーまでたどれない要素。", ""]
    out += [md_table(["種類", "要素", "途切れ", "場所"], [(e["kind"], e["name"], e["break"], e["loc"]) for e in broken])
            if broken else "なし\n"]
    weak = [e for e in tr["up"] if e["roots"] and not any(x["firm"] for x in e["roots"])]
    out += [f"{h} 仮説を通らないと根に届かない要素", ""]
    out += [md_table(["種類", "要素", "根", "場所"],
                     [(e["kind"], e["name"], "、".join(x["root"] for x in e["roots"]), e["loc"]) for e in weak])
            if weak else "なし\n"]
    out += [f"{h} ゴールから下へ(どう実現するか)", ""]
    out += [md_table(["ゴール", "要求", "BUC", "UC", "情報", "状態モデル", "条件"],
                     [(d["goal"], "、".join(d["reqs"]), len(d["bucs"]), len(d["ucs"]), len(d["infos"]),
                       len(d["state_models"]), len(d["conds"])) for d in tr["down"]]) if tr["down"] else "ゴールなし\n"]
    out += [f"{h} 要求ごとの実現", ""]
    out += [md_table(["要求", "種別", "BUC", "UC", "条件", "抜け"],
                     [(r["req"], r["type"], "、".join(r["bucs"]), "、".join(r["ucs"]), "、".join(r["conds"]), r["gap"])
                      for r in tr["realize"]]) if tr["realize"] else "要求なし\n"]
    return out


def md_table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(lines) + "\n"


def build_analysis(d):
    st = load_state(d)
    m = Model(d)
    qs, _ = parse_questions(d / "questions.md")
    issues = run_checks(m, qs, st["phase"])
    out = ["# RDRA 分析", "", "> `rdra.py analysis` で生成。手で編集しない。", ""]
    out += ["## 規模", "", md_table(["要素", "数"], [
        ("ゴール", len(m.goals)), ("要求", len(m.reqs)), ("アクター", len(m.actors)), ("外部システム", len(m.exts)),
        ("業務", len({g for g, _ in m.bucs})), ("BUC", len(m.bucs)),
        ("アクティビティ", sum(len(activities(rs)) for rs in m.bucs.values())),
        ("UC", len(m.ucs)), ("情報", len(m.infos)), ("状態モデル", len(m.state_models)),
        ("条件", len(m.conds)), ("バリエーション", len(m.vars))])]
    rows = []
    for i in issues:
        acc = st["accepted"].get(i.key)
        rows.append((i.severity, i.key, i.msg, i.loc, f"許容: {acc}" if acc else ""))
    out += ["## 整合性チェック", "", md_table(["重要度", "キー", "内容", "場所", "扱い"], rows) if rows else "指摘なし\n"]
    imp = important_ucs(m)
    out += ["## 重要UC", "", "複数のコンテキストにまたがるUC、または複数の状態モデルを変えるUC。", ""]
    out += [md_table(["UC", "コンテキスト", "状態モデル"], [(u, "、".join(c), "、".join(s)) for u, c, s in imp])
            if imp else "該当なし\n"]

    def pivot(title, key_col, pool):
        rs = []
        for k in pool:
            hit = [r for r in m.buc_rows if r["UC"] and k in multi(r[key_col])]
            rs.append((k, "、".join(dict.fromkeys(r["UC"] for r in hit)),
                       "、".join(dict.fromkeys(r["BUC"] for r in hit))))
        return [f"## UC_PIVOT: {title}", "", md_table([title, "UC", "BUC"], rs) if rs else "なし\n"]

    out += ["## トレーサビリティ", "", "`rdra.py trace` と同じ内容。", ""]
    out += trace_markdown(build_trace(m, st["phase"]), "###")
    out += pivot("情報", "情報", m.infos)
    out += pivot("アクター", "アクター", m.actors)
    out += pivot("外部システム", "外部システム", m.exts)
    out += pivot("条件", "条件", m.conds)
    (d / "analysis.md").write_text("\n".join(out), encoding="utf-8")


def build_status(d):
    st = load_state(d)
    m = Model(d)
    qs, _ = parse_questions(d / "questions.md")
    issues = [i for i in run_checks(m, qs, st["phase"]) if i.key not in st["accepted"]]
    phase = st["phase"]
    next_gate = {0: None, 1: "1", 2: "2", 3: "done"}[phase]
    if next_gate:
        reasons = evaluate_gate(d, next_gate)
    elif (d / DRAFT).exists():
        reasons = [f"{DRAFT} を見直し、採用の指示をする(採用すると初期要望.txt になる)"]
    else:
        reasons = ["初期要望.txt を書いて /rdra phase1(inputs/ に資料があれば /rdra draft で下書きを作れる)"]
    counts = {(p, s): 0 for p in PRIORITIES for s in Q_STATES}
    for q in qs.values():
        if (q["priority"], q_status(q)) in counts:
            counts[(q["priority"], q_status(q))] += 1
    hyp_rows = sum(1 for r in m.all_rows() if is_hyp(r))
    sev = {s: sum(1 for i in issues if i.severity == s) for s in SEVERITIES}
    gate_label = {"1": "フェーズ2へ進む条件", "2": "フェーズ3へ進む条件", "done": "完成条件"}.get(next_gate, "")

    out = ["# RDRA 状況", "", "> `rdra.py status` で生成。手で編集しない。", "",
           f"- 現在のフェーズ: **{phase}**{'(完成)' if st.get('done') else ''}",
           f"- 仮説の行: {hyp_rows}",
           f"- チェック指摘: 致命 {sev['致命']} / 警告 {sev['警告']} / 情報 {sev['情報']}", ""]
    out += ["## 質問", "", md_table(["優先度"] + Q_STATES,
                                     [[p] + [counts[(p, s)] for s in Q_STATES] for p in PRIORITIES])]
    if next_gate:
        out += [f"## {gate_label}", ""]
        out += ["満たしている\n"] if not reasons else [f"- {r}" for r in reasons] + [""]
    else:
        out += ["## 次にやること", ""] + [f"- {r}" for r in reasons] + [""]
    if st["force"]:
        out += ["## --force・完成を外した記録", "", md_table(["日時", "判定", "理由"],
                                                  [(f["date"], f["gate"], f["reason"]) for f in st["force"]])]
    if st["accepted"]:
        out += ["## 許容したチェック指摘", "", md_table(["キー", "理由"], list(st["accepted"].items()))]
    accepted_q = [q for q in qs.values() if q_status(q) == "許容"]
    low_open = unresolved(qs, ["低"])
    if accepted_q or low_open:
        out += ["## 残している質問", "", md_table(["ID", "優先度", "状態", "質問"],
                                                [(q["id"], q["priority"], q_status(q), q["title"])
                                                 for q in accepted_q + low_open])]
    (d / "status.md").write_text("\n".join(out), encoding="utf-8")
    return phase, next_gate, reasons, counts, hyp_rows, sev


# ---------------------------------------------------------------- 質問HTML / 回答

def build_html(d):
    qs, _ = parse_questions(d / "questions.md")
    answers = {}
    ap = d / "answers.json"
    if ap.exists():
        try:
            answers = json.loads(ap.read_text(encoding="utf-8")).get("answers", {})
        except json.JSONDecodeError:
            pass
    data = {
        "system": system_name(d),
        "generatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
        "questions": [{
            "id": q["id"], "priority": q["priority"], "phase": q["phase"], "title": q["title"],
            "target": q["fields"].get("対象", ""), "proposal": q["fields"].get("提案", ""),
            "basis": q["fields"].get("根拠", ""), "viewpoint": q["fields"].get("観点", ""),
            "choices": q["choices"], "answer": q["fields"].get("回答", ""), "status": q_status(q),
        } for q in qs.values()],
        "answers": answers,
    }
    tmpl = (SKILL_DIR / "templates" / "questions.html.tmpl").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
    (d / "questions.html").write_text(tmpl.replace("/*__DATA__*/null", payload), encoding="utf-8")
    return len(data["questions"])


def merge_answers(d):
    ap = d / "answers.json"
    if not ap.exists():
        return [], [], []
    answers = json.loads(ap.read_text(encoding="utf-8")).get("answers", {})
    qpath = d / "questions.md"
    qs, lines = parse_questions(qpath)
    merged, reopened, unknown = [], [], []
    for qid, a in answers.items():
        q = qs.get(qid)
        if q is None:
            unknown.append(qid)
            continue
        choice = (a.get("choice") or "").strip()
        note = " ".join((a.get("note") or "").split())
        if not choice and not note:
            continue
        text = ""
        if choice:
            ct = next((c["text"] for c in q["choices"] if c["key"] == choice), "")
            text = f"{choice}) {ct}".strip()
        if note:
            text = f"{text} / 補足: {note}" if text else note
        status = q_status(q)
        if q["fields"].get("回答", "") == text and status != "未回答":
            continue
        if status == "許容":
            continue
        if status == "反映済":
            reopened.append(qid)
        merged.append(qid)
        a_line, s_line = q["lines"].get("回答"), q["lines"].get("状態")
        if a_line is not None:
            lines[a_line] = f"回答: {text}"
        if s_line is not None:
            lines[s_line] = "状態: 回答済"
    qpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return merged, reopened, unknown


# ---------------------------------------------------------------- init

def table_file_content(fname):
    title = fname.split("_", 1)[1].removesuffix(".md")
    out = [f"# {title}", ""]
    for tname, cols in TABLES[fname].items():
        cols = cols + TAIL
        out += [f"## {tname}", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols), ""]
    return "\n".join(out)


# 後から足した列: (ファイル, 表, 列, この列の直前の列)
def cmd_init(d):
    created = []
    d.mkdir(parents=True, exist_ok=True)
    (d / "inputs").mkdir(exist_ok=True)
    keep = d / "inputs" / ".gitkeep"
    if not keep.exists():
        keep.write_text("", encoding="utf-8")
    for src, dst in (("初期要望.txt", "初期要望.txt"), ("checklist-local.md", "checklist-local.md")):
        p = d / dst
        if not p.exists():
            p.write_text((SKILL_DIR / "templates" / src).read_text(encoding="utf-8"), encoding="utf-8")
            created.append(dst)
    for fname in TABLES:
        p = d / fname
        if not p.exists():
            p.write_text(table_file_content(fname), encoding="utf-8")
            created.append(fname)
    qp = d / "questions.md"
    if not qp.exists():
        qp.write_text("# 質問\n\n> 書式は .agents/skills/rdra/references/questions.md。回答は questions.html から。\n\n",
                      encoding="utf-8")
        created.append("questions.md")
    if not (d / ".state.json").exists():
        save_state(d, load_state(d))
        created.append(".state.json")
    return created


# ---------------------------------------------------------------- 初期要望の点検と採用

DRAFT = "初期要望.draft.txt"
REQUEST_HEADINGS = ["システム名", "最重要要求", "背景", "業務の概要", "スコープ外", "その他"]
REQUEST_REQUIRED = ["システム名", "最重要要求", "業務の概要"]
MEMO_HEADING = "AIのメモ(採用時に消える)"
SRC_MARK = re.compile(r"\s*［(?:資料|回答):[^］]*］")
TODO_MARK = "【要記入】"


def lint_request(d, name="初期要望.txt"):
    """初期要望の形を機械的に点検する。[(重要度, 内容)] を返す。意味の判断はしない。"""
    p = d / name
    if not p.exists():
        return [("致命", f"{name} がない")]
    secs = initial_request_sections(d, name)
    out = []
    for h in REQUEST_HEADINGS:
        if h not in secs:
            out.append(("警告", f"見出し「# {h}」がない(テンプレートの見出しを変えない)"))
    empty = [h for h in REQUEST_REQUIRED if not secs.get(h)]
    if len(empty) == len(REQUEST_REQUIRED):
        out.append(("致命", "システム名・最重要要求・業務の概要がすべて空"))
    else:
        out += [("警告", f"{h} が空(phase1 で優先度・高の質問になる)") for h in empty]
    out += [("情報", f"{h} が空") for h in ("背景", "スコープ外") if not secs.get(h)]
    if len(secs.get("最重要要求", [])) > 3:
        out.append(("警告", f"最重要要求が {len(secs['最重要要求'])} 行ある(1〜3行に絞る)"))
    parent, children = None, 0
    for line in secs.get("業務の概要", []) + ["・"]:
        t = line.strip()
        if t.startswith("・"):
            if parent and children == 0:
                out.append(("警告", f"業務の概要「{parent}」の下に個々の業務(「-」の行)がない"))
            parent, children = t.lstrip("・").strip(), 0
        elif t.startswith("-"):
            if parent is None:
                out.append(("警告", f"業務の概要「{t}」の上に業務のまとまり(「・」の行)がない"))
            children += 1
        else:
            out.append(("情報", f"業務の概要に「・」「-」で始まらない行がある: {t}"))
    text = p.read_text(encoding="utf-8")
    todos = [l.strip() for l in text.splitlines() if TODO_MARK in l]
    if name == DRAFT:
        out += [("情報", f"要記入: {t}") for t in todos]
        out += [("警告", f"【要記入】に質問IDがない: {t}") for t in todos if not re.search(r"Q-\d+", t)]
    elif SRC_MARK.search(text) or todos or MEMO_HEADING in secs:
        out.append(("致命", "下書きの印(［資料:…］【要記入】AIのメモ)が残っている。rdra.py adopt で採用する"))
    return out


def request_written(d):
    return any(initial_request_sections(d).get(h) for h in REQUEST_HEADINGS)


def adopt_draft(d, replace=False):
    """人が見直した初期要望.draft.txt を初期要望.txt にする。問題があれば理由のリストを返す。"""
    p = d / DRAFT
    if not p.exists():
        return [f"{DRAFT} がない"]
    lines = p.read_text(encoding="utf-8").splitlines()
    todos = [l.strip() for l in lines if TODO_MARK in l]
    if todos:
        return [f"【要記入】が残っている(書くか、行を消す。空の項目は phase1 で質問になる): {t}" for t in todos]
    qs, _ = parse_questions(d / "questions.md")
    pending = [q["id"] for q in qs.values() if q["phase"] == 0 and q_status(q) == "回答済"]
    if pending:
        return [f"回答が下書きに反映されていない質問がある(先に /rdra draft で反映する): {', '.join(pending)}"]
    if request_written(d) and not replace:
        return ["初期要望.txt にすでに記述がある。下書きで置き換えてよいと人が確認したときだけ --replace を付ける"]
    out, skip = [], False
    for line in lines:
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            skip = m.group(1) == MEMO_HEADING
        if not skip:
            out.append(SRC_MARK.sub("", line).rstrip())
    while out and not out[-1]:
        out.pop()
    (d / "初期要望.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    p.unlink()
    return []


# ---------------------------------------------------------------- PRD(関係者向けHTML)

# (01_要求 の種別, PRDの見出し, 何を入れるか)
REQ_KIND = [("機能", "機能", "システムでできること。画面で入力する、計算する、表示するなど"),
            ("非機能", "非機能", "機能をどれだけ快適・安全に使えるか。速さ、使える端末、個人情報の守り方など"),
            ("ポリシー", "方針", "システムの作り方ではなく、事業・運営として決めること。"
             "料金、だれ向けのサービスか、データをいつ消すか、制度改正への追従など")]


def initial_request_sections(d, name="初期要望.txt"):
    """初期要望.txt を {見出し: [本文の行]} で返す。テンプレートの案内行は除く。"""
    p = d / name
    secs = {}
    if not p.exists():
        return secs
    cur = None
    for line in p.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#\s+(.+?)\s*$", line)
        if m:
            cur = m.group(1)
            secs[cur] = []
            continue
        s = line.strip()
        if cur is None or not s or re.fullmatch(r"[((].*[))]", s) or s in ("・", "-"):
            continue
        secs[cur].append(line.rstrip())
    return secs


def source_badge(src):
    from html import escape as e
    if src == "仮説":
        return '<span class="badge hyp" title="AIの提案。確認が必要">仮説・要確認</span>'
    if src == "回答":
        return '<span class="badge ok" title="質問への回答や人の編集で決まった">決定</span>'
    if src == "要望":
        return '<span class="badge src" title="初期要望に書かれている">初期要望</span>'
    if src.startswith("資料"):
        name = src.split(":", 1)[1] if ":" in src else ""
        return f'<span class="badge src" title="{e(name)}">資料</span>'
    return f'<span class="badge">{e(src or "出典なし")}</span>'


def plain_answer(q):
    """「A) 提案どおり(…)」「D) その他 → ___ / 補足: …」を読みやすい文にする。"""
    a = q["fields"].get("回答", "") or q["fields"].get("提案", "")
    a = re.sub(r"^[A-Z]\)\s*", "", a)
    a = re.sub(r"^その他\s*→\s*_*\s*/\s*補足:\s*", "", a)
    if a.startswith("提案どおり") and q["fields"].get("提案"):
        note = a.split(" / 補足: ", 1)[1] if " / 補足: " in a else ""
        return q["fields"]["提案"] + (f"。補足: {note}" if note else "")
    return a.replace(" / 補足: ", "。補足: ")


def screen_order(m):
    """画面をBUCの行の順に並べる。PRDとモックで同じ番号(scr-N)を使う。"""
    names = []
    for rows in m.bucs.values():
        for r in rows:
            for s in multi(r["画面"]):
                if s not in names:
                    names.append(s)
    return names


def prd_figure(md, caption="", keys=None):
    """diagrams の Mermaid を PRD 用の <figure> にする(絵文字は外す)。
    keys は 図のノードID → 中身の見出し。クリックで中身を出す"""
    from html import escape as e
    body = md.strip().removeprefix("```mermaid").removesuffix("```").strip().replace("👤 ", "")
    body = "\n".join(l for l in body.splitlines() if not l.strip().startswith("classDef k"))
    cap = f"<figcaption>{e(caption)}</figcaption>" if caption else ""
    attr = f' data-keys="{e(json.dumps(keys, ensure_ascii=False))}"' if keys else ""
    return f'<figure class="dg"{attr}><pre class="mermaid">{e(body)}</pre>{cap}</figure>'


def prd_info_diagram(m):
    """情報の関連を左から右にたどれる図にする(erDiagram は情報が多いと横に広がりすぎるため)。"""
    ids = Ids()
    b = ["flowchart LR"]
    for i, r in m.infos.items():
        b.append(f"  {ids('i', i)}([{ql(i)}])")
    hyps = [ids("i", i) for i, r in m.infos.items() if is_hyp(r)]
    for r in m.t["情報関連"]:
        if r["情報"] in m.infos and r["関連先"] in m.infos:
            arrow = "-.->" if is_hyp(r) or r["多重度"] == "多対多" else "-->"
            b.append(f"  {ids('i', r['情報'])} {arrow}|{ql(r['多重度'] or '未定')}| {ids('i', r['関連先'])}")
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def prd_party_diagram(nodes):
    """nodes(ノードID種別, 名前, 図形の左右の記号, 行) を中央に置き、関わるアクター(左)・
    外部システム(右)と線でつなぐ(向きは持たない)。仮説の行でしか関わらないつながりは点線にする。"""
    ids = Ids()
    b = ["flowchart LR"]
    hyps, links = [], []
    for kind, name, (l, r), rows in nodes:
        n = ids(kind, name)
        b.append(f"  {n}{l}{ql(name)}{r}")
        if rows and all(is_hyp(x) for x in rows):
            hyps.append(n)
        for col, k in [("アクター", "a"), ("外部システム", "e")]:
            for w in dict.fromkeys(w for x in rows for w in multi(x[col])):
                hyp = all(is_hyp(x) for x in rows if w in multi(x[col]))
                links.append((k, w, n, hyp))
    for k, w, n, hyp in links:
        line = "-.-" if hyp else "---"
        if k == "a":
            b.append(f"  {ids('a', w)}[{kl('アクター', w)}] {line} {n}")
        else:
            b.append(f"  {n} {line} {ids('e', w)}[[{kl('外部システム', w)}]]")
    b += kind_classes(ids)
    b.append("  " + HYP_STYLE)
    if hyps:
        b.append(f"  class {','.join(hyps)} hyp")
    return mermaid(b)


def prd_business_flow(m):
    """業務と、その業務に関わるアクター・外部システムの図。"""
    rows_g = {}
    for (g, _), rows in m.bucs.items():
        rows_g.setdefault(g, []).extend(rows)
    return prd_party_diagram([("g", g, ("[", "]"), rows) for g, rows in rows_g.items()])


def prd_overall_flow(m, group=None):
    """BUCと、そのBUCに関わるアクター・外部システムの図(group を渡すとその業務のBUCだけ)。"""
    return prd_party_diagram([("b", buc, ("([", "])"), rows) for (g, buc), rows in m.bucs.items()
                              if group is None or g == group])


QREF_PAREN = re.compile(r"[((]\s*Q-\d+(?:\s*[、,・]\s*Q-\d+)*\s*[))]")


DETAIL_KIND = {"i": "情報", "c": "条件", "sm": "状態モデル"}


def prd_cond_table(m, cond):
    """条件の表を、軸の数に合う形の表(HTML)にする。軸1つは値と結果、軸2つは縦横の表、3つ以上は組合せの一覧。"""
    from html import escape

    def e(v):
        return escape(QREF_PAREN.sub("", v))

    rows = m.cond_cells.get(cond)
    axes = m.cond_axes(cond)
    if not rows or not axes:
        return ""

    def cell(r):
        if r is None:
            return '<td><span class="none">未定</span></td>'
        hyp = ' <span class="badge hyp">仮説</span>' if is_hyp(r) else ""
        return f'<td>{e(r["結果"])}{hyp}</td>'

    # どの行も「すべて」の軸は結果を分けないので、表からは省いて注記する
    vals = [multi(r["値"]) for r in rows]
    keep = [k for k in range(len(axes)) if any(len(v) == len(axes) and v[k] != ANY_VALUE for v in vals)]
    note = "、".join(axes[k][0] for k in range(len(axes)) if k not in keep)
    note = f'<div class="sub">{e(note)}がどの値でも、結果は表のとおり</div>' if note else ""
    if len(keep) == 2:
        (a1, v1), (a2, v2) = (axes[k] for k in keep)
        at = {}
        for r in rows:
            for x in m.cell_combos(cond, r) or []:
                at.setdefault((x[keep[0]], x[keep[1]]), r)
        html = (f'<thead><tr><th>縦: {e(a1)}<br>横: {e(a2)}</th>' + "".join(f"<th>{e(v)}</th>" for v in v2) + "</tr></thead><tbody>"
                + "".join(f"<tr><th>{e(x)}</th>" + "".join(cell(at.get((x, y))) for y in v2) + "</tr>" for x in v1))
    else:
        head = "".join(f"<th>{e(axes[k][0])}</th>" for k in keep)
        html = (f"<thead><tr>{head}<th>結果</th></tr></thead><tbody>"
                + "".join("<tr>" + "".join(f"<td>{e(v[k] if len(v) == len(axes) else '')}</td>" for k in keep)
                          + cell(r) + "</tr>" for r, v in zip(rows, vals)))
    return f'{note}<div class="tbl cond-tbl"><table>{html}</tbody></table></div>'


def prd_details(m):
    """UC複合図でクリックしたときに出す、情報・条件・状態モデルの中身(HTML)。"""
    from html import escape

    def e(v):
        return escape(QREF_PAREN.sub("", v))

    def chips(values):
        return "".join(f'<span class="chip">{e(v)}</span>' for v in values)

    def dl(items):
        return "<dl>" + "".join(f"<dt>{e(k)}</dt><dd>{v}</dd>" for k, v in items if v) + "</dl>"

    out = {}
    for name, r in m.infos.items():
        sms = [f'<b>{e(sm)}</b>: {chips(m.states_of(sm))}' for sm in multi(r["状態モデル"])]
        vs = [f'<b>{e(v)}</b>: {chips(multi(m.vars[v]["値"]))}' if v in m.vars else e(v)
              for v in multi(r["バリエーション"])]
        out[f"情報:{name}"] = dl([
            ("説明", e(r["説明"])), ("コンテキスト", e(r["コンテキスト"])),
            ("主な項目", chips(multi(r["属性"])) or '<span class="none">未定</span>'),
            ("状態モデル", "<br>".join(sms)), ("バリエーション", "<br>".join(vs))])
    for name, r in m.conds.items():
        vs = [f'<b>{e(v)}</b>: {chips(multi(m.vars[v]["値"]))}' if v in m.vars else e(v)
              for v in multi(r["バリエーション"])]
        out[f"条件:{name}"] = dl([
            ("説明", e(r["説明"])), ("表", prd_cond_table(m, name)), ("バリエーション", "<br>".join(vs)),
            ("関わる状態モデル", chips(multi(r["状態モデル"])))])
    for sm, rows in m.state_models.items():
        trans = [r for r in rows if r["遷移先"]]
        lines = "".join(f'<li>{e(r["状態"])} → {e(r["遷移先"])}'
                        + (f' <span class="sub">({e(r["遷移UC"])})</span>' if r["遷移UC"] else "") + "</li>"
                        for r in trans)
        out[f"状態モデル:{sm}"] = dl([
            ("持つ情報", chips(m.sm_holders(sm))),
            ("状態", chips(m.states_of(sm))),
            ("移り変わり", f'<ul class="trans">{lines}</ul>' if lines
             else '<span class="none">どのUCでどの状態に移るかは、まだ決まっていません</span>')])
    return out


def build_prd(d):
    from html import escape

    def e(v):
        return escape(QREF_PAREN.sub("", v))
    m = Model(d)
    qs, _ = parse_questions(d / "questions.md")
    sysname = system_name(d)
    secs = initial_request_sections(d)
    now = datetime.datetime.now()

    def chips(values, cls="chip"):
        return "".join(f'<span class="{cls}">{e(v)}</span>' for v in values)

    def memo(key, label):
        return (f'<div class="memo"><label for="memo-{e(key)}">メモ</label>'
                f'<textarea id="memo-{e(key)}" data-key="{e(key)}" data-label="{e(label)}" rows="1" '
                f'placeholder="MTGで出た意見・決まったこと"></textarea></div>')

    # 集計
    all_rows = [r for r in m.all_rows()]
    n_hyp = sum(1 for r in all_rows if is_hyp(r))
    open_qs = [q for q in qs.values() if q_status(q) in UNRESOLVED]
    done_qs = [q for q in qs.values() if q_status(q) in ("反映済", "許容")]

    # 参照の逆引き
    info_use = {}
    for (g, buc), rows in m.bucs.items():
        for r in rows:
            for i in multi(r["情報"]):
                info_use.setdefault(i, [])
                if r["アクティビティ"] and r["アクティビティ"] not in info_use[i]:
                    info_use[i].append(r["アクティビティ"])

    details = prd_details(m)

    toc, body = [], []

    def section(sid, title, html, lead=""):
        toc.append(f'<a href="#{sid}">{e(title)}</a>')
        lead_html = f'<p class="lead">{lead}</p>' if lead else ""
        body.append(f'<section id="{sid}"><h2>{e(title)}</h2>{lead_html}{html}</section>')

    # 1. 目的
    parts = []
    if m.goals:
        parts.append('<h3>ゴール</h3><ul class="reqs">' + "".join(
            f'<li><span class="rid">{e(g)}</span><div class="rbody"><div class="rtitle">{e(r["ゴール"])}'
            + "</div>"
            + (f'<div class="rdesc">達成の判断基準: {e(r["達成の判断基準"])}</div>' if r["達成の判断基準"] else "")
            + (f'<div class="rdesc">{e(r["説明"])}</div>' if e(r["説明"]) else "")
            + "</div></li>" for g, r in m.goals.items()) + "</ul>")
        parts.append("<h3>初期要望</h3>")
    for key, label in [("最重要要求", "いちばん実現したいこと"), ("背景", "背景"), ("スコープ外", "やらないこと")]:
        lines = secs.get(key, [])
        if lines and lines != ["(未記入)"]:
            paras = []  # 「- 」で始まる行は1項目、それ以外の続く行は1段落につなげる
            for x in lines:
                x = x.strip()
                if x.startswith(("- ", "・")) or not paras:
                    paras.append(x.lstrip("-・ ").strip())
                else:
                    paras[-1] += x
            parts.append(f'<div class="quote"><div class="qlabel">{label}</div>'
                         + "".join(f"<p>{e(x)}</p>" for x in paras) + "</div>")
    if parts:
        section("purpose", "目的と背景", "".join(parts) + memo("purpose", "目的と背景"))

    # 2. 使う人
    cards = []
    for name, r in m.actors.items():
        cards.append(f'<div class="card"><div class="card-h"><b>{e(name)}</b></div>'
                     f'<p>{e(r["説明"])}</p></div>')
    ext = []
    for name, r in m.exts.items():
        ext.append(f'<div class="card"><div class="card-h"><b>{e(name)}</b></div>'
                   f'<p>{e(r["説明"])}</p></div>')
    html = prd_figure(diagram_context(m, sysname), "システムと、使う人・つながる他のシステム")
    html += f'<h3>アクター</h3><div class="cards">{"".join(cards) or "<p class=none>まだありません</p>"}</div>'
    html += f'<h3>外部システム</h3><div class="cards">{"".join(ext) or "<p class=none>今のところありません</p>"}</div>'
    section("people", "アクターと外部システム", html + memo("people", "アクターと外部システム"))

    # 3. 要求
    html = ""
    for kind, label, desc in REQ_KIND:
        items = [r for r in m.reqs.values() if r["種別"] == kind]
        if not items:
            continue
        html += f'<h3>{label}</h3><p class="lead">{e(desc)}</p><ul class="reqs">'
        for r in items:
            html += (f'<li><span class="rid">{e(r["ID"])}</span><div class="rbody"><div class="rtitle">{e(r["要求"])}'
                     f'</div>'
                     + (f'<div class="rdesc">{e(r["説明"])}</div>' if e(r["説明"]) else "")
                     + "</div></li>")
        html += "</ul>"
    section("reqs", "要求", html + memo("reqs", "要求"))

    # 4. 業務フロー
    multi_g = len({g for g, _ in m.bucs}) > 1
    html = prd_figure(prd_business_flow(m), "業務と、関わるアクター・外部システム。点線は仮説のつながり") if multi_g else ""
    by_g = {}
    for (g, buc), rows in m.bucs.items():
        by_g.setdefault(g, []).append((buc, rows))
    for g, bucs in by_g.items():
        html += f'<h3>{e(g)}</h3>'
        html += prd_figure(prd_overall_flow(m, g), "BUCと、関わるアクター・外部システム。点線は仮説のつながり")
        if m.flow(g)[0]:
            html += prd_figure(diagram_flow(m, g, wrap=4), f"{g}の業務フロー。アクティビティを担当ごとの枠に置き、流れの順に矢印でつないだもの")
        for buc, rows in bucs:
            steps = []
            for r in rows:
                a = r["アクティビティ"]
                if not a:
                    continue
                if steps and steps[-1]["name"] == a:
                    s = steps[-1]
                else:
                    s = {"name": a, "who": [], "info": [], "uc": [], "screen": [], "event": [], "cond": []}
                    steps.append(s)
                for k, col in [("who", "アクター"), ("who", "外部システム"), ("info", "情報"), ("uc", "UC"),
                               ("screen", "画面"), ("event", "イベント"), ("cond", "条件")]:
                    for v in multi(r[col]):
                        if v not in s[k]:
                            s[k].append(v)
            reqids = sorted({q for r in rows for q in multi(r["要求ID"])})
            li = ""
            for s in steps:
                extra = ""
                if s["uc"]:
                    # UCがあれば、画面・イベント・条件・情報はUC複合図で示す
                    for uc in s["uc"]:
                        if uc in m.ucs:
                            ids = Ids()
                            md = diagram_uc(m, uc, ids)
                            keys = {node: f"{DETAIL_KIND[kind]}:{name}" for (kind, name), node in ids.m.items()
                                    if kind in DETAIL_KIND and f"{DETAIL_KIND[kind]}:{name}" in details}
                            extra += prd_figure(md, f"UC: {uc}", keys)
                    li += (f'<li><div class="step-h"><span class="step-name">{e(s["name"])}</span>'
                           f'{chips(s["who"], "chip who")}</div>{extra}</li>')
                    continue
                if s["screen"]:
                    extra += f'<div class="sub">画面: {chips(s["screen"])}</div>'
                if s["event"]:
                    extra += f'<div class="sub">他システムとのやりとり: {chips(s["event"])}</div>'
                if s["cond"]:
                    extra += f'<div class="sub">条件: {chips(s["cond"])}</div>'
                if s["info"]:
                    extra += f'<div class="sub">扱う情報: {chips(s["info"], "chip info")}</div>'
                li += (f'<li><div class="step-h"><span class="step-name">{e(s["name"])}</span>'
                       f'{chips(s["who"], "chip who")}</div>{extra}</li>')
            key = f"buc-{buc}"
            fig = prd_figure(diagram_flow(m, g, buc, wrap=4)) if steps else ""
            html += (f'<div class="flow"><div class="flow-h"><b>{e(buc)}</b>'
                     f'<span class="sub">{chips(reqids, "chip req")}</span></div>{fig}'
                     f'<details class="more"><summary>アクティビティごとの詳細</summary>'
                     f'<ol class="steps">{li or "<li class=none>まだアクティビティがありません</li>"}</ol></details>{memo(key, buc)}</div>')
    section("flows", "業務フロー", html or '<p class="none">まだありません</p>')

    # 5. 情報
    html = prd_figure(prd_info_diagram(m), "矢印の文字は数の関係(例: 1対多 = 左の1つに右が複数)。点線は多対多") if m.infos else ""
    by_c = {}
    for name, r in m.infos.items():
        by_c.setdefault(r["コンテキスト"] or "(未分類)", []).append(r)
    def kinds(r):
        """情報が持つ状態モデルとバリエーションを、名前と取りうる値で示す。"""
        out = [f'<div>{chips([sm])}<div class="sub">状態: {e("、".join(m.states_of(sm)))}</div></div>'
               for sm in multi(r["状態モデル"])]
        out += [f'<div>{chips([v])}<div class="sub">{e(m.vars[v]["値"]) if v in m.vars else "値は未定"}</div></div>'
                for v in multi(r["バリエーション"])]
        return "".join(out) or "<span class=none>なし</span>"

    for c, rows in by_c.items():
        html += f'<div class="ctx"><h3>{e(c)}</h3><div class="tbl"><table><thead><tr><th>情報</th><th>説明</th><th>主な項目</th><th>状態・バリエーション</th><th>使うアクティビティ</th></tr></thead><tbody>'
        for r in rows:
            html += (f'<tr><td><b>{e(r["情報"])}</b></td><td>{e(r["説明"])}</td><td>{chips(multi(r["属性"])) or "<span class=none>未定</span>"}</td>'
                     f'<td>{kinds(r)}</td>'
                     f'<td>{chips(info_use.get(r["情報"], [])) or "<span class=none>なし</span>"}</td></tr>')
        html += "</tbody></table></div></div>"
    if m.t["情報関連"]:
        html += '<details class="more"><summary>情報のつながりの一覧</summary><ul class="rels">'
        for r in m.t["情報関連"]:
            html += f'<li>{e(r["情報"])} <span class="mult">{e(r["多重度"])}</span> {e(r["関連先"])}</li>'
        html += "</ul></details>"
    section("info", "情報", (html or '<p class="none">まだありません</p>') + memo("info", "情報"),
            "システムが記録する情報です。表の見出しはコンテキストです。")

    # 6. 状態
    if m.state_models:
        html = ""
        for sm, rows in m.state_models.items():
            states = m.states_of(sm)
            trans = [r for r in rows if r["遷移先"]]
            html += f'<div class="sm"><h3>{e(sm)}</h3>'
            if trans:
                html += prd_figure(diagram_state(m, sm, max_ucs=3), "丸が状態、矢印の文字がその状態に移すUC")
                html += '<details class="more"><summary>移り変わりの一覧</summary><ul class="trans">' + "".join(
                    f'<li>{e(r["状態"])} → {e(r["遷移先"])}' + (f'<span class="sub">({e(r["遷移UC"])})</span>' if r["遷移UC"] else "")
                    + f'</li>' for r in trans) + "</ul></details>"
            else:
                html += '<div class="states">' + "".join(f'<span class="state">{e(x)}</span>' for x in states) + "</div>"
                html += '<p class="sub">どのUCでどの状態に移るかは、まだ決まっていません。</p>'
            html += "</div>"
        section("states", "状態遷移", html + memo("states", "状態遷移"),
                "記録した情報が、業務の中でどんな状態を経て移り変わるかです。")

    # 7. 条件
    if m.conds or m.vars:
        html = ""
        if m.conds:
            html += '<ul class="reqs">' + "".join(
                f'<li><div class="rbody"><div class="rtitle">{e(r["条件"])}</div>'
                f'<div class="rdesc">{e(r["説明"])}</div>{prd_cond_table(m, c)}</div></li>'
                for c, r in m.conds.items()) + "</ul>"
        if m.vars:
            html += "<h3>バリエーション</h3><ul class='rels'>" + "".join(
                f'<li><b>{e(r["バリエーション"])}</b>: {chips(multi(r["値"]))}</li>' for r in m.vars.values()) + "</ul>"
        section("rules", "条件", html + memo("rules", "条件"))

    # 8. 決まったこと
    if done_qs:
        html = '<ul class="decisions">'
        for q in done_qs:
            html += (f'<li id="{e(q["id"])}"><div class="dq"><span class="qid">{e(q["id"])}</span>{e(q["title"])}</div>'
                     f'<div class="da">{e(plain_answer(q))}</div></li>')
        html += "</ul>"
        section("decided", "これまでに決まったこと", html + memo("decided", "これまでに決まったこと"),
                "質問への回答で決まったことです。認識が違うものがあれば、メモに書いてください。")

    # 9. 議論したいこと
    html = ""
    pri_cls = {"高": "high", "中": "mid", "低": "low"}
    for q in sorted(open_qs, key=lambda q: (PRIORITIES.index(q["priority"]) if q["priority"] in PRIORITIES else 9, q["id"])):
        f = q["fields"]
        choices = "".join(f'<li><b>{e(c["key"])}</b> {e(c["text"])}</li>' for c in q["choices"])
        html += (f'<div class="oq" id="{e(q["id"])}"><div class="oq-h"><span class="pri {pri_cls.get(q["priority"], "")}">優先度 {e(q["priority"])}</span>'
                 f'<span class="qid">{e(q["id"])}</span><b>{e(q["title"])}</b></div>'
                 f'<dl><dt>AIの提案</dt><dd>{e(f.get("提案", ""))}</dd><dt>理由</dt><dd>{e(f.get("根拠", ""))}</dd>'
                 + (f'<dt>回答</dt><dd>{e(f.get("回答", ""))}</dd>' if f.get("回答") else "") + "</dl>"
                 + (f'<ol class="choices">{choices}</ol>' if choices else "") + memo(q["id"], f'{q["id"]} {q["title"]}') + "</div>")
    hyp = [r for r in all_rows if is_hyp(r)]
    if hyp:
        html += '<h3>AIの仮説で、確認が必要なもの</h3><ul class="rels">' + "".join(
            f'<li>{e(row_label(r))} </li>' for r in hyp) + "</ul>"
    if not html:
        html = '<p class="none">未解決の質問はありません。上の内容に違和感がないかを確認し、気づいたことを各項目のメモに書いてください。</p>'
    section("open", "議論したいこと", html)

    toc.append('<a href="#minutes">議事メモ</a>')
    body.append('<section id="minutes"><h2>議事メモ</h2><p class="lead">各項目に書いたメモをまとめます。'
                'コピーして <code>docs/rdra/inputs/議事録_日付.md</code> に保存し、<code>/rdra apply</code> で反映します。'
                'メモはこのブラウザにだけ保存されます。</p>'
                '<div class="mbar"><button id="copy" type="button">議事メモをコピー</button>'
                '<button id="clear" type="button" class="ghost">メモをすべて消す</button><span id="msg" role="status"></span></div>'
                '<pre id="out" class="out"></pre></section>')

    stats = ('<div class="stats">' + (f'<span class="warn"><b>{n_hyp}</b>確認が必要なAIの仮説</span>' if n_hyp else "")
             + f'<span class="{"warn" if open_qs else ""}"><b>{len(open_qs)}</b>未解決の質問</span></div>')
    header = (f'<header class="top"><div class="eyebrow">要件定義書(PRD)</div>'
              f'<h1>{e(sysname)}</h1><div class="meta">{now.year}年{now.month}月{now.day}日 {now:%H:%M} 時点</div>{stats}'
              '<details class="guide"><summary>この資料の読み方</summary><dl>'
              '<dt>BUC(ビジネスユースケース)</dt><dd>一連の仕事の流れ(例: 利用を始める)。アクティビティを順番に並べたもの</dd>'
              '<dt>アクティビティ</dt><dd>BUCの中の一つひとつの作業</dd>'
              '<dt>UC(ユースケース)</dt><dd>アクティビティの中で、システムを使う部分</dd>'
              '<dt>コンテキスト</dt><dd>役割の近い情報をまとめた単位</dd>'
              '<dt>条件</dt><dd>UCがどう動くかを決めるビジネスルール</dd>'
              '<dt>バリエーション</dt><dd>条件で使う種類・区分と、その値</dd></dl></details></header>')

    tmpl = (SKILL_DIR / "templates" / "prd.html.tmpl").read_text(encoding="utf-8")
    out = (tmpl.replace("__TITLE__", e(f"{sysname} 要件定義書"))
               .replace("__STORE__", e(f"rdra-prd:{sysname}"))
               .replace("<!--__TOC__-->", "".join(toc))
               .replace("<!--__HEADER__-->", header)
               .replace("<!--__BODY__-->", "".join(body) + '<script type="application/json" id="dg-details">'
                        + json.dumps(details, ensure_ascii=False).replace("</", "<\\/") + "</script>"))
    (d / "prd.html").write_text(out, encoding="utf-8")
    return len(open_qs)


# ---------------------------------------------------------------- 画面モック(ワイヤーフレーム)

SYSTEM_SET = re.compile(r"(ID|状態|日時|登録日)$")
UNIT_RULES = [(re.compile(r"(生年月日|開始日|日)$"), "date", ""), (re.compile(r"年齢$"), "number", "歳"),
              (re.compile(r"(率|利回り|金利)$"), "number", "%"), (re.compile(r"(期間)$"), "number", "年"),
              (re.compile(r"(年)$"), "number", "年"),
              (re.compile(r"(額|金|価格|家賃|頭金|保険料|残高|教育費)$"), "number", "円")]
SELECT_RULE = re.compile(r"(種類|区分|形態|続柄|性別|費目|進路|方法|か)$")


def split_attr(attr):
    """「種類(預貯金・NISA・iDeCo・DCなど)」→ ("種類", ["預貯金", "NISA", "iDeCo", "DC"])"""
    m = re.match(r"^(.+?)[((](.+)[))]$", attr)
    if not m:
        return attr, []
    opts = [o.replace("など", "").strip() for o in re.split(r"[・/]", m.group(2)) if "〜" not in o]
    return m.group(1), [o for o in opts if o]


def uc_verb(uc):
    return uc.split("を", 1)[1] if "を" in uc else uc


def build_mock(d):
    from html import escape as e
    m = Model(d)
    qs, _ = parse_questions(d / "questions.md")
    sysname = system_name(d)
    many = {r["関連先"] for r in m.t["情報関連"] if r["多重度"] == "1対多"}
    many |= {r["情報"] for r in m.t["情報関連"] if r["多重度"] == "多対1"}
    many |= {x for r in m.t["情報関連"] if r["多重度"] == "多対多" for x in (r["情報"], r["関連先"])}

    # 画面 → 行(BUCの順)
    screens = {}
    for (g, buc), rows in m.bucs.items():
        for r in rows:
            for s in multi(r["画面"]):
                sc = screens.setdefault(s, {"g": g, "buc": buc, "rows": []})
                sc["rows"].append(r)
    if not screens:
        (d / "mock.html").write_text("<!doctype html><meta charset='utf-8'><title>画面モック</title>"
                                     "<p>画面がまだありません。フェーズ2で画面を洗い出すと作れます。</p>", encoding="utf-8")
        return 0

    def fields(info, ext):
        """情報の属性から入力欄を作る。IDや状態などシステムが決める項目は出さない。"""
        r = m.infos.get(info)
        out = []
        for a in multi(r["属性"]) if r else []:
            label, opts = split_attr(a)
            if label.startswith("年ごとの"):
                continue
            ref = label[:-2] if label.endswith("ID") else ""
            if ref and ref in m.infos and ref not in ("シミュレーション", "世帯", "相談者") and ref != info:
                out.append(f'<label class="f"><span>対象の{e(ref)}</span><select disabled><option>選ぶ</option></select></label>')
                continue
            if SYSTEM_SET.search(label):
                continue
            if ext:
                out.append(f'<label class="f"><span>{e(label)}</span><input disabled placeholder="{e(ext)}から取得"></label>')
                continue
            if opts or SELECT_RULE.search(label):
                if opts and len(opts) <= 3:
                    out.append(f'<div class="f"><span>{e(label)}</span><div class="seg">'
                               + "".join(f'<b class="{"on" if i == 0 else ""}">{e(o)}</b>' for i, o in enumerate(opts)) + "</div></div>")
                else:
                    o = "".join(f"<option>{e(x)}</option>" for x in opts) or "<option>選ぶ</option>"
                    out.append(f'<label class="f"><span>{e(label)}</span><select disabled>{o}</select></label>')
                continue
            kind, unit = "text", ""
            for rx, k, u in UNIT_RULES:
                if rx.search(label):
                    kind, unit = k, u
                    break
            inp = '<input disabled placeholder="年/月/日">' if kind == "date" else '<input disabled>'
            out.append(f'<label class="f"><span>{e(label)}</span><span class="in">{inp}{f"<em>{unit}</em>" if unit else ""}</span></label>')
        return out

    def cf_columns(info):
        r = m.infos.get(info)
        for a in multi(r["属性"]) if r else []:
            if a.startswith("年ごとの"):
                return ["年"] + [c for c in a[len("年ごとの"):].split("・") if c]
        return []

    def table(cols, n=4, cls=""):
        head = "".join(f"<th>{e(c)}</th>" for c in cols)
        body = "".join("<tr>" + "".join("<td><i></i></td>" for _ in cols) + "</tr>" for _ in range(n))
        return f'<div class="tw"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'

    def render_ucs(rows):
        parts, list_actions = [], {}
        for r in rows:
            uc = r["UC"]
            if not uc:
                continue
            infos = multi(r["情報"])
            main = infos[0] if infos else ""
            ext = (multi(r["外部システム"]) or [""])[0]
            verb = uc_verb(uc)
            if len(multi(r["画面"])) >= 3:
                # 多くの画面にまたがるUCは、同じ入力画面を複製せず、各画面の上で編集する対象を切り替える
                parts.insert(0, f'<div class="block row"><span class="hint">編集する対象</span><div class="seg">'
                                f'<b class="on">現状</b><b>{e(main)}を選ぶ</b></div></div>'
                                f'<p class="hint">{e(main)}を選ぶと、この画面で変えた項目だけが{e(main)}に保存されます({e(uc)})</p>')
                continue
            if verb.startswith("認証"):
                parts.append(f'<div class="block center"><p class="hint">{e(ext + "アカウントでログインします" if ext else "")}</p>'
                             f'<button class="btn primary">{e(ext + "でログイン" if ext else "ログイン")}</button></div>')
            elif verb.startswith(("複製", "削除")) or verb.endswith("反映する"):
                list_actions.setdefault(main, []).append(verb.replace("する", ""))
            elif verb.startswith("試算"):
                parts.append(f'<div class="block row"><span class="hint">入力が終わったら試算します</span><button class="btn primary">{e(verb)}</button></div>')
            elif verb.startswith("表示"):
                cols = cf_columns(main)
                parts.append(f'<div class="block"><div class="chart"><span>グラフ: {e("・".join(cols[1:]) or main)}の推移</span>'
                             f'<svg viewBox="0 0 300 80" preserveAspectRatio="none" aria-hidden="true"><polyline points="0,60 50,52 100,55 150,40 200,35 250,22 300,18" /></svg></div>'
                             + (table(cols, 5, "cf") if cols else "") + "</div>")
            elif verb.startswith("比較"):
                cols = cf_columns(main)
                pick = "".join(f'<label class="f"><span>{e(main)}{i}</span><select disabled><option>選ぶ</option></select></label>' for i in ("A", "B"))
                cmp_cols = ["年"] + [f"{c}({x})" for c in cols[-1:] for x in ("A", "B")] if cols else []
                parts.append(f'<div class="block"><div class="grid2">{pick}</div><div class="chart"><span>グラフ: A と B の{e(cols[-1] if cols else main)}を重ねて表示</span>'
                             f'<svg viewBox="0 0 300 80" preserveAspectRatio="none" aria-hidden="true"><polyline points="0,60 75,50 150,42 225,30 300,20" /><polyline class="b" points="0,60 75,56 150,52 225,48 300,44" /></svg></div>'
                             + (table(cmp_cols, 4) if cmp_cols else "") + "</div>")
            elif verb.startswith("退会"):
                targets = "、".join(infos)
                parts.append(f'<div class="block"><p class="warn">退会すると、{e(targets)}のデータが削除されます。元に戻せません。</p>'
                             f'<button class="btn danger">{e(verb.replace("させる", "する"))}</button></div>')
            else:
                fs = fields(main, ext)
                is_list = main in many and not verb.startswith("作成")
                title = f'<div class="bh"><b>{e(main)}</b><span class="uc">{e(uc)}</span></div>'
                if not fs:
                    parts.append(f'<p class="hint">{e(main)}は入力する項目がなく、自動で作られます({e(uc)})</p>')
                    continue
                if is_list:
                    labels = [re.sub(r"<[^>]+>", "", f.split("</span>")[0]) for f in fs]
                    body = (table(labels, 2) + f'<button class="btn ghost">+ {e(main)}を追加</button>'
                            f'<details class="edit"><summary>追加・編集の入力欄</summary><div class="form">{"".join(fs)}</div></details>')
                else:
                    body = f'<div class="form">{"".join(fs)}</div>'
                btn = f'<button class="btn primary">{e(ext + "で" + verb if ext else verb)}</button>'
                parts.append(f'<div class="block">{title}{body}<div class="acts">{btn}</div></div>')
        for main, acts in list_actions.items():
            r = m.infos.get(main)
            cols = [split_attr(a)[0] for a in multi(r["属性"]) if r and (a.startswith(("名前", "状態")) or a.endswith("日時"))] or [main]
            head = "".join(f"<th>{e(c)}</th>" for c in cols) + "<th></th>"
            btns = "".join(f'<button class="btn mini {"danger" if a.startswith("削除") else ""}">{e(a)}</button>' for a in acts)
            body = "".join("<tr>" + "".join("<td><i></i></td>" for _ in cols) + f"<td class='ra'>{btns}</td></tr>" for _ in range(3))
            parts.insert(0, f'<div class="block"><div class="bh"><b>{e(main)}の一覧</b></div><div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>')
        return "".join(parts)

    nav, views = [], []
    names = screen_order(m)
    by_buc = {}
    for s in names:
        by_buc.setdefault(screens[s]["buc"], []).append(s)
    cur_g = None
    for idx, s in enumerate(names):
        sc = screens[s]
        rows = sc["rows"]
        actors = sorted({a for r in rows for a in multi(r["アクター"])})
        admin = any(a == "運営者" for a in actors) or "管理" in s
        if sc["g"] != cur_g:
            cur_g = sc["g"]
            nav.append(f'<div class="ng">{e(cur_g)}</div>')
        hyp = any(is_hyp(r) for r in rows)
        nav.append(f'<a href="#scr-{idx}" data-i="{idx}">{e(s)}{"<sup>仮</sup>" if hyp else ""}</a>')
        sib = by_buc[sc["buc"]]
        steps = ""
        if len(sib) > 2:
            steps = '<div class="steps">' + "".join(
                f'<a href="#scr-{names.index(x)}" class="{"on" if x == s else ""}">{e(x.replace("入力画面", "").replace("画面", ""))}</a>' for x in sib) + "</div>"
        app = (f'<div class="app {"admin" if admin else ""}"><div class="bar"><b>{e(sysname)}{" 管理" if admin else ""}</b>'
               f'<span>{"運営者" if admin else "相談者"}</span></div>{steps}<div class="page"><h3>{e(s.replace("画面", ""))}</h3>{render_ucs(rows)}</div></div>')
        notes = ""
        for r in rows:
            if not r["UC"]:
                continue
            notes += (f'<li><b>{e(r["UC"])}</b>{source_badge(r["出典"])}{"".join(f"<span class=qref>{e(q)}</span>" for q in multi(r["質問"]))}'
                      f'<div class="sub">アクティビティ: {e(r["アクティビティ"])} / 情報: {e("、".join(multi(r["情報"])))}'
                      + (f' / 連携: {e(r["イベント"])}({e(r["外部システム"])})' if r["イベント"] else "") + "</div></li>")
        views.append(
            f'<section class="view" id="scr-{idx}" data-i="{idx}"><div class="vh"><div><div class="crumb">{e(sc["g"])} / {e(sc["buc"])}</div>'
            f'<h2>{e(s)}</h2><div class="sub">使う人: {e("、".join(actors))}</div></div></div>'
            f'<div class="stage"><div class="device">{app}</div></div>'
            f'<aside class="notes"><h4>この画面でできること</h4><ul>{notes}</ul>'
            f'<div class="memo"><label for="memo-{idx}">メモ</label><textarea id="memo-{idx}" data-key="{e(s)}" data-label="{e(s)}" rows="2" placeholder="足りない項目、分かりにくい点など"></textarea></div></aside></section>')

    open_n = sum(1 for q in qs.values() if q_status(q) in UNRESOLVED)
    tmpl = (SKILL_DIR / "templates" / "mock.html.tmpl").read_text(encoding="utf-8")
    now = datetime.datetime.now()
    out = (tmpl.replace("__TITLE__", e(f"{sysname} 画面モック"))
               .replace("__SYSTEM__", e(sysname))
               .replace("__STORE__", e(f"rdra-mock:{sysname}"))
               .replace("__META__", e(f"{now.year}年{now.month}月{now.day}日 {now:%H:%M} 時点・画面 {len(names)}・未解決の質問 {open_n}"))
               .replace("<!--__NAV__-->", "".join(nav))
               .replace("<!--__VIEWS__-->", "".join(views)))
    (d / "mock.html").write_text(out, encoding="utf-8")
    return len(names)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="RDRA要件定義スキルの機械処理")
    ap.add_argument("--dir", default="docs/rdra")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("check")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("gate")
    p.add_argument("gate", choices=["1", "2", "done"])
    p = sub.add_parser("set-phase")
    p.add_argument("phase", type=int, choices=[1, 2, 3])
    p.add_argument("--force", metavar="理由")
    p = sub.add_parser("accept")
    p.add_argument("key")
    p.add_argument("reason")
    p = sub.add_parser("reopen")
    p.add_argument("reason")
    p = sub.add_parser("mark-done")
    p.add_argument("--force", metavar="理由")
    p = sub.add_parser("trace")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("lint-request")
    p.add_argument("--draft", action="store_true")
    p = sub.add_parser("adopt")
    p.add_argument("--replace", action="store_true")
    for name in ("next-qid", "html", "merge-answers", "diagrams", "analysis", "status", "prd", "mock"):
        sub.add_parser(name)
    args = ap.parse_args()
    d = Path(args.dir)

    if args.cmd == "init":
        created = cmd_init(d)
        print("作成: " + (", ".join(created) if created else "なし(全て既存)"))
        return 0
    if not d.exists():
        print(f"{d} がない。先に init を実行する", file=sys.stderr)
        return 2

    if args.cmd == "check":
        st = load_state(d)
        qs, _ = parse_questions(d / "questions.md")
        issues = run_checks(Model(d), qs, st["phase"])
        if args.json:
            print(json.dumps([dict(i.to_dict(), accepted=st["accepted"].get(i.key)) for i in issues],
                             ensure_ascii=False, indent=2))
        else:
            for i in issues:
                acc = "  (許容済)" if i.key in st["accepted"] else ""
                print(f"[{i.severity}] {i.key}  {i.msg}  {i.loc}{acc}")
            print(f"計 {len(issues)} 件")
        return 0
    if args.cmd == "gate":
        reasons = evaluate_gate(d, args.gate)
        if reasons:
            print("満たしていない:")
            for r in reasons:
                print(f"- {r}")
            return 1
        print("満たしている")
        return 0
    if args.cmd == "set-phase":
        st = load_state(d)
        if args.phase < st["phase"]:
            print(f"現在のフェーズは{st['phase']}。フェーズ番号は戻さないので変更しない")
            return 0
        if args.phase > 1:
            reasons = evaluate_gate(d, str(args.phase - 1))
            if reasons and not args.force:
                print("判定条件を満たしていない(--force 理由 で上書き可):")
                for r in reasons:
                    print(f"- {r}")
                return 1
            if reasons:
                st["force"].append({"date": datetime.datetime.now().isoformat(timespec="minutes"),
                                    "gate": f"{args.phase - 1}→{args.phase}", "reason": args.force})
        st["phase"] = args.phase
        save_state(d, st)
        print(f"フェーズ{args.phase}に設定")
        return 0
    if args.cmd == "mark-done":
        st = load_state(d)
        reasons = evaluate_gate(d, "done")
        if reasons and not args.force:
            print("完成条件を満たしていない(--force 理由 で上書き可):")
            for r in reasons:
                print(f"- {r}")
            return 1
        if reasons:
            st["force"].append({"date": datetime.datetime.now().isoformat(timespec="minutes"),
                                "gate": "完成", "reason": args.force})
        st["done"] = True
        save_state(d, st)
        print("完成として記録")
        return 0
    if args.cmd == "reopen":
        st = load_state(d)
        if not st.get("done"):
            print("完成になっていない(変更なし)")
            return 0
        st["done"] = False
        st["force"].append({"date": datetime.datetime.now().isoformat(timespec="minutes"),
                            "gate": "完成を外す", "reason": args.reason})
        save_state(d, st)
        print("完成の記録を外した")
        return 0
    if args.cmd == "accept":
        st = load_state(d)
        st["accepted"][args.key] = args.reason
        save_state(d, st)
        print(f"許容: {args.key}")
        return 0
    if args.cmd == "lint-request":
        issues = lint_request(d, DRAFT if args.draft else "初期要望.txt")
        for sev, msg in issues:
            print(f"[{sev}] {msg}")
        print(f"計 {len(issues)} 件")
        return 1 if any(sev == "致命" for sev, _ in issues) else 0
    if args.cmd == "adopt":
        reasons = adopt_draft(d, args.replace)
        if reasons:
            print("採用できない:")
            for r in reasons:
                print(f"- {r}")
            return 1
        print(f"{DRAFT} を初期要望.txt として採用(下書きは削除)")
        for sev, msg in lint_request(d):
            print(f"[{sev}] {msg}")
        return 0
    if args.cmd == "next-qid":
        qs, _ = parse_questions(d / "questions.md")
        n = max([int(q[2:]) for q in qs] or [0]) + 1
        print(f"Q-{n:03d}")
        return 0
    if args.cmd == "html":
        print(f"questions.html を生成({build_html(d)}問)")
        return 0
    if args.cmd == "merge-answers":
        merged, reopened, unknown = merge_answers(d)
        print(f"取り込み: {', '.join(merged) or 'なし'}")
        if reopened:
            print(f"反映済から回答が変わった(再反映が必要): {', '.join(reopened)}")
        if unknown:
            print(f"questions.md にないID: {', '.join(unknown)}")
        return 0
    if args.cmd == "diagrams":
        build_diagrams(d)
        print("diagrams.md を生成")
        return 0
    if args.cmd == "mock":
        print(f"mock.html を生成(画面 {build_mock(d)})")
        return 0
    if args.cmd == "prd":
        n = build_prd(d)
        print(f"prd.html を生成(未解決の質問 {n} 件)")
        return 0
    if args.cmd == "trace":
        tr = build_trace(Model(d), load_state(d)["phase"])
        print(json.dumps(tr, ensure_ascii=False, indent=2) if args.json else "\n".join(trace_markdown(tr)))
        return 0
    if args.cmd == "analysis":
        build_analysis(d)
        print("analysis.md を生成")
        return 0
    if args.cmd == "status":
        phase, gate, reasons, counts, hyp_rows, sev = build_status(d)
        done = "(完成)" if load_state(d).get("done") else ""
        print(f"フェーズ: {phase}{done} / 仮説の行: {hyp_rows} / 指摘: 致命{sev['致命']} 警告{sev['警告']} 情報{sev['情報']}")
        for p in PRIORITIES:
            print(f"質問[{p}] " + " ".join(f"{s}{counts[(p, s)]}" for s in Q_STATES))
        if gate:
            print(f"次の判定({gate}): " + ("満たしている" if not reasons else f"未達 {len(reasons)} 件"))
            for r in reasons[:15]:
                print(f"- {r}")
        else:
            print("次にやること: " + reasons[0])
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
