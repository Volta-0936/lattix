# Lattix

> プログラムは**単調写像の宣言**であり、答えは定義により**その最小不動点**である。
> だから **答えが実行に依存しない。**

```
field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edges
```

この3行が、バッチ実行・増分更新・レプリカ分散・任意スケジュール・
C へのコンパイル・答えの検査、すべてを兼ねる。

**文書は少なく保つ。** [SPEC.md](SPEC.md)（言語仕様）/ この README（使い方）/
[GUIDE.md](GUIDE.md)（実装ガイド）/ [CLAUDE.md](CLAUDE.md)（行動原理）。

> **この公開ツリーについて。** ここに入っているのは **Python 版**（解釈実行・解析・
> 検査）と **gcc 版**（C バックエンド。`native.py` / `runtime.py`）である。
> 言語も道具も、この二つで一通り使える。
> **自己ホストしたネイティブ処理系（`.lx` だけで自分自身を焼く道）は進行中**なので、
> ここには含めていない。出来たら足す。

---

## 要るもの

- Python 3.10 以上（依存パッケージは無い。標準ライブラリだけ）
- C バックエンドを使うなら **gcc**（または `cc`）。Python 版だけなら要らない

---

## 動かす

```bash
python3 lattix.py examples/01_shortest.lx      # 解く（解釈実行）
```

```
dist[0] = 0
dist[1] = 3
dist[2] = 1
dist[3] = 8
dist[4] = 11
dist[5] = 13
```

同じ源が、C を通しても走る:

```bash
python3 native.py examples/01_shortest.lx      # C に落として解く（データを焼き込む）
python3 runtime.py examples/01_shortest.lx     # C に落とす。**データは実行時に読む**
python3 attest.py examples/01_shortest.lx      # 答えが最小不動点か検査する
```

`runtime.py` が出すのは **プログラムだけを焼いた実行ファイル**である。表（データ）は
焼き込まれず、実行時に読む —— 二列の表なら生バイト、三列以上なら 8バイト小端の列。
一度焼けば Python から離れる。

### 処理系に問う

```bash
python3 lattix.py f.lx --plan            # 層・臨界路・証明書・往復回数
python3 lattix.py f.lx --barriers        # 障壁が残った理由を一行で
python3 lattix.py f.lx --why 'dist[5]'   # **なぜその値なのか** を訊く
python3 lattix.py f.lx --distributable   # 協調不要か（CALM 判定）
python3 lattix.py f.lx --span            # 並列深度（＝階数の最大値）
python3 lattix.py f.lx --canonical       # 正規形
python3 lattix.py f.lx --address         # 意味の内容アドレス
python3 lattix.py f.lx --json            # 機械向け出力
python3 lattix.py f.lx --shuffle 7       # 発火順序を撹拌して同じ答えを確かめる
```

### 実演

```bash
python3 demo/advantage.py    # 同じ1本のソースが、バッチ・増分・分散・任意順序で動く
python3 demo/certified.py    # 途中で止めた実行に完全性の証明書が出る／証明書が合成する
python3 demo/regional.py     # 大域バリアを一度も張らない
python3 demo/bootstrap.py    # Lattix で書いた字句解析器が Lattix のソースを読む
python3 demo/world.py        # 外界と exactly-once
python3 demo/anytime.py      # 途中答えが SOUND と証明できる
python3 demo/parse.py        # CYK 構文解析。曖昧性が束の衝突として出る
python3 demo/native_world.py # 外界との往復 = 実行ファイルの呼び直し（C 側）
python3 demo/native_incremental.py  # ネイティブ増分。5辺追加で join 6 回
```

### 検証

```bash
./check                  # 全検証（gcc が要る。数十分かかる）
python3 test/verify.py   # 43通りの実行 → 1通りの答え
python3 test/nativecheck.py   # C == 解釈実行
python3 test/sabotage.py      # 誤コンパイルを検査器が捕まえるか
```

---

## 書いてみる

```
table edges = (0,1,4), (0,2,1), (2,1,2), (1,3,5)

field dist : min
dist[0] <- 0
dist[j] <- dist[i] + w   for (i,j,w) in edges
print dist
```

- `<-` は代入ではなく **join（寄与）**。だから順序を書く必要が無い
- 束は `min max set or and flat fourv sum count bag`
- **整数は ℤ**（上限なし）。座標だけは有限の資源で、溢れたらそう言って止まる
- 障壁を書く構文は無い。処理系が最も早い健全な位置に置く
- 詳しくは [SPEC.md](SPEC.md)

`examples/` は 01 から 35 まで番号順に機能が増える（21・22 は **Lattix で書いた
Lattix の字句解析器と構文解析器**）。`lib/` は Lattix で書いたライブラリ
（`stratify.lx` は**この言語の成層器を、この言語自身で書いたもの**、
`fold.lx` は前段と生成器を繋ぐ写し）。

---

## 構造

```
lattix.py    処理系（構文解析・成層・極性解析・証明書・解釈実行）
native.py    C バックエンド（単相化・索引導出・スケジューラ選択・領域実行）
runtime.py   C バックエンド（プログラムだけを焼く。データは実行時）
attest.py    答えの検査器 ← 信頼するのはここだけ
check        全検証

examples/    01〜35（31 生成器 / 32 形の導出 / 33 断片だけの前段）
lib/         Lattix で書かれたライブラリ
test/        正しさの検証
bench/       性能測定
demo/        表現力の実演
work/        参照実装と突き合わせる作業場（engine2.py / flat.py）
```

---

## いま何ができるか（証拠は `./check`）

| | |
|---|---|
| 説明 | **なぜその値なのかを訊ける。** 値なら最短の導出木、⊤ なら食い違った二つの寄与、
⊥ ならどのガードがなぜ偽か |
| 解析 | **到達可能性・定数伝播・到達定義・生存変数・死んだ代入・使用前未定義を一つの不動点で。**
向き（前向き/後ろ向き）も反復順序も kill も書かない |
| 順序 | 43通りの実行 → 1通りの答え。ロック 0 行、大域バリア 0 回 |
| 増分 | 1,304× 削減（最悪 7.5×）。無効化ロジック 0 行 |
| 分散 | gossip 6ラウンドで収束。合意プロトコル 0 行 |
| 並列 | 領域ごとに実行。逐次・領域逐次・領域並列で答え完全一致 |
| 信頼 | 誤コンパイル捕捉率 100%。**並列で出した答えも検査できる** |
| 近似 | 途中答えが SOUND。**領域ごとに COMPLETE も証明できる**。証明書は join で合成する |
| 外界 | exactly-once。トランザクションも冪等キーも 0 行 |
| 速度 | 手書き C Dijkstra の 1.3〜1.5倍。DAG なら反復ゼロで 5〜7× |
| 自己適用 | 成層器（6行）・字句解析器・**構文解析器**を Lattix で記述。記号表 0 行 |
| 自己言及 | 構文解析器が **自分自身**を読み、Python 版と同じ内容アドレスを出す |
| 実行形式 | **C を通さずに走る ELF を書く**（`render` はバイト列。終了コードは計算された答え）|
| アセンブラ | **x86-64 を組む。** 命令列はデータが決め、番地は命令番号に沿った鎖で決まる |
| コード生成 | **`.lx` を入れると実行ファイルが出る**（字句 → 構文 → 形 → 機械語、全部 Lattix）|
| 証明 | **答えのある例題 16/16 が SOUND ✓ COMPLETE ✓**（解釈実行・ネイティブ両方） |
| 頂点 | **閉路で ⊤ になった座標にも証人が付く。** ⊤ になる前の確定値が二つ並ぶ（影の店） |
| 撤回 | 事実を消す。**支持は証明書が既に名指している** ので、密グラフでも 200× 以上削減 |
| ビルド | **実ディレクトリを見て、作り直すものと段を出す。** 順序は一行も書かない ——
`-j` を推測しなくてよい（幅が印字される） |
| 束が表現を決める | **⊥ が 0 の束（`or` / `sum` / `count`）は埋めなくてよい** ——
記憶は最初から 0 である |
| 名前 | **8 文字 × 7 ビット = 56 ビット。一つの整数に畳める。**
升で比べるのは、比べるものに名前を付けていないことの言い換えだった |

**削減するのは実行時間ではなく、人間が正しさを保証しなければならないコードの量。**

境界も同じ精度で: 深度は協調の回数を保証するが**実時間は保証しない**。
スパンは並列時間の**上界**であって実測値ではない。増分 1,304× は最良ケース。
手書き C の 1.3〜1.5倍は一つのベンチであって汎用の主張ではない。

---

## ネイティブ化について

**進行中である。** `.lx` で書いた処理系が `.lx` だけで自分自身を焼き直す道
（字句 → 構文 → 形 → 機械語を一枚に畳んだ自己ホスト）は動いているが、
まだ言語の全体を覆っていない —— 焼ける範囲は言語より狭い。
固まるまでこのツリーには入れない。ここにある Python 版と gcc 版で、言語は一通り使える。

---

## ライセンス

Apache License 2.0 —— [LICENSE](LICENSE) / [NOTICE](NOTICE)
