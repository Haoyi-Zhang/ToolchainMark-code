#!/usr/bin/env python3
"""Generate manuscript numbers and tables only from the gated raw study."""
from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[2]
D=ROOT/'artifact/results/admission-study/derived'; OUT=ROOT/'paper/generated';OUT.mkdir(exist_ok=True)
s=json.loads((D/'summary.json').read_text())
accounting=json.loads((ROOT/'artifact/results/admission_denominators.json').read_text())
assert accounting['source_matrix']=='results/admission-study/matrix.csv'
assert s['rows']==accounting['configured_rows']
def n(v):return f'{v:,}'
def rows(name):
 with (D/name).open(newline='') as f:return list(csv.DictReader(f))
macro={
'EvidenceRows':n(s['rows']),'EvidenceClean':n(s['clean_rows']),
'EvidenceNoncleanRows':n(s['defect_rows']),
'EvidenceStageIsolationRows':n(accounting['stage_isolation_rows']),
'EvidenceFaultRows':n(accounting['fault_active_rows']),'EvidenceInconsistent':n(s['defect_verdicts'].get('INCONSISTENT',0)),
'EvidenceInadmissible':n(s['defect_verdicts'].get('INADMISSIBLE',0)),
'EvidenceFaultSatisfied':n(accounting['fault_active_satisfied_rows']),
'EvidenceExposed':n(s['units_exposed']),'EvidenceDesignExposed':str(s['design_exposed']),
'EvidenceExclusive':n(s['direct_exclusive_units']),
'EvidenceReplay':n(s['subject_replay']['matches']),'EvidenceKillsets':n(s['subject_replay']['killsets_equal']),
'EvidenceZeroClasses':str(len(s['zero_sensitivity_classes'])),
'EvidenceZeroOperators':str(len(s['zero_sensitivity_operators'])),
'EvidenceBootstrapSize':str(int(s['bootstrap']['suite_size_median'])),
'EvidenceBootstrapPerfect':n(s['bootstrap']['perfect']),
'EvidenceBootstrapMin':f"{100*s['bootstrap']['minimum']:.1f}\\%",
'EvidenceMedianSeconds':f"{s['run_timing']['median']:.3f}",
'EvidenceComparisonStatement':'A second execution is not yet part of the frozen evidence.'}
rc=D/'rerun_comparison.json'
if rc.exists():
 c=json.loads(rc.read_text())
 if c.get('verdict')=='PASS':macro['EvidenceComparisonStatement']=f"The two retained complete runs agree on all {n(c['rows'])} scientific row keys and {n(c['field_comparisons'])} comparisons over 11 retained non-timing fields; complete request, action, command, artifact, and per-input trajectories were not retained."
(OUT/'admission-results.tex').write_text('% Derived values; do not edit by hand.\n'+''.join('\\newcommand{\\'+k+'}{'+v+'}\n' for k,v in macro.items()))

def table(file,caption,label,cols,header,data):
 text='\\begin{table}[t]\n\\caption{'+caption+'}\n\\label{'+label+'}\n\\small\n\\begin{tabularx}{\\textwidth}{'+cols+'}\n\\toprule\n'+header+' \\\\\n\\midrule\n'
 text+=''.join(' & '.join(str(x) for x in r)+' \\\\\n' for r in data)
 text+='\\bottomrule\n\\end{tabularx}\n\\end{table}\n'
 (OUT/file).write_text(text)

table('admission-overview.tex',
'Three-valued outcomes of the evidence-gated protocol. An inadmissible case contributes to the attempted denominator but never to a fault-exposure numerator.',
 'tab:admission-overview','@{}X r r r r@{}',
 'Surface & Attempted & Satisfied & Inconsistent & Inadmissible',[
 ['Clean',n(s['clean_rows']),n(s['clean'].get('SATISFIED',0)),0,0],
 ['Stage isolation',macro['EvidenceStageIsolationRows'],macro['EvidenceStageIsolationRows'],0,0],
 ['Fault-active mechanisms',macro['EvidenceFaultRows'],macro['EvidenceFaultSatisfied'],macro['EvidenceInconsistent'],macro['EvidenceInadmissible']],
 ['Total',macro['EvidenceRows'],n(s['clean_rows']+s['defect_verdicts']['SATISFIED']),macro['EvidenceInconsistent'],macro['EvidenceInadmissible']]])
reason_names={'source_payload_recovered':'Source extraction does not recover the requested payload',
 'requested_branches_executed':'The requested compiler or optimization branch did not occur',
 'source_carrier_valid':'A valid authoritative source carrier cannot be established',
 'carrier_removed':'Carrier removal did not establish absence',
 'integrity_corruption_established':'Corruption did not reach the intended integrity decision'}
table('admission-reasons.tex','Failed evidence gates in fault executions. Reasons are recorded at the first failed gate, so the rows form a partition rather than overlapping causes.',
 'tab:admission-reasons','@{}X r@{}','First failed gate & Rows',
 [[reason_names[k],n(v)] for k,v in sorted(s['reasons'].items(),key=lambda x:-x[1])])
labels={'round_trip':'Round trip','host_semantics':'+ host observations','compiler_differential':'+ compiler/optimization comparisons','complete_catalog':'Complete catalog'}
table('admission-suites.tex','Fixed suites evaluated on the same planned units. Units with no inconsistent admitted relation remain in the denominator.',
 'tab:admission-suites','@{}X r r@{}','Suite & Design units exposed & All-subject units exposed',
 [[labels[r['suite']],f"{r['design_exposed']}/{r['design_units']}",f"{n(r['expanded_exposed'])}/{n(r['expanded_units'])}"] for r in s['suites']])
table('admission-relations.tex','Nonclean-configured outcomes by relation, including stage isolation. Each relation has 1,296 attempted nonclean rows; all 54 clean rows per relation are satisfied.',
 'tab:admission-relations','@{}X r r r@{}','Relation & Satisfied & Inconsistent & Inadmissible',
 [[r['relation'].replace('MR',r'\mr{')+'}',n(int(r['satisfied'])),n(int(r['inconsistent'])),n(int(r['inadmissible']))] for r in rows('relation_outcomes.csv')])
classes=rows('class_holdout.csv')
table('admission-class-holdout.tex','Fault-class holdout: relations are selected without the named class on the design subject, then evaluated on that class on the other 17 subjects.',
 'tab:current-class-holdout','@{}X r r r@{}','Withheld class & Planned units & Exposed & Sensitivity',
 [[r['fault_class'].capitalize(),n(int(r['test_units'])),n(int(r['exposed'])),f"{float(r['sensitivity'])*100:.1f}\\%"] for r in classes])
# A genuine data comparison, not a chart of unlike quantities on a shared axis.
left=[(name,int(row['design_exposed'])) for name,row in zip(['Round trip','+ host','+ build variation','Full catalog'],s['suites'])]
short={'artifact binding':'Binding','authentication':'Key','configuration':'Build request','embedding':'Embedding','extraction':'Extraction','false positive':'Absent carrier','integrity':'Integrity','normalization':'Normalization','semantic corruption':'Host semantics','stage routing':'Stage routing','state':'State','transformation':'Removal'}
right=[(short.get(r['fault_class'],r['fault_class']),float(r['sensitivity'])) for r in classes]
fig=r'''\begin{minipage}[t]{.46\textwidth}
\centering
\small\textbf{Fixed-suite sensitivity}\\[4pt]
\begin{tikzpicture}[x=.026cm,y=.9cm]
'''
for i,(name,val) in enumerate(left):
 y=4-i;pct=100*val/72
 fig+=f'\\node[font=\\scriptsize,anchor=east] at (-4,{y}) {{{name}}};\n'
 fig+=f'\\draw[black!20,line width=1.8pt] (0,{y})--(100,{y});\\draw[black!65,line width=1.8pt] (0,{y})--({pct:.4f},{y});\\fill ({pct:.4f},{y}) circle (1.6pt);\n'
 fig+=f'\\node[font=\\scriptsize,anchor=west] at (104,{y}) {{{val}/72}};\n'
fig+=r'''\foreach \x in {0,50,100}{\node[font=\scriptsize,anchor=north] at (\x,.5) {\x\%};}
\end{tikzpicture}
\end{minipage}\hfill
\begin{minipage}[t]{.51\textwidth}
\centering
\small\textbf{Held-out class sensitivity}\\[4pt]
\begin{tikzpicture}[x=.026cm,y=.30cm]
'''
for i,(name,val) in enumerate(right):
 y=12-i;pct=100*val
 fig+=f'\\node[font=\\scriptsize,anchor=east] at (-4,{y}) {{{name}}};\\draw[black!20,line width=1pt] (0,{y})--(100,{y});\\fill ({pct:.4f},{y}) circle (1.4pt);\n'
fig+=r'''\foreach \x in {0,50,100}{\node[font=\scriptsize,anchor=north] at (\x,-.3) {\x\%};}
\end{tikzpicture}
\end{minipage}
'''
(ROOT/'paper/figures/results-overview.tex').write_text(fig)
print('generated',len(list(OUT.glob('*.tex'))),'TeX inputs')
