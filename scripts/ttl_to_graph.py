# -*- coding: utf-8 -*-
"""phr-ontology.ttl → Graphviz DOT. graphviz 바이너리 불필요(텍스트 생성)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from rdflib import Graph, RDFS, OWL
PHR = "https://namuh.health/phr#"
import glob
g = Graph()
for _f in sorted(glob.glob("docs/ontology/*.ttl")): g.parse(_f, format="turtle")
ln  = lambda u: str(u).split("#")[-1]
lbl = lambda u: str(g.value(u, RDFS.label) or ln(u))
isphr = lambda u: str(u).startswith(PHR)

subof = [(s, o) for s, o in g.subject_objects(RDFS.subClassOf) if isphr(s) and isphr(o)]
objprops = []
for p in g.subjects(predicate=None, object=OWL.ObjectProperty):
    d, r = g.value(p, RDFS.domain), g.value(p, RDFS.range)
    if d is not None and r is not None and isphr(d) and isphr(r):
        objprops.append((d, ln(p), r))

nodes = set()
for s, o in subof: nodes |= {s, o}
for d, _, r in objprops: nodes |= {d, r}

dot = ['digraph PHR {',
       '  rankdir=LR; bgcolor="white";',
       '  node [shape=box, style="rounded,filled", fillcolor="#eef2f6", color="#c2cedb", fontname="Malgun Gothic", fontsize=11];',
       '  edge [fontname="Malgun Gothic", fontsize=9];']
for n in sorted(nodes, key=ln):
    dot.append(f'  "{ln(n)}" [label="{lbl(n)}"];')
for s, o in subof:
    dot.append(f'  "{ln(o)}" -> "{ln(s)}" [arrowhead=onormal, color="#999999"];')
for d, p, r in objprops:
    dot.append(f'  "{ln(d)}" -> "{ln(r)}" [label="{p}", color="#1F4E79", fontcolor="#1F4E79"];')
dot.append('}')
open("docs/ontology/phr-ontology.dot", "w", encoding="utf-8").write("\n".join(dot))
print(f"DOT 저장: 노드 {len(nodes)} · subClassOf {len(subof)} · 관계 {len(objprops)}")
