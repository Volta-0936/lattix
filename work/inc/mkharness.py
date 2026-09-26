# 試験のための台: expand.s をそのまま使い、argv[1] を読んで展開し、結果を標準出力へ（焼き手を通さずに展開器だけを試す）
s = open('expand.s').read()
s = s.replace('0x11111111', 'OFFSET buf').replace('0x22222222', 'OFFSET bufend')
i = s.index('exit_ok:')
s = s[:i] + '''exit_ok:
    mov rdx, rsi
    lea rsi, [buf]
    sub rdx, rsi
    mov edi, 1
    mov eax, 1
    syscall
    mov eax, 60
    xor edi, edi
    syscall
exit_big:
    mov eax, 60
    mov edi, 6
    syscall
'''
s = s.replace('.text\nexp:', '''.text
.globl _start
_start:
    mov rdi, [rsp+16]
    mov eax, 2
    xor esi, esi
    xor edx, edx
    syscall
    mov rdi, rax
    lea rsi, [buf]
rdl:
    mov eax, 0
    lea rdx, [bufend]
    sub rdx, rsi
    push rdi
    push rsi
    syscall
    pop rsi
    pop rdi
    test rax, rax
    jle rdd
    add rsi, rax
    jmp rdl
rdd:
    jmp exp
exp:''')
s += '\n.bss\n.balign 16\nbuf: .skip 1000000\nbufend:\n'
open('harness.s', 'w').write(s)
