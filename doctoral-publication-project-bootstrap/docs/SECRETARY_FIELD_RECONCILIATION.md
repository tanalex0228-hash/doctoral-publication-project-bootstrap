# Secretary Formal Field Reconciliation

**Scope:** RC4 additional-modification work branch.  This document reconciles
the 2026-09-30 secretary workbook with the two historical exports.  It does
not reinterpret the frozen lifecycle, approval, visibility, evidence, audit,
or statistics contracts.

## Source and classification rules

| Source | Authority |
| --- | --- |
| `資料庫欄位定義2026.9.30.xlsx` | New-entry fields and formal choices |
| PM current-form specification | Labels and conditional behaviour |
| `整合查詢匯出期刊論文.xlsx`, `整合查詢匯出出席國際會議.xlsx` | Historical import/export compatibility only |

`完成` and `草稿` in a historical export are **not** workflow states.  In
particular, `完成` must never be imported as `approved`.  The raw source value
is legacy metadata until PM supplies an explicit historical-status policy.

## Journal article

| Field | 中文名稱 | Source | Result type | Canonical model / field | Data type | Required? | Conditional? | New entry UI? | Legacy import / export | Existing mapping | Migration? | PM decision? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| title | 論文篇名 | formal + export | EXISTING REUSABLE | `PublicationRecord.title` | text | yes | no | yes | yes / yes | exact | no | no |
| journal name | 期刊名 | formal + export | EXISTING REUSABLE | `PublicationRecord.journal_or_conference_name` | text | yes | no | yes | yes / yes | exact | no | no |
| publication stage | 發表進度 | formal + export | EXISTING REUSABLE | `PublicationRecord.publication_stage` | controlled code | yes | accepted/published | yes | map legacy values only | existing broader enum | no | no |
| accepted date | 接受日期 | formal + export | EXISTING REUSABLE | `PublicationRecord.accepted_date` | date | accepted | yes | yes | yes / yes | exact | no | no |
| acceptance evidence | 接受證明 | formal | EXISTING REUSABLE | `SourceDocument(acceptance_letter)` | private evidence | accepted | yes | yes | import where supplied / manifest | existing | no | no |
| volume / issue / pages / date | 卷號／期別／頁數／刊登日期 | formal + export | EXISTING REUSABLE | `PublicationRecord.volume`, `issue`, `pages_or_article_number`, `publication_date` | text/date | published | yes | yes | yes / yes | exact | no | no |
| publication evidence | 佐證資料 | formal | EXISTING REUSABLE | `SourceDocument(journal_proof)` | private PDF, 10 MB form rule | published | yes | yes | import where supplied / manifest | existing private service | no | no |
| journal type | 期刊類型（新） | formal + export | NEW CANONICAL | `JournalArticleDetail.journal_type` | controlled code | yes | no | yes | map export 新 type / yes | none | yes | no |
| old journal type | 期刊類型（舊） | export | LEGACY ONLY | `JournalArticleDetail.legacy_journal_type` | text | no | no | no | preserve / export | none | yes | no |
| rank / impact factor | SCI、SSCI 排名／Impact factor | formal + export | NEW CANONICAL | `international_journal_rank`, `impact_factor` | code / decimal | SCI or SSCI | yes | yes | map / yes | none | yes | no |
| Taiwan journal level | 臺灣期刊收錄級別 | formal + export | NEW CANONICAL | `taiwan_journal_level` | controlled code | TSSCI or THCI | yes | yes | map / yes | none | yes | no |
| custom type | 各院認可之優良期刊／其他說明 | formal | NEW CANONICAL | `custom_journal_type` | text | selected type | yes | yes | import if available / yes | none | yes | no |
| student author order | 作者序 | formal + export | NEW CANONICAL | `JournalArticleDetail.student_author_order` | controlled code | yes | no | yes | map / yes | relational author order is different | yes | no |
| order reason | 第四作者以上原因 | formal + export | NEW CANONICAL | `student_author_order_reason` | text | fourth or later | yes | yes | preserve / yes | none | yes | no |
| student author attribute | 作者屬性 | formal + export | NEW CANONICAL | `student_author_attribute` | controlled code | yes | no | yes | map / yes | `PublicationAuthor` remains actual author list | yes | no |
| corresponding / collaboration | 通訊作者／國際合作 | formal + export | NEW CANONICAL | `is_student_corresponding_author`, `has_international_collaboration` | boolean | yes | no | yes | map / yes | only actual-author correspondence exists today | yes | no |
| media / nature / attribute | 出版媒體／論文性質／論文屬性 | formal + export | NEW CANONICAL | `publication_medium`, `paper_nature`, `paper_attribute` | controlled code | yes | no | yes | map / yes | none | yes | no |
| ISSN / DOI | ISSN／DOI | formal + export | EXISTING REUSABLE | `PublicationRecord.issn`, `doi` | text | no | no | yes | yes / yes | exact | no | no |
| total pages | 總頁數 | formal + export | NEW CANONICAL | `JournalArticleDetail.total_pages` | positive integer | no | no | yes | map / yes | differs from page range | yes | no |
| representative / peer review / citations | 年度代表作／審查機制／引用次數 | formal + export | NEW CANONICAL | `is_annual_representative_work`, `is_peer_reviewed`, `citation_count` | boolean / integer | yes/no/no | no | yes | map / yes | none | yes | no |
| country / place | 出版國／出版地 | formal + export | NEW CANONICAL | `publication_country`, `publication_place` | FK / text | no | no | yes | legacy raw + map / yes | none | yes | country code list required |
| remarks | 備註 | export / PM | NEW CANONICAL | `JournalArticleDetail.remarks` | text | no | no | yes | preserve / yes | none | yes | no |
| SDGs | SDGs | formal + export | NEW CANONICAL | `PublicationSDGAssignment` | normalized assignment | no | max 3; NONE exclusive | yes | map / yes | none | yes | no |

## Conference / academic meeting

| Field | 中文名稱 | Source | Result type | Canonical model / field | Data type | Required? | Conditional? | New entry UI? | Legacy import / export | Existing mapping | Migration? | PM decision? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| conference name | 學術會議名 | formal + export | EXISTING REUSABLE | `PublicationRecord.journal_or_conference_name` | text | yes | no | yes | yes / yes | exact | no | no |
| conference type | 會議屬性 | formal + export | NEW CANONICAL | `ConferenceDetail.conference_type` | controlled code | yes | no | yes | map / yes | none | yes | no |
| organizer | 主辦單位 | formal + export | NEW CANONICAL | `ConferenceDetail.organizer` | text | yes | no | yes | yes / yes | none | yes | no |
| location country / city | 會議地點國家／城市 | formal + export | NEW CANONICAL | `location_country`, `location_city` | FK / text | yes | no | yes | legacy raw + map / yes | none | yes | country code list required |
| participants' countries | 與會人員國家 | formal + export | NEW CANONICAL | `ConferenceParticipantCountry` | normalized assignment | no | max 5 | yes | split legacy raw / yes | none | yes | no |
| dates | 起始／結束日期 | formal + export | NEW CANONICAL | `start_date`, `end_date` | date | yes | no | yes | yes / yes | none | yes | no |
| presentation modes | 發表方式或任務 | formal + export | NEW CANONICAL | `ConferencePresentationMode` + assignment | controlled normalized assignment | no | multi-select | yes | map / yes | none | yes | no |
| subsidy / presented paper | 是否獲補助／是否發表論文 | formal + export | NEW CANONICAL | `received_subsidy`, `presented_paper` | boolean | yes | no | yes | yes / yes | none | yes | no |
| conference evidence | 佐證資料 | formal | NEW CANONICAL | `SourceDocument(conference_evidence)` | private PDF, 10 MB | no | document type | yes | manifest | existing private service | documents migration | no |
| remarks | 備註 | formal + export | NEW CANONICAL | `ConferenceDetail.remarks` | text | no | no | yes | yes / yes | none | yes | no |
| SDGs | SDGs | formal + export | NEW CANONICAL | `PublicationSDGAssignment` | normalized assignment | no | max 3; NONE exclusive | yes | map / yes | none | yes | no |
| journal-like fields when presented | 論文篇名、作者、通訊作者等 | export only | PM DECISION REQUIRED | no canonical expansion yet | legacy payload | n/a | `presented_paper=yes` | no | preserve externally / existing export only | ambiguous | no | **yes** |

## Decisions intentionally not guessed

1. The secretary workbook specifies a dropdown but does not contain the full
   country-code master list.  The observed legacy values (`0`, `13`, `27`,
   `425`, `A00`, etc.) are sufficient to preserve imports but not to invent a
   complete selectable country catalogue.  The model supports that catalogue;
   PM/secretary must provide the authoritative full list before its production
   fixture and all-country form selector are released.
2. The export's legacy status values are retained as import/export metadata;
   there is no workflow-state mapping without PM approval.
3. For a conference with `presented_paper=yes`, the historical export contains
   journal-like authorship and paper metadata.  Whether those fields become
   canonical conference-paper detail fields is a PM decision; they are not
   silently duplicated into this domain extension.
