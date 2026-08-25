# push する（この箱の外から）

このリポジトリは **commit 三本まで済んでいる**。`origin` も
`https://github.com/Volta-0936/lattix.git` に向けてある。あとは push だけ。

Claude が走っている砂箱の git プロキシが「セッションに登録されていない
リポジトリには資格情報を注さない」と言って 403 を返すので、**あなたの
Windows の端末（PowerShell か Git Bash）から**一度だけ叩いてほしい。

```bash
mkdir D:\\Lattix\\pub
tar xzf D:\\Lattix\\lattix\\lattix-repo.tar.gz -C D:\\Lattix\\pub
cd D:\\Lattix\\pub\\lattix
git push -u origin main
```

（既にある `D:\Lattix\lattix` とぶつからないよう、別の場所に展開する。
push が済んだら `pub` は捨ててよい。）

`git push` が GitHub の資格情報を訊いてきたら、ブラウザ認証か
Personal Access Token を使う。Git for Windows なら普通は
Credential Manager が窓を出す。

## 入っている物

```
1bf6704  Apache License 2.0
2af0a15  accept.py: 木の場所を数えて言う（配る前の一行）
e2c0842  Lattix — 木ぜんぶ（2026-08-24 の状態）
```

- `LICENSE` / `NOTICE` —— Apache-2.0（Copyright 2026 Riku (Volta-0936)）
- `.gitignore` —— `_gen/` と `__pycache__/` を外す
- `.gitattributes` —— `lattix` は binary、`.lx`/`.py`/`.md` は LF

## 上げたあとの確認（6 秒）

clone した木が本物かどうかは、自分で焼かせれば分かる:

```bash
git clone https://github.com/Volta-0936/lattix.git
cd lattix && chmod +x lattix
./lattix lattix.lx L1 && cmp L1 lattix && echo "自分を焼いてバイト一致"
```

## 済ませてある検査（この箱で実測）

| | 結果 |
|---|---|
| `./lattix lattix.lx` → 出力 | 木の `lattix` と **バイト一致**（自己再生産） |
| `python3 test/accept.py` | **61 / 61 一致** |
| `python3 test/relation.py` | 一致 49 / 未対応 3 / 食い違い 0 |
| `sh work/run_all2.sh` | 一致 19 / 食い違い 0 |
| `test/verify.py` `nativecheck.py` `runtimecheck.py` | 全部 OK |
