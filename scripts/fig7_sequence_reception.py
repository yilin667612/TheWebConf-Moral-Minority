"""Reception versus comment-sequence position, independent of arrival-hour plots.

Commands: self-test; fetch --output NEW.jsonl; plot --source NEW.jsonl.
fetch performs read-only MongoDB queries through the existing analysis server.
No comment bodies, authors, or comment IDs are exported. Output files are
created exclusively, so a failed fetch cannot silently overwrite a prior run.
plot rejects incomplete collections and defaults to fixed sets of posts.

Sequence matches fig5_all_annotation.py (current Figure 3): first 24 hours,
recognized top-level judgments sorted by timestamp and comment ID, ten
equal-count stages, floor(10 * zero-based rank / total). All judgments set
the sequence BEFORE splitting majority/minority. Reception uses all eligible
posts, not the certainty annotation sample. No certainty filter is applied.
"""
import argparse
import base64
import collections
import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SIDES = {'NTA': 'NA', 'NAH': 'NA', 'YTA': 'YA', 'ESH': 'YA'}
FIELDS = ('n', 'score_n', 'score_sum', 'reply_sum')


def summarize_post(post, comments):
    children = collections.Counter(c.get('parent_id') for c in comments)
    retained = []
    for c in comments:
        if c.get('top_level') is not True or c.get('label') not in SIDES:
            continue
        pt, ct = post.get('created_utc'), c.get('created_utc')
        if not isinstance(pt, datetime.datetime) or not isinstance(ct, datetime.datetime):
            continue
        if 0 <= (ct-pt).total_seconds() < 86400:
            retained.append(c)
    retained.sort(key=lambda c: (c['created_utc'], str(c['_id'])))
    cells = {}
    total = len(retained)
    for rank, c in enumerate(retained):
        stage = 10*rank//total
        side = 'majority' if SIDES[c['label']] == post['dominant'] else 'minority'
        group = side if post['band'] == 'high' else 'low'
        cell = cells.setdefault(f'{group}|{stage}', dict.fromkeys(FIELDS, 0))
        cell['n'] += 1
        score = c.get('score')
        if isinstance(score, (int, float)) and math.isfinite(score):
            cell['score_n'] += 1
            cell['score_sum'] += score
        cell['reply_sum'] += children[c['_id']]
    assert sum(c['n'] for c in cells.values()) == total
    return dict(post_id=str(post['_id']), band=post['band'], dominant=post['dominant'],
                first_day_judgments=total, cells=cells)


def collect_remote(expected, completed_ids=()):
    # Runs only on the archive host. Deliberately no write-capable operations.
    from pymongo import MongoClient
    client = MongoClient('mongodb://127.0.0.1:27017', serverSelectionTimeoutMS=10000)
    db = client['reddit']
    posts = []
    for p in db.submissions.find({'YANA_total': {'$gte': 200}, 'YANA_split': {'$ne': None}},
            {'_id': 1, 'YANA_split': 1, 'created_utc': 1}).sort('_id', 1):
        share = p['YANA_split']
        if share == .5:
            continue
        band = 'high' if share <= .2 or share >= .8 else 'low' if .4 <= share <= .6 else None
        if band:
            p.update(band=band, dominant='YA' if share > .5 else 'NA')
            posts.append(p)
    digest = hashlib.sha256('\n'.join(str(p['_id']) for p in posts).encode()).hexdigest()
    assert digest == expected['post_ids_sha256'] and len(posts) == expected['selected_posts'], 'Post selection changed'
    assert [str(p['_id']) for p in posts[:len(completed_ids)]] == list(completed_ids), 'Resume prefix differs'
    def emit(record):
        print(json.dumps(record, separators=(',', ':')), flush=True)
    manifest = dict(kind='manifest', community='AITA', posts=len(posts), bands=dict(collections.Counter(p['band'] for p in posts)),
        post_ids_sha256=digest, first_day_hours=24, stages=10,
        retrieved_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        score='Last recorded score; missing excluded',
        reply='All recorded direct children, including those after the first day',
        ordering='Timestamp then string comment ID; all first-day judgment comments before group split')
    if not completed_ids:
        emit(manifest)
    import sys
    from concurrent.futures import ThreadPoolExecutor
    def read_batch(batch):
        by_post = collections.defaultdict(list)
        for c in db.comments.find({'link_id': {'$in': [p['_id'] for p in batch]}},
                {'_id': 1, 'link_id': 1, 'parent_id': 1, 'top_level': 1,
                 'label': 1, 'score': 1, 'created_utc': 1}).batch_size(10000).max_time_ms(180000):
            by_post[c['link_id']].append(c)
        return [dict(kind='post', **summarize_post(p, by_post[p['_id']])) for p in batch]
    batches = [posts[start:start+40] for start in range(len(completed_ids), len(posts), 40)]
    done = len(completed_ids)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, rows in enumerate(pool.map(read_batch, batches)):
            for row in rows:
                emit(row)
            done += len(rows)
            if index % 20 == 0:
                print(f'{done}/{len(posts)} posts', file=sys.stderr, flush=True)
    emit(dict(kind='complete', posts=len(posts)))
    client.close()


def fetch(args):
    import bson
    import pymongo
    expected = json.loads(args.reference.read_text())['communities']['AITA']['manifest']
    previous, completed_ids = [], []
    if args.resume:
        lines = args.resume.read_text().splitlines()
        for index, line in enumerate(lines):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                assert index == len(lines)-1, 'Invalid interior checkpoint record'
                break
            if index == 0:
                assert record['kind'] == 'manifest' and record['post_ids_sha256'] == expected['post_ids_sha256']
                assert record['first_day_hours'] == 24 and record['stages'] == 10
            else:
                assert record['kind'] == 'post', 'Resume only an incomplete collection'
                completed_ids.append(record['post_id'])
            previous.append(line)
        assert previous and len(set(completed_ids)) == len(completed_ids)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for module in (bson, pymongo):
            directory = Path(module.__file__).parent
            for path in directory.rglob('*.py'):
                archive.write(path, str(Path(directory.name)/path.relative_to(directory)))
    payload = base64.b64encode(buffer.getvalue()).decode()
    source = Path(__file__).read_text()
    bootstrap = "import base64,io,sys,tempfile,zipfile\nwith tempfile.TemporaryDirectory(prefix='sequence-reception-') as tmp:\n"
    bootstrap += f" zipfile.ZipFile(io.BytesIO(base64.b64decode({payload!r}))).extractall(tmp)\n sys.path.insert(0,tmp)\n"
    bootstrap += f" scope={{'__name__':'sequence_remote','__file__':'/tmp/fig7_sequence_reception.py'}}\n exec(compile({source!r},'fig7_sequence_reception.py','exec'),scope)\n scope['collect_remote']({expected!r},{completed_ids!r})\n"
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=30',
        'u1033719@cray.comp.anu.edu.au',
        'srun --nodes=1 --ntasks=1 --nodelist=dijkstra --partition=cpu --qos=interactive --time=01:00:00 --cpus-per-task=4 --mem=8G python3 -u -']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        if previous:
            handle.write('\n'.join(previous)+'\n')
            handle.flush()
        subprocess.run(command, input=bootstrap, text=True, stdout=handle, check=True)


def plot(args):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter, FixedLocator, NullLocator, FuncFormatter
    records = [json.loads(line) for line in args.source.read_text().splitlines()]
    assert records[0]['kind'] == 'manifest' and records[-1]['kind'] == 'complete', 'Incomplete collection'
    posts = records[1:-1]
    assert all(p['kind'] == 'post' for p in posts)
    assert len(posts) == records[0]['posts'] == records[-1]['posts']
    assert len({p['post_id'] for p in posts}) == len(posts)
    assert records[0]['first_day_hours'] == 24 and records[0]['stages'] == 10
    groups = [('majority', 'High agreement · Majority', '#5770DB', 'o'),
              ('minority', 'High agreement · Minority', '#DB5F57', 's'),
              ('low', 'Low agreement', '#8D99A8', '^')]
    values = {(group, metric): [] for group, *_ in groups for metric in ['score', 'reply']}
    for post in posts:
        for group, *_ in groups:
            cells = [post['cells'].get(f'{group}|{stage}', {}) for stage in range(10)]
            for metric, numerator, denominator in [('score', 'score_sum', 'score_n'), ('reply', 'reply_sum', 'n')]:
                row = [c[numerator]/c[denominator] if c.get(denominator, 0) else np.nan for c in cells]
                if not np.isfinite(row).any():
                    continue
                if args.selection == 'fixed' and not np.isfinite(row).all():
                    continue
                values[group, metric].append(row)
    ink = '#37474F'
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'pdf.fonttype': 42,
        'text.color': ink, 'axes.labelcolor': ink, 'axes.edgecolor': ink, 'xtick.color': ink, 'ytick.color': ink})
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.45))
    summary = []
    for ax, metric, label in zip(axes, ['score', 'reply'], ['Mean comment score', 'Mean reply count']):
        for group, name, color, marker in groups:
            matrix = np.asarray(values[group, metric])
            assert matrix.ndim == 2 and matrix.shape[1] == 10, (group, metric, 'No eligible posts')
            n = np.isfinite(matrix).sum(axis=0)
            assert (n > 0).all()
            means = np.nanmean(matrix, axis=0)
            ax.plot((np.arange(10)+.5)/10, means, color=color, marker=marker, ms=3.2, lw=1.8, label=name)
            summary.append(dict(group=group, metric=metric, n_posts=n.tolist(), means=means.tolist()))
        ax.set_yscale('symlog', linthresh=1 if metric == 'score' else .01)
        # Match the arrival-hour preview so vertical scales are comparable.
        limits = (-60, 1600) if metric == 'score' else (0, 4)
        ticks = [-10, -1, 0, 1, 10, 100, 1000] if metric == 'score' else [0, .01, .1, 1]
        assert all(limits[0] <= value <= limits[1]
                   for item in summary if item['metric'] == metric for value in item['means']), 'Clipped mean'
        ax.set_ylim(limits)
        ax.yaxis.set_major_locator(FixedLocator(ticks))
        ax.yaxis.set_minor_locator(NullLocator())
        ax.set_xlim(0, 1)
        ax.set_xticks([0, .25, .5, .75, 1])
        ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v:g}'))
        ax.set_ylabel(label, fontsize=10.5, labelpad=3)
        ax.tick_params(labelsize=10, length=3, pad=3)
        ax.spines[['top', 'right']].set_visible(False)
        ax.axhline(0, color=ink, lw=.65)
        ax.grid(axis='y', color='#DCE2E7', lw=.55, alpha=.7)
        ax.set_axisbelow(True)
    fig.legend(*axes[0].get_legend_handles_labels(), loc='upper center', bbox_to_anchor=(.52, 1),
        ncol=3, frameon=False, fontsize=10, handlelength=1.5, columnspacing=1.1, handletextpad=.4)
    fig.supxlabel('Comment-sequence position (first 24 h)', fontsize=10.5, y=.015)
    fig.subplots_adjust(left=.085, right=.99, bottom=.17, top=.86, wspace=.28)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = args.output/f'aita_sequence_reception_{args.selection}'
    fig.savefig(stem.with_suffix('.pdf'), bbox_inches='tight', pad_inches=.04)
    fig.savefig(stem.with_suffix('.png'), dpi=220, bbox_inches='tight', pad_inches=.04)
    plt.close(fig)
    stem.with_suffix('.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        selection=args.selection, summary=summary, method=__doc__,
        caveats='Post-equal averages; separate post sets per group and metric. No uncertainty intervals. Final recorded outcomes, not within-comment change.'), indent=2)+'\n')
    print(stem.with_suffix('.pdf'))


def self_test():
    time = datetime.datetime(2020, 1, 1)
    post = dict(_id='p', created_utc=time, band='high', dominant='NA')
    comments = [dict(_id=f'c{i:02}', parent_id='p', top_level=True, label='NTA' if i%2 == 0 else 'YTA',
        score=i, created_utc=time+datetime.timedelta(seconds=i)) for i in range(20)]
    # This late reply counts as reception but not as a sequence judgment.
    comments.append(dict(_id='reply', parent_id='c00', top_level=False,
        created_utc=time+datetime.timedelta(days=2)))
    row = summarize_post(post, comments[::-1])
    assert row['first_day_judgments'] == 20 and len(row['cells']) == 20
    assert row['cells']['majority|0']['reply_sum'] == 1
    assert row['cells']['minority|9']['score_sum'] == 19
    comments[0]['score'] = None
    assert summarize_post(post, comments)['cells']['majority|0']['score_n'] == 0
    low = summarize_post(dict(post, band='low'), comments)
    assert len(low['cells']) == 10 and all(c['n'] == 2 for c in low['cells'].values())
    # Timestamp ties follow comment IDs, and 24h is excluded.
    for c in comments[:20]: c['created_utc'] = time
    comments.append(dict(_id='late', parent_id='p', top_level=True, label='NTA', score=99,
        created_utc=time+datetime.timedelta(hours=24)))
    assert summarize_post(post, comments[::-1])['cells'] == summarize_post(post, comments)['cells']
    assert summarize_post(post, comments)['first_day_judgments'] == 20
    print('PASS: ordering, 10 stages, group split, late replies, missing scores, low-agreement pooling, 24h exclusion')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('self-test')
    p = sub.add_parser('fetch')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--resume', type=Path, help='Continue an incomplete collection into a NEW output file')
    p.add_argument('--reference', type=Path, default=ROOT/'scripts/data/fig3_arrival_post_equal.json')
    p = sub.add_parser('plot')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--selection', choices=['fixed', 'available'], default='fixed')
    p.add_argument('--output', type=Path, default=ROOT/'output/fig7_sequence_reception')
    args = parser.parse_args()
    if args.command == 'self-test': self_test()
    elif args.command == 'fetch': fetch(args)
    else: plot(args)


if __name__ == '__main__':
    main()
