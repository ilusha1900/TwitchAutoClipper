"""Reproducible native Windows x64 bootstrap (GNU as + objcopy + nm).
Build on Linux: python -I build_native_launcher.py
The resulting EXE opens start.cmd beside itself. It does not embed Python.
Only Windows system DLLs are imported; no download or elevation occurs in EXE.
"""
from pathlib import Path
import struct
import subprocess
import tempfile

ASM = r'''
.intel_syntax noprefix
.section .text
.global start
start:
    sub rsp, 0x38
    xor ecx, ecx
    lea rdx, [rip + path_buffer]
    mov r8d, 32768
    call QWORD PTR [rip + iat_filename]
    test eax, eax
    jz failure
    cmp eax, 32758
    jae failure
    lea r10, [rip + path_buffer]
    xor ecx, ecx
    xor edx, edx
scan:
    movzx eax, WORD PTR [r10 + rcx * 2]
    test eax, eax
    jz scan_done
    cmp eax, 92
    je separator
    cmp eax, 47
    jne next_char
separator:
    mov edx, ecx
next_char:
    inc ecx
    jmp scan
scan_done:
    test edx, edx
    jz failure
    lea r11, [rip + dir_buffer]
    xor ecx, ecx
copy_dir:
    cmp ecx, edx
    jae dir_done
    mov ax, WORD PTR [r10 + rcx * 2]
    mov WORD PTR [r11 + rcx * 2], ax
    inc ecx
    jmp copy_dir
dir_done:
    mov WORD PTR [r11 + rcx * 2], 0
    inc edx
    lea r10, [r10 + rdx * 2]
    lea r11, [rip + script_name]
    xor ecx, ecx
copy_name:
    mov ax, WORD PTR [r11 + rcx * 2]
    mov WORD PTR [r10 + rcx * 2], ax
    inc ecx
    test ax, ax
    jnz copy_name
    lea rcx, [rip + path_buffer]
    call QWORD PTR [rip + iat_attributes]
    cmp eax, -1
    je failure
    xor ecx, ecx
    lea rdx, [rip + open_string]
    lea r8, [rip + path_buffer]
    xor r9d, r9d
    lea rax, [rip + dir_buffer]
    mov QWORD PTR [rsp + 32], rax
    mov QWORD PTR [rsp + 40], 1
    call QWORD PTR [rip + iat_shell]
    cmp rax, 32
    jle failure
    xor ecx, ecx
    call QWORD PTR [rip + iat_exit]
failure:
    xor ecx, ecx
    lea rdx, [rip + error_message]
    lea r8, [rip + title_string]
    mov r9d, 16
    call QWORD PTR [rip + iat_message]
    mov ecx, 1
    call QWORD PTR [rip + iat_exit]
    int3
.balign 4096
.global data_start, imports, imports_end, iat_start, iat_end, data_end
 data_start:
 imports:
    .long kernel_lookup - start + 4096, 0, 0, kernel_name - start + 4096, iat_start - start + 4096
    .long shell_lookup - start + 4096, 0, 0, shell_name - start + 4096, iat_shell - start + 4096
    .long user_lookup - start + 4096, 0, 0, user_name - start + 4096, iat_message - start + 4096
    .long 0, 0, 0, 0, 0
 imports_end:
.balign 8
 kernel_lookup:
    .quad hint_filename - start + 4096
    .quad hint_attributes - start + 4096
    .quad hint_exit - start + 4096
    .quad 0
 shell_lookup:
    .quad hint_shell - start + 4096
    .quad 0
 user_lookup:
    .quad hint_message - start + 4096
    .quad 0
 iat_start:
 iat_filename: .quad hint_filename - start + 4096
 iat_attributes: .quad hint_attributes - start + 4096
 iat_exit: .quad hint_exit - start + 4096
    .quad 0
 iat_shell: .quad hint_shell - start + 4096
    .quad 0
 iat_message: .quad hint_message - start + 4096
    .quad 0
 iat_end:
 kernel_name: .asciz "KERNEL32.dll"
 shell_name: .asciz "SHELL32.dll"
 user_name: .asciz "USER32.dll"
.balign 2
 hint_filename: .short 0
    .asciz "GetModuleFileNameW"
.balign 2
 hint_attributes: .short 0
    .asciz "GetFileAttributesW"
.balign 2
 hint_exit: .short 0
    .asciz "ExitProcess"
.balign 2
 hint_shell: .short 0
    .asciz "ShellExecuteW"
.balign 2
 hint_message: .short 0
    .asciz "MessageBoxW"
'''


def align(value, boundary):
    return (value + boundary - 1) // boundary * boundary


def build():
    wide_strings = {
        'script_name': 'start.cmd',
        'open_string': 'open',
        'title_string': 'Twitchautoclipper 1.0',
        'error_message': 'Could not open start.cmd. Extract ALL files from Twitchautoclipper-1.0.zip into one folder, then run Twitchautoclipper.exe again. Keep the EXE next to start.cmd.',
    }
    assembly = ASM
    for name, value in wide_strings.items():
        assembly += '\n.balign 2\n' + name + ':\n.byte ' + ','.join(
            str(x) for x in (value + '\0').encode('utf-16le')) + '\n'
    assembly += '\n.balign 16\npath_buffer: .zero 65536\ndir_buffer: .zero 65536\ndata_end:\n'
    with tempfile.TemporaryDirectory(prefix='clipper_native_') as work:
        source, obj, binary = [Path(work) / name for name in ('launcher.s', 'launcher.o', 'launcher.bin')]
        source.write_text(assembly, encoding='ascii')
        subprocess.run(['as', '--64', '-o', str(obj), str(source)], check=True)
        # All references must resolve inside the section; no absolute addresses are used.
        relocs = subprocess.check_output(['objdump', '-r', str(obj)], text=True)
        if 'R_X86_64_' in relocs:
            raise RuntimeError('Unexpected unresolved assembly relocation: ' + relocs)
        symbols = {}
        for line in subprocess.check_output(['nm', '-n', str(obj)], text=True).splitlines():
            parts = line.split()
            if len(parts) == 3:
                symbols[parts[2]] = int(parts[0], 16)
        subprocess.run(['objcopy', '-O', 'binary', '-j', '.text', str(obj), str(binary)], check=True)
        blob = binary.read_bytes()
    data_offset = symbols['data_start']
    code, data = blob[:data_offset], blob[data_offset:]
    code_rva, data_rva = 0x1000, 0x1000 + data_offset
    reloc_rva = align(data_rva + len(data), 4096)
    reloc = struct.pack('<IIHH', code_rva, 12, 0, 0)  # ABSOLUTE padding; code is position-independent.
    code_raw, data_raw = align(len(code), 512), align(len(data), 512)
    headers_size = 512
    optional = bytearray(240)
    struct.pack_into('<HBBIIIII', optional, 0, 0x20B, 1, 0, code_raw, data_raw + 512, 0,
                     code_rva, code_rva)
    struct.pack_into('<QII', optional, 24, 0x140000000, 4096, 512)
    struct.pack_into('<HHHHHH', optional, 40, 6, 0, 1, 0, 6, 0)
    struct.pack_into('<IIII', optional, 52, 0, align(reloc_rva + len(reloc), 4096), headers_size, 0)
    struct.pack_into('<HHQQQQII', optional, 68, 2, 0x160, 0x100000, 0x1000,
                     0x100000, 0x1000, 0, 16)
    struct.pack_into('<II', optional, 112 + 8, symbols['imports'] + code_rva,
                     symbols['imports_end'] - symbols['imports'])
    struct.pack_into('<II', optional, 112 + 5 * 8, reloc_rva, len(reloc))
    struct.pack_into('<II', optional, 112 + 12 * 8, symbols['iat_start'] + code_rva,
                     symbols['iat_end'] - symbols['iat_start'])
    dos = bytearray(128)
    dos[:2] = b'MZ'
    struct.pack_into('<I', dos, 60, 128)
    dos[64:64+len(b'Twitchautoclipper Windows x64 launcher\r\n')] = b'Twitchautoclipper Windows x64 launcher\r\n'
    coff = struct.pack('<HHIIIHH', 0x8664, 3, 0, 0, 0, len(optional), 0x22)
    def section(name, size, rva, raw_size, raw_pointer, flags):
        return struct.pack('<8sIIIIIIHHI', name, size, rva, raw_size, raw_pointer, 0, 0, 0, 0, flags)
    headers = (bytes(dos) + b'PE\0\0' + coff + bytes(optional) +
               section(b'.text', len(code), code_rva, code_raw, 512, 0x60000020) +
               section(b'.data', len(data), data_rva, data_raw, 512 + code_raw, 0xC0000040) +
               section(b'.reloc', len(reloc), reloc_rva, 512, 512 + code_raw + data_raw, 0x42000040))
    if len(headers) > headers_size:
        raise RuntimeError('PE headers exceed reserved area')
    output = (headers.ljust(headers_size, b'\0') + code.ljust(code_raw, b'\0') +
              data.ljust(data_raw, b'\0') + reloc.ljust(512, b'\0'))
    Path('Twitchautoclipper.exe').write_bytes(output)
    print(f'Built native Windows x64 bootstrap: Twitchautoclipper.exe ({len(output)} bytes)')


if __name__ == '__main__':
    build()
