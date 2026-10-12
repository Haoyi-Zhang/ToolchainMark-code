"""Draw retained sensitivity counts with the original physical panel extents."""
import argparse
import csv
from fractions import Fraction
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
from matplotlib import font_manager, pyplot as plt
from plot_font import PDF_METADATA, regular_libertine

HERE = Path(__file__).resolve().parent
BOXES = [(-66.06106102117062, 1.921464508094645, 100.64916562889167, 108.61103860523039),
         (-61.14107098381072, -14.065922789539227, 84.96294894146949, 135.82593275217934)]
LABELS = {'artifact binding': 'Binding', 'authentication': 'Key', 'configuration': 'Build request',
          'embedding': 'Embedding', 'extraction': 'Extraction', 'false positive': 'Absent carrier',
          'integrity': 'Integrity', 'normalization': 'Normalization', 'semantic corruption': 'Host semantics',
          'stage routing': 'Stage routing', 'state': 'State', 'transformation': 'Removal'}


def refresh_data(derived, target):
    summary = json.loads((derived/'summary.json').read_text(encoding='utf-8'))
    with (derived/'class_holdout.csv').open(encoding='utf-8', newline='') as stream:
        classes = list(csv.DictReader(stream))
    rows = []
    for label, row in zip(['Round trip', '+ host', '+ build variation', 'Full catalog'], summary['suites']):
        rows.append(['fixed', row['suite'], label, row['design_exposed'], row['design_units']])
    for row in classes:
        rows.append(['holdout', row['fault_class'], LABELS[row['fault_class']], int(row['exposed']), int(row['test_units'])])
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['panel', 'identity', 'label', 'exposed', 'planned'])
        writer.writerows(rows)


def draw(data, output, font):
    with data.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    fixed = [r for r in rows if r['panel'] == 'fixed']
    holdout = [r for r in rows if r['panel'] == 'holdout']
    if [r['label'] for r in fixed] != ['Round trip', '+ host', '+ build variation', 'Full catalog'] or len(holdout) != 12:
        raise ValueError('The original four-suite and twelve-class selection is required.')
    if [int(r['exposed']) for r in fixed] != [21, 27, 33, 69] or any(int(r['planned']) != 72 for r in fixed):
        raise ValueError('The retained fixed-suite counts changed.')
    if sum(int(r['exposed']) == 0 for r in holdout) != 5:
        raise ValueError('The five zero-sensitivity classes must remain visible.')
    size = 8.5*72/72.27
    prop = font_manager.FontProperties(fname=str(font), size=size)
    output.mkdir(parents=True, exist_ok=True)
    paths = []
    with plt.rc_context({'font.family': prop.get_name(), 'font.size': size, 'pdf.fonttype': 42, 'text.usetex': False}):
        for panel, selected, step, tick_y, name in [(0, fixed, .9, .5, 'results-overview-fixed.pdf'),
                                                   (1, holdout, .38, -.3, 'results-overview-holdout.pdf')]:
            xmin, ymin, xmax, ymax = BOXES[panel]
            xunit, yunit = .026*72/2.54, step*72/2.54
            fig = plt.figure(figsize=((xmax-xmin)/72, (ymax-ymin)/72))
            ax = fig.add_axes([0, 0, 1, 1])
            ax.set(xlim=(xmin/xunit, xmax/xunit), ylim=(ymin/yunit, ymax/yunit))
            ax.set_axis_off()
            gap = size/3
            for i, row in enumerate(selected):
                y = len(selected)-i
                numerator, denominator = int(row['exposed']), int(row['planned'])
                if denominator <= 0 or not 0 <= numerator <= denominator:
                    raise ValueError('Invalid exposed/planned count.')
                percent = float(100*Fraction(numerator, denominator))
                ax.hlines(y, 0, 100, color='0.8', linewidth=(1.8 if panel == 0 else 1)*72/72.27)
                if panel == 0:
                    ax.hlines(y, 0, percent, color='0.35', linewidth=1.8*72/72.27)
                ax.scatter([percent], [y], s=((3.2 if panel == 0 else 2.8)*72/72.27)**2,
                           color='black', linewidths=0, clip_on=False, zorder=3)
                ax.text(-4-gap/xunit, y, row['label'], ha='right', va='center', fontproperties=prop)
                if panel == 0:
                    ax.text(104+gap/xunit, y, f'{numerator}/{denominator}', ha='left', va='center', fontproperties=prop)
            for value in (0, 50, 100):
                ax.text(value, tick_y-gap/yunit, f'{value}%', ha='center', va='top', fontproperties=prop)
            path = output/name
            fig.savefig(path, metadata=PDF_METADATA)
            plt.close(fig)
            paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path)
    parser.add_argument('--data', type=Path, default=HERE/'results-overview.csv')
    parser.add_argument('--out-dir', type=Path, default=HERE)
    parser.add_argument('--refresh-data', type=Path, metavar='DERIVED', help='Read retained summary/class counts; do not execute experiments.')
    args = parser.parse_args()
    if args.refresh_data:
        refresh_data(args.refresh_data, args.data)
    for path in draw(args.data, args.out_dir, regular_libertine(HERE, args.font)):
        print(path.name)


if __name__ == '__main__':
    main()
