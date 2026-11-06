# UNT-1 — source-grounded migration boundary

Authoritative source: `59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e` (origin/main at scope creation).
`manifest.json` schema `1.0.0` is a deterministic inventory of tracked `app/`,
`scripts/` and `samples/` files, not a statement about what is installed or executed.
Original sources and binary archives must remain byte-identical. This ticket adds
no Java or migrated business logic. Proposed destination: Java 21 Spring Boot
modular monolith, PostgreSQL. Module names are proposals, not discovered facts.

## Selected boundary and constraints

Approved: core CICS online and batch; CBEXPORT/CBIMPORT; CORPT00C report submission,
TDQ and internal-reader JCL/PROC path; COADM01C and COUSR00C–COUSR03C user maintenance.
Optional `app/app-authorization-ims-db2-mq`, `app/app-transaction-type-db2` and
`app/app-vsam-mq` are inventoried but **excluded** (Db2/IMS/MQ). Shared build and
sample artifacts mentioning these technologies are retained as compatibility
provenance, not permission to migrate the extensions.

`dispositions.json` is the hand-curated, ordered, last-match-wins scope overlay.
Its explicit `source_gaps` register records missing source separately from file
dispositions, with evidence, ownership, impact, proposed disposition, a pending
decision, operator request and blocking steps. COCRDSEC/CDV1 is proposed
`excluded-pending-decision`, not silently or finally excluded. The curated
`dynamic_navigation_policy` also expands into a manifest gap per dynamic edge,
each with its own source citation and ID. No unresolved navigation is merely logged.
`migrated` means planned migration, never completed migration. No member is
classified `unused-with-evidence`: even `UNUSED1Y.cpy` is not declared unused just
because of its name. Any later unused classification needs a reproducible search
over all source and confirmation about external callers; the current check rejects
unused declarations until such an evidence mechanism is explicitly implemented.

Devin has **no mainframe access**. A human OPERATOR executes the original in an
approved isolated environment and supplies captures. Inventory is not blocked by
missing runtime evidence; equivalence and cutover are.

## Verified from source

All citations are exact path/line/text triples in the manifest. Evidence on binary
or empty entries cites the repository license for provenance only; file existence
and contents are established by tracked path, byte count and Git blob hash, not by
a fictional text line. No archive is unpacked or represented as installed software.

### Counts and coverage

| Area | Tracked files |
|---|---:|
| app (including optional extensions, data and all support dirs) | 240 |
| scripts (including markers) | 56 |
| samples (individual entries, including two binary runtime ZIPs) | 15 |
| Total | 311 |
| Core app/cbl | 31 |
| Core app/cpy | 30 |
| Core app/jcl | 38 |

Across all included directories there are 44 COBOL sources (25 containing active
EXEC CICS, 19 without), 62 copybooks (including generated BMS and extensions),
21 BMS sources, 55 JCL members, 6 PROCs, 2 assembler sources, 2 macros,
4 CSD files, 2 scheduler files, 24 data files and 89 support files.
These categories describe repository artifacts, not runtime invocation counts.

### CICS overview

`app/csd/CARDDEMO.CSD` supplies 61 resource definitions (including FILE,
PROGRAM, MAPSET and TRANSACTION); each has source citations and attributes.
`cics.bms_definitions` separately inventories DFHMSD mapsets and DFHMDI maps.

| Surface | Source programs / contract | Proposed module |
|---|---|---|
| Sign-on / navigation | COSGN00C, COMEN01C, COCOM01Y, COMEN02Y | online / identity adapter |
| Accounts / cards | COACTVWC, COACTUPC, COCRDLIC, COCRDSLC, COCRDUPC | card-services |
| Transactions / bill payment | COTRN00C–COTRN02C, COBIL00C | card-services |
| Administration | COADM01C, COUSR00C–COUSR03C, COADM02Y | card-services / identity adapter |
| Report submission | CORPT00C, CORPT00 mapset, COCOM01Y | online / batch |

`cics.navigation` records XCTL/LINK/RETURN TRANSID edges and COMMAREA-related
COPY members. Many targets are data items (CDEMO-TO-PROGRAM, menu table selections,
WS-TRANID) rather than quoted program names. The graph faithfully records these
expressions; **it is not a resolved runtime call graph**. COCOM01Y is a shared
communication contract, not proof that every edge uses exactly the same layout.

CORPT00C embeds `EXEC PROC=TRANREPT` in generated JCL (line 94), then writes
records to CICS TD queue `JOBS` (lines 517–522). `app/proc/TRANREPT.prc`
contains report work; `app/jcl/TRANREPT.jcl` is a separate batch member.
`app/jcl/INTRDRJ1.JCL` demonstrates IEBGENER writing to SYSOUT=(A,INTRDR) and
references INTRDRJ2. This proves source paths, **not** that queue JOBS is routed
to an internal reader in the deployed region. Request the DCT/TDQUEUE definition,
JES routing and submitted spool from the operator before asserting that link.

### Batch overview

The manifest contains per-member jobs, ordered EXEC steps, PGM/PROC references,
DD allocation and DSN/DISP lineage, including samples and excluded extensions.
Core job groups:

| Purpose | JCL members | Principal programs/utilities |
|---|---|---|
| Dataset setup / load | ACCTFILE, CARDFILE, CUSTFILE, XREFFILE, TRANFILE, TRANIDX, TRANTYPE, TRANCATG, TCATBALF, DISCGRP, DEFCUST | IDCAMS, SDSF |
| Security / alternative organizations | DUSRSECJ, ESDSRRDS | IEFBR14, IEBGENER, IDCAMS |
| GDG / report allocation | DEFGDGB, DEFGDGD, DALYREJS, REPTFILE | IDCAMS, IEBGENER |
| Reads | READACCT, READCARD, READCUST, READXREF | CBACT01C/02C/03C, CBCUS01C |
| Interest / posting | INTCALC, POSTTRAN, COMBTRAN | CBACT04C, CBTRN02C, SORT, IDCAMS |
| Statements / reports | CREASTMT, TRANREPT, PRTCATBL | CBSTM03A, CBTRN03C, SORT, REPROC |
| Backup / synchronization | TRANBKP, WAITSTEP, OPENFIL, CLOSEFIL | REPROC, IDCAMS, COBSWAIT/MVSWAIT, SDSF |
| Export / import | CBEXPORT, CBIMPORT | same-named COBOL programs, IDCAMS |
| Host submission / transport | INTRDRJ1, INTRDRJ2, FTPJCL, TXT2PDF1 | IEBGENER, IDCAMS, FTP, IKJEFT1B |
| Resource installation | CBADMCDJ | DFHCSDUP |

DISP=NEW/MOD suggests allocation/write intent. DISP=SHR/OLD **does not establish
read vs write**; these DDs deliberately say unknown. SORT control cards, COBOL
OPEN modes, IDCAMS INFILE/OUTFILE and executed utility behavior must be reconciled
before constructing a dataflow DAG. Symbolic DSNs, temporary datasets, GDG offsets,
JCLLIB search and PROC overrides remain source expressions, not expanded host DSNs.

Scheduler reconciliation treats JCL member identity separately from JOB card name.
Both CA7 listing and Control-M XML are parsed, including dependency statements /
INCOND and OUTCOND conditions, scripts references and unscheduled core members.
CA7 **CLOSEFIL1 and CLOSEFIL2 map explicitly to member CLOSEFIL** in the listing
(lines 225 and 252); job-name-only matching would falsely report missing JCL.
Control-M members reconcile against all inventoried JCL, including excluded
extension jobs: this does not put those jobs back in scope. The actual scheduler
and which schedules are active are unknown. Unscheduled JCL is not evidence of
dead code (manual setup, submission and operator-run jobs exist).

### Dataset and key overview

KEYS below is `(length, zero-based offset)` from IDCAMS, not a SQL key declaration.
Full definitions, RELATE/PATHENTRY, RECORDSIZE, DD lineage and CSD FILE→DSNAME
mapping are in `datasets` in the manifest. Repeated definitions are kept, not
silently deduplicated. CSD maps eight logical FILE names to DSNAMEs.

| Core object (AWS.M2.CARDDEMO prefix unless noted) | Primary KEYS | RECORDSIZE | Alternate KEYS / path |
|---|---|---|---|
| ACCTDATA.VSAM.KSDS | 11,0 | 300,300 | — |
| CARDDATA.VSAM.KSDS | 16,0 | 150,150 | AIX 11,16; AIX.PATH; NONUNIQUEKEY |
| CARDXREF.VSAM.KSDS | 16,0 | 50,50 | AIX 11,25; AIX.PATH |
| CUSTDATA.VSAM.KSDS | 9,0 | 500,500 | — |
| AWS.CUSTDATA.CLUSTER (DEFCUST) | 10,0 | 500,500 | separate definition, not equivalent by assumption |
| TRANSACT.VSAM.KSDS | 16,0 | 350,350 | AIX 26,304; AIX.PATH |
| TRXFL.VSAM.KSDS (CBIMPORT) | 32,0 | 350,350 | — |
| EXPORT.DATA | 4,28 | 500,500 | inspect CVEXPORT and export sequence contract |
| DISCGRP.VSAM.KSDS | 16,0 | 50,50 | — |
| USRSEC.VSAM.KSDS | 8,0 | 80,80 | ESDS and RRDS variants also defined |
| TCATBALF.VSAM.KSDS | 17,0 | 50,50 | — |
| TRANCATG.VSAM.KSDS | 6,0 | 60,60 | — |
| TRANTYPE.VSAM.KSDS | 2,0 | 60,60 | — |

GDGs include TRANSACT.BKUP, TRANSACT.DALY, TRANREPT, TCATBALF.BKUP,
SYSTRAN and TRANSACT.COMBINED (DEFGDGB); other GDG definitions and all sequential
DD DSNs are preserved individually. PostgreSQL mapping must preserve duplicate
alternate keys, record ordering, decimal representations and report generation
semantics; catalog definitions alone are not a relational design.

### Findings and ambiguities

* **Registered missing implementation:** CSD defines PROGRAM(COCRDSEC) at line
  211. CDV1 at lines 388–390 is labelled `DEVELOPER TRANSACTION - 1` and points
  to it, but no matching source program is inventoried. It is not part of approved
  user journeys. Register `csd-cdv1-cocrdsec` proposes `excluded-pending-decision`,
  owned by manager/human-decision. The operator must confirm whether a COCRDSEC
  load module exists on the host and whether CDV1 is used; supply source or approve
  exclusion. Do not invent behavior or substitute COCRDSLC. This remains a decision
  needed and blocks developer-transaction scope approval and cutover approval.
* **Scheduler aliases:** CA7 explicitly lists CLOSEFIL as the member for both
  CLOSEFIL1 and CLOSEFIL2. Member resolution is verified from the listing; deployed
  scheduler overrides, activation and per-job parameters remain unverified.
* README's job table labels CLOSEFIL/OPENFIL as IEFBR14, whereas actual members
  execute **SDSF** and issue CEMT commands to a named region. Source wins over
  the descriptive table; installed region names and authorization remain unknown.
* `app/jcl/CBADMCDJ.jcl` includes resource names differing from CARDDEMO.CSD
  (for example COACT00S). The requested canonical resource inventory uses
  CARDDEMO.CSD, not the assumption that every install script is synchronized.
* Customer keys differ between DEFCUST and CUSTFILE. Neither README terminology
  nor matching record size establishes equivalent key semantics.
* Static COPY references resolve to inventoried copybooks or explicitly listed
  CICS/MQ system members. COPY resolution is basename-based, not proof of the
  deployed SYSLIB search order when duplicate member names exist.
* Optional extension dependencies (SQLCA, MQ calls, CBLTDLI, Db2 preprocessors)
  are still visible in inventory and external dependencies, but remain excluded.

## Hypotheses (not runtime facts)

* CP037 is a **hypothesis**. A directory named EBCDIC does not specify a CCSID.
* Proposed Spring modules, adapter boundaries and owner roles are planning choices.
* TD queue JOBS probably submits generated reports through JES; the deployed
  queue-to-reader connection is missing evidence, not a verified integration.
* A data-item navigation target cannot be resolved merely from a variable name.
  Runtime branch values and externally initiated transactions remain unverified.

## Missing runtime / operator evidence

The manifest has precise per-core-screen and per-core-JCL requests, owned by
**operator**, with impact. Supply sanitized records, not production secrets.

1. Installed z/OS/CICS/COBOL/HLASM/LE versions, compiler options and link-edit maps;
   actual code pages for each dataset, RECFM/LRECL/BLKSIZE, catalog LISTCAT and
   active CICS FILE/TRANSACTION/PROGRAM/MAPSET and TDQUEUE definitions.
2. Every screen journey, including login failure, empty lookups, paging, field
   validation, return navigation, admin authorization/user maintenance and report
   confirmation/cancel/error. Capture transaction IDs, input/output and record diffs.
3. Each core batch member's expanded JCL/PROCs, input bytes/layout, output bytes,
   SYSOUT/spool, RC/abend, totals and restart/error/empty cases. Setup/delete jobs
   require isolated datasets and explicit operator approval before execution.
4. TDQ JOBS routing, generated report JCL, internal-reader/JES submission spool,
   report/date parameters, FTP destinations/redacted credentials and TXT2PDF output.
5. RACF profiles/permissions (redacted), scheduler product actually in use, active
   calendars/dependencies, CLOSEFIL1/2 runtime overrides and COCRDSEC load/source
   provenance. Never infer production use from sample scheduler dates or ZIP files.

## External dependencies, ownership and impact

`verified` below means **reference verified from source**, not installed/version
verified. Every manifest external has exact citations (unless hypothesis/unknown),
an owner, migration impact, later blocking steps and a precise operator ask.

| Dependency | Source status | Owner | Migration impact / evidence needed |
|---|---|---|---|
| z/OS, CICS TS | verified references | operator | Host/JES/CICS replacement semantics; versions and installed definitions |
| Enterprise COBOL compiler/options, IGYCRCTL, DFHECP1 | verified references | operator | Capture actual compile/translator options, listings and numeric behavior |
| HLASM, ASMA90, MVSWAIT/COBDATFT + ASMWAIT/COCDATFT macros | verified references | operator | Replace wait/date host routines; macro expansion/link-edit evidence |
| CP037 | hypothesis | operator | Validate per-file CCSID and lossless round-trip before data import |
| RACF | verified references | operator | Map runtime access controls to approved identity/RBAC model |
| DFSORT/SORT, IDCAMS | verified references | operator | Preserve sort collations, keys, allocation and restart behavior |
| IEBGENER, IEFBR14, DFHCSDUP, SDSF | verified references | operator | Replace copy/allocation/install/operator-command contracts |
| HEWL, IEWL, IKJEFT01, IKJEFT1B | verified references | operator | Host link-edit / TSO integration; installed procedures and execution options |
| FTP, TXT2PDF | verified references | operator | Approve secure transport/report format replacement; captures/licenses |
| internal reader, TDQ | verified references; deployed connection unknown | operator | Obtain JES and JOBS queue routing; replace with controlled job submission |
| CA7/Control-M | verified definitions | operator | Choose actual scheduler, calendars and dependency semantics |
| CEEDAYS, CEE3ABD / LE date services | verified references | operator | Date conversion and abend/error equivalence; LE runtime options |
| DFHAID, DFHBMSCA | verified references | operator | CICS system copybooks/keyboard constants, not repository members |
| SQLCA, CBLTDLI, DFSRRC00, DSNHPC, MQOPEN/MQCLOSE/MQGET/MQPUT/MQPUT1, CMQ* copybooks | verified references, excluded extension context | operator | Do not migrate optional Db2/IMS/MQ; preserve boundary and build provenance |
| Third-party licenses | LICENSE/NOTICE verified | manager/human-decision | Repository Apache 2.0 notice does not grant host-product entitlements; legal review required |

All runtime versions, entitlement and deployed settings remain unknown until
operator evidence arrives. These block runtime equivalence/cutover, not generation.

## Decisions needed

Manager/human-decision owns: (1) actual scheduler and job/override activation;
(2) identity provider/RBAC and privileged admin acceptance; (3) PostgreSQL keys,
decimal/date/record compatibility and restart/idempotency policy; (4) report,
transport and job-submission replacements; (5) scope/module/ownership approval and
COCRDSEC disposition. No implicit scope expansion to optional extensions.

## Transfer notes

Git blob identity protects both original text and bytes. Classification records
`git check-attr text binary` results (currently unspecified) and uses UTF-8 decode
plus NUL detection; this is a **file transport heuristic**, not codec detection.
EBCDIC directory labels are recorded separately. Transfer raw datasets in binary
mode until CCSID, packed/zoned decimals, record boundaries and checksums are known;
avoid newline conversion or automatic EBCDIC translation of binary/numeric fields.
ASCII examples are not authority for production data encoding.

Host-only load libraries, CICS resource installations, VSAM catalogs, JES state,
RACF database/profiles, scheduler state and runtime license material are **not**
reconstructed from source. Runtime ZIP samples are opaque individual inventory
entries with hashes, not unpacked secondary source trees or verified host assets.

## Work-unit method (manual versus AI comparison)

Per-file bytes and text line counts are deterministic. COBOL uses fixed columns
8–72; column 7 `*`/`/` comments are excluded. Nonblank remaining lines are the
non-comment code-line proxy (including declarations and continuations). CICS
command count matches active EXEC CICS; paragraph count matches area-A labels
ending in a period. Non-COBOL code metrics are null rather than misleading zero;
binary line counts are null. These are lexical proxies, not compiler semantics
or complexity estimates. Include verification and evidence collection as separate
work units. Record identical baseline SHA, assigned boundary, operator fixtures,
elapsed active time, review corrections and acceptance outcomes for manual and AI
runs. Do not fabricate effort, speedup or equivalence numbers from source size.

## Reproduction and consistency gate

Python 3 standard library only; run from repository root:

```sh
python3 migration/scope/tools/inventory.py
python3 migration/scope/tools/inventory.py --check
python3 migration/scope/tools/check_manifest.py
python3 -m unittest discover -s migration/scope/tests -v
git diff --stat origin/main --diff-filter=MD
```

**Green inventory CI does not mean missing source has been supplied:** every
unresolved CSD program/mapset must have an explicit registered gap with owner,
exact evidence and a pending decision; an unregistered resource fails the gate.
Registered gaps remain visible in check output and the manifest. Register structure,
unique IDs, curated policy fidelity and per-edge dynamic navigation coverage are
also checked. COCRDSEC/CDV1 remains a human decision, not an approved exclusion.
CA7 aliases are resolved from the member column, not guessed from names.
Unit tests assert gap accounting and independently test unregistered CSD resources,
missing owner/evidence/decision, unregistered dynamic targets, corruption,
unresolved COPY/PGM/PROC, duplicate coverage, citation and scope tampering. A passing
unit suite does not mean the original source is complete or runtime-equivalent.

Freshness and blob checks use HEAD tracked sources; after a scope-only commit the
same source set/hashes regenerate identically. The source SHA stays pinned to the
approved baseline rather than becoming the hash of this generated manifest commit.
Navigation/scheduler reconciliation guards fidelity to parsed source; it does not
claim dynamic target resolution. Existing source gaps cannot be repaired under
the additions-only/no-business-migration constraint.
