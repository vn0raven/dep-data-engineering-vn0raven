"""DEP Milestone 4: reproducible descriptive analysis of the M3 OSM extract.

All figures are about OpenStreetMap *coverage*, not operational route viability.
No fare, schedule, vehicle service, or travel-time claims are calculated.
"""
from __future__ import annotations

import argparse
import json
from html import escape
import shutil
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # file output works without GUI / internet
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIGURES = [
    ("01_route_stop_coverage.png", "Coverage of ordered stops by mapped route"),
    ("02_stop_metadata_quality.png", "Completeness of stop names and coordinates"),
    ("03_stop_coordinate_spread.png", "Where geocoded mapped stops appear"),
    ("04_candidate_transfer_stops.png", "Stops shared by multiple OSM route relations"),
]


def load_data(processed_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Require the M3 CSV schema; keep OSM identifiers as text."""
    files = [processed_dir / f for f in ('stops.csv', 'routes.csv', 'route_stops.csv')]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError('Milestone 3 outputs missing: ' + ', '.join(missing))
    stops, routes, route_stops = (pd.read_csv(p, dtype={'stop_id': 'string', 'route_id': 'string'}) for p in files)
    required = {
        'stops': {'stop_id', 'name', 'latitude', 'longitude'},
        'routes': {'route_id', 'route_name', 'route_mode'},
        'route_stops': {'route_id', 'stop_id', 'stop_sequence'},
    }
    for label, df in [('stops', stops), ('routes', routes), ('route_stops', route_stops)]:
        absent = required[label] - set(df.columns)
        if absent:
            raise ValueError(f'{label} is missing M3 columns: {sorted(absent)}')
    if stops['stop_id'].isna().any() or stops['stop_id'].duplicated().any():
        raise ValueError('M3 stops must have unique, non-null stop_id')
    if routes['route_id'].isna().any() or routes['route_id'].duplicated().any():
        raise ValueError('M3 routes must have unique, non-null route_id')
    if route_stops.duplicated(['route_id', 'stop_sequence']).any():
        raise ValueError('Duplicate ordered occurrences in route_stops')
    if not set(route_stops['route_id']).issubset(set(routes['route_id'])):
        raise ValueError('route_stops refers to unknown route')
    if not set(route_stops['stop_id']).issubset(set(stops['stop_id'])):
        raise ValueError('route_stops refers to unknown stop')
    for field in ('latitude', 'longitude'):
        stops[field] = pd.to_numeric(stops[field], errors='coerce')
    return stops, routes, route_stops


def summarise(stops: pd.DataFrame, routes: pd.DataFrame, route_stops: pd.DataFrame) -> dict:
    """Calculate all M4 headline numbers from CSVs, never from manually entered data."""
    names = stops['name'].fillna('').astype(str).str.strip().ne('')
    coords = stops['latitude'].between(-90, 90) & stops['longitude'].between(-180, 180)
    per_route = route_stops.groupby('route_id').size().reindex(routes['route_id'], fill_value=0)
    route_counts = route_stops.groupby('stop_id')['route_id'].nunique()
    candidates = route_counts[route_counts >= 2]
    route_stops_count = int(len(route_stops))
    connections = sum(max(int(n)-1, 0) for n in per_route.to_numpy())
    candidate_df = stops[stops['stop_id'].isin(candidates.index)]
    named_shared = candidate_df['name'].fillna('').astype(str).str.strip().ne('')
    return {
        'source_file': (str(stops['source_file'].iloc[0]) if 'source_file' in stops.columns and len(stops) else 'unknown'),
        'stops': int(len(stops)),
        'routes': int(len(routes)),
        'route_stop_occurrences': route_stops_count,
        'modes': {str(k): int(v) for k, v in routes['route_mode'].value_counts(dropna=False).items()},
        'routes_with_ordered_stops': int((per_route > 0).sum()),
        'routes_without_ordered_stops': int((per_route == 0).sum()),
        'named_stops': int(names.sum()),
        'unnamed_stops': int((~names).sum()),
        'geocoded_stops': int(coords.sum()),
        'stops_without_coordinates': int((~coords).sum()),
        'shared_stops': int(len(candidates)),
        'shared_stops_named': int(named_shared.sum()),
        'shared_stops_without_coordinates': int((~(candidate_df['latitude'].between(-90, 90) & candidate_df['longitude'].between(-180, 180))).sum()),
        'ordered_adjacent_pairs': int(connections),
        'comparison_scope': 'OSM route relations and stop metadata, not confirmed current local operations',
        'fare_data_available': False,
        'travel_time_data_available': False,
    }


def _format_axes(ax, title: str, subtitle: str):
    ax.set_title(title, loc='left', fontsize=14, weight='bold', pad=28, color='#1c2b3f')
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, ha='left', va='bottom', fontsize=9, color='#66768b')
    ax.grid(axis='x', alpha=.13, color='#52677a')
    ax.set_axisbelow(True)
    ax.spines[['top','right','left']].set_visible(False)
    ax.tick_params(axis='both', length=0, labelcolor='#425469', labelsize=9, pad=6)


def plot_route_coverage(routes: pd.DataFrame, rs: pd.DataFrame):
    counts = rs.groupby('route_id').size()
    q = routes[['route_id','route_name','route_mode']].copy()
    q['count'] = q['route_id'].map(counts).fillna(0).astype(int)
    q = q.sort_values(['count','route_id'], ascending=[True,True]).reset_index(drop=True)
    labels = [f"{str(v)[:30]}  · {str(rid).split(':')[-1]}" for v, rid in zip(q['route_name'].fillna('Unnamed route'), q['route_id'])]
    fig, ax = plt.subplots(figsize=(12.5,7.8))
    bars = ax.barh(np.arange(len(q)),q['count'],color=['#1e958d' if n > 0 else '#cbd7e2' for n in q['count']],height=.66)
    ax.set_yticks(np.arange(len(q)), labels)
    ax.set_xlim(0,max(1,int(q['count'].max()))+1.6)
    ax.set_xlabel('Explicit ordered stop/platform occurrences in OSM relation',labelpad=12,color='#66768b')
    _format_axes(ax,'Routes with explicitly mapped stop sequences','Route names may describe intercity / ferry trips; no operational status is inferred.')
    for b, n in zip(bars,q['count']):
        ax.text(b.get_width()+.13,b.get_y()+b.get_height()/2,str(n),va='center',fontsize=9,color='#203449')
    fig.subplots_adjust(left=.32,right=.96,top=.86,bottom=.10)
    return fig


def plot_metadata_quality(stops: pd.DataFrame):
    named = stops['name'].fillna('').astype(str).str.strip().ne('')
    coord = stops['latitude'].between(-90,90)&stops['longitude'].between(-180,180)
    avail=np.array([int(named.sum()),int(coord.sum())]); miss=np.array([int((~named).sum()),int((~coord).sum())]); y=np.arange(2)
    fig, ax = plt.subplots(figsize=(10.5,5.4))
    ax.barh(y,avail,color='#1e958d',height=.45,label='Present')
    ax.barh(y,miss,left=avail,color='#e6ab63',height=.45,label='Missing')
    ax.set_yticks(y,['Stop name','Valid coordinates'])
    ax.invert_yaxis();ax.set_xlim(0,len(stops)*1.15)
    _format_axes(ax,'Missing fields are a routing and search limitation',f'{len(stops)} unique mapped stops in processed OSM data; missing does not mean invalid record.')
    for i,(v,m) in enumerate(zip(avail,miss)):
        if v: ax.text(v/2,i,str(v),ha='center',va='center',color='white',fontsize=11,weight='bold')
        if m: ax.text(v+m/2,i,str(m),ha='center',va='center',color='#493b20',fontsize=11,weight='bold')
    ax.legend(frameon=False,loc='lower right',ncol=2)
    ax.set_xlabel('Number of stop records',labelpad=12,color='#66768b')
    fig.subplots_adjust(left=.19,right=.97,top=.78,bottom=.15)
    return fig


def plot_coordinate_spread(stops: pd.DataFrame):
    clean=stops.loc[stops['latitude'].between(-90,90) & stops['longitude'].between(-180,180)]
    fig,ax=plt.subplots(figsize=(10.5,6.5))
    ax.scatter(clean.longitude,clean.latitude,color='#2e85b7',alpha=.60,s=27,edgecolors='white',linewidths=.3)
    terminal=clean.loc[clean['name'].fillna('').astype(str).str.contains('Davao City Overland Transport Terminal',case=False,regex=False)]
    if not terminal.empty:
        ax.scatter(terminal.longitude,terminal.latitude,color='#e79a45',marker='*',s=185,zorder=4,edgecolors='white',linewidths=.8,label='OSM-labeled DCOTT')
        ax.legend(frameon=False,loc='upper right')
    _format_axes(ax,'Geographic extent of the retained stop records','Coordinates are plotted without basemap; some route members lie far outside Davao City.')
    ax.set_xlabel('Longitude (degrees east)',labelpad=12,color='#66768b')
    ax.set_ylabel('Latitude (degrees north)',labelpad=12,color='#66768b')
    ax.grid(axis='y',alpha=.13,color='#52677a')
    fig.subplots_adjust(left=.12,right=.96,top=.82,bottom=.14)
    return fig


def plot_shared_stops(stops: pd.DataFrame,rs: pd.DataFrame):
    unique=rs.groupby('stop_id')['route_id'].nunique()
    shared=unique[unique>=2].sort_values(ascending=True)
    s=stops.set_index('stop_id')
    labels=[]
    for sid in shared.index:
        name=s.loc[sid,'name']
        name=str(name).strip() if pd.notna(name) else ''
        labels.append((name[:34] if name else 'Unnamed stop') + ' · ' + str(sid).split(':')[-1])
    fig,ax=plt.subplots(figsize=(11.4,6.5))
    bars=ax.barh(np.arange(len(shared)),shared.values,color=['#1e958d' if 'Davao City Overland' in x else '#7faec9' for x in labels],height=.63)
    ax.set_yticks(np.arange(len(shared)), labels)
    ax.set_xlim(0,max(3,int(shared.max())+1))
    _format_axes(ax,'Shared stop identifiers suggest possible transfers','Coinciding OSM members do NOT establish real-world interchange, city coverage or schedule compatibility.')
    ax.set_xlabel('Distinct OSM route relations containing this stop',labelpad=12,color='#66768b')
    for b,n in zip(bars,shared.values):ax.text(b.get_width()+.08,b.get_y()+b.get_height()/2,str(int(n)),va='center',color='#203449',fontsize=10)
    fig.subplots_adjust(left=.37,right=.96,top=.80,bottom=.13)
    return fig


def _fmt_pct(n,d):
    return f'{100*n/d:.1f}%' if d else 'n/a'


def insights_markdown(m: dict)->str:
    p=_fmt_pct(m['routes_with_ordered_stops'],m['routes']); n_pct=_fmt_pct(m['unnamed_stops'],m['stops'])
    return f'''# M4 — Initial Insights: Davao Commute Router

**Source snapshot:** `{m['source_file']}` (OpenStreetMap via Overpass; route and stop records may be intercity).  
**Interpretive scope:** A descriptive audit of the Milestone 3 OSM extract, **not** a measured assessment of Davao City's current public transport coverage, actual operations or rider experience.

## Figure 1 — Route-to-stop coverage

![Mapped route stop occurrences](../output/figures/01_route_stop_coverage.png)

**Observation.** {m['routes_with_ordered_stops']} of {m['routes']} mapped OSM route relations ({p}) include explicit stop/platform members; {m['routes_without_ordered_stops']} have none. There are {m['route_stop_occurrences']} ordered route-stop occurrences in total. Some long-distance routes have more recorded stops than local numbered routes.

**Interpretation.** The extracted stop sequences are insufficient to operate a reliable Davao-only bus/jeepney router. A route with zero explicit stops is not proof that it has no real-world stops.

## Figure 2 — Stop metadata completeness

![Stop metadata completeness](../output/figures/02_stop_metadata_quality.png)

**Observation.** {m['unnamed_stops']} of {m['stops']} stops ({n_pct}) have no name; {m['stops_without_coordinates']} lack valid point coordinates.

**Interpretation.** Unnamed records reduce destination search usability. Non-point or missing coordinates prevent direct map snapping without additional geometry processing. These records were intentionally retained instead of guessed or deleted.

## Figure 3 — Geographic dispersion

![Coordinate spread](../output/figures/03_stop_coordinate_spread.png)

**Observation.** The {m['geocoded_stops']} valid stop coordinates have a broad geographic spread. Some belong to route relations connecting Davao with destinations elsewhere in the Philippines.

**Interpretation.** A Davao-filtered OSM extraction can still include out-of-area *relation members*. We must clip and verify the actual geographic service area before presenting city-specific coverage. This scatterplot is **not** a cartographic route map or service-area polygon.

## Figure 4 — Candidate shared stops

![Shared stop identifiers](../output/figures/04_candidate_transfer_stops.png)

**Observation.** {m['shared_stops']} unique stop identifiers occur in two or more route relations; {m['shared_stops_named']} of these records have names, and {m['shared_stops_without_coordinates']} lack point coordinates.

**Interpretation.** These overlaps are *candidate* transfer references only. They do not prove walkability, direction, local relevance, transfer legality, operating hours or current service.

## Cautious inference and next action

The first barrier to estimating the **fastest and cheapest door-to-door commute** is not algorithm selection: it is data completeness and geographic/service validation. The Milestone 3 data contain **no validated fares, timetables, waiting-time profiles, tricycle operating zones or local walking network**. Therefore, neither commute time nor fare can be calculated responsibly from these tables alone.

The analyses support prioritizing (1) Davao-only route scope and ordered boarding data, (2) verifiable local service records, (3) route/fare operating rules, and (4) separate walkable-road extraction. The charts cannot establish the true number of active routes in the city, overall stop coverage, traffic conditions or whether any specific transfer is feasible.

## Reproducibility

From repository root:

```powershell
pip install -r requirements.txt
python scripts/m4_insights.py
```

This builds four PNG charts, `data/processed/m4_insights_summary.json`, this document, and a **static offline-viewable** `dashboard/index.html`. These artifacts are generated from the checked-in M3 CSVs with no internet calls. Open the dashboard locally in a browser. Inspect `notebooks/m4_initial_insights.ipynb` to run the analysis interactively.

## Data governance

OpenStreetMap data: © OpenStreetMap contributors, ODbL 1.0. See <https://www.openstreetmap.org/copyright>. The descriptive charts are generated from the July 8, 2026 committed extract. Do not label OSM route relations as current government-authorized services without corroboration.
'''


def dashboard_html(m: dict)->str:
    p=_fmt_pct(m['routes_with_ordered_stops'],m['routes']); missing=_fmt_pct(m['unnamed_stops'],m['stops'])
    cards=[('Mapped route relations',str(m['routes']),'Not necessarily active local services'),('Routes with ordered stops',str(m['routes_with_ordered_stops']),p+' of mapped relations'),('Mapped stop records',str(m['stops']),missing+' have no name'),('Candidate shared stops',str(m['shared_stops']),'Not verified physical transfers')]
    names=[('01','Route sequencing',FIGURES[0][0],f"Only {m['routes_with_ordered_stops']} of {m['routes']} route relations have ordered stop members. This is an OSM mapping gap, not evidence a service is inactive."),('02','Metadata quality',FIGURES[1][0],f"{m['unnamed_stops']} stops have no name; {m['stops_without_coordinates']} lack usable point coordinates. Both limit offline route search."),('03','Coordinate spread',FIGURES[2][0],'Some retained relation members lie outside Davao City. Geographic scope must be verified before making local coverage claims.'),('04','Candidate interchanges',FIGURES[3][0],f"{m['shared_stops']} stop identifiers are shared by multiple routes. They are not verified usable transfers.")]
    card_html=''.join(f'<article class="stat"><div class="stat-label">{escape(label)}</div><strong>{escape(value)}</strong><small>{escape(note)}</small></article>' for label,value,note in cards)
    chart_html=''.join(f'''<article class="panel" id="chart-{num}"><div class="panel-head"><span class="figure-tag">FIGURE {num}</span><h2>{escape(title)}</h2></div><img loading="lazy" src="assets/figures/{escape(fname)}" alt="{escape(FIGURES[int(num)-1][1])}" /><p>{escape(note)}</p></article>''' for num,title,fname,note in names)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light"><title>Davao Commute Router · Milestone 4 Insights</title>
<style>
:root{{--ink:#142840;--muted:#5b6d82;--bg:#f3f6fa;--card:#fff;--teal:#087e79;--line:#e0e7ef;}}
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}}
a{{color:#006b79}}.hero{{padding:3.2rem max(1.5rem,calc((100% - 1100px)/2));background:#112d43;color:white}}
.kicker{{text-transform:uppercase;letter-spacing:.16em;color:#8fe0d3;font-size:.78rem;font-weight:750}}h1{{font-size:clamp(2rem,4vw,3.2rem);margin:.55rem 0 1rem;max-width:790px;line-height:1.12}}.hero p{{max-width:790px;color:#d0e0e7}}
.wrap{{max-width:1100px;margin:auto;padding:1.7rem 1.5rem 4rem}}.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-top:-3.2rem;position:relative}}
.stat,.panel,.note{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 6px 20px #1428400a}}.stat{{padding:1.25rem}}.stat-label{{font-size:.83rem;font-weight:650;color:var(--muted)}}.stat strong{{display:block;font-size:2.05rem;letter-spacing:-.04em;margin:.35rem 0}}.stat small{{display:block;color:var(--muted);font-size:.78rem}}.section-intro{{margin:2.8rem 0 1rem}}.section-intro h2{{font-size:1.5rem;margin:.2rem 0}}.section-intro p{{color:var(--muted);margin:.25rem 0}}.charts{{display:grid;grid-template-columns:1fr 1fr;gap:1.1rem}}.panel{{overflow:hidden}}.panel-head{{padding:1.4rem 1.5rem 0}}.panel-head h2{{font-size:1.12rem;margin:.3rem 0 .3rem}}.figure-tag{{font-size:.69rem;color:var(--teal);font-weight:800;letter-spacing:.1em}}.panel img{{display:block;width:100%;height:auto;object-fit:contain;background:white}}.panel p{{padding:0 1.5rem 1.5rem;margin:0;color:var(--muted);font-size:.91rem}}
.note{{padding:1.6rem;margin-top:1.4rem;border-left:4px solid var(--teal)}}.note h2{{margin:0 0 .5rem}}.note p{{margin:.5rem 0;color:#405468}}footer{{padding:1.5rem 0;color:var(--muted);font-size:.79rem}}
@media(max-width:850px){{.stats{{grid-template-columns:repeat(2,1fr)}}.charts{{grid-template-columns:1fr}}}}@media(max-width:460px){{.stats{{grid-template-columns:1fr 1fr}}.stat strong{{font-size:1.6rem}}.wrap{{padding:1.6rem 1rem}}.hero{{padding:2.4rem 1rem 4rem}}}}
</style></head>
<body><header class="hero"><div class="kicker">DEP Engineering Open Track / M4 · Initial insights</div><h1>Davao Commute Router<br>What the available data can actually tell us</h1><p>Four reproducible visualizations of mapped route connectivity, stop completeness, geographic reach and possible interchanges—without inventing fares, travel times or active transport services.</p></header>
<main class="wrap"><section class="stats" aria-label="Analysis statistics">{card_html}</section><div class="section-intro"><div class="kicker" style="color:#087e79">OpenStreetMap snapshot analysis</div><h2>Four evidence-based findings</h2><p>Source: {escape(m['source_file'])}. Counts describe the processed OSM extract, not officially authorized Davao service.</p></div><section class="charts">{chart_html}</section><aside class="note"><h2>Cautious inference</h2><p>These records reveal a coverage and validation problem, not a finished multimodal transport network. Even though {m['ordered_adjacent_pairs']} adjacent stop pairs can be derived, no valid basis exists here for estimating actual fare, passenger wait, service status, or fastest door-to-door route. Many retained stop records are associated with nonlocal intercity routes.</p><p><strong>Recommended next step:</strong> verify local route geography and ordered boarding locations, then integrate dated official fares, schedules, pedestrian network and any authorized tricycle zones. Treat shared stop IDs as unverified transfer candidates.</p></aside><footer>Data: © OpenStreetMap contributors · <a href="https://www.openstreetmap.org/copyright">ODbL attribution</a> · <a href="https://github.com/vn0raven/dep-data-engineering-vn0raven">Project repository</a> · Charts and this page work offline once the repository is downloaded.</footer></main></body></html>'''


def run(processed_dir:Path, figures_dir:Path, documentation_path:Path, dashboard_path:Path):
    stops, routes, rs=load_data(processed_dir)
    m=summarise(stops,routes,rs)
    # Stable, deterministic artifacts; do not add runtime-generated timestamps.
    figures_dir.mkdir(parents=True,exist_ok=True)
    for fname,func in zip([x[0] for x in FIGURES],[lambda:plot_route_coverage(routes,rs),lambda:plot_metadata_quality(stops),lambda:plot_coordinate_spread(stops),lambda:plot_shared_stops(stops,rs)]):
        fig=func()
        fig.savefig(figures_dir/fname,dpi=165,facecolor='white')
        plt.close(fig)
    summary=processed_dir/'m4_insights_summary.json'
    summary.write_text(json.dumps(m,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    documentation_path.parent.mkdir(parents=True,exist_ok=True)
    documentation_path.write_text(insights_markdown(m),encoding='utf-8')
    dashboard_path.parent.mkdir(parents=True,exist_ok=True)
    published_figures = dashboard_path.parent / 'assets' / 'figures'
    published_figures.mkdir(parents=True, exist_ok=True)
    for fname, _ in FIGURES:
        shutil.copyfile(figures_dir / fname, published_figures / fname)
    dashboard_path.write_text(dashboard_html(m),encoding='utf-8')
    print(json.dumps({'figures':len(FIGURES),'summary':str(summary),'dashboard':str(dashboard_path),**m},indent=2))
    return m


def main():
    p=argparse.ArgumentParser(description='Generate DEP M4 initial insights from existing M3 outputs (offline)')
    p.add_argument('--processed-dir',type=Path,default=ROOT/'data'/'processed')
    p.add_argument('--figures-dir',type=Path,default=ROOT/'output'/'figures')
    p.add_argument('--document',type=Path,default=ROOT/'docs'/'MILESTONE4_INSIGHTS.md')
    p.add_argument('--dashboard',type=Path,default=ROOT/'dashboard'/'index.html')
    args=p.parse_args()
    run(args.processed_dir,args.figures_dir,args.document,args.dashboard)

if __name__=='__main__':
    main()
