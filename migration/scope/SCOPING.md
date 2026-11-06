# Source-grounded migration boundary

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
`dynamic_navigation_policy` expands into a manifest gap only for runtime-dependent
edges, each with its own source citation, reason and ID. Resolved data-item edges
retain their literal and assignment provenance in the navigation graph instead.
No unresolved navigation is merely logged.
`migrated` means planned migration, never completed migration. No member is
classified `unused-with-evidence`: even `UNUSED1Y.cpy` is not declared unused just
because of its name. Any later unused classification needs a reproducible search
over all source and confirmation about external callers; the current check rejects
unused declarations until such an evidence mechanism is explicitly implemented.

Devin has **no mainframe access**. A human OPERATOR executes the original in an
approved isolated environment and supplies captures. Inventory is not blocked by
missing runtime evidence; planned implementation and qualification need it.
**Cutover is explicitly out of scope**, not a required step or deliverable.

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
expressions and finite literal-proven candidates where possible; **it is not an
observed runtime call graph**. COCOM01Y is a shared
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
  needed to settle the capture-protocol boundary and target architecture; its
  proposed exclusion and pending human decision are unchanged.
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

### Variable-target navigation: 36 resolved, 19 runtime-dependent

All 55 variable-target edges are classified, including excluded extensions (which
remain excluded). All current literal-proven candidate targets resolve to an
inventoried program or a transaction in an inventoried CSD. No additional missing
candidate implementation was found. Only the 19 runtime-dependent edges remain
operator-evidence gaps; COCRDSEC/CDV1 remains the separate missing-source decision.

The resolver expands core COPY contracts with original file/line provenance;
tracks quoted VALUE clauses, direct MOVE literals, aliases and group overwrites;
and uses a last assignment only when no intervening branch join, paragraph,
PERFORM/CALL or CICS completion separates it from the transfer. Immutable constants
produce finite sets. Menu tables use literal PIC X(08) slots, their REDEFINES/OCCURS
layout, literal option count, numeric/range checks and error-flag guard. A menu set
is a path-insensitive upper bound: it includes optional extension members, not an
approval to migrate them. Each candidate cites the literal, declaration/assignment
chain, table overlay where applicable, and transfer site.

For COMMAREA, known internal caller transfers and their literal-proven field writes
are unioned and cited through the receiving group MOVE. A finite closed caller set
can resolve in the resolver's regression fixture. In this repository the remaining
19 edges all have incoming COMMAREA group writes and public CICS transaction entry:
external callers can supply values outside that union. Local literals remain useful
partial candidates, not an exhaustive proof. CDEMO-FROM-PROGRAM copied into
CDEMO-TO-PROGRAM inherits that uncertainty. Group INITIALIZE/input writes and
unsupported producers also retain uncertainty rather than being assumed constants.
This is conservative lexical dataflow, not a COBOL compiler/control-flow proof or
an assertion of host execution. Candidate provenance and detailed reasons/citations
are in each edge's `resolution` object and the runtime gap register.
Of these 19, **15 are core** (`app/cbl`) and **four are conditional on rescoping**:
two in the excluded authorization extension and two in the excluded transaction-type
extension. All remain inventory findings. The four extension operator requests are
conditional only and have empty `blocking_for` lists: they block no approved-core
step. Both edges and gap records carry `scope_class`, checked against source-file
disposition. Static resolution is not runtime proof; core golden coverage remains
required regardless of finite candidate sets.

| Source edge (path:line) | Operation / data item | Classification | Literal-proven candidates (partial for runtime rows) |
|---|---|---|---|
| `app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:254` | RETURN `WS-CICS-TRANID` | statically-resolved | `CPVS` |
| `app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:323` | XCTL `CDEMO-TO-PROGRAM` | statically-resolved | `COPAUS1C` |
| `app/app-authorization-ims-db2-mq/cbl/COPAUS0C.cbl:675` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COMEN01C`, `COPAUS0C`, `COPAUS1C`, `COSGN00C` |
| `app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:202` | RETURN `WS-CICS-TRANID` | statically-resolved | `CPVD` |
| `app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:248` | LINK `WS-PGM-AUTH-FRAUD` | statically-resolved | `COPAUS2C` |
| `app/app-authorization-ims-db2-mq/cbl/COPAUS1C.cbl:368` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COMEN01C`, `COPAUS0C`, `COPAUS1C`, `COSGN00C` |
| `app/app-transaction-type-db2/cbl/COTRTLIC.cbl:620` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C`, `COTRTLIC`, `COTRTUPC` |
| `app/app-transaction-type-db2/cbl/COTRTLIC.cbl:648` | XCTL `LIT-ADDTPGM` | statically-resolved | `COTRTUPC` |
| `app/app-transaction-type-db2/cbl/COTRTLIC.cbl:910` | RETURN `LIT-THISTRANID` | statically-resolved | `CTLI` |
| `app/app-transaction-type-db2/cbl/COTRTUPC.cbl:457` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C`, `COTRTLIC`, `COTRTUPC` |
| `app/app-transaction-type-db2/cbl/COTRTUPC.cbl:567` | RETURN `LIT-THISTRANID` | statically-resolved | `CTTU` |
| `app/cbl/COACTUPC.cbl:956` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COACTUPC`, `COMEN01C`, `COSGN00C` |
| `app/cbl/COACTUPC.cbl:1015` | RETURN `LIT-THISTRANID` | statically-resolved | `CAUP` |
| `app/cbl/COACTVWC.cbl:349` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COACTVWC`, `COMEN01C`, `COSGN00C` |
| `app/cbl/COACTVWC.cbl:402` | RETURN `LIT-THISTRANID` | statically-resolved | `CAVW` |
| `app/cbl/COADM01C.cbl:111` | RETURN `WS-TRANID` | statically-resolved | `CA00` |
| `app/cbl/COADM01C.cbl:146` | XCTL `CDEMO-ADMIN-OPT-PGMNAME(WS-OPTION` | statically-resolved | `COTRTLIC`, `COTRTUPC`, `COUSR00C`, `COUSR01C`, `COUSR02C`, `COUSR03C` |
| `app/cbl/COADM01C.cbl:169` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C`, `COTRTLIC`, `COTRTUPC`, `COUSR02C`, `COUSR03C` |
| `app/cbl/COADM01C.cbl:280` | RETURN `WS-TRANID` | statically-resolved | `CA00` |
| `app/cbl/COBIL00C.cbl:146` | RETURN `WS-TRANID` | statically-resolved | `CB00` |
| `app/cbl/COBIL00C.cbl:282` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COBIL00C`, `COMEN01C`, `COSGN00C` |
| `app/cbl/COCRDLIC.cbl:402` | XCTL `LIT-MENUPGM` | statically-resolved | `COMEN01C` |
| `app/cbl/COCRDLIC.cbl:538` | XCTL `CCARD-NEXT-PROG` | statically-resolved | `COCRDSLC` |
| `app/cbl/COCRDLIC.cbl:566` | XCTL `CCARD-NEXT-PROG` | statically-resolved | `COCRDUPC` |
| `app/cbl/COCRDLIC.cbl:615` | RETURN `LIT-THISTRANID` | statically-resolved | `CCLI` |
| `app/cbl/COCRDSLC.cbl:331` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COCRDLIC`, `COCRDSLC`, `COMEN01C`, `COSGN00C` |
| `app/cbl/COCRDSLC.cbl:402` | RETURN `LIT-THISTRANID` | statically-resolved | `CCDL` |
| `app/cbl/COCRDUPC.cbl:473` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COCRDLIC`, `COCRDUPC`, `COMEN01C`, `COSGN00C` |
| `app/cbl/COCRDUPC.cbl:554` | RETURN `LIT-THISTRANID` | statically-resolved | `CCUP` |
| `app/cbl/COMEN01C.cbl:107` | RETURN `WS-TRANID` | statically-resolved | `CM00` |
| `app/cbl/COMEN01C.cbl:156` | XCTL `CDEMO-MENU-OPT-PGMNAME(WS-OPTION` | statically-resolved | `COACTUPC`, `COACTVWC`, `COBIL00C`, `COCRDLIC`, `COCRDSLC`, `COCRDUPC`, `COPAUS0C`, `CORPT00C`, `COTRN00C`, `COTRN01C`, `COTRN02C` |
| `app/cbl/COMEN01C.cbl:185` | XCTL `CDEMO-MENU-OPT-PGMNAME(WS-OPTION` | statically-resolved | `COACTUPC`, `COACTVWC`, `COBIL00C`, `COCRDLIC`, `COCRDSLC`, `COCRDUPC`, `COPAUS0C`, `CORPT00C`, `COTRN00C`, `COTRN01C`, `COTRN02C` |
| `app/cbl/COMEN01C.cbl:202` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COACTUPC`, `COACTVWC`, `COBIL00C`, `COCRDSLC`, `COCRDUPC`, `COMEN01C`, `COPAUS0C`, `COPAUS1C`, `COSGN00C`, `COTRN00C`, `COTRN01C`, `COTRN02C` |
| `app/cbl/CORPT00C.cbl:199` | RETURN `WS-TRANID` | statically-resolved | `CR00` |
| `app/cbl/CORPT00C.cbl:549` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COMEN01C`, `COSGN00C` |
| `app/cbl/CORPT00C.cbl:587` | RETURN `WS-TRANID` | statically-resolved | `CR00` |
| `app/cbl/COSGN00C.cbl:98` | RETURN `WS-TRANID` | statically-resolved | `CC00` |
| `app/cbl/COTRN00C.cbl:138` | RETURN `WS-TRANID` | statically-resolved | `CT00` |
| `app/cbl/COTRN00C.cbl:193` | XCTL `CDEMO-TO-PROGRAM` | statically-resolved | `COTRN01C` |
| `app/cbl/COTRN00C.cbl:519` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COMEN01C`, `COSGN00C`, `COTRN00C`, `COTRN01C` |
| `app/cbl/COTRN01C.cbl:136` | RETURN `WS-TRANID` | statically-resolved | `CT01` |
| `app/cbl/COTRN01C.cbl:206` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COMEN01C`, `COSGN00C`, `COTRN00C`, `COTRN01C` |
| `app/cbl/COTRN02C.cbl:156` | RETURN `WS-TRANID` | statically-resolved | `CT02` |
| `app/cbl/COTRN02C.cbl:509` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COMEN01C`, `COSGN00C`, `COTRN02C` |
| `app/cbl/COTRN02C.cbl:530` | RETURN `WS-TRANID` | statically-resolved | `CT02` |
| `app/cbl/COUSR00C.cbl:141` | RETURN `WS-TRANID` | statically-resolved | `CU00` |
| `app/cbl/COUSR00C.cbl:197` | XCTL `CDEMO-TO-PROGRAM` | statically-resolved | `COUSR02C` |
| `app/cbl/COUSR00C.cbl:207` | XCTL `CDEMO-TO-PROGRAM` | statically-resolved | `COUSR03C` |
| `app/cbl/COUSR00C.cbl:515` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C`, `COUSR02C`, `COUSR03C` |
| `app/cbl/COUSR01C.cbl:107` | RETURN `WS-TRANID` | statically-resolved | `CU01` |
| `app/cbl/COUSR01C.cbl:176` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C` |
| `app/cbl/COUSR02C.cbl:135` | RETURN `WS-TRANID` | statically-resolved | `CU02` |
| `app/cbl/COUSR02C.cbl:259` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C`, `COUSR00C`, `COUSR02C`, `COUSR03C` |
| `app/cbl/COUSR03C.cbl:134` | RETURN `WS-TRANID` | statically-resolved | `CU03` |
| `app/cbl/COUSR03C.cbl:206` | XCTL `CDEMO-TO-PROGRAM` | runtime-dependent | `COADM01C`, `COSGN00C`, `COUSR00C`, `COUSR02C`, `COUSR03C` |

### Reproducible COCRDSEC absence evidence

Search scope is the **whole tracked authoritative source revision**, with no path
exclusions. Searching current HEAD also finds this ticket's documentation and
register, so baseline searches avoid treating our own notes as original source.
The only content references are CSD registration, and no filename matches. This
establishes repository absence, never absence of a host load module.

```sh
git grep -n -i COCRDSEC 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e --
```
Exact stdout (exit 0):
```text
59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e:app/csd/CARDDEMO.CSD:211: DEFINE PROGRAM(COCRDSEC) GROUP(CARDDEMO)
59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e:app/csd/CARDDEMO.CSD:390:        PROGRAM(COCRDSEC) TWASIZE(0) PROFILE(DFHCICST) STATUS(ENABLED)
```

```sh
git ls-tree -r --name-only 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e | grep -i cocrdsec
```
Exact stdout is empty (exit 1). The stdlib generator reproduces
the filename filter with Python's case-insensitive regex, not a grep dependency.
Both commands, outputs and exit codes are retained in the missing-source gap and
checked against a fresh search.
CI fetches full history so the pinned authoritative source revision is available
for these searches even when it is not the PR checkout commit.

Verbatim registration lines from `app/csd/CARDDEMO.CSD` (211; 388–390):
```text
 DEFINE PROGRAM(COCRDSEC) GROUP(CARDDEMO)
 DEFINE TRANSACTION(CDV1) GROUP(CARDDEMO)
 DESCRIPTION(DEVELOPER TRANSACTION - 1)
        PROGRAM(COCRDSEC) TWASIZE(0) PROFILE(DFHCICST) STATUS(ENABLED)
```

### Minimal human/operator inputs still needed

Stable plan references used throughout the manifest and requests:

| Plan ID / ticket key | Function |
|---|---|
| s1.2/UNT-2 | Operator capture protocol and initial captures |
| s1.3/UNT-3 | Golden corpus |
| s2.1/UNT-4 | Target architecture |
| s3.1/UNT-7 | PostgreSQL data schema |
| s3.2/UNT-8 | Legacy data codecs (EBCDIC/packed/zoned) |
| s4.1-s4.4/UNT-10..UNT-13 | Online journeys; range used rather than guessing an individual step |
| s5.1-s5.4/UNT-14..UNT-17 | Batch; range used rather than guessing an individual step |
| s6.1/UNT-18 | Qualification consumes the golden corpus |

| Input / owner | Why source does not settle it | Dependent plan step and impact |
|---|---|---|
| COCRDSEC host load/source provenance and CDV1 usage; operator supplies, manager decides | Developer CSD entry has no source; exclusion is only proposed, not approved | s1.2/UNT-2: settle capture-protocol boundary; s2.1/UNT-4: settle developer-transaction architecture boundary without inventing implementation |
| **15 core** runtime target/COMMAREA requests; operator | Incoming public transaction COMMAREA is not a closed literal set | s1.2/UNT-2: capture protocol and initial values; s1.3/UNT-3: golden navigation corpus; s4.1-s4.4/UNT-10..UNT-13: safe dispatch and online acceptance; s6.1/UNT-18: qualification consumes goldens |
| **Four conditional** runtime requests (two authorization, two transaction-type); operator only if rescoped | Source files are excluded; no approved-core runtime evidence is required for them | No approved-core blocker (`blocking_for=[]`); requests activate only after an explicit rescoping decision |
| Screen inputs/outputs and validation/empty/error journeys for approved programs; operator | Finite source candidates do not prove executed branches or screen behavior | s1.2/UNT-2: initial screen capture protocol; s1.3/UNT-3: golden screens; s4.1-s4.4/UNT-10..UNT-13: online journey coverage; s6.1/UNT-18: qualification consumes goldens |
| Actual dataset CCSIDs, catalog keys/record boundaries and sanitized raw records; operator | CP037 remains a hypothesis; differing customer definitions need a contract decision | s1.2/UNT-2: raw transfer protocol; s1.3/UNT-3: golden raw bytes; s3.1/UNT-7: schema field/key contracts; s3.2/UNT-8: lossless EBCDIC/packed/zoned codecs; s6.1/UNT-18: qualification consumes decoded goldens |
| Expanded JCL/PROCs, batch input/output bytes, spool, RC/abend and restart samples; operator | Symbolic DSNs and DISP are not complete runtime access semantics | s1.2/UNT-2: batch capture protocol; s1.3/UNT-3: golden batch corpus; s3.1/UNT-7 and s3.2/UNT-8: record contracts; s5.1-s5.4/UNT-14..UNT-17: batch output/order/restart semantics; s6.1/UNT-18: qualification consumes goldens |
| Redacted RACF/identity profiles; operator, manager approves replacements | Source references do not prove installed authorization | s2.1/UNT-4: identity/RBAC architecture; s4.1-s4.4/UNT-10..UNT-13: relevant privileged online journeys; s6.1/UNT-18: qualification consumes authorization goldens |
| Active CICS/TDQUEUE/JES and scheduler definitions; operator, manager approves replacements | JOBS-to-reader routing and active calendars are unverified | s2.1/UNT-4: scheduling/submission architecture; s1.3/UNT-3: golden batch/report outputs; s5.1-s5.4/UNT-14..UNT-17: orchestration; s4.1-s4.4/UNT-10..UNT-13: TDQ report submission; s6.1/UNT-18: qualification consumes goldens |
| Installed runtime/compiler options and versions; operator | Source dependencies are not installed configuration | s1.2/UNT-2: reproducible capture baseline; s2.1/UNT-4: compatibility architecture; s6.1/UNT-18: qualification against the resulting golden corpus |

No mainframe execution or fabricated captures are included. Static resolution
reduces the target-discovery request, not the need for the approved golden corpus.


## Hypotheses (not runtime facts)

* CP037 is a **hypothesis**. A directory named EBCDIC does not specify a CCSID.
* Proposed Spring modules, adapter boundaries and owner roles are planning choices.
* TD queue JOBS probably submits generated reports through JES; the deployed
  queue-to-reader connection is missing evidence, not a verified integration.
* Data-item navigation is resolved only with literal and assignment evidence.
  Finite sets are conservative source upper bounds, not claims that every candidate
  is feasible on every branch. Runtime branch execution and externally initiated
  COMMAREA contents remain unverified.

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
operator evidence arrives. These inform the mapped architecture, implementation
and qualification steps, not inventory generation. Excluded-extension dependencies
are conditional on rescoping and block no approved-core step.

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
claim runtime branch observations. Existing source gaps cannot be repaired under
the additions-only/no-business-migration constraint.
