#!/usr/bin/env python3
"""Contrôle des fiches équipes de la cartographie.

Vérifie, pour chaque cartographie/fiches/*.yaml :
  - clé `equipe` connue et fichier corpus correspondant ;
  - identifiants de domaines / thèmes / applications présents dans vocabulaire.json ;
  - 1-2 domaines principaux, 3-8 thèmes principaux, chaque thème avec une phrase et 1-3 preuves ;
  - chaque preuve et publication représentative = id existant du corpus de l'équipe ;
  - pas de nom de permanent dans les phrases (granularité équipe) ;
  - couverture : toutes les équipes ayant un corpus non vide ont une fiche ;
  - chaque fiche correspond à une équipe de data.yaml (labo/sigle) ;
  - les clés de scores.json (thèmes, secteurs) existent dans vocabulaire.json.
Signale aussi les équipes à faible corpus (< 10 publications) à relire en priorité.
Code de sortie 1 s'il y a des erreurs.
Mode public (--public, dépôt GitHub) : corpus = cartographie/donnees/publications, pas de contrôle des noms
(la liste des permanents n'est pas publiée).
"""
import json, sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CARTO = ROOT / 'cartographie'

voc = json.loads((CARTO / 'vocabulaire.json').read_text())
DOM = {d['id'] for d in voc['domaines']}
THE = {t['id'] for t in voc['themes']}
APP = {a['id'] for a in voc['applications']}
PUBLIC = '--public' in sys.argv
CORPUS = CARTO / 'donnees' / 'publications' if PUBLIC else CARTO / 'corpus'
perms = {} if PUBLIC else yaml.safe_load(open(ROOT / 'permanents' / 'permanents.yaml', encoding='utf-8'))
noms = {p['nom'] for v in perms.values() for p in (v.get('permanents') or []) + [e for e in (v.get('emerites') or []) if isinstance(e, dict)]}
noms_famille = {n.split()[-1] for n in noms if len(n.split()[-1]) >= 4}

DATA = yaml.safe_load(open(ROOT / ('data.yaml' if PUBLIC else 'data_propose.yaml'), encoding='utf-8'))
EQUIPES_DATA = {f'{l}/{s}' for l, v in DATA.items() if isinstance(v, dict) for s in (v.get('Equipes') or {})}
SCORES = json.loads((CARTO / 'donnees' / 'scores.json' if PUBLIC else CARTO / 'scores.json').read_text())

erreurs, avertissements = [], []
corpus_ids = {}
for f in CORPUS.glob('*.json'):
    c = json.loads(f.read_text())
    corpus_ids[f.stem] = (c['equipe'], {p['id'] for p in c['publications']})

vues = set()
for f in sorted((CARTO / 'fiches').glob('*.yaml')):
    e = lambda m: erreurs.append(f'{f.stem}: {m}')
    try:
        fi = yaml.safe_load(open(f, encoding='utf-8'))
    except yaml.YAMLError as ex:
        e(f'YAML invalide ({ex})'); continue
    if f.stem not in corpus_ids:
        e('pas de corpus correspondant'); continue
    equipe, ids = corpus_ids[f.stem]
    vues.add(f.stem)
    if fi.get('equipe') != equipe:
        e(f"clé equipe {fi.get('equipe')!r} ≠ {equipe!r}")
    if fi.get('equipe') not in EQUIPES_DATA:
        e(f"équipe {fi.get('equipe')!r} absente de data.yaml (renommée ou retirée ? renommer ou supprimer la fiche)")
    d = fi.get('domaines') or {}
    pr, se = d.get('principaux') or [], d.get('secondaires') or []
    if not 1 <= len(pr) <= 2:
        e(f'{len(pr)} domaines principaux (1-2 attendus)')
    for x in pr + se:
        if x not in DOM:
            e(f'domaine inconnu {x}')
    th = fi.get('themes') or []
    if not 3 <= len(th) <= 8:  # thèmes principaux (avec phrase) ; les autres viennent des scores
        (avertissements if th else erreurs).append(f'{f.stem}: {len(th)} thèmes principaux (3-8 attendus)')
    for t in th:
        if t.get('id') not in THE:
            e(f"thème inconnu {t.get('id')}")
        if not t.get('phrase'):
            e(f"thème {t.get('id')} sans phrase")
        if not t.get('preuves'):
            e(f"thème {t.get('id')} sans preuve")
        for p in t.get('preuves') or []:
            if p not in ids:
                e(f"preuve {p} absente du corpus (thème {t.get('id')})")
    for a in fi.get('applications') or []:
        if a.get('id') not in APP:
            e(f"application inconnue {a.get('id')}")
        for p in a.get('preuves') or []:
            if p not in ids:
                e(f"preuve {p} absente du corpus (application {a.get('id')})")
    for x in fi.get('themes_exclus') or []:  # masqués à la relecture (faux positifs des scores)
        if x not in THE:
            e(f"thème masqué inconnu {x}")
    for x in fi.get('applications_exclues') or []:
        if x not in APP:
            e(f"application masquée inconnue {x}")
    rep = fi.get('publications_representatives') or []
    if not 3 <= len(rep) <= 5:
        avertissements.append(f'{f.stem}: {len(rep)} publications représentatives (3-5 attendues)')
    for p in rep:
        if p not in ids:
            e(f'publication représentative {p} absente du corpus')
    textes = ' '.join([fi.get('pour_etudiants') or '', fi.get('pour_entreprises') or ''] +
                      [t.get('phrase') or '' for t in th])
    for n in noms_famille:
        if f' {n} ' in f' {textes} ' or f' {n},' in textes or f' {n}.' in textes:
            avertissements.append(f'{f.stem}: nom de famille « {n} » dans les textes (à vérifier)')
    for champ in ('pour_etudiants', 'pour_entreprises'):
        if not fi.get(champ):
            e(f'{champ} vide')
    if len(ids) < 10:
        avertissements.append(f'{f.stem}: corpus faible ({len(ids)} publications) — relire en priorité')
    if fi.get('remarques'):
        avertissements.append(f"{f.stem}: remarque — {str(fi['remarques'])[:200]}")

for stem, (equipe, ids) in corpus_ids.items():
    if ids and stem not in vues:
        erreurs.append(f'{stem}: fiche manquante')

for stem, sc in SCORES.items():
    for couche, connus in (('themes', THE), ('applications', APP)):
        for k in (sc.get(couche) or {}):
            if k not in connus:
                erreurs.append(f'{stem}: scores.json, clé {couche} {k!r} absente de vocabulaire.json (recalculer les scores)')

print(f'{len(vues)} fiches contrôlées, {len(erreurs)} erreurs, {len(avertissements)} avertissements')
for m in erreurs:
    print('ERREUR  ', m)
for m in avertissements:
    print('ATTENTION', m)
sys.exit(1 if erreurs else 0)
