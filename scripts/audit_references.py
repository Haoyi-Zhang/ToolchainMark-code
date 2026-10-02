#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / 'paper'
ARTIFACT = ROOT / 'artifact'
TEX = PAPER / 'main.tex'
BIB = PAPER / 'references.bib'
RECORDS = PAPER / 'evidence' / 'reference_records.json'
LEDGER = ARTIFACT / 'citation_support.csv'
SHAPE = PAPER / 'citation_shape_audit.json'
VERIFY = PAPER / 'reference_verification_audit.json'
LINE_AUDIT = PAPER / 'reference_line_by_line_audit.csv'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_tex(text: str) -> str:
    text = re.sub(r'%.*', '', text)
    text = re.sub(r'\\cite\{[^}]+\}', '', text)
    text = re.sub(r'\\(?:textsc|emph|textit|textbf|texttt|mathrm|mathsf)\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\(?:mr|suite)\{([^{}]*)\}', r'\1', text)
    text = re.sub(r'\\[A-Za-z@]+\*?(?:\[[^\]]*\])?', '', text)
    text = text.replace('~', ' ')
    text = text.replace('``', '"').replace("''", '"')
    text = text.replace('--', '-')
    text = re.sub(r'[{}$]', '', text)
    text = re.sub(r'\\([%&_#])', r'\1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def parse_bib(text: str) -> dict[str, dict[str, str]]:
    entries: dict[str, dict[str, str]] = {}
    for match in re.finditer(r'@(\w+)\{([^,]+),\s*(.*?)\n\}', text, re.S):
        entry_type, key, body = match.group(1).lower(), match.group(2).strip(), match.group(3)
        fields: dict[str, str] = {'entry_type': entry_type}
        for fm in re.finditer(r'^\s*(\w+)\s*=\s*\{(.*?)\}\s*,?\s*$', body, re.M | re.S):
            fields[fm.group(1).lower()] = fm.group(2).strip()
        entries[key] = fields
    return entries


def normalize_people(value: str) -> str:
    value = strip_tex(value).lower()
    value = value.replace(' and ', ' ')
    return re.sub(r'[^a-z0-9]+', '', value)


def structural_audit(tex: str, bib: dict, records: list, receipts: list) -> dict:
    commands=re.findall(r'\\cite\{([^}]+)\}',tex)
    sentences = re.split(r'(?<=[.!?])\s+', re.sub(r'(?m)^\s*%.*$', '', tex))
    multiple = [sentence for sentence in sentences if len(re.findall(r'\\cite\{', sentence)) > 1]
    keys=[k.strip() for c in commands for k in c.split(',')]
    rk={r['citation_key'] for r in records}; bk=set(bib)
    doi=[r['doi'].casefold() for r in records]
    return {'record_count':len(records),'citation_commands':len(commands),'unique_citation_keys':len(set(keys)),
      'multi_key_commands':sum(',' in c for c in commands),
      'adjacent_citation_piles':len(re.findall(r'\\cite\{[^}]+\}\s*\\cite\{[^}]+\}',tex)),
      'uncited_bibliography_keys':sorted(bk-set(keys)),'missing_bibliography_keys':sorted(set(keys)-bk),
      'metadata_record_keys_match':rk==bk,'doi_records_unique':len(doi)==len(set(doi)),
      'receipt_keys_unique':len(receipts)==len({r['citation_key'] for r in receipts}),
      'fresh_record_checks':sum(bool(r['record_located_this_revision']) for r in receipts),
      'sentences_with_multiple_citation_commands':len(multiple),
      'multiple_citation_sentence_examples':multiple[:4],
      'numeric_citation_ranges':len(re.findall(r'\\cite\{[^}]*\d\s*[-–]\s*\d[^}]*\}', tex)),
      'full_text_review_claimed':False}

def main() -> None:
    tex=TEX.read_text(); bib=parse_bib(BIB.read_text()); records=json.loads(RECORDS.read_text())
    receipts=json.loads((PAPER/'evidence/reference_review_20260923.json').read_text())
    byreceipt={r['citation_key']:r for r in receipts}; shape=structural_audit(tex,bib,records,receipts)
    citations=[]; section=''; subsection=''
    for lineno,line in enumerate(tex.splitlines(),1):
        m=re.match(r'\\section\{([^}]+)\}',line)
        if m: section=m.group(1);subsection=''
        m=re.match(r'\\subsection\{([^}]+)\}',line)
        if m:subsection=m.group(1)
        for m in re.finditer(r'\\cite\{([^}]+)\}',line):
            left=max(line.rfind('. ',0,m.start()),line.rfind('? ',0,m.start()))
            left=left+2 if left>=0 else 0
            ends=[x for x in [line.find('. ',m.end()),line.find('? ',m.end())] if x>=0]
            right=min(ends)+1 if ends else len(line)
            for key in m.group(1).split(','):
                citations.append({'key':key.strip(),'line':lineno,'section':section,'subsection':subsection,'sentence':strip_tex(line[left:right])})
    audit=[];ledger=[];local_mismatches=[]
    for rec in records:
        key=rec['citation_key']; b=bib.get(key,{}); rr=byreceipt[key]; cs=[c for c in citations if c['key']==key]
        def norm(t):return re.sub(r'[^a-z0-9]','',strip_tex(str(t)).lower())
        match=norm(b.get('title',''))==norm(rec['title']) and b.get('doi','').casefold()==rec['doi'].casefold() and str(b.get('year',''))==str(rec['year'])
        if not match:local_mismatches.append(key)
        location='; '.join(f"{c['section']} / {c['subsection']}, line {c['line']}" for c in cs)
        context=' || '.join(c['sentence'] for c in cs)
        status='RECORD_LOCATED_SCOPE_LIMITED' if rr['record_located_this_revision'] else 'INHERITED_NOT_FRESHLY_VERIFIED'
        audit.append({'reference_number':rec['number'],'citation_key':key,'title':rec['title'],'authors':rec['authors'],'year':rec['year'],'doi':rec['doi'],'source_locator':rr['locator'],'source_class':rr['source_class'],'local_record_consistency':'PASS' if match else 'FAIL','external_review_status':status,'verification_scope':rr['verification_scope'],'manuscript_location':location,'local_claims':context,'support_status':'CLAIM_CONTEXT_RETAINED_NOT_AUTOMATICALLY_PROVEN','full_text_reviewed':False})
        evidence={'reference':rec,'receipt':rr,'contexts':cs}
        ledger.append({'citation_key':key,'manuscript_location':location,'scholarly_identifier':f"doi:{rec['doi']}",'source_locator':rr['locator'],'support_paraphrase':context,'evidence_sha256':hashlib.sha256(json.dumps(evidence,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'verification_status':status})
    for path,rows in [(LINE_AUDIT,audit),(LEDGER,ledger)]:
        with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    shape['local_record_mismatches']=local_mismatches
    shape['structural_verdict']='PASS' if not(local_mismatches or shape['multi_key_commands'] or shape['adjacent_citation_piles'] or shape['sentences_with_multiple_citation_commands'] or shape['numeric_citation_ranges'] or shape['uncited_bibliography_keys'] or shape['missing_bibliography_keys']) and shape['metadata_record_keys_match'] and shape['doi_records_unique'] else 'FAIL'
    SHAPE.write_text(json.dumps(shape,indent=2)+'\n')
    report={'schema_version':'2026-09-23-evidence-separated','record_count':len(records),'unique_scholarly_identifiers':len({r['doi'].casefold() for r in records}),'fresh_documented_record_checks':shape['fresh_record_checks'],'inherited_records_not_freshly_reverified':[r['citation_key'] for r in receipts if not r['record_located_this_revision']],'source_class_counts':dict(Counter(r['source_class'] for r in receipts)),'structural_verdict':shape['structural_verdict'],'semantic_verdict':'PARTIAL_EXTERNAL_REVIEW_NOT_FULL_TEXT_CERTIFICATION','verification_scope':'Structural bibliography/citation checks are automated. External receipts record only actually located scholarly records and their scope. A citation occurrence, matching local record, or hash is not proof that a source supports a claim. No universal 73/73 full-text or sentence-support certification is inferred.','imported_audits':'artifact/results/protocol-history/imported-audits','verdict':'PASS_STRUCTURAL_WITH_DISCLOSED_REVIEW_LIMITS'}
    VERIFY.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    if shape['structural_verdict']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
