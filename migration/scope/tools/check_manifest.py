#!/usr/bin/env python3
"""Validate inventory integrity; report source gaps without inventing artifacts."""
import json
from pathlib import Path
import sys
import inventory

DISPOSITIONS = {'migrated', 'compatibility-adapter', 'unused-with-evidence', 'excluded'}


def validate(manifest, freshness=True):
    results = []
    def check(name, ok):
        results.append((name, bool(ok)))
    entries = manifest.get('entries', [])
    actual = inventory.tracked()
    paths = [e['path'] for e in entries]
    check('tracked coverage and HEAD blob SHAs', len(paths) == len(set(paths)) and set(paths) == set(actual)
          and all(e['blob_sha'] == actual.get(e['path']) for e in entries))
    check('core counts (cbl=31 cpy=30 jcl=38)', all(sum(Path(p).parent.as_posix() == 'app/' + k for p in paths) == n for k, n in [('cbl', 31), ('cpy', 30), ('jcl', 38)]))
    check('schema and authoritative source SHA', manifest.get('schema_version') == '1.0.0' and manifest.get('source_sha') == inventory.SOURCE_SHA)
    check('dispositions, ownership and evidence', all(e.get('disposition') in DISPOSITIONS and e.get('owner') and e.get('target_module') and e.get('reason') and e.get('evidence') for e in entries))
    evidence_ok = True
    def walk(value):
        nonlocal evidence_ok
        if isinstance(value, dict):
            if {'path', 'line', 'text'} <= value.keys():
                p = inventory.ROOT / value['path']
                if not p.is_file():
                    evidence_ok = False
                else:
                    lines = p.read_bytes().decode('latin-1' if '\ufffd' in p.read_bytes().decode('utf-8', errors='replace') else 'utf-8').splitlines()
                    evidence_ok &= 0 < value['line'] <= len(lines) and lines[value['line']-1] == value['text']
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(manifest)
    check('all source citations exact', evidence_ok)
    copies = {Path(e['path']).stem.upper() for e in entries if e['kind'] == 'copybook'}
    externals = {e['name'].upper() for e in manifest['external_dependencies']}
    check('COPY resolves or explicitly external', all(d['value'].upper() in copies | externals for e in entries for d in e['dependencies'] if d['type'] == 'copy'))
    programs = {Path(e['path']).stem.upper() for e in entries if e['kind'].startswith('cobol') or e['kind'] == 'asm'}
    check('JCL PGM resolves or explicitly external', all(d['value'].upper() in programs | externals for e in entries for d in e['dependencies'] if d['type'] == 'pgm'))
    procs = {Path(e['path']).stem.upper() for e in entries if e['kind'] == 'proc'}
    check('PROC references resolve', all(s['proc'] is None or s['proc'].upper() in procs for j in manifest['batch']['jobs'] for s in j['steps']))
    transactions = {r['name'] for r in manifest['cics']['resources'] if r['type'] == 'transaction'}
    check('literal XCTL/LINK/RETURN targets resolve', all(
        d['value'].upper() in (transactions if d['operation'] == 'RETURN' else programs)
        for e in entries for d in e['dependencies'] if d['type'] == 'navigation' and d['binding'] == 'literal'))
    mapsets = {r['name'] for r in manifest['cics']['bms_definitions'] if r['type'] == 'DFHMSD'}
    check('literal BMS mapsets resolve', all(d['value'].upper() in mapsets for e in entries for d in e['dependencies'] if d['type'] == 'mapset' and d['binding'] == 'literal'))
    # Reconcile against independently re-parsed source, not a permissive allow-list.
    expected = inventory.generate()
    check('CSD and navigation faithfully reconcile (source gaps reported)', manifest['cics'] == expected['cics'])
    check('CSD program/mapset resources resolve to inventoried implementation', not source_gaps(manifest))
    check('scheduler jobs have JCL members', not any(s['missing_members'] for s in manifest['batch']['scheduler_reconciliation']))
    check('scheduler missing/unscheduled members faithfully reconcile', manifest['batch']['scheduler_reconciliation'] == expected['batch']['scheduler_reconciliation'])
    check('approved scope retained and optional extensions excluded', all(
        e['disposition'] == 'excluded' if e['path'].startswith(('app/app-authorization-ims-db2-mq/', 'app/app-transaction-type-db2/', 'app/app-vsam-mq/'))
        else e['disposition'] != 'excluded' if Path(e['path']).stem.upper() in {'CBEXPORT', 'CBIMPORT', 'CORPT00C', 'COADM01C', 'COUSR00C', 'COUSR01C', 'COUSR02C', 'COUSR03C'} else True for e in entries))
    check('no unsupported unused declarations', all(e['disposition'] != 'unused-with-evidence' for e in entries))
    if freshness:
        check('deterministic regeneration equals committed manifest', manifest == expected)
    return results


def source_gaps(manifest):
    programs = {Path(e['path']).stem.upper() for e in manifest['entries'] if e['kind'].startswith('cobol') or e['kind'] == 'asm'}
    mapsets = {r['name'] for r in manifest['cics']['bms_definitions'] if r['type'] == 'DFHMSD'}
    return [r['name'] for r in manifest['cics']['resources'] if
            (r['type'] == 'program' and r['name'] not in programs) or
            (r['type'] == 'mapset' and r['name'] not in mapsets)]


def main():
    manifest = json.loads((inventory.SCOPE / 'manifest.json').read_text())
    results = validate(manifest)
    for name, ok in results:
        print(('PASS' if ok else 'FAIL') + ' ' + name)
    print('SOURCE GAP unresolved CSD resources: ' + ', '.join(source_gaps(manifest)))
    print('SOURCE GAP dynamic navigation requires operator captures; scheduler missing members are recorded, not supplied.')
    return int(not all(ok for _, ok in results))


if __name__ == '__main__':
    sys.exit(main())
