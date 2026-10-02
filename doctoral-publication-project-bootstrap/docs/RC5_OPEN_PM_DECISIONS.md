# RC5 Open PM Decisions

## Revision semantics documentation conflict

The current application deliberately preserves the deployed implementation:
an approved revision is merged into the existing current official
`PublicationRecord`; it does not become a second current/public record.

Some Notion documentation instead describes an approved revision becoming the
new current official version.  RC5 does not alter this frozen lifecycle
semantic.  Product management must choose one model and update the stale
documentation before a future architecture change.

## Country master

The formal secretary workbook describes country-backed fields but does not
provide a complete authoritative country-code master.  RC5 uses the existing
active `Country` rows and does not invent codes.  PM/secretary must supply the
production reference list and import mapping before any bulk data release.

## Legacy conference paper fields

Historical conference exports include journal-like paper/author fields when
`presented_paper=yes`.  The reconciliation contract marks these as legacy-only
until PM decides whether they become canonical conference detail fields.  RC5
does not duplicate them into the new conference UI.
