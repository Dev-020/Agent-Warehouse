"""Line-mapped reverse placeholder substitution and 3-way merge."""
from __future__ import annotations

import difflib
import re

def reverse_substitute(t_bytes: bytes, b_bytes: bytes, d_bytes: bytes, settings: dict[str, str], warn_callback) -> bytes:
    t_lines = t_bytes.splitlines(keepends=True)
    b_lines = b_bytes.splitlines(keepends=True)
    d_lines = d_bytes.splitlines(keepends=True)

    if len(t_lines) != len(b_lines):
        # Fallback if mismatch
        return d_bytes

    ops = difflib.SequenceMatcher(None, b_lines, d_lines, autojunk=False).get_opcodes()
    p_lines = []
    
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            p_lines.extend(t_lines[i1:i2])
        elif tag == "replace":
            t_chunk = b"".join(t_lines[i1:i2]).decode("utf-8", "replace")
            d_chunk = b"".join(d_lines[j1:j2]).decode("utf-8", "replace")
            
            # Find which placeholders were present in T chunk
            ph_names = set(re.findall(r"\{\{([a-z][a-z0-9_]*)\}\}", t_chunk))
            
            for n in ph_names:
                if n in settings and settings[n]:
                    d_chunk = d_chunk.replace(str(settings[n]), f"{{{{{n}}}}}")
            p_lines.append(d_chunk.encode("utf-8"))
        elif tag == "insert":
            d_chunk = b"".join(d_lines[j1:j2]).decode("utf-8", "replace")
            for k, v in settings.items():
                if v and v in d_chunk:
                    warn_callback(f"inserted line contains literal '{v}' for setting '{k}'; review needed")
            p_lines.append(d_chunk.encode("utf-8"))
        elif tag == "delete":
            pass
            
    return b"".join(p_lines)
