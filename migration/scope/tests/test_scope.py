import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import inventory
import check_manifest
from navigation import Resolver


class ParserTests(unittest.TestCase):
    def test_cobol_comments_and_dependencies(self):
        text = "       COPY COCOM01Y.\n      *COPY ABSENT.\n           CALL 'CEEDAYS'.\n           EXEC CICS XCTL PROGRAM('COMEN01C') END-EXEC."
        deps = inventory.dependencies(text)
        self.assertEqual([d['value'] for d in deps if d['type'] == 'copy'], ['COCOM01Y'])
        self.assertTrue(any(d['type'] == 'navigation' and d['value'] == 'COMEN01C' for d in deps))

    def test_empty_parsers(self):
        self.assertEqual(inventory.dependencies(''), [])
        self.assertEqual(inventory.parse_csd('x', ''), [])
        self.assertEqual(inventory.parse_defines('x', ''), [])
        self.assertEqual(inventory.parse_jcl('x', '')['steps'], [])

    def test_jcl_continuation_and_lineage(self):
        j = inventory.parse_jcl('x', '//TEST JOB A\n//S EXEC PGM=SORT\n//IN DD DISP=SHR,\n// DSN=A.B\n')
        self.assertEqual(j['steps'][0]['pgm'], 'SORT')
        self.assertEqual(j['dds'][0]['dsn'], 'A.B')
        self.assertEqual(j['dds'][0]['step'], 'S')

    def test_idcams_primary_name_and_keys(self):
        rows = inventory.parse_defines('x', 'DEFINE CLUSTER (NAME(BASE) KEYS(11 0) RECORDSIZE(300 300)) DATA(NAME(BASE.DATA))\n/*')
        self.assertEqual(rows[0]['attributes']['NAME'], 'BASE')
        self.assertEqual(rows[0]['attributes']['KEYS'], '11 0')

    def test_csd(self):
        rows = inventory.parse_csd('x', 'DEFINE TRANSACTION(CR00) GROUP(X)\n PROGRAM(CORPT00C)\n')
        self.assertEqual(rows[0]['attributes']['PROGRAM'], 'CORPT00C')


class IntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((inventory.SCOPE / 'manifest.json').read_text())

    def test_manifest(self):
        failures = {name for name, ok in check_manifest.validate(self.manifest) if not ok}
        self.assertEqual(failures, set())
        self.assertEqual(check_manifest.source_gaps(self.manifest), ['COCRDSEC'])
        ca7 = self.manifest['batch']['scheduler_reconciliation'][0]
        self.assertEqual(ca7['job_to_member']['CLOSEFIL1'], 'CLOSEFIL')
        self.assertEqual(ca7['job_to_member']['CLOSEFIL2'], 'CLOSEFIL')
        menus = [e for e in self.manifest['cics']['navigation'] if 'OPT-PGMNAME' in e['value']]
        self.assertEqual([len(e['resolution']['candidates']) for e in menus], [6, 11, 11])
        self.assertTrue(all(e['resolution']['classification'] == 'statically-resolved' for e in menus))
        self.assertTrue(any('REDEFINES' in ev['text'] for ev in menus[0]['resolution']['candidates'][0]['evidence']))

    def test_tampered_blob_and_duplicate(self):
        m = copy.deepcopy(self.manifest)
        m['entries'][0]['blob_sha'] = 'bad'
        m['entries'].append(m['entries'][0])
        self.assertFalse(dict(check_manifest.validate(m))['tracked coverage and HEAD blob SHAs'])

    def test_tampered_citation(self):
        m = copy.deepcopy(self.manifest)
        e = next(e for e in m['entries'] if e['evidence'][0]['line'] > 0)
        e['evidence'][0]['text'] = 'NOT SOURCE'
        self.assertFalse(dict(check_manifest.validate(m))['all source citations exact'])

    def test_unresolved_copy(self):
        m = copy.deepcopy(self.manifest)
        m['entries'][0]['dependencies'].append({'type': 'copy', 'value': 'ABSENT'})
        self.assertFalse(dict(check_manifest.validate(m))['COPY resolves or explicitly external'])

    def test_scope_exclusion_tamper(self):
        m = copy.deepcopy(self.manifest)
        next(e for e in m['entries'] if e['path'] == 'app/cbl/CBEXPORT.cbl')['disposition'] = 'excluded'
        self.assertFalse(all(ok for _, ok in check_manifest.validate(m)))

    def test_missing_program_and_proc(self):
        m = copy.deepcopy(self.manifest)
        m['entries'][0]['dependencies'].append({'type': 'pgm', 'value': 'ABSENT'})
        m['batch']['jobs'][0]['steps'].append({'proc': 'ABSENT'})
        checks = dict(check_manifest.validate(m))
        self.assertFalse(checks['JCL PGM resolves or explicitly external'])
        self.assertFalse(checks['PROC references resolve'])

    def test_scheduler_tamper(self):
        m = copy.deepcopy(self.manifest)
        m['batch']['scheduler_reconciliation'][0]['missing_members'] = ['ABSENT']
        self.assertFalse(dict(check_manifest.validate(m))['scheduler missing/unscheduled members faithfully reconcile'])

    def test_unresolved_navigation(self):
        m = copy.deepcopy(self.manifest)
        m['entries'][0]['dependencies'].append({'type': 'navigation', 'binding': 'literal', 'operation': 'XCTL', 'value': 'ABSENT'})
        self.assertFalse(dict(check_manifest.validate(m))['literal XCTL/LINK/RETURN targets resolve'])

    def test_unregistered_csd_resource(self):
        m = copy.deepcopy(self.manifest)
        m['cics']['resources'].append({'type': 'program', 'name': 'ABSENT'})
        self.assertFalse(dict(check_manifest.validate(m))['unresolved CSD resources explicitly registered with evidence and decision'])

    def test_gap_without_owner_or_decision(self):
        for field in ('owner', 'decision', 'evidence'):
            with self.subTest(field=field):
                m = copy.deepcopy(self.manifest)
                gap = next(g for g in m['source_gaps'] if g['kind'] == 'missing-source')
                del gap[field]
                self.assertFalse(dict(check_manifest.validate(m))['unresolved CSD resources explicitly registered with evidence and decision'])

    def test_unregistered_dynamic_target(self):
        m = copy.deepcopy(self.manifest)
        gap = next(g for g in m['source_gaps'] if g['kind'] == 'unresolved-dynamic-target')
        m['source_gaps'].remove(gap)
        self.assertFalse(dict(check_manifest.validate(m))['source gap register and dynamic navigation accounting match curated policy'])

    def test_tampered_resolved_candidate(self):
        m = copy.deepcopy(self.manifest)
        edge = next(e for e in m['cics']['navigation'] if e['binding'] == 'data-item' and e['resolution']['classification'] == 'statically-resolved')
        edge['resolution']['candidates'][0]['target'] = 'ABSENT'
        self.assertFalse(dict(check_manifest.validate(m))['statically resolved candidate targets and citation chains resolve'])

    def test_runtime_scope_and_conditional_blocker_tamper(self):
        for tamper in ('edge-scope', 'gap-scope', 'empty-core-blockers', 'conditional-blockers'):
            with self.subTest(tamper=tamper):
                m = copy.deepcopy(self.manifest)
                scope = 'conditional-on-rescoping' if tamper == 'conditional-blockers' else 'core'
                gap = next(g for g in m['source_gaps'] if g.get('scope_class') == scope)
                if tamper == 'edge-scope':
                    edge = next(e for e in m['cics']['navigation'] if e['source'] == gap['source'] and e['line'] == int(gap['id'].split(':')[-2]))
                    edge['resolution']['scope_class'] = 'conditional-on-rescoping'
                elif tamper == 'gap-scope':
                    gap['scope_class'] = 'conditional-on-rescoping'
                elif tamper == 'empty-core-blockers':
                    gap['blocking_for'] = []
                else:
                    gap['blocking_for'] = inventory.blocking('online')
                self.assertFalse(dict(check_manifest.validate(m))['runtime scope matches source dispositions; excluded edges block no core steps'])

    def test_unrecognized_plan_blocker(self):
        m = copy.deepcopy(self.manifest)
        m['operator_evidence_requests'][0]['blocking_for'] = ['unrecognized-step']
        self.assertFalse(dict(check_manifest.validate(m))['blocking steps use approved stable plan IDs and ticket keys only'])


class ResolverTests(unittest.TestCase):
    @staticmethod
    def fixed(*lines):
        return '\n'.join('       ' + line for line in lines) + '\n'

    @staticmethod
    def edges(contents):
        return [dict(d, source=p, evidence=[inventory.citation(p, t.splitlines(), d['line']-1)])
                for p, t in contents.items() for d in inventory.dependencies(t) if d['type'] == 'navigation']

    def test_literal_value(self):
        contents = {'P.cbl': self.fixed('01 TARGET PIC X(8) VALUE', "'DEST'.", 'PROCEDURE DIVISION.', 'EXEC CICS XCTL PROGRAM(TARGET) END-EXEC.')}
        edges = self.edges(contents)
        result = Resolver(contents, edges).resolve(edges[0])
        self.assertEqual(result['classification'], 'statically-resolved')
        self.assertEqual([c['target'] for c in result['candidates']], ['DEST'])
        self.assertTrue(any("'DEST'" in ev['text'] for ev in result['candidates'][0]['evidence']))

    def test_move_literal_assignment_chain(self):
        contents = {'P.cbl': self.fixed('01 TARGET PIC X(8).', "01 CONST PIC X(8) VALUE 'DEST'.", 'PROCEDURE DIVISION.', 'MOVE CONST TO TARGET', 'EXEC CICS XCTL PROGRAM(TARGET) END-EXEC.')}
        edges = self.edges(contents)
        result = Resolver(contents, edges).resolve(edges[0])
        self.assertEqual(result['classification'], 'statically-resolved')
        chain = result['candidates'][0]['evidence']
        self.assertTrue(any('MOVE CONST TO TARGET' in ev['text'] for ev in chain))
        contents['P.cbl'] = contents['P.cbl'].replace('MOVE CONST TO TARGET', "MOVE 'DEST' TO TARGET")
        edges = self.edges(contents)
        self.assertEqual(Resolver(contents, edges).resolve(edges[0])['classification'], 'statically-resolved')

    def test_commarea_propagated_union_and_external_negative(self):
        contents = {'A.cbl': self.fixed('01 CARDDEMO-COMMAREA.', '05 CDEMO-FROM-PROGRAM PIC X(8).', 'PROCEDURE DIVISION.', "MOVE 'FIRST' TO CDEMO-FROM-PROGRAM", "EXEC CICS XCTL PROGRAM('CALLEE') COMMAREA(CARDDEMO-COMMAREA) END-EXEC."),
                    'B.cbl': self.fixed('01 CARDDEMO-COMMAREA.', '05 CDEMO-FROM-PROGRAM PIC X(8).', 'PROCEDURE DIVISION.', "MOVE 'SECOND' TO CDEMO-FROM-PROGRAM", "EXEC CICS XCTL PROGRAM('CALLEE') COMMAREA(CARDDEMO-COMMAREA) END-EXEC."),
                    'CALLEE.cbl': self.fixed('01 CARDDEMO-COMMAREA.', '05 CDEMO-FROM-PROGRAM PIC X(8).', 'PROCEDURE DIVISION.', 'MOVE DFHCOMMAREA TO CARDDEMO-COMMAREA', 'EXEC CICS XCTL PROGRAM(CDEMO-FROM-PROGRAM) END-EXEC.')}
        edges = self.edges(contents)
        result = Resolver(contents, edges).resolve(edges[-1])
        self.assertEqual(result['classification'], 'statically-resolved')
        self.assertEqual([c['target'] for c in result['candidates']], ['FIRST', 'SECOND'])
        for candidate in result['candidates']:
            self.assertTrue(any('MOVE DFHCOMMAREA' in ev['text'] for ev in candidate['evidence']))
            self.assertTrue(any('TO CDEMO-FROM-PROGRAM' in ev['text'] for ev in candidate['evidence']))
        result = Resolver(contents, edges, ['CALLEE']).resolve(edges[-1])
        self.assertEqual(result['classification'], 'runtime-dependent')
        self.assertIn('externally initiated', result['reason'])

    def test_runtime_terminal_input_and_group_overwrite(self):
        for write in ('ACCEPT TARGET', 'MOVE INPUT-RECORD TO GROUP-RECORD'):
            with self.subTest(write=write):
                contents = {'P.cbl': self.fixed('01 GROUP-RECORD.', "05 TARGET PIC X(8) VALUE 'DEST'.", 'PROCEDURE DIVISION.', write, 'EXEC CICS XCTL PROGRAM(TARGET) END-EXEC.')}
                edges = self.edges(contents)
                result = Resolver(contents, edges).resolve(edges[0])
                self.assertEqual(result['classification'], 'runtime-dependent')
                self.assertTrue(result['evidence'])

    def test_conditional_assignment_is_not_a_proof(self):
        contents = {'P.cbl': self.fixed('01 TARGET PIC X(8).', 'PROCEDURE DIVISION.', 'IF SWITCH = 1', "MOVE 'DEST' TO TARGET", 'END-IF', 'EXEC CICS XCTL PROGRAM(TARGET) END-EXEC.')}
        edges = self.edges(contents)
        self.assertEqual(Resolver(contents, edges).resolve(edges[0])['classification'], 'runtime-dependent')


if __name__ == '__main__':
    unittest.main()
