#!/usr/bin/env python3
"""Collect official regulated prices. No replacement on an invalid/incomplete fetch."""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import tempfile
import urllib.request
ROOT = Path(__file__).resolve().parents[1]

class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in {'script','style'}: self.skip+=1
    def handle_endtag(self,tag):
        if tag in {'script','style'}: self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if not self.skip and data.strip(): self.parts.append(' '.join(data.split()))
def words(html):
    p=Text();p.feed(html);return ' '.join(p.parts)
def date(value): return datetime.strptime(value.strip(),'%B %d, %Y').date().isoformat()
def amount(value):
    v=float(value)
    if not 20 <= v <= 1000: raise ValueError('Price outside supported cents/litre range')
    return v

def ns_html(html):
    text=words(html)
    d=re.search(r'As at:\s*(?:\w+,\s*)?([A-Z][a-z]+ \d{1,2}, \d{4})',text)
    if not d: raise ValueError('Missing NS source date')
    pattern=r'Gasoline Prices:\s*Zone (\d+)\s*cents/litre\s*Regular\s*Unleaded\s*Self-Service\s*Min\s*([\d.]+)\s*Max\s*([\d.]+)\s*Ultra-Low\s*Sulfur Diesel\s*Self-Service\s*Min\s*([\d.]+)\s*Max\s*([\d.]+)'
    matches=re.findall(pattern,text)
    if {x[0] for x in matches} != set('123456') or len(matches)!=6: raise ValueError('Expected all six NS zones')
    rows=[]
    for zone,lo,hi,dlo,dhi in matches:
        for fuel,a,b in [('regular',lo,hi),('diesel',dlo,dhi)]:
            rows.append({'id':f'ns-zone{zone}-{fuel}-self','province':'NS','zone':f'Zone {zone}','fuel':fuel,'service':'self','min':amount(a),'max':amount(b),'effective_date':date(d[1])})
    return rows

def pei_html(html):
    text=words(html)
    d=re.search(r'Retail Dealer Pump Prices\s*[–-]\s*All Brands\s*[–-]\s*([A-Z][a-z]+ \d{1,2}, \d{4})',text)
    if not d: raise ValueError('Missing PEI pump price date')
    rows=[]
    for kind,service in [('SS','self'),('FS','full')]:
        match=re.search(r'PUMP PRICE \('+kind+r'\)\s*((?:\d+\.\d+\s*){8})',text)
        if not match: raise ValueError('Missing PEI '+service+' table')
        values=[amount(x) for x in match[1].split()]
        for i,fuel in enumerate(['regular','midgrade','premium','diesel']):
            rows.append({'id':f'pei-island-{fuel}-{service}','province':'PEI','zone':'Island-wide','fuel':fuel,'service':service,'min':values[2*i],'max':values[2*i+1],'effective_date':date(d[1])})
    oil=re.search(r'Furnace Oil\s*[–-]\s*([A-Z][a-z]+ \d{1,2}, \d{4}).*?Maximum Price \(After Tax\)\s*(\d+\.\d+)',text)
    if not oil: raise ValueError('Missing PEI after-tax furnace oil maximum')
    rows.append({'id':'pei-island-furnace-delivery','province':'PEI','zone':'Island-wide','fuel':'furnace','service':'delivery','min':None,'max':amount(oil[2]),'effective_date':date(oil[1])})
    # IRAC's arrows are changes to self-serve MIN (oil: after-tax MAX), not both ends of the range.
    for table,fuel in [('3','regular'),('19','premium'),('4','diesel'),('5','furnace')]:
        block=re.search(r'<table\b[^>]*\bid="tablepress-'+table+r'".*?</table>',html,re.S)
        change=re.search(r'fa-arrow-alt-(up|down)[^>]*></i>\s*(\d+(?:\.\d+)?)',block[0]) if block else None
        if change:
            target=next(x for x in rows if x['fuel']==fuel and x['service'] in {'self','delivery'})
            target['published_change']=round(float(change[2])*(1 if change[1]=='up' else -1),3)
            target['change_basis']='maximum' if fuel=='furnace' else 'minimum'
    return rows

ADAPTERS={'ns_html':ns_html,'pei_html':pei_html}
def validate(rows,expected):
    if len(rows)!=expected or len({r['id'] for r in rows})!=len(rows): raise ValueError('Incomplete or duplicate price table')
    for r in rows:
        amount(r['max'])
        if r['min'] is not None and (amount(r['min'])>r['max']): raise ValueError('Inverted price range')
        if datetime.fromisoformat(r['effective_date']).year<2020: raise ValueError('Unexpected source edition')

def collect(config,previous=None,fetch=None,now=None):
    now=now or datetime.now(timezone.utc).isoformat(timespec='seconds')
    previous=previous or {'sources':[],'history':[]}
    prior={s['id']:s for s in previous['sources']}; sources=[]; history=list(previous.get('history',[])); failures=[]
    def download(url):
        req=urllib.request.Request(url,headers={'User-Agent':'CoolCode FuelWindow/1.0 (+https://coolcode.ca/fuelwindow/)'})
        with urllib.request.urlopen(req,timeout=config['timeout_seconds']) as response:
            if response.status!=200: raise ValueError('Unexpected source HTTP status')
            body=response.read(config['max_bytes']+1)
            if len(body)>config['max_bytes']: raise ValueError('Source exceeds byte limit')
            return body
    fetch=fetch or download
    for source in config['sources']:
        try:
            body=fetch(source['url']); rows=ADAPTERS[source['adapter']](body.decode('utf-8-sig'));validate(rows,source['expected_rows'])
            old=prior.get(source['id']); editions={r['effective_date'] for r in rows}
            if old and min(editions)<min(r['effective_date'] for r in old['prices']): raise ValueError('Source edition moved backwards')
            entry={'id':source['id'],'label':source['label'],'url':source['url'],'checked_at':now,'status':'ok','sha256':hashlib.sha256(body).hexdigest(),'prices':rows}
            signature=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
            if not any(h['source']==source['id'] and h['signature']==signature for h in history):
                history.append({'source':source['id'],'signature':signature,'captured_at':now,'prices':rows})
            sources.append(entry)
        except Exception as error:
            failures.append(source['id']); old=prior.get(source['id'])
            if not old: raise RuntimeError('No valid snapshot for '+source['id']) from error
            sources.append({**old,'status':'retained','last_error':type(error).__name__,'last_attempt_at':now})
    # Bound each source independently; new sources must not erase existing captures.
    history=[h for h in history if h in [x for x in history if x['source']==h['source']][-config['history_limit']:]]
    return {'schema':1,'last_attempt_at':now,'sources':sources,'history':history,'row_count':sum(len(s['prices']) for s in sources)},failures

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture-dir',type=Path);args=parser.parse_args()
    config=json.loads((ROOT/'config/sources.json').read_text());target=ROOT/'web/data/prices.json'
    previous=json.loads(target.read_text()) if target.exists() else None
    fetch=None
    if args.fixture_dir:
        fetch=lambda url:(args.fixture_dir/('fuel-ns.html' if 'nserbt.ca' in url else 'fuel-pei.html')).read_bytes()
    snapshot,failures=collect(config,previous,fetch)
    target.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=target.parent,delete=False) as f:
        json.dump(snapshot,f,ensure_ascii=False,indent=2);f.write('\n');temp=Path(f.name)
    temp.replace(target)
    print(f"{snapshot['row_count']} regulated price rows; retained sources: {', '.join(failures) or 'none'}")
    # Retained data is deployable with its original checked_at; source errors remain visible.
if __name__=='__main__':main()
