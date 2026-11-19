"""Extract LTFRB SUMMARY sheet to a private staging CSV using Python stdlib.

Reads XLSX as its OpenXML ZIP representation; never modifies the source workbook.
This intentionally avoids Excel automation and macros. Supported: shared strings,
inline strings, numeric cells, and regular string URLs in column O.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PKG = '{http://schemas.openxmlformats.org/package/2006/relationships}'
ID_PATTERN = re.compile(r'drive\.google\.com/file/d/([A-Za-z0-9_-]+)')
COLS = ['route_no','region','mode','route_name','route_classification','lptrp_classification',
        'corridor_1','lgu_1','direction_1','length_km_1','corridor_2','lgu_2',
        'direction_2','length_km_2','source_url']
OUTPUT_COLS = COLS + ['file_id','excel_row','source_workbook_sha256']


def extract(workbook: Path) -> list[dict]:
    with zipfile.ZipFile(workbook) as archive:
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        mapping = {r.attrib['Id']: r.attrib['Target'] for r in rels.findall(f'{PKG}Relationship')}
        sheet = next((s for s in book.findall(f'{MAIN}sheets/{MAIN}sheet') if s.attrib['name'] == 'SUMMARY'), None)
        if sheet is None:
            raise ValueError('Expected SUMMARY sheet not found')
        target = mapping[sheet.attrib[f'{REL}id']].lstrip('/')
        target = target if target.startswith('xl/') else 'xl/' + target
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            ss = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            for item in ss.findall(f'{MAIN}si'):
                strings.append(''.join(t.text or '' for t in item.iter(f'{MAIN}t')))
        root = ET.fromstring(archive.read(target))
        result = []
        source_sha = hashlib.sha256(workbook.read_bytes()).hexdigest()
        for row in root.findall(f'{MAIN}sheetData/{MAIN}row'):
            number = int(row.attrib['r'])
            if number < 3:
                continue
            cells = {}
            for c in row.findall(f'{MAIN}c'):
                letters = re.match(r'[A-Z]+',c.attrib['r']).group(0)
                v = c.find(f'{MAIN}v')
                if c.attrib.get('t') == 'inlineStr':
                    inline = c.find(f'{MAIN}is')
                    value = ''.join(t.text or '' for t in inline.iter(f'{MAIN}t')) if inline is not None else ''
                elif v is None:
                    value = ''
                elif c.attrib.get('t') == 's':
                    value = strings[int(v.text)]
                else:
                    value = v.text or ''
                cells[letters] = str(value).strip()
            if not re.fullmatch(r'\d+',cells.get('A','')):
                continue
            fields = [cells.get(chr(65+i),'') for i in range(15)]
            record = dict(zip(COLS,fields))
            match = ID_PATTERN.search(record['source_url'])
            record['file_id'] = match.group(1) if match else ''
            record['excel_row'] = number
            record['source_workbook_sha256'] = source_sha
            result.append(record)
        return result


def main():
    p = argparse.ArgumentParser(description='Stage LTFRB SUMMARY workbook without modifying original')
    p.add_argument('--workbook', required=True, type=Path)
    p.add_argument('--out', type=Path, default=Path('data/staging/ltfrb/route_register.csv'))
    args = p.parse_args()
    rows = extract(args.workbook)
    if not rows:
        raise SystemExit('No SUMMARY route records found')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLS)
        writer.writeheader();writer.writerows(rows)
    meta = {
        'route_rows': len(rows),
        'unique_gdrive_files': len({r['file_id'] for r in rows if r['file_id']}),
        'missing_file_ids': sum(not r['file_id'] for r in rows),
        'modes': dict(sorted(Counter(r['mode'] for r in rows).items())),
        'classifications': dict(sorted(Counter(r['route_classification'] for r in rows).items())),
        'source_workbook_sha256': rows[0]['source_workbook_sha256'],
        'warning': 'Route register metadata is not evidence of current operations or navigation-ready linework.',
    }
    args.out.with_suffix('.summary.json').write_text(json.dumps(meta, indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.out),**meta},indent=2))

if __name__ == '__main__':
    main()
