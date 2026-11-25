"""Convert TopicSpan content_lines / intro_lines to DITA 1.3 XML.

State-machine converter (Option A from issue 0014). No external dependencies.
"""
from __future__ import annotations

import csv
import html
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Inline markup helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html.escape(s, quote=False)


def _inline(text: str) -> str:
    text = _esc(text)
    text = re.sub(r'`([^`]+)`', r'<codeph>\1</codeph>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    return text


# ---------------------------------------------------------------------------
# Fragment renderers
# ---------------------------------------------------------------------------

def _render_frag(frag: dict, indent: str = '          ') -> str:
    t = frag['type']
    if t == 'p':
        return f'{indent}<p>{_inline(frag["text"])}</p>'
    elif t == 'code':
        lang = frag.get('lang')
        attr = f' outputclass="language-{lang}"' if lang else ''
        code = _esc(frag['text'])
        return f'{indent}<codeblock{attr}>{code}</codeblock>'
    elif t == 'note':
        return f'{indent}<note type="note"><p>{_inline(frag["text"])}</p></note>'
    elif t == 'ul':
        parts = []
        for item in frag['items']:
            sub = ''.join(
                _render_frag(sf, indent='').lstrip()
                for sf in item['sub']
            )
            if sub:
                parts.append(f'{indent}  <li>{_inline(item["text"])}\n{sub}</li>')
            else:
                parts.append(f'{indent}  <li>{_inline(item["text"])}</li>')
        return f'{indent}<ul>\n' + '\n'.join(parts) + f'\n{indent}</ul>'
    return ''


# ---------------------------------------------------------------------------
# Task converter: content_lines → <task>
# ---------------------------------------------------------------------------

def _convert_task(lines: list[str], span_id: str, title: str) -> str:
    shortdesc_lines: list[str] = []
    prereq_bullets: list[dict] = []
    prereq_prose: list[dict] = []
    steps: list[dict] = []
    cur: dict | None = None
    cur_ul: dict | None = None
    cur_li: dict | None = None
    bullet_indent = 0

    para: list[str] = []
    code_acc: list[str] = []
    code_lang: str | None = None
    state = 'intro'
    state_before_code = 'intro'

    def flush_para() -> str | None:
        if para:
            t = '\n'.join(para)
            para.clear()
            return t
        return None

    def push_para_to_step():
        t = flush_para()
        if t and cur is not None:
            cur['info'].append({'type': 'p', 'text': t})

    def push_para_to_li():
        t = flush_para()
        if t and cur_li is not None:
            cur_li['sub'].append({'type': 'p', 'text': t})

    def push_para_to_prereq():
        t = flush_para()
        if t:
            prereq_prose.append({'type': 'p', 'text': t})

    def close_li():
        nonlocal cur_li
        if cur_li is not None and cur_ul is not None:
            cur_ul['items'].append(cur_li)
            cur_li = None

    def close_ul():
        nonlocal cur_ul
        if cur_ul is not None:
            if cur is not None:
                cur['info'].append(cur_ul)
            cur_ul = None

    def open_bullet(item_text: str, raw_indent: int):
        nonlocal cur_ul, cur_li, state, bullet_indent
        close_li()
        if cur_ul is None:
            cur_ul = {'type': 'ul', 'items': []}
            bullet_indent = raw_indent
            push_para_to_step()
        cur_li = {'text': item_text, 'sub': []}
        state = 'in_bullet'

    def exit_bullet():
        push_para_to_li()
        close_li()
        close_ul()

    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        i += 1

        if re.match(r'^<a ', s) or re.match(r'^<!--', s) or re.match(r'^#{1,2} ', s):
            continue

        # Code fence
        if s.startswith('```'):
            if state == 'code':
                stripped = '\n'.join(
                    l.lstrip(' \t') if l.strip() else '' for l in code_acc
                ).strip('\n')
                frag = {'type': 'code', 'lang': code_lang, 'text': stripped}
                if state_before_code == 'in_bullet' and cur_li is not None:
                    push_para_to_li()
                    cur_li['sub'].append(frag)
                elif cur is not None:
                    push_para_to_step()
                    cur['info'].append(frag)
                code_acc.clear()
                code_lang = None
                state = state_before_code
            else:
                state_before_code = state
                code_lang = s[3:].strip() or None
                state = 'code'
            continue

        if state == 'code':
            code_acc.append(raw.rstrip())
            continue

        # Blockquote NOTE — join continuation lines with \n (not space)
        if s.startswith('> '):
            content = s[2:]
            if re.match(r'\*\*NOTE:\*\*', content, re.I):
                note_body = content[9:].strip()
                note_acc = [note_body] if note_body else []
                while i < len(lines) and lines[i].strip().startswith('>'):
                    more = lines[i].strip()
                    note_acc.append(more[2:] if more.startswith('> ') else '')
                    i += 1
                note_text = '\n'.join(x for x in note_acc if x).strip()
                frag: dict = {'type': 'note', 'text': note_text}
                if state == 'in_bullet' and cur_li is not None:
                    push_para_to_li()
                    cur_li['sub'].append(frag)
                elif cur is not None:
                    push_para_to_step()
                    cur['info'].append(frag)
            continue

        # Section headings
        if s == '**Prerequisites**':
            if state == 'in_bullet':
                exit_bullet()
            t = flush_para()
            if t:
                shortdesc_lines = t.splitlines()
            state = 'prereq'
            continue

        if s == '**Procedure**':
            if state == 'in_bullet':
                exit_bullet()
            push_para_to_prereq()
            state = 'steps'
            continue

        if s == '**Additional resources**':
            if state == 'in_bullet':
                exit_bullet()
            elif state == 'in_step':
                push_para_to_step()
            if cur:
                steps.append(cur)
                cur = None
            state = 'additional'
            continue

        # Empty line
        if not s:
            if state == 'intro' and para:
                shortdesc_lines = list(para)
                para.clear()
            elif state == 'prereq_post':
                push_para_to_prereq()
            elif state == 'in_step':
                push_para_to_step()
            continue

        # State dispatch
        if state == 'intro':
            para.append(s)

        elif state == 'prereq':
            if s.startswith(('* ', '- ')):
                prereq_bullets.append({'text': s[2:].strip(), 'sub': []})
            else:
                state = 'prereq_post'
                para.append(s)

        elif state == 'prereq_post':
            para.append(s)

        elif state == 'steps':
            m = re.match(r'^(\d+)\.\s+(.*)', s)
            if m:
                cur = {'cmd': m.group(2), 'info': []}
                state = 'in_step'

        elif state == 'in_step':
            m = re.match(r'^(\d+)\.\s+(.*)', s)
            if m:
                push_para_to_step()
                steps.append(cur)
                cur = {'cmd': m.group(2), 'info': []}
                continue
            if s.startswith(('* ', '- ')):
                raw_indent = len(raw) - len(raw.lstrip())
                open_bullet(s[2:].strip(), raw_indent)
                continue
            para.append(s)

        elif state == 'in_bullet':
            m = re.match(r'^(\d+)\.\s+(.*)', s)
            if m:
                exit_bullet()
                push_para_to_step()
                steps.append(cur)
                cur = {'cmd': m.group(2), 'info': []}
                state = 'in_step'
                continue
            raw_indent = len(raw) - len(raw.lstrip())
            if s.startswith(('* ', '- ')) and raw_indent == bullet_indent:
                # Sibling bullet at same indent
                push_para_to_li()
                close_li()
                cur_li = {'text': s[2:].strip(), 'sub': []}
                continue
            if raw_indent <= bullet_indent and not s.startswith(('* ', '- ')):
                # Non-bullet at step level — exit bullet list
                push_para_to_li()
                exit_bullet()
                state = 'in_step'
                para.append(s)
                continue
            # Sub-content of current bullet
            para.append(s)

        elif state == 'additional':
            pass  # dropped per issue 0014

    # Flush residuals
    if state == 'in_bullet':
        exit_bullet()
    elif state == 'in_step':
        push_para_to_step()
    if cur:
        steps.append(cur)

    # Render XML
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN"'
        ' "../../dtd/libs/fmdita/dita_resources/DITA-1.3/dtd/technicalContent/dtd/task.dtd">',
        f'<task id="{span_id}">',
        f'  <title>{_inline(title)}</title>',
    ]
    if shortdesc_lines:
        out.append(f'  <shortdesc>{_inline(chr(10).join(shortdesc_lines))}</shortdesc>')
    out.append('  <taskbody>')
    if prereq_bullets or prereq_prose:
        out.append('    <prereq>')
        if prereq_bullets:
            out.append(_render_frag({'type': 'ul', 'items': prereq_bullets}, indent='      '))
        for frag in prereq_prose:
            out.append(_render_frag(frag, indent='      '))
        out.append('    </prereq>')
    if steps:
        out.append('    <steps>')
        for step in steps:
            out.append('      <step>')
            out.append(f'        <cmd>{_inline(step["cmd"])}\n</cmd>')
            if step['info']:
                out.append('        <info>')
                for frag in step['info']:
                    out.append(_render_frag(frag))
                out.append('        </info>')
            out.append('      </step>')
        out.append('    </steps>')
    out.append('  </taskbody>')
    out.append('</task>')
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Concept converter: content_lines → <concept>
# ---------------------------------------------------------------------------

def _convert_concept(lines: list[str], span_id: str, title: str) -> str:
    paragraphs: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s == '**Additional resources**':
            if s == '**Additional resources**':
                break
            continue
        if re.match(r'^<a ', s) or re.match(r'^<!--', s):
            continue
        paragraphs.append(s)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN"'
        ' "../../dtd/libs/fmdita/dita_resources/DITA-1.3/dtd/technicalContent/dtd/concept.dtd">',
        f'<concept id="{span_id}">',
        f'  <title>{_inline(title)}</title>',
    ]
    if paragraphs:
        out.append(f'  <shortdesc>{_inline(paragraphs[0])}</shortdesc>')
    out.append('  <conbody>')
    for p in paragraphs[1:]:
        out.append(f'    <p>{_inline(p)}</p>')
    out.append('  </conbody>')
    out.append('</concept>')
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Assembly converter: intro_lines → <concept>
# ---------------------------------------------------------------------------

def _convert_assembly(intro_lines: list[str], span_id: str, title: str) -> str:
    paragraphs: list[str] = []
    for line in intro_lines:
        s = line.strip()
        if s:
            paragraphs.append(s)

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN"'
        ' "../../dtd/libs/fmdita/dita_resources/DITA-1.3/dtd/technicalContent/dtd/concept.dtd">',
        f'<concept id="{span_id}">',
        f'  <title>{_inline(title)}</title>',
    ]
    if paragraphs:
        out.append(f'  <shortdesc>{_inline(paragraphs[0])}</shortdesc>')
    out.append('  <conbody>')
    for p in paragraphs[1:]:
        out.append(f'    <p>{_inline(p)}</p>')
    out.append('  </conbody>')
    out.append('</concept>')
    return '\n'.join(out)


# ---------------------------------------------------------------------------
# Public conversion entry point
# ---------------------------------------------------------------------------

def convert_span(span: dict, topic_type: str | None, role: str) -> str:
    """Convert a single span dict to DITA XML."""
    span_id = span.get('anchor') or span.get('topic_id', '')
    title = span.get('heading', '')
    if role == 'assembly':
        return _convert_assembly(span.get('intro_lines', []), span_id, title)
    elif topic_type == 'task':
        return _convert_task(span.get('content_lines', []), span_id, title)
    else:
        return _convert_concept(span.get('content_lines', []), span_id, title)


# ---------------------------------------------------------------------------
# Mapping CSV loader
# ---------------------------------------------------------------------------

def load_mapping(mapping_path: Path) -> dict[tuple[str, str], str]:
    """Return {(anchor_id, source_dir): target_dir} from mapping.csv."""
    result: dict[tuple[str, str], str] = {}
    with mapping_path.open(newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            key = (row['anchor_id'].strip(), row['source_dir'].strip())
            result[key] = row['target_dir'].strip()
    return result


# ---------------------------------------------------------------------------
# Model JSON loader (single-file and batch runs)
# ---------------------------------------------------------------------------

def _load_model_jsons(run_dir: Path) -> list[dict]:
    single = run_dir / 'model.json'
    index = run_dir / 'index.json'
    if single.exists():
        return [json.loads(single.read_text(encoding='utf-8'))]
    if index.exists():
        return [
            json.loads(p.read_text(encoding='utf-8'))
            for p in sorted(run_dir.rglob('model.json'))
        ]
    raise FileNotFoundError(f"No model.json or index.json found in {run_dir}")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_convert(
    run_dir: Path,
    output_dir: Path,
    mapping_path: Path,
    dry_run: bool = False,
) -> int:
    """Read model.json(s), route spans via mapping.csv, write DITA files."""
    if not run_dir.exists():
        print(f"error: {run_dir}: no such directory", file=sys.stderr)
        return 1
    if not mapping_path.exists():
        print(f"error: {mapping_path}: no such file", file=sys.stderr)
        return 1

    try:
        models = _load_model_jsons(run_dir)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    mapping = load_mapping(mapping_path)

    provisional_warnings: list[str] = []
    unmapped_warnings: list[str] = []
    written: list[Path] = []

    def process_span(span: dict) -> None:
        anchor = span.get('anchor') or span.get('topic_id', '')
        source_path_str = span.get('source_path', '')
        source_dir = Path(source_path_str).parent.name if source_path_str else ''
        role = span.get('role', 'topic')
        topic_type = span.get('topic_type')
        heading = span.get('heading', anchor)
        file_name = Path(source_path_str).name if source_path_str else ''

        if anchor.startswith('~'):
            provisional_warnings.append(f'  {source_dir}/{file_name}: "{heading}" ({anchor})')
        else:
            key = (anchor, source_dir)
            if key not in mapping:
                unmapped_warnings.append(f'  {source_dir}/{file_name}: "{heading}" ({anchor})')
            else:
                target_dir = mapping[key]
                prefix = f'{source_dir}-assembly-' if role == 'assembly' else f'{source_dir}-'
                filename = f'{prefix}{anchor}.dita'
                dest = output_dir / target_dir / filename
                xml = convert_span(span, topic_type, role)
                if dry_run:
                    print(f"[dry-run] would write: {dest}")
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(xml, encoding='utf-8')
                    written.append(dest)

        for member in span.get('members', []):
            process_span(member)

    for model in models:
        for span in model.get('spans', []):
            process_span(span)

    if provisional_warnings:
        n = len(provisional_warnings)
        print(
            f"WARNING: skipping {n} unanchored span(s)"
            f" — add <a id=\"...\"> to source before converting:",
            file=sys.stderr,
        )
        for w in provisional_warnings:
            print(w, file=sys.stderr)

    if unmapped_warnings:
        n = len(unmapped_warnings)
        print(f"WARNING: skipping {n} span(s) with no mapping.csv entry:", file=sys.stderr)
        for w in unmapped_warnings:
            print(w, file=sys.stderr)

    if not dry_run:
        print(f"written: {len(written)} file(s)")

    return 0
