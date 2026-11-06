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
    pgm_allowlist = json.loads((inventory.SCOPE / 'dispositions.json').read_text())['external_pgm_allowlist']
    referenced_pgms = {d['value'].upper() for e in entries for d in e['dependencies'] if d['type'] == 'pgm'}
    referenced_pgms.update(s['pgm'].upper() for j in manifest['batch']['jobs'] for s in j['steps'] if s.get('pgm'))
    allowlist_evidence = True
    for name, spec in pgm_allowlist.items():
        path, line = spec['source_reference'].rsplit(':', 1)
        allowlist_evidence &= any(e['path'] == path and any(d['type'] == 'pgm' and d['value'].upper() == name and d.get('line') == int(line)
                                  for d in e['dependencies']) for e in entries)
    check('curated external PGM allowlist has referenced programs and vendor rationale',
          manifest.get('external_pgm_allowlist') == pgm_allowlist and
          set(pgm_allowlist) <= referenced_pgms - programs and allowlist_evidence and
          all(all(spec.get(k) for k in ('product', 'rationale', 'vendor_reference', 'source_reference')) for spec in pgm_allowlist.values()))
    check('JCL PGM resolves or explicitly external', referenced_pgms <= programs | (set(pgm_allowlist) & externals))
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
    dynamic = [e for e in manifest['cics']['navigation'] if e['binding'] == 'data-item']
    check('every dynamic navigation edge classified with evidence', all(isinstance(e.get('resolution'), dict) and
          e['resolution'].get('classification') in ('statically-resolved', 'runtime-dependent') and
          e['resolution'].get('reason') and e['resolution'].get('evidence') for e in dynamic))
    all_transactions = {r['name'] for r in manifest['cics']['all_csd_resources'] if r['type'] == 'transaction'}
    check('statically resolved candidate targets and citation chains resolve', all(
        e['resolution']['candidates'] and all(c.get('evidence') and c.get('resolution') == 'inventoried' and
        c['target'] in (all_transactions if e['operation'] == 'RETURN' else programs)
        for c in e['resolution']['candidates']) for e in dynamic if e['resolution']['classification'] == 'statically-resolved'))
    gaps = manifest.get('source_gaps', [])
    required = ('id', 'resource', 'kind', 'owner', 'evidence', 'decision', 'impact')
    check('source gaps have unique IDs, ownership, evidence and recorded decisions',
          len({g.get('id') for g in gaps}) == len(gaps) and all(all(g.get(k) for k in required) and isinstance(g.get('blocking_for'), list) and
          (g.get('decision_status') == 'approved' or (g.get('proposed_disposition') and g.get('operator_evidence_needed'))) for g in gaps))
    card_search = [g for g in gaps if g.get('resource') == 'COCRDSEC']
    approved_exclusion = {
        'id': 'csd-cdv1-cocrdsec', 'resource': 'COCRDSEC', 'transaction': 'CDV1',
        'kind': 'missing-source', 'disposition': 'excluded', 'decision_status': 'approved',
        'owner': 'manager/human-decision',
        'decision': 'd-missing-card-search=exclude-missing-registration, selected by David in Plan view, plan revision 28',
        'migration_in_scope': False, 'original_capture_required': False,
        'original_capture_in_denominator': False, 'parity_in_denominator': False,
        'parity_passed': False, 'parity_status': 'excluded-not-evaluated', 'blocking_for': []}
    excluded = len(card_search) == 1 and all(card_search[0].get(k) == v for k, v in approved_exclusion.items())
    excluded &= all('operator_evidence_needed' not in g and 'proposed_disposition' not in g for g in card_search)
    excluded &= not any(resource in json.dumps(manifest['operator_evidence_requests'] + manifest['decisions_needed']).upper()
                        for resource in ('COCRDSEC', 'CDV1', 'CSD-CDV1-COCRDSEC'))
    check('CDV1/COCRDSEC approved exclusion is nonblocking, outside captures and never parity-passed', excluded)
    registered_csd = [g['resource'] for g in gaps if g.get('kind') == 'missing-source']
    check('unresolved CSD resources explicitly registered with evidence and decision',
          sorted(registered_csd) == sorted(source_gaps(manifest)) and
          all(g.get('owner') and g.get('decision') and g.get('evidence') and
              all(ev.get('path') == 'app/csd/CARDDEMO.CSD' for ev in g['evidence'])
              for g in gaps if g.get('kind') == 'missing-source'))
    check('source gap register and dynamic navigation accounting match curated policy', gaps == expected['source_gaps'])
    runtime = [e for e in dynamic if e['resolution']['classification'] == 'runtime-dependent']
    runtime_gaps = {g['id']: g for g in gaps if g.get('kind') == 'unresolved-dynamic-target'}
    runtime_ids = {f"navigation:{e['source']}:{e['line']}:{e['operation']}" for e in runtime}
    check('only runtime-dependent edges have operator gaps with reasons and requests', set(runtime_gaps) == runtime_ids and
          all(g.get('reason') and g.get('evidence') and g.get('operator_evidence_needed') for g in runtime_gaps.values()))
    dispositions = {e['path']: e['disposition'] for e in entries}
    scoped = True
    core_steps = set(inventory.blocking('protocol', 'goldens', 'online'))
    for edge in runtime:
        gap = runtime_gaps.get(f"navigation:{edge['source']}:{edge['line']}:{edge['operation']}", {})
        expected_scope = 'conditional-on-rescoping' if dispositions.get(edge['source']) == 'excluded' else 'core'
        scoped &= edge['resolution'].get('scope_class') == expected_scope and gap.get('scope_class') == expected_scope and gap.get('source') == edge['source']
        if expected_scope == 'core':
            scoped &= core_steps <= set(gap.get('blocking_for', []))
        else:
            scoped &= gap.get('blocking_for') == [] and gap.get('operator_evidence_needed', '').startswith('Conditional on rescoping')
    check('runtime scope matches source dispositions; excluded edges block no core steps', scoped)
    check('runtime scope counts core=15 conditional=4 (authorization=2 transaction-type=2)',
          sum(e['source'].startswith('app/cbl/') and dispositions.get(e['source']) != 'excluded' for e in runtime) == 15 and
          sum(e['source'].startswith('app/app-authorization-ims-db2-mq/') for e in runtime) == 2 and
          sum(e['source'].startswith('app/app-transaction-type-db2/') for e in runtime) == 2 and len(runtime) == 19)
    blocker_lists = []
    def collect_blockers(value):
        if isinstance(value, dict):
            if 'blocking_for' in value:
                blocker_lists.append(value['blocking_for'])
            for item in value.values():
                collect_blockers(item)
        elif isinstance(value, list):
            for item in value:
                collect_blockers(item)
    collect_blockers(manifest)
    check('blocking steps use approved stable plan IDs and ticket keys only', manifest.get('plan_steps') == inventory.PLAN_STEPS and
          all(isinstance(steps, list) and all(step in inventory.PLAN_STEPS for step in steps) for steps in blocker_lists))
    check('COCRDSEC whole-source absence searches reproduce exactly', all(g.get('absence_evidence') == inventory.absence_evidence()
          for g in gaps if g.get('resource') == 'COCRDSEC'))
    check('scheduler jobs have JCL members', not any(s['missing_members'] for s in manifest['batch']['scheduler_reconciliation']))
    check('scheduler missing/unscheduled members faithfully reconcile', manifest['batch']['scheduler_reconciliation'] == expected['batch']['scheduler_reconciliation'])
    check('approved scope retained and optional extensions excluded', all(
        e['disposition'] == 'excluded' if e['path'].startswith(('app/app-authorization-ims-db2-mq/', 'app/app-transaction-type-db2/', 'app/app-vsam-mq/'))
        else e['disposition'] != 'excluded' if Path(e['path']).stem.upper() in {'CBEXPORT', 'CBIMPORT', 'CORPT00C', 'COADM01C', 'COUSR00C', 'COUSR01C', 'COUSR02C', 'COUSR03C', 'COCRDLIC', 'COCRDSLC', 'COCRDUPC'} else True for e in entries))
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
    print('REGISTERED SOURCE GAP approved exclusion: ' + ', '.join(g['resource'] for g in manifest['source_gaps'] if g.get('disposition') == 'excluded' and g.get('decision_status') == 'approved'))
    print('REGISTERED RUNTIME GAPS dynamic navigation targets: ' + str(sum(g['kind'] == 'unresolved-dynamic-target' for g in manifest['source_gaps'])))
    print('RUNTIME NAVIGATION SCOPE core: ' + str(sum(g.get('kind') == 'unresolved-dynamic-target' and g.get('scope_class') == 'core' for g in manifest['source_gaps'])) +
          '; conditional-on-rescoping: ' + str(sum(g.get('kind') == 'unresolved-dynamic-target' and g.get('scope_class') == 'conditional-on-rescoping' for g in manifest['source_gaps'])))
    print('STATICALLY RESOLVED dynamic navigation targets: ' + str(sum(e['binding'] == 'data-item' and e['resolution']['classification'] == 'statically-resolved' for e in manifest['cics']['navigation'])))
    return int(not all(ok for _, ok in results))


if __name__ == '__main__':
    sys.exit(main())
