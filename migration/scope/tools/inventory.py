#!/usr/bin/env python3
"""Deterministic source inventory. No host execution or inferred runtime facts."""
import argparse
import fnmatch
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
SCOPE = ROOT / 'migration/scope'
SOURCE_SHA = '59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def tracked():
    return dict((p, meta.split()[2]) for row in git('ls-tree', '-r', 'HEAD', 'app', 'scripts', 'samples').splitlines()
                for meta, p in [row.split('\t', 1)])


def citation(path, lines, index):
    return {'path': path, 'line': index + 1, 'text': lines[index]}


def active_cobol(text):
    return '\n'.join('' if len(s) > 6 and s[6] in '*/' else s[7:72] for s in text.splitlines())


def dependencies(text):
    code = active_cobol(text)
    result = []
    patterns = {
        'copy': r'(?m)^[ \t]*COPY\s+[\'\"]?([\w-]+)',
        'call': r'\bCALL\s+[\'\"]([\w-]+)',
        'navigation': r'\b(XCTL|LINK|RETURN)\s+(?:PROGRAM|TRANSID)\s*\(\s*([^)]*)\)',
        'map': r'\bMAP\s*\(\s*([^)]*)\)',
        'mapset': r'\bMAPSET\s*\(\s*([^)]*)\)',
        'file': r'\bFILE\s*\(\s*([^)]*)\)',
        'pgm': r'\bPGM\s*=\s*[\'\"]?([\w&.-]+)',
        'dsn': r'\bDSN(?:AME)?\s*=\s*([^,\s]+)'}
    for kind, pattern in patterns.items():
        source = code if kind not in ('pgm', 'dsn') else text
        for m in re.finditer(pattern, source, re.I):
            result.append({'type': kind, 'value': m.group(m.lastindex).strip(" '\""),
                           'binding': 'literal' if m.group(m.lastindex).strip().startswith(("'", '"')) or kind in ('copy', 'call', 'pgm', 'dsn') else 'data-item',
                           'operation': m.group(1).upper() if kind == 'navigation' else kind,
                           'line': source.count('\n', 0, m.start()) + 1})
    return result


def parse_csd(path, text):
    rows = []
    lines = text.splitlines()
    for m in re.finditer(r'\bDEFINE\s+(FILE|PROGRAM|MAPSET|TRANSACTION)\(([^)]+)\)(.*?)(?=\bDEFINE\s|\Z)', text, re.S):
        rows.append({'type': m[1].lower(), 'name': m[2],
                     'attributes': dict(re.findall(r'(\w+)\(([^)]+)\)', m[3])),
                     'evidence': [citation(path, lines, text.count('\n', 0, m.start()))]})
    return rows


def parse_jcl(path, text):
    """Join physical JCL continuations; keep instream IDCAMS separate."""
    records = []
    for i, line in enumerate(text.splitlines()):
        if not line.startswith('//') or line.startswith('//*'):
            continue
        body = line[2:72]
        m = re.match(r'(\S+)\s+(JOB|EXEC|DD|PROC)\s*(.*)', body)
        if m:
            records.append([m[1], m[2], m[3], i])
        elif records and body[:1].isspace():
            records[-1][2] += ' ' + body.strip()
    job = Path(path).stem.upper()
    step = None
    steps, dds = [], []
    for name, op, body, i in records:
        ev = [citation(path, text.splitlines(), i)]
        if op == 'JOB':
            job = name
        if op == 'EXEC':
            step = name
            pgm = re.search(r'PGM\s*=\s*([^,\s]+)', body)
            proc = re.search(r'PROC\s*=\s*([^,\s]+)', body)
            steps.append({'step': step, 'pgm': pgm[1].strip("'\"") if pgm else None,
                          'proc': proc[1] if proc else (body.split(',')[0].strip() if not pgm else None), 'evidence': ev})
        if op == 'DD':
            ds = re.search(r'DSN(?:AME)?\s*=\s*([^,\s]+)', body)
            disp = re.search(r'DISP\s*=\s*(\([^)]*\)|[^,\s]+)', body)
            dds.append({'job': job, 'step': step, 'dd': name, 'dsn': ds[1] if ds else None,
                        'disp': disp[1] if disp else None, 'parameters': body,
                        'access': 'allocation/write' if disp and ('NEW' in disp[1] or 'MOD' in disp[1]) else 'unknown (DISP is not access intent)',
                        'evidence': ev})
    return {'path': path, 'job': job, 'steps': steps, 'dds': dds}


def parse_defines(path, text):
    out = []
    clean = '\n'.join('' if s.startswith('//') else s for s in text.splitlines())
    for m in re.finditer(r'\bDEFINE\s+(CLUSTER|ALTERNATEINDEX|PATH|GDG|GENERATIONDATAGROUP)\b(.*?)(?=/\*|\bDEFINE\s|\Z)', clean, re.S | re.I):
        attrs = dict(re.findall(r'(NAME|KEYS|RECORDSIZE|RELATE|PATHENTRY|LIMIT)\s*\(([^)]+)\)', m[2], re.I))
        # NAME occurs again for DATA/INDEX; the first is the logical object.
        name = re.search(r'\bNAME\s*\(([^)]+)\)', m[2], re.I)
        if name:
            attrs['NAME'] = name[1]
        out.append({'type': m[1].upper(), 'attributes': attrs,
                    'evidence': [citation(path, text.splitlines(), clean.count('\n', 0, m.start()))]})
    return out


def generate():
    dispositions = json.loads((SCOPE / 'dispositions.json').read_text())
    overlay = dispositions['rules']
    entries, jobs, definitions = [], [], []
    contents = {}
    for path, sha in sorted(tracked().items()):
        raw = (ROOT / path).read_bytes()
        try:
            txt = raw.decode('utf-8')
            binary = '\x00' in txt
        except UnicodeDecodeError:
            txt, binary = raw.decode('latin-1'), True
        contents[path] = txt
        lines = txt.splitlines()
        suffix = Path(path).suffix.lower()
        kind = {'.cpy': 'copybook', '.bms': 'bms', '.csd': 'csd', '.jcl': 'jcl', '.prc': 'proc', '.asm': 'asm', '.mac': 'macro', '.ca7': 'scheduler', '.controlm': 'scheduler'}.get(suffix, 'support')
        if suffix == '.cbl':
            kind = 'cobol-online' if 'EXEC CICS' in txt else 'cobol-batch'
        if '/data/' in path:
            kind = 'data-ebcdic' if '/EBCDIC/' in path else 'data-ascii' if '/ASCII/' in path else 'data'
        deps = dependencies(txt) if suffix in ('.cbl', '.cpy', '.jcl', '.prc') else []
        if suffix in ('.jcl', '.prc'):
            deps = [d for d in deps if d['type'] in ('pgm', 'dsn')]
        for dep in deps:
            dep['evidence'] = [citation(path, lines, dep['line'] - 1)]
        attrs = git('check-attr', 'text', 'binary', '--', path).splitlines()
        policy = {}
        for rule in overlay:
            if fnmatch.fnmatchcase(path, rule['pattern']):
                policy.update({k: v for k, v in rule.items() if k != 'pattern'})
        entries.append(dict(path=path, blob_sha=sha, kind=kind, text_or_binary='binary' if binary else 'text',
                            classification_method={'heuristic': 'UTF-8 decode plus NUL detection; EBCDIC directory labels are not codec proof', 'git_attributes': attrs},
                            metrics={'bytes': len(raw), 'lines': None if binary else len(lines),
                                     'non_comment_code_lines': sum(bool(s.strip()) for s in active_cobol(txt).splitlines()) if suffix == '.cbl' else None,
                                     'cics_commands': len(re.findall(r'EXEC\s+CICS\b', active_cobol(txt), re.I)) if suffix == '.cbl' else None,
                                     'paragraphs': len(re.findall(r'^       [\w-]+\.\s*$', txt, re.M)) if suffix == '.cbl' else None},
                            dependencies=deps, evidence=[citation(path, lines, 0)] if lines and not binary else [citation('LICENSE', (ROOT / 'LICENSE').read_text().splitlines(), 0)],
                            evidence_basis='source first line' if lines and not binary else 'repository license citation; existence/bytes established by tracked path and blob SHA, not text decoding',
                            evidence_status='verified-from-source', **policy))
        if suffix in ('.jcl', '.prc'):
            jobs.append(parse_jcl(path, txt))
            definitions.extend(parse_defines(path, txt))
    csd = parse_csd('app/csd/CARDDEMO.CSD', contents['app/csd/CARDDEMO.CSD'])
    bms = []
    for p, text in sorted(contents.items()):
        if Path(p).suffix.lower() == '.bms':
            bms.extend({'path': p, 'name': m[1], 'type': m[2],
                        'evidence': [citation(p, text.splitlines(), text.count('\n', 0, m.start()))]}
                       for m in re.finditer(r'(?m)^(\w+)\s+(DFHMSD|DFHMDI)\b', text))
    navigation = []
    for entry in entries:
        for dep in entry['dependencies']:
            if dep['type'] == 'navigation':
                navigation.append({'source': entry['path'], **dep,
                                   'commarea_copybooks': [d['value'] for d in entry['dependencies'] if d['type'] == 'copy' and 'COM' in d['value']],
                                   'resolution': 'literal' if re.search(r"(?:PROGRAM|TRANSID)\s*\(\s*['\"]", contents[entry['path']].splitlines()[dep['line']-1]) else 'dynamic; operator journey required'})
    scheduled = []
    for path in ('app/scheduler/CardDemo.ca7', 'app/scheduler/CardDemo.controlm'):
        text = contents[path]
        pattern = r'\bJOB=([\w-]+)' if path.endswith('ca7') else r'<JOB\s[^>]*\bMEMNAME="([^"]+)"'
        names = sorted(set(re.findall(pattern, text)))
        member_mapping = dict(re.findall(r'(?m)^\s*([\w-]+)\s+\d+\s+([\w-]+)\s+CARDDEMO\b', text)) if path.endswith('ca7') else {n: n for n in names}
        resolved_members = {member_mapping.get(n, n) for n in names}
        members = {Path(j['path']).stem.upper() for j in jobs}
        scheduled.append({'path': path, 'jobs': names, 'job_to_member': member_mapping,
                          'member_mapping_evidence': [citation(path, text.splitlines(), i) for i, s in enumerate(text.splitlines()) if re.match(r'^\s*[\w-]+\s+\d+\s+[\w-]+\s+CARDDEMO\b', s)],
                          'missing_members': sorted(resolved_members-members),
                          'dependencies': [{'line': i+1, 'text': s} for i, s in enumerate(text.splitlines()) if 'SCHID=' in s or '<INCOND ' in s or '<OUTCOND ' in s],
                          'not_scheduled_core_jcl': sorted({Path(j['path']).stem.upper() for j in jobs if j['path'].startswith('app/jcl/')}-resolved_members),
                          'script_references': [{'path': p, 'jobs': sorted(n for n in names if n in t)} for p, t in contents.items() if p.startswith('scripts/') and any(n in t for n in names)]})
    external = external_dependencies(entries, contents)
    gaps = list(dispositions['source_gaps'])
    for edge in navigation:
        if edge['binding'] == 'data-item':
            gaps.append(dict(dispositions['dynamic_navigation_policy'],
                             id=f"navigation:{edge['source']}:{edge['line']}:{edge['operation']}",
                             resource=edge['value'], evidence=edge['evidence']))
    return {'schema_version': '1.0.0', 'source_sha': SOURCE_SHA, 'entries': entries,
            'cics': {'resources': csd, 'navigation': navigation, 'bms_definitions': bms},
            'datasets': {'definitions': definitions, 'dd_lineage': [dd for j in jobs for dd in j['dds']],
                         'cics_file_mapping': [r for r in csd if r['type'] == 'file']},
            'batch': {'jobs': jobs, 'scheduler_reconciliation': scheduled},
            'external_dependencies': external,
            'source_gaps': sorted(gaps, key=lambda gap: gap['id']),
            'operator_evidence_requests': operator_requests(entries, jobs),
            'decisions_needed': [{'id': k, 'owner': 'manager/human-decision', 'impact': v} for k, v in {
                'scheduler': 'Choose actual scheduler and approve missing-member reconciliation; do not implement absent jobs.',
                'security': 'Approve Spring identity/RBAC replacement and privileged admin journeys.',
                'dataset-contracts': 'Approve PostgreSQL keys, decimal/date encoding and restart/idempotency contracts.',
                'report-delivery': 'Choose replacement for TDQ/internal-reader, FTP and TXT2PDF; preserve report acceptance fixtures.',
                'scope-freeze': 'Approve proposed module ownership and disposition overlay before migration.'}.items()] +
                [{'id': gap['id'], 'owner': gap['owner'], 'impact': gap['impact'], 'decision': gap['decision']}
                 for gap in dispositions['source_gaps']]}


def external_dependencies(entries, contents):
    specs = {'z/OS': r'z/OS|MVS|SYSUID', 'CICS TS': r'EXEC CICS|DEFINE TRANSACTION',
             'Enterprise COBOL compiler/options': r'COBOL|IGYCRCTL', 'HLASM': r'ASMA90|HLASM|CSECT',
             'code page CP037': r'CP037|IBM-037', 'RACF': r'RACF', 'DFSORT/SORT': r'PGM=SORT',
             'FTP': r'PGM=FTP|\bFTP\b', 'TXT2PDF': r'TXT2PDF', 'internal reader': r'INTRDR',
             'TDQ': r'WRITEQ TD|TDQUEUE|QUEUE\(', 'CA7/Control-M': r'JOBNAME=|1LJOB',
             'MVSWAIT/COBDATFT/maclib': r'MVSWAIT|COBDATFT|ASMWAIT|COCDATFT',
             'LE date services': r'CEE(?:DAYS|DASE|SECS|SECI|DATE)', 'third-party licenses': r'Apache|Copyright'}
    pgms = {d['value'] for e in entries for d in e['dependencies'] if d['type'] == 'pgm'}
    programs = {Path(e['path']).stem.upper() for e in entries if e['kind'].startswith('cobol') or e['kind'] == 'asm'}
    for p in sorted(pgms-programs):
        specs[p] = r'PGM\s*=\s*[\'\"]?' + re.escape(p)
    specs.update({'DFHAID': r'COPY DFHAID', 'DFHBMSCA': r'COPY DFHBMSCA', 'SQLCA': r'INCLUDE SQLCA|COPY SQLCA'})
    for e in entries:
        for d in e['dependencies']:
            if d['type'] in ('copy', 'call') and (d['value'].startswith(('CMQ', 'MQ', 'CEE')) or d['value'] == 'CBLTDLI'):
                specs[d['value']] = re.escape(d['value'])
    searchable = dict(contents)
    for p in ('README.md', 'LICENSE', 'NOTICE'):
        searchable[p] = (ROOT / p).read_text()
    result = []
    for name, pattern in sorted(specs.items()):
        evidence = []
        for path, txt in sorted(searchable.items()):
            for i, s in enumerate(txt.splitlines()):
                if re.search(pattern, s, re.I):
                    evidence.append(citation(path, txt.splitlines(), i))
                    break
            if len(evidence) >= 3:
                break
        result.append({'name': name, 'status': 'verified' if evidence else ('hypothesis' if name == 'code page CP037' else 'unknown'),
                       'evidence': evidence, 'owner': 'operator' if name != 'third-party licenses' else 'manager/human-decision',
                       'impact_on_migration': 'Source dependency only; installed product/version, configuration and replacement equivalence are unverified.',
                       'blocking_for': ['runtime-equivalence', 'cutover-approval'],
                       'operator_evidence_needed': 'Supply installed version/configuration, invocation/options, license entitlement and sanitized success/failure captures for ' + name})
    return result


def operator_requests(entries, jobs):
    requests = [{'id': 'runtime-baseline', 'owner': 'operator', 'ask': 'Capture z/OS, CICS TS, compiler and HLASM versions; compiler/link-edit options; LE configuration; actual dataset CCSID/code page and transfer mode; RACF profiles (redacted); active scheduler product, calendars, dependencies and restart rules.', 'impact': 'Blocks executable equivalence and cutover, not inventory.'}]
    for e in entries:
        if e['kind'] == 'cobol-online' and e['disposition'] != 'excluded':
            requests.append({'id': e['path'], 'owner': 'operator', 'ask': 'Capture every reachable screen journey for ' + Path(e['path']).stem + ', including navigation, validation/empty/error, admin authorization, COMMAREA and resulting record changes, with sanitized before/after data.', 'impact': 'Required acceptance fixtures; no mainframe access available to Devin.'})
    for j in jobs:
        if j['path'].startswith('app/jcl/'):
            requests.append({'id': j['path'], 'owner': 'operator', 'ask': 'Run ' + j['job'] + ' in isolated approved environment; supply expanded JCL/PROC, input/output record layouts and sanitized bytes, spool/SYSOUT, RC/abend, DD allocation, restart/empty/error captures and reconciliation totals.', 'impact': 'Required batch equivalence fixtures; destructive setup jobs require operator approval.'})
    return requests


def serialized():
    return json.dumps(generate(), indent=2, sort_keys=True, ensure_ascii=True) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    output = serialized()
    target = SCOPE / 'manifest.json'
    if args.check:
        ok = target.exists() and target.read_text() == output
        print(('PASS' if ok else 'FAIL') + ' manifest freshness')
        return 0 if ok else 1
    target.write_text(output)
    print('Wrote migration/scope/manifest.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
