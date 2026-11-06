"""Conservative literal provenance for fixed-format COBOL navigation.

Finite sets are source upper bounds, not claims of branch feasibility. Unknown
inputs, group overwrites and unsupported producers retain runtime uncertainty.
"""
from pathlib import Path
import re


def code_lines(text):
    return ['' if len(s) > 6 and s[6] in '*/' else s[7:72] for s in text.splitlines()]


def evidence(path, text, start, end=None):
    lines = text.splitlines()
    return [{'path': path, 'line': i + 1, 'text': lines[i]} for i in range(start, (start if end is None else end) + 1)]


def unique(items):
    return [dict(path=p, line=l, text=t) for p, l, t in sorted({(e['path'], e['line'], e['text']) for e in items})]


class Resolver:
    def __init__(self, contents, edges, public_programs=()):
        self.contents = contents
        self.edges = edges
        self.public = set(public_programs)
        self.public_evidence = public_programs if isinstance(public_programs, dict) else {}
        self.copybooks = {}
        for path in sorted(contents):
            if Path(path).suffix.lower() == '.cpy':
                self.copybooks.setdefault(Path(path).stem.upper(), []).append(path)
        self.models = {path: self.model(path) for path in sorted(contents) if Path(path).suffix.lower() == '.cbl'}
        self.caller_targets = {}
        self.caller_values = {}

    def expand(self, path, seen=()):
        if path in seen:
            return []
        rows = []
        for i, line in enumerate(code_lines(self.contents[path])):
            rows.append((line, evidence(path, self.contents[path], i)[0]))
            m = re.match(r'\s*COPY\s+([\w-]+)', line, re.I)
            if m:
                matches = self.copybooks.get(m[1].upper(), [])
                # Prefer the core contracts when an extension duplicates a member.
                core = [p for p in matches if p.startswith(('app/cpy/', 'app/cpy-bms/'))]
                if len(core or matches) == 1:
                    rows.extend(self.expand((core or matches)[0], (*seen, path)))
        return rows

    def model(self, path):
        rows = self.expand(path)
        text = '\n'.join(s for s, _ in rows)
        declarations, stack = {}, []
        matches = list(re.finditer(r'(?m)^\s*(\d{2})\s+([\w-]+)\b', text))
        for index, m in enumerate(matches):
            level, name = int(m[1]), m[2].upper()
            if level == 88:
                continue
            while stack and stack[-1][0] >= level:
                stack.pop()
            end = matches[index+1].start() if index+1 < len(matches) else len(text)
            body = text[m.start():end]
            val = re.search(r'\bVALUE\s+([\'\"])(.*?)\1', body, re.S | re.I)
            startline = text.count('\n', 0, m.start())
            ev = [rows[startline][1]]
            if val:
                ev += [rows[text.count('\n', 0, m.start() + val.start())][1],
                       rows[text.count('\n', 0, m.start() + val.end())][1]]
            declarations[name] = {'parents': [s[1] for s in stack], 'value': val[2].strip() if val else None,
                                  'evidence': unique(ev)}
            stack.append((level, name))
        code = '\n'.join(code_lines(self.contents[path]))
        writes = []
        for m in re.finditer(r'\bMOVE\s+((?:(?!\bMOVE\b).){1,250}?)\s+TO\s+([\w-]+)', code, re.S | re.I):
            start = code.count('\n', 0, m.start())
            end = code.count('\n', 0, m.end())
            writes.append({'source': m[1].strip(), 'target': m[2].upper(), 'line': start+1, 'end': end+1,
                           'evidence': evidence(path, self.contents[path], start, end)})
        # Group INITIALIZE is a real write to all children, not a literal target.
        stops = r'MOVE|SET|IF|ELSE|EXEC|END-IF|PERFORM|GO|CONTINUE|DISPLAY|EVALUATE|END-EVALUATE'
        for m in re.finditer(r'\bINITIALIZE\s+((?:(?!(?:' + stops + r')\b)[\w-]+\s*)+)', code, re.I):
            for name in m[1].split():
                if name in declarations:
                    writes.append({'source': '<INITIALIZE>', 'target': name, 'line': code.count('\n', 0, m.start())+1,
                                   'end': code.count('\n', 0, m.end())+1,
                                   'evidence': evidence(path, self.contents[path], code.count('\n', 0, m.start()))})
        return {'declarations': declarations, 'writes': writes, 'code': code, 'rows': rows}

    def writes(self, path, variable):
        model = self.models[path]
        parents = model['declarations'].get(variable, {}).get('parents', [])
        return [w for w in model['writes'] if w['target'] == variable or w['target'] in parents]

    def straight_line_write(self, path, variable, line):
        """Only use an assignment when no intervening control-flow join/call exists."""
        model = self.models[path]
        writes = [w for w in self.writes(path, variable) if w['end'] < line]
        if not writes:
            return None
        last = max(writes, key=lambda w: w['end'])
        between = '\n'.join(model['code'].splitlines()[last['end']:line-1])
        if re.search(r'\b(?:IF|ELSE|WHEN|END-IF|END-EVALUATE|PERFORM|GO|CALL|END-EXEC|GOBACK)\b|^\S[\w-]*\.\s*$', between, re.M):
            return None
        return last

    def expression(self, path, expression, trail=(), at_line=None, callers=True):
        expression = expression.strip()
        literal = re.fullmatch(r"(['\"])(.*?)\1", expression, re.S)
        if literal:
            value = literal[2].strip()
            return ({value: []}, []) if value else ({}, [('blank target is not a proven navigation value', [])])
        variable = re.split(r'[ (]', expression)[0].upper()
        key = (path, variable)
        if key in trail:
            return {}, [('cyclic assignment requires runtime values', [])]
        trail = (*trail, key)
        model = self.models[path]
        decl = model['declarations'].get(variable)
        candidates, unknown = {}, []
        writes = self.writes(path, variable)
        immediate = self.straight_line_write(path, variable, at_line) if at_line else None
        if immediate:
            writes = [immediate]
        elif decl and decl['value']:
            candidates[decl['value']] = decl['evidence']
        if not immediate and (not decl or not decl['value']):
            unknown.append(('initial value is not proven before all control-flow paths to this use', decl['evidence'] if decl else []))
        for write in writes:
            source = write['source']
            if source == '<INITIALIZE>':
                unknown.append(('INITIALIZE may clear ' + variable + ' before a later assignment', write['evidence']))
                continue
            if write['target'] != variable:
                if 'DFHCOMMAREA' in source.upper():
                    propagated, reasons = self.incoming(path, variable, trail) if callers else ({}, [])
                    for target, ev in propagated.items():
                        candidates.setdefault(target, []).extend(ev + write['evidence'])
                    unknown.extend(reasons)
                    if Path(path).stem.upper() in self.public:
                        unknown.append(('externally initiated CICS COMMAREA can overwrite ' + variable + '; caller set is not closed', write['evidence'] + self.public_evidence.get(Path(path).stem.upper(), [])))
                    elif not propagated:
                        unknown.append(('incoming COMMAREA has no closed literal-proven caller set', write['evidence']))
                    continue
                unknown.append(('group overwrite of ' + variable + ' by ' + source, write['evidence']))
                continue
            values, reasons = self.expression(path, source, trail, callers=callers)
            for target, ev in values.items():
                candidates.setdefault(target, []).extend(ev + write['evidence'])
            unknown.extend((reason, ev + write['evidence']) for reason, ev in reasons)
        # Unknown terminal/file producers never become a finite set by naming convention.
        if not immediate:
            for i, s in enumerate(model['code'].splitlines()):
                if re.search(r'\b(?:INTO|SET|ACCEPT)\s*\(?\s*' + re.escape(variable) + r'\b', s):
                    unknown.append(('input or address mutation of ' + variable, evidence(path, self.contents[path], i)))
        return {t: unique(ev) for t, ev in candidates.items()}, unknown

    def incoming(self, destination, variable, trail):
        """Union only literal-proven internal caller writes; retain open-call uncertainty."""
        candidates, unknown = {}, []
        for edge in self.edges:
            if edge['operation'] not in ('XCTL', 'LINK'):
                continue
            caller = edge['source']
            if edge['binding'] == 'literal':
                targets = {edge['value']: edge['evidence']}
            else:
                key = (caller, edge['line'])
                if key not in self.caller_targets:
                    result = self.menu(edge)
                    self.caller_targets[key] = result if result is not None else self.expression(caller, edge['value'], at_line=edge['line'], callers=False)
                targets, _ = self.caller_targets[key]
            if Path(destination).stem.upper() not in targets:
                continue
            key = (caller, variable, edge['line'])
            if key not in self.caller_values:
                self.caller_values[key] = self.expression(caller, variable, at_line=edge['line'], callers=False)
            vals, reasons = self.caller_values[key]
            for target, ev in vals.items():
                candidates.setdefault(target, []).extend(ev + edge['evidence'] + targets[Path(destination).stem.upper()])
            unknown.extend(reasons)
        return {t: unique(ev) for t, ev in candidates.items()}, unknown

    def menu(self, edge):
        variable = edge['value'].split('(')[0]
        path = edge['source']
        model = self.models[path]
        decl = model['declarations'].get(variable)
        if not decl or 'OPT-PGMNAME' not in variable:
            return None
        source = decl['evidence'][0]['path']
        text = self.contents[source]
        lines = code_lines(text)
        count = re.search(r'\b([\w-]+-OPT-COUNT)\s+PIC\s+9\(02\)\s+VALUE\s+(\d+)', '\n'.join(lines))
        rows = [(i, m[1]) for i, s in enumerate(lines) for m in [re.search(r"PIC\s+X\(08\)\s+VALUE\s+'([^']+)'", s)] if m]
        guards = [(i, s) for i, s in enumerate(model['code'].splitlines()[:edge['line']]) if re.search(r'WS-OPTION.*(?:NOT NUMERIC|OPT-COUNT|ZEROS)|IF NOT ERR-FLG-ON', s)]
        if not count or len(rows) != int(count[2]) or len(guards) < 4 or self.writes(path, variable) or self.writes(path, count[1]):
            return None
        ev = list(decl['evidence'])
        ev += [evidence(source, text, i)[0] for i, s in enumerate(lines) if 'REDEFINES' in s or 'OCCURS' in s]
        member = Path(source).stem.upper()
        ev += [evidence(path, self.contents[path], i)[0] for i, s in enumerate(model['code'].splitlines()) if re.search(r'\bCOPY\s+' + re.escape(member) + r'\b', s)]
        ev += [evidence(path, self.contents[path], i)[0] for i, _ in guards]
        ev += evidence(source, text, '\n'.join(lines).count('\n', 0, count.start()))
        return {t.strip(): unique(evidence(source, text, i) + ev) for i, t in rows}, []

    def resolve(self, edge):
        result = self.menu(edge)
        if result is None:
            result = self.expression(edge['source'], edge['value'], at_line=edge['line'])
        values, unknown = result
        evidence_list = unique([e for _, es in unknown for e in es] + edge['evidence'])
        return {'classification': 'runtime-dependent' if unknown or not values else 'statically-resolved',
                'candidates': [{'target': target, 'evidence': unique(ev + edge['evidence'])} for target, ev in sorted(values.items())],
                'reason': '; '.join(sorted({reason for reason, _ in unknown})) if unknown else 'finite literal-proven source upper bound; branch feasibility is not asserted',
                'evidence': evidence_list}
