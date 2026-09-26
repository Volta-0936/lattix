# 口の include 展開（14y）—— 焼いた本の口が、読んだ源の `include "path"` の行を、そのファイルの中身に差し替える。
# 定義（lattix.py の _expand_includes）と同じ規則: 行の頭の空白を飛ばして `include ` で始まる行（後ろが空白だけなら
# include ではない）。パスは残りの空白と両端の `"` を落としたもの。探す順は 基点/パス → パス → examples/パス → lib/パス
# （基点は取り込んだファイルの居場所。いちばん外は今の場所）。行は `# --- included from パス ---` と中身に替わる
# （中身は最後の改行を一つ落として行で繋がる —— 改行で終わる中身はそのまま、終わらない中身には改行を一つ足す。
# 最後のバイトは写す前に一バイト読んで見る。だから字は定義とバイトまで同じ —— 違うのは \r を落とさないことだけ）。
# 入れ子は取り込んだ中身をそのまま読み続けて開く（枠の積み: 終わりの番地と基点）。
#
# 入口: rsi = 読んだ字の終わり。出口: rsi = 展開した字の終わり（exit_ok へ）。置き場を越えれば exit_big（終了コード 6）。
# 開けない・読めない・深すぎる（32 段）・長すぎるパスは標準エラーに言って終了コード 8。
# 使うのは rax rcx rdx rsi rdi r8 r12 r13 r14 r15 と rsp の下 64KB（rbx r10 rbp は触らない。rsp は戻す）。
# r12 = 字の終わり E、r13 = 行の頭、r14 = 枠の数、r15 = 入口の rsp。
# 枠 i: FR(i) = r15 - 8192 - (i+1)*1040 に [終わり（次の元の行の頭）][基点の長さ][基点 1024]。パスを組む場所 PB = r15 - 8192。
# 控え: [r15-8] 行の頭 ls / -16 行の終わり le / -24 改行の後ろ le1 / -32 試す番 k / -40 fd / -48 前置きの長さ
#       -56 中身の長さ S / -64 パスの頭（源の上）/ -72 パスの長さ L / -80 ずれ delta / -88 差す長さ N / -96 印の長さ M
#       -104 中身の頭 / -120 中身の最後のバイト / -128 足す改行（0 か 1）
.intel_syntax noprefix
.text
exp:
    mov r15, rsp
    sub rsp, 65536
    mov r12, rsi
    .balign 4, 0x90
    nop                            # 即値を四バイトの升に揃える（焼き手が升ごと差す）
    mov r13, 0x11111111            # RBUF（読んだ字の頭 —— 焼き手が差す）
    mov r14, 1
    lea rax, [r15 - 8192 - 1040]   # 枠 0: 終わりは無限、基点は空
    mov qword ptr [rax], -1
    mov qword ptr [rax+8], 0
line:
    cmp r14, 1                     # 終わった枠を下ろす
    jbe popped
    mov rax, r14
    imul rax, rax, 1040
    mov rdx, r15
    sub rdx, rax
    sub rdx, 8192
    cmp r13, [rdx]
    jb popped
    dec r14
    jmp line
popped:
    cmp r13, r12
    jae done
    mov rcx, r13
ws:
    cmp rcx, r12
    jae nl
    movzx eax, byte ptr [rcx]
    cmp al, 32
    je ws_inc
    cmp al, 9
    je ws_inc
    cmp al, 13
    je ws_inc
    cmp al, 11
    je ws_inc
    cmp al, 12
    jne ws_done
ws_inc:
    inc rcx
    jmp ws
ws_done:
    lea rax, [rcx+8]
    cmp rax, r12
    ja nl
    cmp dword ptr [rcx], 0x6c636e69     # "incl"
    jne nl
    cmp dword ptr [rcx+4], 0x20656475   # "ude "
    jne nl
    lea rdi, [rcx+8]
le_loop:
    cmp rdi, r12
    jae le_done
    cmp byte ptr [rdi], 10
    je le_done
    inc rdi
    jmp le_loop
le_done:                           # rdi = 行の終わり le
    lea rsi, [rcx+8]
ps_loop:
    cmp rsi, rdi
    jae nl                         # 後ろが空白だけなら include ではない（定義: 'include' に strip される）
    movzx eax, byte ptr [rsi]
    cmp al, 32
    je ps_inc
    cmp al, 9
    je ps_inc
    cmp al, 13
    je ps_inc
    cmp al, 11
    je ps_inc
    cmp al, 12
    jne ps_done
ps_inc:
    inc rsi
    jmp ps_loop
ps_done:
    mov rdx, rdi
pe_loop:
    movzx eax, byte ptr [rdx-1]
    cmp al, 32
    je pe_dec
    cmp al, 9
    je pe_dec
    cmp al, 13
    je pe_dec
    cmp al, 11
    je pe_dec
    cmp al, 12
    jne q1
pe_dec:
    dec rdx
    jmp pe_loop
q1:
    cmp rsi, rdx
    jae q_done
    cmp byte ptr [rsi], 34
    jne q2
    inc rsi
    jmp q1
q2:
    cmp rdx, rsi
    jbe q_done
    cmp byte ptr [rdx-1], 34
    jne q_done
    dec rdx
    jmp q2
q_done:
    mov [r15-8], r13
    mov [r15-16], rdi
    lea rax, [rdi+1]
    cmp rdi, r12
    jb le1_ok
    mov rax, rdi
le1_ok:
    mov [r15-24], rax
    mov [r15-64], rsi
    mov rax, rdx
    sub rax, rsi
    mov [r15-72], rax
    cmp rax, 2000
    ja err_long
    mov qword ptr [r15-32], 0
try:
    mov rax, [r15-32]
    cmp rax, 0
    jne t1
    mov rax, r14                   # k = 0: 基点（いちばん上の枠）
    imul rax, rax, 1040
    mov rsi, r15
    sub rsi, rax
    sub rsi, 8192
    mov rcx, [rsi+8]
    add rsi, 16
    mov rax, [r15-64]
    cmp byte ptr [rax], 47         # 絶対のパスは基点を付けない
    jne have_prefix
    xor ecx, ecx
    jmp have_prefix
t1:
    mov rdx, [r15-64]
    cmp byte ptr [rdx], 47         # 絶対のパスは一度だけ
    je err_open
    cmp rax, 1
    jne t2
    xor ecx, ecx                   # k = 1: 今の場所
    jmp have_prefix
t2:
    cmp rax, 2
    jne t3
    lea rsi, [rip + s_examples]    # k = 2: examples/
    mov ecx, 9
    jmp have_prefix
t3:
    cmp rax, 3
    jne err_open
    lea rsi, [rip + s_lib]         # k = 3: lib/
    mov ecx, 4
have_prefix:
    lea rdi, [r15-8192]
    mov [r15-48], rcx
    rep movsb
    mov rsi, [r15-64]
    mov rcx, [r15-72]
    rep movsb
    mov byte ptr [rdi], 0
    mov eax, 2                     # open(PB, O_RDONLY)
    lea rdi, [r15-8192]
    xor esi, esi
    xor edx, edx
    syscall
    test rax, rax
    jns opened
    inc qword ptr [r15-32]
    jmp try
opened:
    mov [r15-40], rax
    mov rdi, rax                   # 大きさ = lseek(fd, 0, SEEK_END)
    mov eax, 8
    xor esi, esi
    mov edx, 2
    syscall
    test rax, rax
    js err_open
    cmp rax, 0x40000000            # ディレクトリなど（読めない）
    ja err_open
    mov [r15-56], rax
    mov qword ptr [r15-120], 0     # 中身の最後のバイト（空なら 0）
    test rax, rax
    jz no_last
    lea rsi, [rax-1]               # lseek(fd, S-1, SEEK_SET) して一バイト読む
    mov rdi, [r15-40]
    mov eax, 8
    xor edx, edx
    syscall
    xor eax, eax
    mov rdi, [r15-40]
    lea rsi, [r15-120]
    mov edx, 1
    syscall
no_last:
    mov eax, 8                     # lseek(fd, 0, SEEK_SET)
    mov rdi, [r15-40]
    xor esi, esi
    xor edx, edx
    syscall
    xor eax, eax                   # 足す改行: 中身が改行で終わらなければ一つ（定義は最後の改行を一つ落として行で繋ぐ）
    cmp byte ptr [r15-120], 10
    je nl_add
    inc eax
nl_add:
    mov [r15-128], rax
    mov rax, [r15-72]
    add rax, 25
    mov [r15-96], rax              # M = 20 + L + 5
    add rax, [r15-56]
    add rax, [r15-128]
    mov [r15-88], rax              # N = M + S + 足す改行
    mov rdx, [r15-24]
    sub rdx, [r15-8]
    sub rax, rdx
    mov [r15-80], rax              # delta = N - (le1 - ls)
    mov rdx, r12
    add rdx, rax
    .balign 4, 0x90
    nop
    cmp rdx, 0x22222222            # CAP（置き場の終わり —— 焼き手が差す）
    ja too_big
    mov rcx, r12
    sub rcx, [r15-24]              # 後ろの字の数 = E - le1
    test rax, rax
    jz moved
    js move_fwd
    lea rsi, [r12-1]               # 後ろへずらす: 後ろから写す
    lea rdi, [rsi+rax]
    std
    rep movsb
    cld
    jmp moved
move_fwd:
    mov rsi, [r15-24]
    lea rdi, [rsi+rax]
    rep movsb
moved:
    add r12, [r15-80]
    mov rcx, 1                     # 外側の枠の終わりもずらす
fr_loop:
    cmp rcx, r14
    jae fr_done
    mov rax, rcx
    inc rax
    imul rax, rax, 1040
    mov rdx, r15
    sub rdx, rax
    sub rdx, 8192
    mov rax, [r15-80]
    add [rdx], rax
    inc rcx
    jmp fr_loop
fr_done:
    mov rdi, [r15-8]               # 印の行
    lea rsi, [rip + s_mark1]
    mov ecx, 20
    rep movsb
    lea rsi, [r15-8192]
    add rsi, [r15-48]
    mov rcx, [r15-72]
    rep movsb
    lea rsi, [rip + s_mark2]
    mov ecx, 5
    rep movsb
    mov [r15-104], rdi             # 中身の頭
    mov r8, [r15-56]
rd_loop:
    test r8, r8
    jz rd_done
    xor eax, eax
    mov rdi, [r15-40]
    mov rsi, [r15-104]
    add rsi, [r15-56]
    sub rsi, r8
    mov rdx, r8
    syscall
    test rax, rax
    jle err_open
    sub r8, rax
    jmp rd_loop
rd_done:
    mov eax, 3                     # close
    mov rdi, [r15-40]
    syscall
    cmp qword ptr [r15-128], 0
    je rsv_done
    mov rdi, [r15-104]
    add rdi, [r15-56]
    mov byte ptr [rdi], 10         # 改行で終わらない中身: 行を閉じる
rsv_done:
    cmp r14, 32
    jae err_deep
    mov rax, r14                   # 枠を積む: 終わり = ls + N、基点 = パスの居場所
    inc rax
    imul rax, rax, 1040
    mov rdx, r15
    sub rdx, rax
    sub rdx, 8192
    mov rax, [r15-8]               # 枠の終わり = ls + N（次の行の頭）
    add rax, [r15-88]
    mov [rdx], rax
    mov rcx, [r15-48]
    add rcx, [r15-72]
    lea rsi, [r15-8192]
bl_loop:
    test rcx, rcx
    jz bl_done
    cmp byte ptr [rsi+rcx-1], 47
    je bl_done
    dec rcx
    jmp bl_loop
bl_done:
    cmp rcx, 1000
    ja err_long
    mov [rdx+8], rcx
    lea rdi, [rdx+16]
    rep movsb
    inc r14
    mov r13, [r15-104]             # 取り込んだ中身を読み続ける（入れ子）
    jmp line
nl:
    cmp rcx, r12
    jae nl_end
    cmp byte ptr [rcx], 10
    je nl_found
    inc rcx
    jmp nl
nl_found:
    lea r13, [rcx+1]
    jmp line
nl_end:
    mov r13, r12
    jmp line
done:
    mov rsi, r12
    mov rsp, r15
    jmp exit_ok
too_big:
    mov rsp, r15
    jmp exit_big
err_long:
    lea rsi, [rip + s_long]
    mov edx, 30
    jmp err_say
err_deep:
    lea rsi, [rip + s_deep]
    mov edx, 28
    jmp err_path
err_open:
    lea rsi, [rip + s_open]
    mov edx, 28
err_path:
    mov edi, 2
    mov eax, 1
    syscall
    lea rsi, [r15-8192]
    add rsi, [r15-48]
    mov rdx, [r15-72]
err_say:
    mov edi, 2
    mov eax, 1
    syscall
    lea rsi, [rip + s_nl]
    mov edx, 1
    mov edi, 2
    mov eax, 1
    syscall
    mov edi, 8
    mov eax, 60
    syscall
s_examples: .ascii "examples/"
s_lib:      .ascii "lib/"
s_mark1:    .ascii "# --- included from "
s_mark2:    .ascii " ---\n"
s_open:     .ascii "lattix: cannot open include "
s_deep:     .ascii "lattix: include nested > 32 "
s_long:     .ascii "lattix: include path too long "
s_nl:       .ascii "\n"
    .balign 4, 0x90                # 四バイトの升で終わる
exit_ok:
    .byte 0x48, 0x89, 0x73, 0xf0   # 焼き手の形 123: mov [rbx-16], rsi
    .byte 0xe9, 0, 0, 0, 0         # 焼き手の形 78: jmp -> 41
exit_big:
    .byte 0xe9, 0, 0, 0, 0         # 焼き手の形 78: jmp -> 入力の踏み台（終了コード 6）
