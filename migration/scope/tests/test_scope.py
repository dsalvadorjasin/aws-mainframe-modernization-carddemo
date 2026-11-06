import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import inventory
import check_manifest


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
        self.assertEqual(failures, {'CSD program/mapset resources resolve to inventoried implementation'})
        self.assertEqual(check_manifest.source_gaps(self.manifest), ['COCRDSEC'])
        ca7 = self.manifest['batch']['scheduler_reconciliation'][0]
        self.assertEqual(ca7['job_to_member']['CLOSEFIL1'], 'CLOSEFIL')
        self.assertEqual(ca7['job_to_member']['CLOSEFIL2'], 'CLOSEFIL')

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


if __name__ == '__main__':
    unittest.main()
