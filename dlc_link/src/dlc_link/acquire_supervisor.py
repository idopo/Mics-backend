"""Pure PowerShell-text builder for the lab-computer acquisition supervisor (D-88).

Text only -- no `subprocess`, no file I/O, no network. The lab computer must stay free
of any interpreted-language runtime (D-66), so the supervisor cannot be a script in
this package's own language that happens to run there; it is PowerShell text GENERATED
on a different machine by `dlc_link` and never executed by this package itself.

Kept boring on purpose (`38-07-PLAN.md` Task 1 action): parameters at the top as
`$var=` assignments with a comment naming each, then the ffmpeg argument array, then
the bounded restart loop -- a researcher with no other tooling on that machine has to
be able to read and debug this without help.
"""

# A conservative per-line character budget for every generated line -- the plan's own
# paste-safety rule is "under 100 characters"; 90 leaves headroom for the array-
# assignment wrapper itself and for one extra comma before the next token is appended,
# so the final rendered line never crosses 100.
_ARRAY_LINE_BUDGET = 90


def ps_quote(token):
    """PowerShell single-quoted string literal: the only special case is an embedded
    single quote, doubled per PowerShell's own escaping rule."""
    return "'{}'".format(str(token).replace("'", "''"))


def _declare_long_literal(var_name, raw_value):
    """A single token -- the tee spec is one file leg plus one delivery leg in ONE
    string -- can be too long to quote on one line by itself, and a per-token chunker
    cannot split INSIDE a token. This breaks `raw_value` into `$var = '...'` / `$var +=
    '...'` lines, each under `_ARRAY_LINE_BUDGET`, that reconstruct the exact original
    string when PowerShell concatenates them."""
    lines = []
    index, length = 0, len(raw_value)
    first = True
    while index < length or first:
        prefix = "{} = '".format(var_name) if first else "{} += '".format(var_name)
        available = _ARRAY_LINE_BUDGET - len(prefix) - 1  # -1 for the closing quote
        used = 0
        chunk_chars = []
        while index < length and used < available:
            char = raw_value[index]
            cost = 2 if char == "'" else 1  # a literal quote doubles under escaping
            if used + cost > available:
                break
            chunk_chars.append(char)
            used += cost
            index += 1
        escaped = "".join(chunk_chars).replace("'", "''")
        lines.append("{}{}'".format(prefix, escaped))
        first = False
        if index >= length:
            break
    return lines


def render_argv_lines(argv, array_var="a"):
    """Returns `(decl_lines, array_lines)` that together build `$<array_var>` to hold
    `argv`. `decl_lines` declares a short `$tN` variable for any token too long to fit
    a single array-assignment line on its own (see `_declare_long_literal`);
    `array_lines` is the `$a=@(...)` / `$a+=@(...)` sequence, referencing `$tN` in place
    of that token's literal. Every line in both lists stays under `_ARRAY_LINE_BUDGET`
    characters -- length-aware grouping rather than a fixed token count, because a
    device name with spaces and brackets in it is much longer than an ffmpeg flag."""
    decl_lines = []
    elements = []
    long_token_count = 0
    lone_overhead = len("${}+=@(".format(array_var)) + 1  # the ')' this element would close

    for token in argv:
        quoted = ps_quote(token)
        if lone_overhead + len(quoted) <= _ARRAY_LINE_BUDGET:
            elements.append(quoted)
            continue
        var_name = "$t{}".format(long_token_count)
        long_token_count += 1
        decl_lines += _declare_long_literal(var_name, token)
        elements.append(var_name)

    groups = []
    current, current_len = [], len("${}+=@(".format(array_var))
    for element in elements:
        addition = len(element) + (1 if current else 0)  # ", " separator once non-empty
        if current and current_len + addition > _ARRAY_LINE_BUDGET:
            groups.append(current)
            current, current_len = [], len("${}+=@(".format(array_var))
        current.append(element)
        current_len += addition
    if current:
        groups.append(current)

    array_lines = []
    for index, group in enumerate(groups):
        prefix = "${}=@(".format(array_var) if index == 0 else "${}+=@(".format(array_var)
        array_lines.append("{}{})".format(prefix, ",".join(group)))

    return decl_lines, array_lines


def build_supervisor_ps1(ffmpeg_path_var, argv, working_dir_var, log_dir_var,
                          max_restarts, restart_delay_s):
    """Returns the supervisor's PowerShell text.

    `ffmpeg_path_var`, `working_dir_var`, `log_dir_var` are the literal PowerShell
    right-hand-side expressions to assign to `$ff` / `$wd` / `$lg` (e.g. a quoted path
    or an `$env:USERPROFILE`-based expression) -- this module takes no position on
    where ffmpeg lives or where segments land; that is the caller's decision, never a
    hardcoded literal in this function.

    `argv` is the ffmpeg argument list (as from `acquire.build_ffmpeg_argv`), excluding
    the executable itself. Every attempt gets its OWN `-RedirectStandardError` path,
    named with a timestamp and the attempt number, because that log file is witness 3
    of the completeness test and `-RedirectStandardError` truncates on each new run --
    reusing one path across attempts would lose every attempt but the last.
    """
    decl_lines, array_lines = render_argv_lines(argv, array_var="a")

    lines = [
        "# GENERATED by dlc-link-relay --print supervisor (dlc_link.acquire_supervisor).",
        "# Hand edits drift from the generator -- regenerate instead of editing this file.",
        "# See dlc_link/RUNBOOK.md, ACQUISITION section, for what each piece is for.",
        "",
        "$ff = {}".format(ffmpeg_path_var),
        "$wd = {}".format(working_dir_var),
        "$lg = {}".format(log_dir_var),
        "$maxRestarts = {}".format(int(max_restarts)),
        "$restartDelaySec = {}".format(restart_delay_s),
        "",
        "# The ffmpeg argument array. Each line stays short on purpose -- a long single",
        "# line wraps on paste in a Windows terminal, which cost two real failures in the",
        "# 2026-09-10 rig session (38-HARDWARE-VALIDATION.md, rule 3, defect 8.3).",
    ]
    lines += decl_lines
    lines += array_lines
    lines += [
        "",
        "New-Item -ItemType Directory -Force -Path $wd,$lg | Out-Null",
        "",
        "$attempt = 0",
        "$lastExit = $null",
        "while ($attempt -lt $maxRestarts) {",
        "    $attempt++",
        "    if ($attempt -gt 1) {",
        '        Write-Host "restart attempt $attempt after previous exit code $lastExit"',
        "        Start-Sleep -Seconds $restartDelaySec",
        "    }",
        '    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"',
        '    $err = Join-Path $lg "acq-$stamp-attempt$attempt.err.log"',
        "    $sp = @{FilePath=$ff; ArgumentList=$a; WorkingDirectory=$wd}",
        "    $proc = Start-Process @sp -NoNewWindow -Wait -PassThru -RedirectStandardError $err",
        "    $lastExit = $proc.ExitCode",
        "}",
        'Write-Host "gave up after $attempt attempts; last exit code $lastExit; log $err"',
        'Write-Host "segment directory: $wd"',
        'Write-Host "log directory: $lg"',
    ]
    return "\n".join(lines) + "\n"
