#!/usr/bin/env python3
"""Génère cartographie/cartographie.html : page autonome « qui fait quoi » en informatique graphique,
réduite à deux tableaux croisés (thèmes × équipes, secteurs × équipes) + fiche équipe au clic (2026-11-07).

Entrées : cartographie/vocabulaire.json, cartographie/fiches/*.yaml, cartographie/corpus/*.json,
          cartographie/stats.json, data_propose.yaml,
          ../example-formations-graphique/data.yaml (formations IG par ville, pour les étudiants)
Sortie  : cartographie/cartographie.html (données JSON incluses ; Leaflet chargé depuis cdnjs pour la carte)

Granularité équipe : aucun nom d'auteur ; seul le correspondant AFIG est nommé.

Mode public (--public, dépôt GitHub / github.io) : lit data.yaml, cartographie/donnees/{scores,stats}.json et
cartographie/donnees/publications/*.json (titres, lieux, liens, sans résumé) ; aucune liste de permanents
(seuls les effectifs) ; écrit _site/index.html.
Usage : python scripts/carto_generer.py [--public]
"""
import unicodedata
import json, re, sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CARTO = ROOT / 'cartographie'
FORMATIONS = ROOT.parent / 'example-formations-graphique' / 'data.yaml'
PUBLIC = '--public' in sys.argv
if PUBLIC:
    CHEMINS = {'data': ROOT / 'data.yaml', 'scores': CARTO / 'donnees' / 'scores.json', 'stats': CARTO / 'donnees' / 'stats.json',
               'corpus': CARTO / 'donnees' / 'publications', 'theses': CARTO / 'donnees' / 'theses.json', 'permanents': None,
               'permanents_public': CARTO / 'donnees' / 'permanents.json', 'sortie': ROOT / '_site' / 'index.html'}
else:
    CHEMINS = {'data': ROOT / 'data_propose.yaml', 'scores': CARTO / 'scores.json', 'stats': CARTO / 'stats.json',
               'corpus': CARTO / 'corpus', 'theses': CARTO / 'theses_equipes.json', 'permanents': ROOT / 'permanents' / 'permanents.yaml', 'sortie': CARTO / 'cartographie.html'}

COORD = {  # coordonnées approximatives des sites
    'Lille': (50.63, 3.06), 'Strasbourg': (48.58, 7.75), 'Rennes': (48.11, -1.68), 'Vannes': (47.66, -2.76),
    'Toulouse': (43.60, 1.44), 'Saint Mandé': (48.84, 2.42), 'Dijon': (47.32, 5.04), 'Saint-Denis': (48.94, 2.36),
    'Marne-la-Vallée': (48.84, 2.59), 'Lyon': (45.76, 4.84), 'Montpellier': (43.61, 3.88), 'Palaiseau': (48.71, 2.21),
    'Grenoble': (45.19, 5.72), 'Marseille': (43.30, 5.37), 'Limoges': (45.83, 1.26), 'Poitiers': (46.58, 0.34),
    'Nancy': (48.69, 6.18), 'Bordeaux': (44.84, -0.58), 'Calais': (50.95, 1.86), 'Sophia Antipolis': (43.62, 7.05),
    'Saclay': (48.73, 2.17),
}
REGION_FORMATION = {'Palaiseau': 'Paris', 'Saint-Denis': 'Paris', 'Marne-la-Vallée': 'Paris', 'Saclay': 'Paris',
                    'Saint Mandé': 'Paris', 'Sophia Antipolis': None, 'Orsay': 'Paris', 'Gif-sur-Yvette': 'Paris',
                    'Évry-Courcouronnes': 'Paris', 'Montbonnot-Saint-Martin': 'Grenoble', 'Talence': 'Bordeaux'}


REGION = {  # région administrative de chaque site (regroupement « par localité »)
    'Lille': 'Hauts-de-France', 'Calais': 'Hauts-de-France', 'Strasbourg': 'Grand Est', 'Nancy': 'Grand Est',
    'Rennes': 'Bretagne', 'Vannes': 'Bretagne', 'Toulouse': 'Occitanie', 'Montpellier': 'Occitanie',
    'Dijon': 'Bourgogne-Franche-Comté', 'Lyon': 'Auvergne-Rhône-Alpes', 'Grenoble': 'Auvergne-Rhône-Alpes',
    'Marseille': "Provence-Alpes-Côte d'Azur", 'Sophia Antipolis': "Provence-Alpes-Côte d'Azur",
    'Limoges': 'Nouvelle-Aquitaine', 'Poitiers': 'Nouvelle-Aquitaine', 'Bordeaux': 'Nouvelle-Aquitaine',
    'Palaiseau': 'Île-de-France', 'Saclay': 'Île-de-France', 'Saint-Denis': 'Île-de-France',
    'Marne-la-Vallée': 'Île-de-France', 'Saint Mandé': 'Île-de-France',
    # ajouts du 2026-11-08 (fusion du dépôt research-team)
    'Montbonnot-Saint-Martin': 'Auvergne-Rhône-Alpes', 'Le Bourget-du-Lac': 'Auvergne-Rhône-Alpes', 'Talence': 'Nouvelle-Aquitaine',
    'Orsay': 'Île-de-France', 'Gif-sur-Yvette': 'Île-de-France', 'Évry-Courcouronnes': 'Île-de-France', 'Paris': 'Île-de-France',
    'Reims': 'Grand Est', 'Brest': 'Bretagne', 'Cesson-Sévigné': 'Bretagne', 'Nantes': 'Pays de la Loire',
    'Laval': 'Pays de la Loire', 'Chalon-sur-Saône': 'Bourgogne-Franche-Comté',
}


def vecteur(e):
    """Profil thématique d'une équipe : scores continus des thèmes (v² = part du thème le plus fort, cf.
    carto_scores.py) + domaines de la fiche (principal 1, secondaire 0,5)."""
    v = {'t:' + t: x['v'] ** 2 for t, x in e['st'].items()}
    for d in e['domaines'].get('principaux') or []:
        v['d:' + d] = v.get('d:' + d, 0) + 1.0
    for d in e['domaines'].get('secondaires') or []:
        v['d:' + d] = v.get('d:' + d, 0) + 0.5
    return v


def cosinus(a, b):
    num = sum(a[k] * b[k] for k in a.keys() & b.keys())
    den = (sum(x * x for x in a.values()) * sum(x * x for x in b.values())) ** 0.5
    return num / den if den else 0.0


def regroupement_thematique(equipes, vocab, nb_groupes=10):
    """Classification ascendante hiérarchique (lien moyen, distance = 1 - cosinus), en Python pur.
    Renvoie l'ordre des feuilles du dendrogramme et `nb_groupes` groupes (coupe du dendrogramme).
    Chaque groupe est nommé par ses deux domaines dominants."""
    vecs = [vecteur(e) for e in equipes]
    n = len(equipes)
    dist = [[1 - cosinus(vecs[i], vecs[j]) for j in range(n)] for i in range(n)]
    grappes = {i: [i] for i in range(n)}          # id -> feuilles (dans l'ordre du dendrogramme)
    hauteur = {i: 0.0 for i in range(n)}
    fusions = []
    suivant = n
    while len(grappes) > 1:
        ids = list(grappes)
        meilleur = None
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = grappes[ids[x]], grappes[ids[y]]
                d = sum(dist[i][j] for i in a for j in b) / (len(a) * len(b))
                if meilleur is None or d < meilleur[0]:
                    meilleur = (d, ids[x], ids[y])
        d, a, b = meilleur
        grappes[suivant] = grappes.pop(a) + grappes.pop(b)
        hauteur[suivant] = d
        fusions.append((d, a, b, suivant))
        suivant += 1
    ordre = next(iter(grappes.values()))
    # coupe : on rejoue les n - nb_groupes premières fusions
    groupe = {i: i for i in range(n)}
    membres = {i: [i] for i in range(n)}
    for d, a, b, c in fusions[:max(n - nb_groupes, 0)]:
        membres[c] = membres.pop(a) + membres.pop(b)
        for i in membres[c]:
            groupe[i] = c
    # numérotation des groupes dans l'ordre des feuilles + nom par domaines dominants
    noms_dom = {d['id']: d['fr'] for d in vocab['domaines']}
    num, libelles = {}, []
    for i in ordre:
        g = groupe[i]
        if g not in num:
            num[g] = len(num)
            poids = {}
            for k in membres.get(g, [i]):
                for cle, val in vecs[k].items():
                    if cle.startswith('d:'):
                        poids[cle[2:]] = poids.get(cle[2:], 0) + val
            top = sorted(poids, key=lambda x: -poids[x])[:2]
            libelles.append(' · '.join(noms_dom[x] for x in top))
    for rang, i in enumerate(ordre):
        equipes[i]['ordre_thematique'] = rang
        equipes[i]['groupe_thematique'] = num[groupe[i]]
    return libelles


def coordonnees(lab, eq, ville):
    """Coordonnées du champ « Coordonnées » de data.yaml (équipe, sinon labo si l'équipe est sur son site), sinon COORD."""
    c = eq.get('Coordonnées') or (None if eq.get('Ville') else lab.get('Coordonnées'))
    return tuple(c) if c else COORD.get(ville)


def ville_equipe(lab, eq):
    v = (eq.get('Ville') or lab.get('Ville') or '').split(',')[0].strip()
    return v


def couche_scores(sc, corpus, exemples):
    """Scores d'une couche (thèmes ou secteurs) pour la page : v (0-1), nb explicites/implicites, exemples,
    et toutes les publications qui contribuent (c : [id, contribution, explicite, mots-clés])."""
    res = {}
    for k, x in sc.items():
        contrib = [c for c in x.get('contributions') or [] if c[0] in corpus]
        for i, *_ in contrib:
            p = corpus[i]
            exemples.setdefault(i, {'titre': p['titre'], 'annee': p['annee'], 'url': p['url'], 'lieu': p['lieu'],
                                    'partiel': bool(p.get('via_partiel'))})
        res[k] = {'v': x['v'], 'p': x.get('profil', 0), 'vol': x.get('volume', 0), 'e': x['explicites'], 'i': x['implicites'], 'f': x.get('fiche', False),
                  'ex': [i for i in x['exemples'][:3] if i in corpus], 'c': contrib}
    return res


ORDRE_IG = {'oui': 0, 'partiel': 1, 'non': 2, 'inconnu': 3}


def statut_affiche(statut):
    """« HDR » est implicite pour les professeurs, les directeurs de recherche (Senior Researcher, DR) et les
    émérites : on ne l'affiche que pour les autres grades (MCF, Associate Professor, chargés de recherche...)."""
    if re.match(r'(PR|Professor|Professeur|PU|Senior Researcher|DR|Emeritus|Émérite)\b', statut, re.I):
        return re.sub(r',?\s*HDR\b', '', statut).strip(' ,')
    return statut


def sites_perso():
    """Sites web professionnels des permanents (permanents/sites/trouves_*.yaml) : {(équipe, nom): url}."""
    res = {}
    for f in sorted((ROOT / 'permanents' / 'sites').glob('trouves_*.yaml')):
        for eq, personnes in (yaml.safe_load(open(f, encoding='utf-8')) or {}).items():
            for nom, v in (personnes or {}).items():
                if isinstance(v, dict) and v.get('site'):
                    res[(eq, nom)] = v['site']
    return res


def membres(p, equipe='', sites={}):
    """Permanents de l'équipe (sources publiques, permanents/permanents.yaml) : nom, statut, employeur, annotation IG,
    site web professionnel s'il est connu."""
    res = [{'nom': m['nom'], 'site': sites.get((equipe, m['nom'])), 'statut': statut_affiche(m.get('statut') or ''), 'employeur': m.get('employeur') or '',
            'ig': m.get('ig') or 'inconnu', 'domaines': m.get('ig_domaines') or '', 'emerite': emerite}
           for emerite, cle in ((False, 'permanents'), (True, 'emerites')) for m in p.get(cle) or []]
    res.sort(key=lambda m: (m['emerite'], ORDRE_IG.get(m['ig'], 9), m['nom'].split()[-1]))
    return {'liste': res, 'source': p.get('source'), 'date': p.get('date_source')}


# Laboratoires présentés en un bloc par site quand leurs équipes sont dans deux villes d'une même région
# (demande de Damien, 2026-11-13 : « XLIM Poitiers » et « XLIM Limoges » plutôt qu'un seul bloc XLIM).
SITES_SEPARES = {'XLIM'}


def annuaire(data, ids_fiches, sites_noms={}):
    """Annuaire classique (même contenu que le README du dépôt GitHub, généré depuis data.yaml) : villes ->
    laboratoires -> équipes. Une équipe est rangée dans sa propre ville (champ Ville de l'équipe, sinon du labo)."""
    villes = {}
    for labo in sorted(data, key=str.lower):
        lab = data[labo]
        info_lab = {'sigle': labo, 'nom': lab.get('Nom', ''), 'url': lab.get('URL'), 'umr': lab.get('UMR'),
                    'correspondant': lab.get('Correspondant'), 'correspondant_site': sites_noms.get(lab.get('Correspondant')), 'equipes': []}
        eqs = lab.get('Equipes') or {}
        if not eqs:
            v = (lab.get('Ville') or 'Autre').split(',')[0].strip()
            villes.setdefault(v, {}).setdefault(labo, dict(info_lab, ville=lab.get('Ville', '')))
            continue
        for sigle in sorted(eqs, key=str.lower):
            eq = eqs[sigle]
            v = ville_equipe(lab, eq) or 'Autre'
            bloc = villes.setdefault(v, {}).setdefault(labo, dict(info_lab, equipes=[], ville=lab.get('Ville', '')))
            fid = re.sub(r'[^A-Za-z0-9]+', '_', f'{labo}/{sigle}').strip('_')  # même nom que le corpus (carto_stats.fichier_equipe)
            bloc['equipes'].append({'sigle': sigle, 'nom': eq.get('Nom', ''), 'url': eq.get('URL'),
                                    'correspondant': eq.get('Correspondant'), 'correspondant_site': sites_noms.get(eq.get('Correspondant')), 'themes': eq.get('Thèmes', ''),
                                    'ville': eq.get('Ville') or lab.get('Ville', ''), 'inria': 'Inria' in eq,
                                    'fiche': fid if fid in ids_fiches else None})
    sans_accent = lambda s: unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode().lower()
    # regroupement par région (demande de Damien, 2026-11-08) : un labo dont les équipes sont dans plusieurs villes
    # d'une même région n'apparaît qu'une fois ; sa ville est affichée dans son en-tête, celle d'une équipe située
    # ailleurs dans sa tuile. Le champ « ville » du bloc porte le nom de la région (ancre #v-region).
    regions = {}
    for v in villes:
        reg = REGION.get(v, 'Autre')
        bloc_r = regions.setdefault(reg, {'villes': set(), 'labos': {}})
        bloc_r['villes'].add(v)
        for labo, l in villes[v].items():
            site = (REGION_FORMATION.get(v) or v) if labo in SITES_SEPARES else ''  # un bloc par site
            cle = (labo, site)
            if cle in bloc_r['labos']:
                bloc_r['labos'][cle]['equipes'] += l.get('equipes', [])
                continue
            vl = site or (l.get('ville') or '').split(',')[0].strip()
            bloc_r['labos'][cle] = dict(l, equipes=list(l.get('equipes', [])), site=site, ville_aff=vl if REGION.get(vl) == reg else '')
    res = []
    for reg in sorted(regions, key=lambda x: (x == 'Autre', sans_accent(x))):
        labos = sorted(regions[reg]['labos'].values(), key=lambda l: (l['ville_aff'] == '', sans_accent(l['ville_aff']), l['sigle'].lower()))
        for l in labos:
            l['equipes'].sort(key=lambda e: (sans_accent(e['ville'].split(',')[0]), e['sigle'].lower()))
        res.append({'ville': reg, 'villes': sorted(regions[reg]['villes'], key=sans_accent), 'labos': labos})
    return res


def charger():
    voc = json.loads((CARTO / 'vocabulaire.json').read_text())
    scores = json.loads(CHEMINS['scores'].read_text())
    perms = yaml.safe_load(open(CHEMINS['permanents'], encoding='utf-8')) if CHEMINS['permanents'] else None
    sites = sites_perso() if perms is not None else {}
    # version publique : noms, statuts et sites des permanents, sans annotation IG (carto_exporter_public.py)
    pp = CHEMINS.get('permanents_public')
    perms_pub = json.loads(pp.read_text()) if perms is None and pp and pp.exists() else None
    if perms_pub:
        sites = {(eq, m['nom']): m['site'] for eq, v in perms_pub.items() for m in v['liste'] if m.get('site')}
    stats = json.loads(CHEMINS['stats'].read_text())
    theses = json.loads(CHEMINS['theses'].read_text()) if CHEMINS['theses'].exists() else {}
    data = yaml.safe_load(open(CHEMINS['data'], encoding='utf-8'))
    formations = {}
    if FORMATIONS.exists():
        for ville, f in (yaml.safe_load(open(FORMATIONS, encoding='utf-8')).get('Listing') or {}).items():
            formations[ville] = [{'nom': x.get('Name'), 'titre': x.get('Title'), 'url': x.get('url'), 'principale': k == 'main'}
                                 for k in ('main', 'other') for x in (f.get(k) or [])]
    equipes = []
    for fichier in sorted((CARTO / 'fiches').glob('*.yaml')):
        fi = yaml.safe_load(open(fichier, encoding='utf-8'))
        corpus = {p['id']: p for p in json.loads((CHEMINS['corpus'] / f'{fichier.stem}.json').read_text())['publications']}
        # thèses en IG de l'équipe : documents du corpus des scores (identifiant « these: » + NNT, voir carto_scores.py)
        for x in (theses.get(fi['equipe']) or {}).get('soutenues') or []:
            corpus['these:' + x['id']] = {'titre': x['titre'], 'annee': x['annee'], 'url': 'https://theses.fr/' + x['id'],
                                          'lieu': 'Thèse, ' + x['etablissement'], 'type': 'these'}
        labo, sigle = fi['equipe'].split('/', 1)
        lab = data.get(labo) or {}
        eq = (lab.get('Equipes') or {}).get(sigle)
        if eq is None:  # équipe renommée ou retirée de data.yaml : on ignore la fiche plutôt que de planter
            print(f"ATTENTION {fichier.name} : équipe {fi['equipe']} absente de data.yaml, fiche ignorée", file=sys.stderr)
            continue
        ville = ville_equipe(lab, eq)
        region = REGION_FORMATION.get(ville, ville)
        pub = lambda i: {k: corpus[i][k] for k in ('titre', 'annee', 'lieu', 'url', 'type')} if i in corpus else None
        st = stats.get(fi['equipe'], {})
        exemples = {}
        sc = scores.get(fichier.stem, {'themes': {}, 'applications': {}})
        equipes.append({
            'st': couche_scores(sc['themes'], corpus, exemples), 'sa': couche_scores(sc['applications'], corpus, exemples),
            'exemples': exemples, 'membres': membres(perms.get(fi['equipe']) or {}, fi['equipe'], sites) if perms is not None else (perms_pub.get(fi['equipe']) if perms_pub else None),
            'id': fichier.stem, 'sigle': sigle, 'labo': labo, 'nom': eq.get('Nom', ''), 'labo_nom': lab.get('Nom', ''),
            'ville': ville, 'region': REGION.get(ville, 'Autre'), 'coord': coordonnees(lab, eq, ville), 'url': eq.get('URL'), 'labo_url': lab.get('URL'),
            'inria': 'Inria' in eq or labo == 'Inria', 'correspondant': eq.get('Correspondant'), 'correspondant_site': {n: u for (_, n), u in sites.items()}.get(eq.get('Correspondant')),
            'domaines': fi['domaines'], 'themes': fi['themes'], 'applications': [a['id'] for a in fi.get('applications') or []],
            'representatives': [p for p in (pub(i) for i in fi.get('publications_representatives') or []) if p],
            'synthese': fi.get('synthese', ''), 'pour_etudiants': fi.get('pour_etudiants', ''), 'pour_entreprises': fi.get('pour_entreprises', ''),
            'stats': {'permanents_ig': st.get('permanents_ig'), 'permanents_partiel': st.get('permanents_partiel', 0),
                      'publications': st.get('publications'),
                      'lieux': [l for l, _ in st.get('lieux_principaux', [])[:5] if l != '(lieu inconnu)'],
                      'par_annee': st.get('par_annee', {})},
            'formations': formations.get(region, []) if region else [],
            # thèses : champs affichés seulement (mots-clés et résumés servent au calcul des scores, pas à la page)
            'theses': (lambda v: v and {**v, 'soutenues': [{k: x[k] for k in ('id', 'titre', 'titre_en', 'annee', 'etablissement')}
                                                          for x in v['soutenues']]})(theses.get(fi['equipe'])),
        })
    voc = dict(voc, groupes_thematiques=regroupement_thematique(equipes, voc))
    return voc, equipes, annuaire(data, {e['id'] for e in equipes}, {n: u for (_, n), u in sites.items()})


PAGE = r"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cartographie IG</title>
<style>
:root{--bg:#ffffff;--panel:#ffffff;--ink:#18181b;--muted:#71717a;--line:#e4e4e7;--accent:#4d7c0f;--accent-soft:#f1fadf;--brand:#a2d026;--hdr:#18181b;--hdr-ink:#ffffff;--hdr-muted:#a1a1aa;--warn:#92400e;--warn-bg:#fffbeb;--heat0:#f4f4f5;--heat1:#d9f99d;--heat2:#a3e635;--heat3:#65a30d;--heat4:#3f6212;--chip:#f4f4f5;--labo-bg:#f4f4f5;--team-bg:#fafafa}
/* fond blanc par défaut, même si le système est en mode sombre ; thème sombre seulement avec data-theme="dark" */
:root[data-theme="dark"]{--bg:#09090b;--panel:#18181b;--ink:#fafafa;--muted:#a1a1aa;--line:#27272a;--accent:#bef264;--accent-soft:#1f2a0e;--brand:#a2d026;--hdr:#000000;--hdr-ink:#ffffff;--hdr-muted:#a1a1aa;--warn:#fcd34d;--warn-bg:#291d06;--heat0:#27272a;--heat1:#365314;--heat2:#4d7c0f;--heat3:#84cc16;--heat4:#d9f99d;--chip:#27272a;--labo-bg:#202023;--team-bg:#141416}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header,main,footer{max-width:1400px;margin:0 auto;padding:0 16px}
main{max-width:none}  /* les tableaux prennent toute la largeur de la fenêtre */
main h2,main p.meta,main .chips,main .outils{max-width:1368px;margin-left:auto;margin-right:auto}
/* bandeau aux couleurs de l'AFIG : anthracite du logo, filet vert anis */
header{max-width:none;background:var(--hdr);color:var(--hdr-ink);padding:20px max(16px,calc((100% - 1368px)/2)) 14px;border-bottom:4px solid var(--brand)}
header h1 b{color:var(--brand);font-weight:inherit}
header .sub{color:var(--hdr-muted)}
header .nav a{color:var(--brand)}header .nav a:hover{text-decoration:underline}
/* barre commune aux pages AFIG (équipes, entreprises, carte) */
.sites{display:flex;flex-wrap:wrap;align-items:center;gap:4px 16px;font-size:13px;margin:0 0 12px}
.sites a{color:var(--hdr-muted);text-decoration:none}.sites a:hover{color:var(--hdr-ink);text-decoration:underline}
.sites a[aria-current]{color:var(--hdr-ink);font-weight:600}
.sites .afig{font-weight:800;color:var(--brand)}.sites .gh{margin-left:auto}
h1{font-size:24px;margin:0 0 4px} h2{font-size:19px;margin:28px 0 6px} h3{font-size:16px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 12px}
.banner{background:var(--warn-bg);color:var(--warn);border-radius:8px;padding:8px 12px;font-size:13px;margin:8px 0 4px}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:13px;cursor:pointer;color:var(--ink);font-family:inherit}
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:var(--panel)}
.meta{color:var(--muted);font-size:13px}
.tag{display:inline-block;background:var(--accent-soft);color:var(--accent);border-radius:4px;padding:1px 6px;font-size:12px;margin:2px 4px 2px 0}
.outils{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}
.selection{font-size:13px;color:var(--accent)} .selection button{font:inherit;font-size:12px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:1px 8px;cursor:pointer;margin-left:6px}
.matrice{width:fit-content;max-width:100%;margin:0 auto;overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--panel);max-height:78vh}
.matrice table{border-collapse:collapse;font-size:12px}
.matrice th{position:sticky;background:var(--panel);font-weight:500;z-index:1}
.matrice thead tr.noms th{top:24px;height:150px;vertical-align:bottom;padding:4px 2px;z-index:2}
.matrice thead tr.taille th{height:48px;vertical-align:bottom;padding:2px 1px;z-index:2;font-size:10px;font-weight:400;color:var(--muted)}
.matrice thead tr.t-perm th{top:182px} .matrice thead tr.t-pub th{top:234px;height:18px;border-bottom:1px solid var(--line)}
.matrice thead tr.taille th:first-child{text-align:right;padding-right:8px;font-size:11px}
.matrice thead tr.taille i{display:block;width:12px;margin:0 auto;border-radius:2px 2px 0 0}
.matrice thead tr.taille i.ig{background:var(--heat4)} .matrice thead tr.taille i.part{background:var(--heat1)} .matrice thead tr.taille i.pub{background:var(--heat2)}
.matrice thead tr.taille b{display:block;font-weight:400;margin-top:2px}
.matrice thead tr.grp th{top:0;height:24px;padding:2px 3px;z-index:2;font-size:11px;font-weight:700;color:var(--accent);background:var(--accent-soft);
 border-left:2px solid var(--panel);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:0;cursor:help}
.matrice thead tr.grp th:first-child{background:var(--panel)}
.matrice .sep{border-left:2px solid var(--accent)!important}
.seg{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:8px;padding:2px;background:var(--panel);margin:6px 0}
.seg-l{max-width:1368px;margin:0 auto}
.seg .meta{padding:0 8px}.seg .chip{border:0;border-radius:6px;background:none}
.seg .chip[aria-pressed="true"]{background:var(--ink);color:var(--panel)}
.legende-groupes{display:block;max-width:1368px;margin:0 auto 6px}.legende-groupes summary{cursor:pointer}
#legende-groupes{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--muted);padding-top:4px}
#legende-groupes b{color:var(--accent)}
.matrice thead th span{writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;cursor:pointer}
.matrice thead th span:hover{color:var(--accent)}
.matrice tbody th{left:0;text-align:left;padding:2px 8px;white-space:nowrap;max-width:340px;overflow:hidden;text-overflow:ellipsis}
.matrice tbody th .lien{cursor:pointer} .matrice tbody th .lien:hover{color:var(--accent);text-decoration:underline}
.matrice tbody th.actif{color:var(--accent);font-weight:700}
.matrice td{width:22px;min-width:22px;height:22px;border:1px solid var(--bg)}  /* cases carrées */
.matrice td[data-cell]{cursor:pointer}
.contrib{margin:6px 0;font-size:14px;display:grid;grid-template-columns:62px 1fr;gap:2px 10px;align-items:start}
.contrib .src{font-size:11px;border-radius:4px;padding:1px 5px;text-align:center;white-space:nowrap}
.src-titre{background:var(--heat4);color:var(--panel)}.src-resume{background:var(--heat1);color:var(--ink)}
.kw{font-size:12px;color:var(--muted)}.kw b{color:var(--accent);font-weight:600}
.btn{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:6px;padding:2px 10px;cursor:pointer}
.h0{background:var(--heat0)}.h1{background:var(--heat1)}.h2{background:var(--heat2)}.h3{background:var(--heat3)}.h4{background:var(--heat4)}
.dom-row th{background:var(--accent-soft)!important;color:var(--accent);font-weight:700}
.legend{display:flex;gap:6px;align-items:center;font-size:12px;color:var(--muted)}.legend i{width:120px;height:12px;display:inline-block;border-radius:2px;background:linear-gradient(90deg,var(--heat1),var(--heat4));background:linear-gradient(90deg,color-mix(in srgb,var(--heat4) 8%,var(--heat0)),var(--heat4))}
.membres{width:100%;border-collapse:collapse;font-size:13px}.membres td{padding:3px 6px;border-top:1px solid var(--line);vertical-align:top}
.membres td:first-child{white-space:nowrap;font-weight:500}.ig{display:inline-block;font-size:11px;border-radius:4px;padding:0 5px;white-space:nowrap}
.ig-oui{background:var(--heat4);color:var(--panel)}.ig-partiel{background:var(--heat1);color:var(--ink)}.ig-non,.ig-inconnu{background:var(--chip);color:var(--muted)}
.piste{display:inline-block;width:50px;height:8px;border-radius:2px;background:var(--heat0);vertical-align:middle;margin-right:6px;overflow:hidden}.piste i{display:block;height:100%;background:var(--heat3)}
.autres{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:2px 16px;font-size:13px}
.autres div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
dialog{border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--ink);max-width:760px;width:calc(100% - 32px);padding:0}
dialog::backdrop{background:rgba(0,0,0,.4)}
.dlg{padding:18px} .close{float:right;background:none;border:0;font-size:22px;color:var(--muted);cursor:pointer}
.theme{margin:8px 0} .pub{margin:6px 0;font-size:14px} a{color:var(--accent)}
.spark{display:flex;align-items:flex-end;gap:2px;height:28px;margin:4px 0}.spark i{display:block;width:8px;background:var(--heat3);border-radius:2px 2px 0 0}
footer{padding:16px;color:var(--muted);font-size:12px}
/* annuaire des équipes (contenu du README GitHub) */
.annuaire{max-width:1368px;margin:0 auto}
.ann-outils{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin:8px 0 4px}
.ann-outils input{font:inherit;font-size:14px;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);width:min(320px,100%)}
.ann-villes{display:flex;flex-wrap:wrap;gap:4px}.ann-villes a{font-size:12px;text-decoration:none;background:var(--chip);border-radius:999px;padding:2px 9px;color:var(--ink)}
.ann-villes a:hover{background:var(--accent-soft);color:var(--accent)}
.labo-site{font-weight:700;font-size:14px;color:var(--accent);margin:4px 0 0}.ville{position:relative}.ancre-ville{position:absolute;top:0;left:0;width:0;height:0;scroll-margin-top:12px}  /* hors de la grille de .ville */
.ville{margin:18px 0 0}.ville h3{font-size:15px;margin:0 0 8px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600;
 display:flex;align-items:center;gap:10px}.ville h3::after{content:"";flex:1;height:1px;background:var(--line)}
.labos{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}
.labo{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.labo-t{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;margin-bottom:2px}
.labo-t a,.labo-t b{font-weight:700;font-size:15px;text-decoration:none}.labo-n{font-size:13px;color:var(--muted);margin:0 0 6px}
.equipe{border-top:1px solid var(--line);padding:8px 0 4px}
.equipe-t{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px}.equipe-t a.sig{font-weight:700;color:var(--accent);text-decoration:none}
.equipe-t a.sig:hover{text-decoration:underline}.equipe-t .nom{font-size:13px}
.equipe .th{font-size:13px;color:var(--muted);font-style:italic;margin:3px 0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.equipe .pied{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center;font-size:12px;color:var(--muted)}
.badge{font-size:11px;border-radius:4px;padding:0 6px;background:var(--chip);color:var(--muted);white-space:nowrap}
.btn-fiche{font:inherit;font-size:12px;border:1px solid var(--accent);color:var(--accent);background:none;border-radius:6px;padding:0 8px;cursor:pointer;margin-left:auto}
.btn-fiche:hover{background:var(--accent-soft)}
.nav{display:flex;gap:14px;font-size:14px;margin:6px 0 0}.nav a{text-decoration:none}
/* annuaire : trois niveaux — ville (filet), labo (bandeau teinté), équipe (tuile en retrait) */
.labos{align-items:start}
.labo{padding:0;overflow:hidden;border-radius:10px}
.labo-t{display:block;margin:0;padding:10px 14px 9px;background:var(--labo-bg);border-bottom:1px solid var(--line)}
.labo-id{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px}
.labo-t a,.labo-t b{font-size:17px;font-weight:750;color:var(--ink);letter-spacing:-.01em;text-decoration:none}
.labo-t a:hover{color:var(--accent);text-decoration:underline}
.labo-n{margin:2px 0 0;font-size:13px;line-height:1.35;color:var(--muted)}
.badge-umr{margin-left:auto;font-variant-numeric:tabular-nums;background:var(--panel);border:1px solid var(--line)}
.equipes{list-style:none;margin:0;padding:8px;display:grid;gap:6px}
.equipe{border:0;background:var(--team-bg);border-radius:7px;padding:8px 10px}
.equipe-t{flex-wrap:nowrap;align-items:center;gap:8px}
.equipe-t .sig{font-size:15px;font-weight:700;color:var(--accent)}
.lien-sig{font:inherit;background:none;border:0;padding:0;cursor:pointer}.lien-sig:hover{text-decoration:underline}
.site{font-size:13px;text-decoration:none;color:var(--muted)}.site:hover{color:var(--accent)}
.equipe .nom{font-size:13.5px;font-weight:500;line-height:1.35;margin:1px 0 0}
.equipe .th{margin:4px 0}
.btn-fiche{margin-left:auto;flex:none;background:var(--panel);padding:1px 9px}
.badge-inria{background:none;border:1px solid var(--line)}
.labo-vide{margin:0;padding:8px 14px 10px;font-size:12px;color:var(--muted)}
.equipe .syn{font-size:13px;line-height:1.4;margin:4px 0 2px}
.eq-themes{display:flex;flex-wrap:wrap;gap:3px;margin:5px 0 4px}
.tag-btn{font:inherit;font-size:11.5px;line-height:1.4;background:var(--accent-soft);color:var(--accent);border:0;border-radius:4px;padding:1px 6px;cursor:pointer;text-align:left}
.tag-btn:hover{background:var(--accent);color:var(--panel)}
/* ville à gauche ; à droite, un labo par ligne : identité du labo, puis ses équipes en tuiles */
.ville{display:grid;grid-template-columns:150px 1fr;gap:12px;margin:0;padding:14px 0;border-top:1px solid var(--line);scroll-margin-top:12px}
.ville:first-child{border-top:0}
.ville h3{margin:10px 0 0;display:block;position:sticky;top:12px;align-self:start}.ville h3::after{display:none}
.labos{grid-template-columns:1fr;gap:10px}
.labo{display:grid;grid-template-columns:220px 1fr}
.labo-t{border-bottom:0;border-right:1px solid var(--line)}
.equipes{grid-template-columns:repeat(auto-fill,minmax(270px,1fr));align-content:start}
@media (max-width:760px){.ville{grid-template-columns:1fr;gap:6px}.ville h3{position:static;margin:0}
 .labo{grid-template-columns:1fr}.labo-t{border-right:0;border-bottom:1px solid var(--line)}}
/* tableaux : coin figé, survol, mobile */
.matrice thead th:first-child{left:0;z-index:4}
.matrice td[data-cell]:hover{outline:2px solid var(--ink);outline-offset:-2px}
.matrice thead tr.taille i.part:not([style*="height:0px"]){margin-bottom:2px}
.matrice thead tr.grp th{font-size:10px;letter-spacing:0}
@media (max-width:600px){.matrice tbody th{max-width:42vw;font-size:11px;padding:2px 6px}.matrice tbody th .meta{display:none}
 .matrice thead tr.taille th:first-child{font-size:9px;white-space:normal}}
/* typographie */
h1{font-size:27px;letter-spacing:-.015em;text-wrap:balance}
main>section>h2{font-size:21px;margin:44px auto 4px;padding-top:22px;border-top:1px solid var(--line)}
main>section:first-child>h2{border-top:0;padding-top:0;margin-top:24px}
/* fiche */
dialog{max-height:min(88vh,920px)}
.close{position:sticky;top:0;z-index:2;background:var(--panel);width:36px;height:36px;border-radius:0 0 0 8px}
.dlg h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:22px 0 6px;padding-top:12px;border-top:1px solid var(--line)}
.dlg-labo{font-size:14px;font-weight:500;color:var(--muted);margin-left:8px}
/* tons modernes : neutres froids, tuiles blanches bordées */
.equipe{background:var(--panel);border:1px solid var(--line)}
.banner{border:1px solid color-mix(in srgb,var(--warn) 25%,transparent)}
header .banner{background:color-mix(in srgb,var(--brand) 12%,transparent);color:var(--hdr-muted);border-color:color-mix(in srgb,var(--brand) 35%,transparent)}
.chip{border-color:transparent}.chip:hover{border-color:var(--line)}
@media (max-width:600px){h1{font-size:20px}}
/* tuile équipe : sigle et synthèse d'abord, le reste en retrait */
.equipes{grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:8px}
.equipe{display:flex;flex-direction:column;padding:10px 12px 8px;transition:border-color .15s}
.equipe:hover{border-color:color-mix(in srgb,var(--accent) 40%,var(--line))}
.equipe-t{display:flex;align-items:baseline;gap:6px}
.equipe-t .sig{font-size:18px;font-weight:750;letter-spacing:-.01em;color:var(--ink)}
.equipe-t .sig:hover{color:var(--accent)}
.equipe-t .badge-inria{font-size:10.5px;padding:0 5px;align-self:center}
.eq-nb{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.eq-nb b{font-size:15px;font-weight:650;color:var(--ink)}.eq-nb small{font-size:11px;margin-left:1px}
.equipe .nom{font-size:12px;font-weight:400;line-height:1.3;color:var(--muted);margin:0 0 6px;
 display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.equipe .syn{font-size:14px;line-height:1.45;color:var(--ink);font-style:normal;margin:0 0 8px;
 display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.eq-themes{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 8px}
.tag-btn,.tag-plus{font:inherit;font-size:11.5px;line-height:1.6;border-radius:999px;padding:0 8px;cursor:pointer;
 max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tag-btn{background:var(--chip);color:var(--ink);border:1px solid transparent}
.tag-btn:hover{background:var(--accent-soft);color:var(--accent);border-color:color-mix(in srgb,var(--accent) 30%,transparent)}
.tag-plus{background:none;border:1px dashed var(--line);color:var(--muted)}
.tag-plus:hover{color:var(--accent);border-color:var(--accent)}
.equipe .pied{margin-top:auto;padding-top:6px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;align-items:center;gap:2px 8px;font-size:12px;color:var(--muted)}
.pied .actions{margin-left:auto;display:flex;gap:12px;align-items:center}
.dlg-liens{display:flex;flex-wrap:wrap;gap:8px}.dlg-liens .btn{text-decoration:none}.btn-carte{border-color:var(--accent);color:var(--accent)}
.pied .site{font-size:12px;color:var(--muted);text-decoration:none}.pied .site:hover{color:var(--accent);text-decoration:underline}
.btn-fiche{font:inherit;font-size:12px;font-weight:600;border:0;background:none;padding:0;margin:0;color:var(--accent);cursor:pointer}
.btn-fiche:hover{background:none;text-decoration:underline}
@media (max-width:760px){.equipe .syn{-webkit-line-clamp:4}.equipe .nom{-webkit-line-clamp:3}}
/* carte des domaines */
.carte-w{display:grid;grid-template-columns:minmax(0,1fr);gap:12px 28px;max-width:1240px;margin:6px auto 0}
@media (min-width:1100px){.carte-w{grid-template-columns:minmax(0,1fr) 260px;align-items:start}}
.carte-defil{position:relative;overflow-x:auto;overscroll-behavior-x:contain}
#carte svg{display:block;width:100%;min-width:600px;height:auto;font-family:inherit;touch-action:pan-x pan-y}
.c-cercle{fill:none;stroke:color-mix(in srgb,var(--ink) 16%,transparent)}
.c-centre{fill:color-mix(in srgb,var(--accent) 4%,transparent)}
.c-rayon{stroke:color-mix(in srgb,var(--ink) 8%,transparent)}
.c-dom{cursor:pointer;outline:none}
.c-dom .c-hit{fill:transparent}
.c-dom circle{fill:var(--accent);stroke:var(--bg);stroke-width:2.5}
.c-dom text{font-size:15px;font-weight:700;fill:var(--ink);letter-spacing:-.01em}
.c-dom:hover text,.c-dom.actif text{fill:var(--accent)}
.c-dom:focus-visible .c-hit{stroke:var(--accent);stroke-width:2}
.c-dom.pale{opacity:.3}
.c-eq{cursor:pointer;outline:none;transition:opacity .15s}
.c-eq rect{fill:var(--panel);stroke:color-mix(in srgb,var(--ink) 24%,transparent);stroke-width:1}
.c-eq text{font-weight:650;fill:var(--ink)}
.c-eq.t0 text{font-weight:600}
.c-eq:hover rect,.c-eq.actif rect{stroke:var(--accent);stroke-width:2}
.c-eq.actif rect{fill:var(--accent-soft)}
.c-eq:focus-visible rect{stroke:var(--ink);stroke-width:2.5}
.c-eq.pale{opacity:.15}
#c-liens line{stroke:var(--accent);stroke-opacity:.5;stroke-linecap:round}
/* panneau : légende au repos, détail au survol */
.c-panneau{border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:12px 14px;font-size:13px;line-height:1.45;min-height:230px}
@media (min-width:1100px){.c-panneau{position:sticky;top:12px}}
.c-panneau h3{font-size:15px;margin:0 0 2px;letter-spacing:-.01em}
.c-panneau .sous,.c-panneau .c-aide{color:var(--muted);margin:0 0 8px}
.c-panneau ul{list-style:none;margin:8px 0;padding:0}
.c-panneau li{display:grid;grid-template-columns:minmax(0,1fr) 56px 34px;align-items:center;gap:6px;margin:3px 0}
.c-panneau li i{display:block;height:6px;border-radius:0 3px 3px 0;background:var(--accent)}
.c-panneau li b{font-weight:650;text-align:right;font-variant-numeric:tabular-nums}
.c-panneau .c-fiche{font:inherit;font-weight:600;border:0;background:none;padding:0;color:var(--accent);cursor:pointer}
.c-leg{display:grid;gap:12px}
.c-leg h4{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 4px;font-weight:600}
.c-tailles{display:grid;gap:4px;color:var(--muted);font-size:12px}
.c-pill{display:inline-block;border:1px solid color-mix(in srgb,var(--ink) 24%,transparent);border-radius:999px;padding:0 .6em;font-weight:650;color:var(--ink);background:var(--panel);line-height:1.5}
.c-schema{display:block;width:100%;height:auto}
.c-schema .s-c{fill:color-mix(in srgb,var(--accent) 4%,transparent);stroke:color-mix(in srgb,var(--ink) 16%,transparent)}
.c-schema .s-d{fill:var(--accent)}.c-schema text{font-size:11px;fill:var(--muted)}
.c-schema rect{fill:var(--panel);stroke:color-mix(in srgb,var(--ink) 24%,transparent)}
.c-schema .s-l{stroke:var(--accent);stroke-opacity:.5}
/* version texte */
.c-liste{max-width:1240px;margin:10px auto 0}
.c-liste dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;font-size:13px;margin:8px 0}
.c-liste dt{font-weight:650}.c-liste dd{margin:0;color:var(--muted)}
@media (max-width:700px){#carte-reg{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px}#carte-reg .chip{flex:none}
 .c-panneau{min-height:0}.c-liste dl{grid-template-columns:1fr}.c-liste dd{margin-bottom:6px}}
/* recherche par mot-clé */
.ann-champ{position:relative;width:min(420px,100%)}.ann-outils .ann-champ input{width:100%;padding:8px 12px;font-size:15px}
.ann-sugg{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 4px);margin:0;padding:4px;list-style:none;background:var(--panel);
 border:1px solid var(--line);border-radius:10px;box-shadow:0 10px 30px rgb(0 0 0 / .14);max-height:380px;overflow:auto}
.ann-sugg .sugg-type,.ann-sugg .sugg-titre{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);padding:8px 8px 2px}
.ann-sugg [role=option]{display:flex;align-items:baseline;gap:8px;padding:6px 8px;border-radius:6px;cursor:pointer;font-size:14px}
.ann-sugg [role=option] small{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}
.ann-sugg [role=option]:hover,.ann-sugg [aria-selected=true]{background:var(--accent-soft)}
.ann-filtres{display:flex;flex-wrap:wrap;gap:6px;width:100%}.ann-filtres:empty{display:none}
.filtre{display:inline-flex;align-items:center;gap:6px;background:var(--accent-soft);color:var(--ink);border-radius:999px;padding:3px 4px 3px 11px;font-size:13px}
.filtre small{color:var(--accent);font-weight:600}
.filtre button{font:inherit;border:0;background:none;cursor:pointer;color:var(--muted);width:22px;height:22px;border-radius:50%;line-height:1}
.filtre button:hover{background:var(--panel);color:var(--ink)}
.filtre-tout{font:inherit;font-size:12px;border:0;background:none;color:var(--muted);cursor:pointer;text-decoration:underline}
.equipe .raison{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 8px;font-size:12px}
.equipe .raison span{background:var(--accent-soft);color:var(--accent);border-radius:4px;padding:1px 6px;font-weight:600}
.pied a.corr,.labo-vide a.corr{color:inherit;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:2px}.pied a.corr:hover,.labo-vide a.corr:hover{color:var(--accent);text-decoration-color:currentColor}
.theses{list-style:none;margin:4px 0;padding:0}.theses li{margin:4px 0;line-height:1.4}.theses li>.meta:first-child{display:inline-block;width:38px;font-variant-numeric:tabular-nums}.theses-plus summary{cursor:pointer;margin:4px 0}
</style>
</head>
<body>
<header>
 <nav class="sites" aria-label="Pages de l'AFIG"><a class="afig" href="https://www.asso-afig.fr/" target="_blank" rel="noopener">AFIG</a><a href="https://afig-asso.github.io/research-team/" aria-current="page">Équipes de recherche</a><a href="https://afig-asso.github.io/entreprises/">Entreprises</a><a href="https://afig-asso.github.io/cartographie/">Carte de France</a><a class="gh" href="https://github.com/Afig-Asso/research-team">GitHub</a></nav>
 <h1>Qui fait quoi en <b>informatique graphique</b> ?</h1>
 <p class="sub">Équipes de recherche françaises en informatique graphique : thèmes de recherche et secteurs d'application.</p>
 <nav class="nav"><a href="#annuaire">Équipes</a><a href="#carte-s">Carte</a><a href="#themes">Thèmes</a><a href="#secteurs">Secteurs d'application</a></nav>
</header>
<main>
 <section class="annuaire" id="annuaire">
  <h2>Équipes de recherche</h2>
  <p class="meta" id="ann-resume"></p>
  <div class="ann-outils"><div class="ann-champ"><input type="search" id="ann-q" placeholder="Mot-clé : jeu vidéo, santé, Gaussian splatting, Lyon…" aria-label="Rechercher une équipe par mot-clé" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="ann-sugg" autocomplete="off"><ul class="ann-sugg" id="ann-sugg" role="listbox" aria-label="Suggestions" hidden></ul></div><div class="ann-filtres" id="ann-filtres"></div><div class="ann-villes" id="ann-villes"></div></div>
  <div id="ann-liste"><p class="meta">Chargement…</p></div>
  <p class="meta">Compléter ou modifier : <a href="mailto:contact@asso-afig.fr">contact@asso-afig.fr</a> ou une demande de fusion sur le <a href="https://github.com/Afig-Asso/research-team" target="_blank" rel="noopener">dépôt GitHub</a>.</p>
 </section>
  <section id="carte-s">
  <h2>Carte des domaines</h2>
  <p class="meta">Chaque équipe est attirée par les domaines où elle publie : près d'un domaine quand elle s'y concentre, vers le centre quand elle en couvre plusieurs. Les domaines voisins sur le cercle sont ceux que les mêmes équipes partagent.</p>
  <div class="chips" id="carte-reg" role="group" aria-label="Filtrer la carte par région"></div>
  <div class="carte-w"><div class="carte-defil" id="carte"></div><aside class="c-panneau" id="c-panneau"></aside></div>
  <details class="c-liste"><summary class="meta">Version texte : équipes consacrant au moins 15 % de leurs publications à chaque domaine</summary><div id="carte-liste"></div></details>
 </section>
 <section id="themes">
  <h2>Thèmes × équipes</h2>
  <details class="legende-groupes"><summary class="meta">Colonnes par région : composition des groupes</summary><div id="legende-groupes"></div></details>
  <p class="meta">Intensité : part des publications de l'équipe sur le thème. Sous les noms : permanents et publications. Clic : thème → filtre, équipe → fiche, case → publications.</p>
  <div class="chips" id="filtre-dom"></div>
  <div class="outils"><div class="legend">abordé <i></i> central</div><div class="selection" id="sel-theme"></div></div>
  <div class="matrice" id="matrice"></div>
 </section>
 <section id="secteurs">
  <h2>Secteurs d'application × équipes</h2>
  <div class="chips" id="filtre-dom-app"></div>
  <div class="outils"><div class="legend">abordé <i></i> central</div><div class="selection" id="sel-app"></div></div>
  <div class="matrice" id="matrice-app"></div>
 </section>
</main>
<dialog id="dlg"><div class="dlg" id="dlg-c"></div></dialog>
<footer>AFIG — Association Française d'Informatique Graphique. Données : annuaire des équipes, HAL, OpenAlex. Fiches générées automatiquement.
 Voir aussi : <a href="https://afig-asso.github.io/entreprises/">entreprises en informatique graphique</a> · <a href="https://afig-asso.github.io/cartographie/">carte de France des équipes et des entreprises</a> · dépôts GitHub <a href="https://github.com/Afig-Asso/research-team">research-team</a>, <a href="https://github.com/Afig-Asso/entreprises">entreprises</a>, <a href="https://github.com/Afig-Asso/cartographie">cartographie</a>.</footer>
<script>
const VOC=__VOC__, EQ=__EQ__;
const D=Object.fromEntries(VOC.domaines.map(x=>[x.id,x])), T=Object.fromEntries(VOC.themes.map(x=>[x.id,x])), A=Object.fromEntries(VOC.applications.map(x=>[x.id,x]));
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const doms=e=>[...e.domaines.principaux||[],...e.domaines.secondaires||[]];
const nomEq=e=>`${e.sigle} (${e.labo})`;  // nom de l'équipe suivi de son laboratoire
// ancre stable d'une équipe (liens croisés avec l'annuaire et la carte) : #LABO-SIGLE, caractères hors [A-Za-z0-9] -> « - »
const ancreEq=(l,s)=>(l+'-'+s).replace(/[^A-Za-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
const URL_CARTE='https://afig-asso.github.io/cartographie/';
const lienCarte=(l,s)=>`${URL_CARTE}?equipe=${encodeURIComponent(l+'/'+s).replace(/%2F/g,'/')}`;
const dlg=$('#dlg'); dlg.addEventListener('click',ev=>{if(ev.target===dlg)fermer()});
// la fiche ouverte est dans l'adresse (#LJK-MAVERICK) ; fermer la fiche retire l'ancre
const retirerAncre=()=>{const e=EQ.find(x=>x.id===dlg.dataset.eq);if(e&&'#'+ancreEq(e.labo,e.sigle)===location.hash)history.replaceState(null,'',location.pathname+location.search)};
const fermer=()=>{dlg.close();retirerAncre()};
dlg.addEventListener('close',retirerAncre);dlg.addEventListener('cancel',retirerAncre);
// équipe avec fiche : la fiche s'ouvre ; sans fiche (annuaire seul) : défilement jusqu'à sa tuile (rendue après le chargement)
const ficheDepuisAncre=()=>{const e=EQ.find(x=>'#'+ancreEq(x.labo,x.sigle)===location.hash);if(e){if(!(dlg.open&&dlg.dataset.eq===e.id))fiche(e.id);return}
 const n=location.hash.length>1&&document.getElementById(decodeURIComponent(location.hash.slice(1)));if(n)n.scrollIntoView()};
window.addEventListener('hashchange',ficheDepuisAncre);
// chaque section est rendue à part : une erreur dans l'une n'empêche pas les autres (ni l'ouverture de la fiche visée)
function section(sels,f){try{f()}catch(err){console.error(err);sels.forEach(sel=>{const c=document.querySelector(sel);if(c)c.innerHTML='<p class="banner">Erreur d’affichage de cette section. Les autres parties de la page restent utilisables.</p>'})}}
function bind(root){root.querySelectorAll('[data-eq]').forEach(n=>n.onclick=()=>fiche(n.dataset.eq));
 root.querySelectorAll('[data-site]').forEach(n=>n.onclick=()=>{const e=EQ.find(x=>x.id===n.dataset.site);const u=e.url||e.labo_url;if(u)window.open(u,'_blank','noopener');else fiche(e.id)});
 root.querySelectorAll('[data-cell]').forEach(n=>n.onclick=()=>{const [id,c,k]=n.dataset.cell.split('|');cellule(id,c,k)})}
// publications qui contribuent au score d'une case (équipe × thème ou secteur)
function cellule(id,c,k){const e=EQ.find(x=>x.id===id),x=e[c][k],V=c==='st'?T:A;
 const ph=c==='st'?e.themes.find(t=>t.id===k)?.phrase:'';const mx=Math.max(...x.c.map(r=>r[1]),1e-9);
 $('#dlg-c').innerHTML=`<button class="close" aria-label="Fermer" onclick="fermer()">×</button>
 <h2 style="margin-top:0">${esc(V[k].fr)}</h2>
 <p><b>${esc(nomEq(e))}</b> — ${esc(e.nom)} ${x.f?' · retenu dans la fiche':''}</p><p>${mesureTxt(x)}</p>
 ${ph?`<p>${esc(ph)}</p>`:''}
 <p class="meta">${x.e} publication(s) avec le thème dans le titre (comptent 1), ${x.i} avec une mention dans le résumé seulement (comptent 0,1 à 0,8 selon les mots-clés).
  Publications de membres « IG en partie » ×0,5 ; 2021 et après ×1,2 ; avant 2016 ×0,8.</p>
 <p><button class="btn" onclick="fiche('${e.id}')">Fiche de l'équipe</button> ${e.url?`<a class="btn" style="text-decoration:none" href="${esc(e.url)}" target="_blank" rel="noopener">Site de l'équipe ↗</a>`:''}</p>
 <h3>Publications (${x.c.length})</h3>
 ${x.c.map(([pid,w,ex,kw])=>{const p=e.exemples[pid];if(!p)return '';return `<div class="contrib"><span class="src ${ex?'src-titre':'src-resume'}" title="contribution ${w}">${ex?'titre':'résumé'}</span>
  <div>${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titre)}</a>`:esc(p.titre)} <span class="meta">— ${esc(p.lieu)}, ${p.annee}${p.partiel?' · membre IG en partie':''}</span>
  <div class="kw"><span class="piste" style="width:40px"><i style="width:${Math.round(100*w/mx)}%"></i></span>mots-clés : <b>${esc(kw)}</b></div></div></div>`}).join('')}`;
 dlg.dataset.eq="";dlg.showModal();dlg.scrollTop=0}
function liste(e,sc,V){const c=sc===e.st?'st':'sa';return Object.entries(sc).filter(([k])=>V[k]).sort((a,b)=>b[1].p-a[1].p).map(([k,x])=>{const ex=x.ex.map(i=>e.exemples[i]).filter(Boolean).map(p=>`• ${p.titre} (${p.annee})`).join('\n');
 return `<div title="${esc(detail(x))}${ex?'\n'+esc(ex):''}"><span class="piste"><i style="width:${Math.round(100*intensite(x,c))}%"></i></span>${esc(V[k].fr)}</div>`}).join('')}
const LIB_IG={oui:'IG',partiel:'IG en partie',non:'hors IG',inconnu:'IG ?'};
function tableMembres(e){const m=e.membres;if(!m.liste.length)return '<p class="meta">Liste non disponible.</p>';
 return `<table class="membres">${m.liste.map(p=>`<tr><td>${p.site?`<a href="${esc(p.site)}" target="_blank" rel="noopener">${esc(p.nom)}</a>`:esc(p.nom)}${p.nom===e.correspondant?' <span class="meta">(correspondant)</span>':''}</td>
  <td class="meta">${esc([p.emerite?'émérite':p.statut,p.employeur].filter(Boolean).join(', '))}</td>
  ${p.ig?`<td><span class="ig ig-${p.ig}">${LIB_IG[p.ig]||p.ig}</span></td>`:''}<td class="meta">${esc(p.domaines)}</td></tr>`).join('')}</table>
 ${m.liste.some(p=>p.ig)?`<p class="meta">« IG » : annotation automatique d'après les publications, à vérifier.</p>`:`<p class="meta">${m.source?`Source : <a href="${esc(m.source)}" target="_blank" rel="noopener">page de l'équipe</a>. `:''}Mots-clés de recherche établis automatiquement d'après les publications, à vérifier.</p>`}`}
function listeTheses(l){const li=t=>`<li><span class="meta">${t.annee}</span> <a href="https://theses.fr/${encodeURIComponent(t.id)}" target="_blank" rel="noopener"${t.titre_en&&t.titre_en!==t.titre?` title="${esc(t.titre_en)}"`:''}>${esc(t.titre)}</a> <span class="meta">— ${esc(t.etablissement)}</span></li>`;
 if(!l.length)return '<p class="meta">Aucune thèse en IG trouvée sur la période.</p>';
 return `<ul class="theses">${l.slice(0,6).map(li).join('')}</ul>${l.length>6?`<details class="theses-plus"><summary class="meta">${l.length-6} autres thèses</summary><ul class="theses">${l.slice(6).map(li).join('')}</ul></details>`:''}`}
function fiche(id){const e=EQ.find(x=>x.id===id); const s=e.stats; const ys=Object.entries(s.par_annee||{}); const mx=Math.max(1,...ys.map(y=>y[1]));
 $('#dlg-c').innerHTML=`<button class="close" aria-label="Fermer" onclick="fermer()">×</button>
 <h2 style="margin-top:0">${esc(e.sigle)}<span class="dlg-labo">${esc(e.labo)} · ${esc(e.ville)}</span></h2>
 <p style="margin:0 0 4px;font-weight:500">${esc(e.nom)}</p>
 <p class="meta">${esc(e.labo_nom)}${e.inria?' · équipe commune Inria':''}</p>
 <p class="dlg-liens">${e.url?`<a class="btn" href="${esc(e.url)}" target="_blank" rel="noopener">Site de l'équipe ↗</a>`:''}<a class="btn btn-carte" href="${esc(lienCarte(e.labo,e.sigle))}" title="L'équipe et les entreprises proches sur la carte de France">Voir sur la carte de France ↗</a></p>
 ${e.correspondant?`<p>Correspondant AFIG : ${corr(e.correspondant,e.correspondant_site)}</p>`:''}
 <p><b>Synthèse :</b> ${esc(e.synthese||e.pour_etudiants)}</p><p><b>Expertise :</b> ${esc(e.pour_entreprises)}</p>
 <div>${doms(e).map((d,i)=>`<span class="tag" style="${i<(e.domaines.principaux||[]).length?'font-weight:700':''}">${esc(D[d].fr)}</span>`).join('')}</div>
 <h3>Thèmes principaux</h3>${e.themes.map(t=>`<div class="theme"><b>${esc(T[t.id].fr)}</b> — ${esc(t.phrase)}</div>`).join('')}
 <h3>Tous les thèmes abordés</h3><div class="autres">${liste(e,e.st,T)}</div>
 <h3>Secteurs d'application</h3><div class="autres">${liste(e,e.sa,A)}</div>
 <h3>Publications représentatives</h3>${e.representatives.map(p=>`<div class="pub">${p.url?`<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.titre)}</a>`:esc(p.titre)} <span class="meta">— ${esc(p.lieu)}, ${p.annee}</span></div>`).join('')}
 ${e.theses?`<h3>Thèses en IG soutenues ${e.theses.debut}-${e.theses.fin} (${e.theses.soutenues.length})</h3><p class="meta">Thèses dirigées par les permanents IG de l'équipe, d'après theses.fr, retenues en IG d'après leur titre et leurs mots-clés${e.theses.hors_ig?` (${e.theses.hors_ig} autre${e.theses.hors_ig>1?'s':''} hors IG non affichée${e.theses.hors_ig>1?'s':''})`:''}${e.theses.en_preparation?` ; ${e.theses.en_preparation} en préparation`:''}.</p>${listeTheses(e.theses.soutenues)}`:''}
 ${e.membres?`<h3>Permanents (${e.membres.liste.length})</h3>${tableMembres(e)}`:''}
 <h3>Activité __DEBUT__-__FIN__</h3><p class="meta">${s.permanents_ig??'?'} permanents en IG${s.permanents_partiel?` (+ ${s.permanents_partiel} en partie)`:''} · ${s.publications??'?'} publications · lieux principaux : ${esc((s.lieux||[]).join(', '))}</p>
 <div class="spark" title="publications par an">${ys.map(([y,n])=>`<i style="height:${Math.max(2,26*n/mx)}px" title="${y} : ${n}"></i>`).join('')}</div>`;
 dlg.dataset.eq=e.id;const a='#'+ancreEq(e.labo,e.sigle);if(location.hash!==a)history.replaceState(null,'',a);
 if(!dlg.open)dlg.showModal();dlg.scrollTop=0}
// regroupement des colonnes : domaine principal, région, ou proximité thématique (calculée dans le générateur)
const REG_COURT={'Île-de-France':'IDF','Auvergne-Rhône-Alpes':'ARA','Bretagne':'BRE','Hauts-de-France':'HDF','Grand Est':'GE',
 'Occitanie':'OCC','Bourgogne-Franche-Comté':'BFC',"Provence-Alpes-Côte d'Azur":'PACA','Nouvelle-Aquitaine':'NA'};
const DOM_COURT={rendu:'Rendu',modelisation:'Mod',geometrie:'Géo',animation:'Anim',humains:'Hum',capture:'Capt',rv:'RV',
 visu:'Visu',fabrication:'Fab',images:'Img',ia:'IA'};
let MODE='region';
const MODES={
 domaine:{cle:e=>e.domaines.principaux[0], rang:e=>VOC.domaines.findIndex(d=>d.id===e.domaines.principaux[0]), court:k=>DOM_COURT[k]||k, long:k=>D[k].fr, interne:(a,b)=>a.sigle.localeCompare(b.sigle)},
 region:{cle:e=>e.region, rang:e=>e.region, court:k=>REG_COURT[k]||k, long:k=>k, interne:(a,b)=>a.ville.localeCompare(b.ville)||a.sigle.localeCompare(b.sigle)},
 thematique:{cle:e=>e.groupe_thematique, rang:e=>e.groupe_thematique, court:k=>'G'+(k+1), long:k=>VOC.groupes_thematiques[k], interne:(a,b)=>a.ordre_thematique-b.ordre_thematique}};
function ordonner(liste){const m=MODES[MODE];return [...liste].sort((a,b)=>{const ra=m.rang(a),rb=m.rang(b);return (ra<rb?-1:ra>rb?1:0)||m.interne(a,b)})}
function groupesCols(cols){const m=MODES[MODE],g=[];cols.forEach(e=>{const k=m.cle(e);if(!g.length||g[g.length-1].k!==k)g.push({k,cols:[]});g[g.length-1].cols.push(e)});return g}
function legende(){const m=MODES[MODE];const g=groupesCols(ordonner(EQ));
 $('#legende-groupes').innerHTML=g.map(x=>`<span><b>${esc(m.court(x.k))}</b> ${MODE==='region'?'':esc(m.long(x.k))+' — '}${esc(x.cols.map(nomEq).join(', '))}</span>`).join('')}
const ordreEq=EQ;
// intensité d'une case = profil de l'équipe : part pondérée des publications de l'équipe qui touchent le thème,
// échelle commune à toutes les équipes (référence : 95e centile des cases), racine pour étaler les teintes
function reference(c){const p=EQ.flatMap(e=>Object.values(e[c]).map(x=>x.p)).sort((a,b)=>a-b);return p[Math.floor(.95*(p.length-1))]||1}
const REF={st:reference('st'),sa:reference('sa')};
function intensite(x,c){if(!x)return 0;return Math.max(.04,Math.min(1,Math.sqrt(x.p/REF[c])))}
const scoreT=(e,t)=>intensite(e.st[t],'st'), scoreA=(e,a)=>intensite(e.sa[a],'sa');
const mesureTxt=x=>`${Math.round(100*x.p)} % des publications de l'équipe`;
const couleur=v=>`color-mix(in srgb,var(--heat4) ${Math.round(8+92*v)}%,var(--heat0))`;
const detail=(x,ph)=>`${mesureTxt(x)} (${x.e} avec le thème dans le titre, ${x.i} dans le résumé seulement)${ph?' — '+ph:''}`;
// tableau générique : groupes = [[titre, [ids de lignes]]], libellé(id), score(e,id), info(e,id)
const PUBMAX=Math.max(1,...EQ.map(e=>e.stats.publications||0)), PERMMAX=Math.max(1,...EQ.map(e=>(e.stats.permanents_ig||0)+(e.stats.permanents_partiel||0)));
function tableau(cible, selEl, etat, groupes, libelle, score, info){
 const cols=ordonner(ordreEq.filter(e=>(!etat.ligne||score(e,etat.ligne))&&groupes.some(([,ids])=>ids.some(id=>score(e,id)))));
 const m=MODES[MODE], gc=groupesCols(cols), debut=new Set(gc.map(g=>g.cols[0].id));
 const sep=e=>debut.has(e.id)?' sep':'';
 let h=`<table><thead><tr class="grp"><th></th>${gc.map(g=>`<th colspan="${g.cols.length}" title="${esc(m.long(g.k))}">${esc(m.court(g.k))}</th>`).join('')}</tr>
  <tr class="noms"><th></th>${cols.map(e=>`<th class="${sep(e)}"><span data-eq="${e.id}" title="${esc(e.nom)} — ${esc(e.labo)}, ${esc(e.ville)} (clic : fiche de l'équipe)">${esc(nomEq(e))}</span></th>`).join('')}</tr>
  <tr class="taille t-perm"><th title="Permanents de l'équipe : foncé = IG, clair = IG en partie (même échelle pour toutes les équipes)">permanents IG <span style="color:var(--heat4)">■</span> + en partie <span style="color:var(--heat1)">■</span></th>${cols.map(e=>{const s=e.stats,ig=s.permanents_ig||0,pa=s.permanents_partiel||0;return `<th class="${sep(e)}" title="${esc(nomEq(e))} : ${ig} permanents IG${pa?' + '+pa+' en partie':''}"><i class="part" style="height:${Math.round(32*pa/PERMMAX)}px"></i><i class="ig" style="height:${Math.round(32*ig/PERMMAX)}px;border-radius:0"></i><b>${ig+pa}</b></th>`}).join('')}</tr>
  <tr class="taille t-pub"><th title="Nombre de publications distinctes __DEBUT__-__FIN__ (même échelle pour toutes les équipes)">publications __DEBUT__-__FIN__</th>${cols.map(e=>{const n=e.stats.publications||0;return `<th class="${sep(e)}" title="${esc(nomEq(e))} : ${n} publications"><b>${n}</b></th>`}).join('')}</tr></thead><tbody>`;
 groupes.forEach(([titre,ids])=>{const lignes=ids.filter(id=>cols.some(e=>score(e,id)));if(!lignes.length)return;
  h+=`<tr class="dom-row"><th colspan="${cols.length+1}">${esc(titre)}</th></tr>`;
  lignes.forEach(id=>{const n=cols.filter(e=>score(e,id)).length;const lib=libelle(id);
   h+=`<tr><th class="${etat.ligne===id?'actif':''}" title="${esc(lib.en)}"><span class="lien" data-ligne="${id}">${esc(lib.fr)}</span> <span class="meta">(${n})</span></th>${cols.map(e=>{const s=score(e,id);return `<td class="${s?'h'+Math.max(1,Math.ceil(4*s)):'h0'}${sep(e)}" ${s?`style="background:${couleur(s)}" data-cell="${e.id}|${etat.couche}|${id}" title="${esc(nomEq(e))} — ${esc(info(e,id))}"`:''}></td>`}).join('')}</tr>`})});
 cible.innerHTML=h+'</tbody></table>';bind(cible);
 // en-têtes figés : chaque ligne d'en-tête se colle exactement sous la précédente (hauteurs mesurées, pas de trou)
 figer(cible);
 cible.querySelectorAll('[data-ligne]').forEach(n=>n.onclick=()=>{etat.ligne=etat.ligne===n.dataset.ligne?null:n.dataset.ligne;etat.rendre()});
 selEl.innerHTML=etat.ligne?`${cols.length} équipe(s) pour « ${esc(libelle(etat.ligne).fr)} »<button>tout afficher</button>`:`${cols.length} équipes`;
 selEl.querySelector('button')?.addEventListener('click',()=>{etat.ligne=null;etat.rendre()})}
function figer(cible){let y=0;cible.querySelectorAll('thead tr').forEach(r=>{[...r.cells].forEach(c=>c.style.top=y+'px');y+=r.getBoundingClientRect().height})}
addEventListener('resize',()=>document.querySelectorAll('.matrice').forEach(figer));
function filtresDomaines(el,etat){el.innerHTML=VOC.domaines.map(d=>`<button class="chip" data-d="${d.id}" aria-pressed="false" title="${esc(d.description)}">${esc(d.fr)}</button>`).join('');
 el.querySelectorAll('[data-d]').forEach(b=>b.onclick=()=>{etat.dom=etat.dom===b.dataset.d?null:b.dataset.d;el.querySelectorAll('[data-d]').forEach(x=>x.setAttribute('aria-pressed',x.dataset.d===etat.dom));etat.rendre()})}
// thèmes, groupés par domaine
const etatT={dom:null,ligne:null,couche:'st'};
const groupesT=VOC.domaines.map(d=>[d.fr,VOC.themes.filter(t=>t.domaines[0]===d.id).map(t=>t.id)]);
etatT.rendre=()=>{const g=etatT.dom?groupesT.filter(([fr])=>fr===D[etatT.dom].fr):groupesT;
 tableau($('#matrice'),$('#sel-theme'),etatT,g,id=>T[id],scoreT,(e,id)=>detail(e.st[id],e.themes.find(x=>x.id===id)?.phrase))};
filtresDomaines($('#filtre-dom'),etatT);
// secteurs, groupés par famille
const FAMILLES=[['Création et industries culturelles',['jeu_video','cinema_vfx','art_musique','mode_textile','patrimoine']],
 ['Industrie et conception',['industrie_cao','fabrication_additive','robotique']],
 ['Ville, territoire et environnement',['architecture_urbain','geographie','environnement','securite_foules']],
 ['Santé, sport et société',['sante','sport','education','accessibilite','biologie']],
 ['Données et décision',['sciences_donnees']]];
const rangees=new Set(FAMILLES.flatMap(f=>f[1])); const autres=VOC.applications.map(a=>a.id).filter(a=>!rangees.has(a)); if(autres.length)FAMILLES.push(['Autres',autres]);
const etatA={dom:null,ligne:null,couche:'sa'};
etatA.rendre=()=>tableau($('#matrice-app'),$('#sel-app'),etatA,FAMILLES.map(([f,ids])=>[f,ids.filter(id=>A[id])]),id=>A[id],scoreA,(e,id)=>detail(e.sa[id]));
filtresDomaines($('#filtre-dom-app'),etatA);
section(['#matrice','#matrice-app'],()=>{legende();etatT.rendre();etatA.rendre()});
// annuaire : villes -> laboratoires -> équipes, filtré par la recherche
const ANN=__ANN__;
const corr=(nom,url)=>url?`<a class="corr" href="${esc(url)}" target="_blank" rel="noopener" title="Page web de ${esc(nom)}">${esc(nom)}</a>`:esc(nom);
const sansAccent=s=>String(s??'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
const lien=(u,t,cls='')=>u?`<a class="${cls}" href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>`:`<b class="${cls}">${esc(t)}</b>`;
const ancre=v=>'v-'+sansAccent(String(v??'').split(',')[0]).replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');  // même règle que city_id() de cartographie/site/carte.js
const tuile=(e,v,l)=>{const f=EQ.find(x=>x.id===e.fiche),st=f?f.stats:{};
 const nIG=st.permanents_ig??'?',nP=st.permanents_partiel||0;
 const sig=e.fiche?`<button class="sig lien-sig" data-eq="${e.fiche}" title="Ouvrir la fiche">${esc(e.sigle)}</button>`:lien(e.url,e.sigle,'sig');
 return `<li class="equipe" id="${ancreEq(l.sigle,e.sigle)}">
  <div class="equipe-t">${sig}${e.inria?'<span class="badge badge-inria" title="Équipe commune Inria">Inria</span>':''}${f?`<span class="eq-nb" title="${nIG} permanents en IG${nP?`, +${nP} en partie`:''}"><b>${nIG}</b>${nP?`<small>+${nP}</small>`:''} perm.</span>`:''}</div>
  <div class="nom" title="${esc(e.nom)}">${esc(e.nom)}</div>
  ${f&&f.synthese?`<p class="syn">${esc(f.synthese)}</p>`:(e.themes?`<p class="syn" title="${esc(e.themes)}">${esc(e.themes)}</p>`:'')}${raison(e)}
  <div class="pied">${e.correspondant?`<span>Correspondant : ${corr(e.correspondant,e.correspondant_site)}</span>`:''}${e.ville&&e.ville.split(',')[0].trim()!==l.ville_aff?`<span class="badge">${esc(e.ville)}</span>`:''}<span class="actions">${e.url&&e.fiche?`<a class="site" href="${esc(e.url)}" target="_blank" rel="noopener">Site ↗</a>`:''}<a class="site" href="${esc(lienCarte(l.sigle,e.sigle))}" title="Voir l'équipe et les entreprises proches sur la carte de France">Carte ↗</a>${e.fiche?`<button class="btn-fiche" data-eq="${e.fiche}">Fiche →</button>`:''}</span></div>
 </li>`};
// recherche par mot-clé : complétion sur les secteurs (entreprises), domaines (étudiants), thèmes (chercheurs),
// équipes, laboratoires et villes ; une suggestion choisie devient un filtre (plusieurs filtres : toutes les conditions)
const FILTRES=[];
const pct=x=>`${Math.max(1,Math.round(100*x))} %`;
let SUGG=null;
function suggestions(){if(SUGG)return SUGG;const L=[];
 const part=(f,seuil)=>EQ.map(e=>[e.id,f(e)]).filter(([,p])=>p!==null&&p>=seuil);
 VOC.applications.forEach(a=>L.push({type:'Secteur',fr:a.fr,en:a.en,
  eqs:new Map(EQ.filter(e=>(e.applications.includes(a.id)&&intensite(e.sa[a.id],'sa')>=.3)||intensite(e.sa[a.id],'sa')>=.6).map(e=>[e.id,e.sa[a.id]?.p||0]))}));
 VOC.domaines.forEach(d=>L.push({type:'Domaine',fr:d.fr,en:d.en,aide:d.description,
  eqs:new Map(EQ.filter(e=>doms(e).includes(d.id)||CARTE.PT[e.id][d.id]>=.12).map(e=>[e.id,CARTE.PT[e.id][d.id]]))}));
 VOC.themes.forEach(t=>L.push({type:'Thème',fr:t.fr,en:t.en,
  eqs:new Map(EQ.filter(e=>(e.themes.some(x=>x.id===t.id)&&intensite(e.st[t.id],'st')>=.3)||intensite(e.st[t.id],'st')>=.6).map(e=>[e.id,e.st[t.id]?.p||0]))}));
 const tous=ANN.flatMap(v=>v.labos.flatMap(l=>l.equipes.map(e=>({e,l,v}))));
 tous.filter(x=>x.e.fiche).forEach(({e,l})=>L.push({type:'Équipe',fr:`${e.sigle} (${l.sigle})`,en:e.nom,fiche:e.fiche}));
 [...new Map(tous.map(x=>[x.l.sigle,x.l])).values()].forEach(l=>L.push({type:'Laboratoire',fr:l.sigle,en:l.nom,labo:l.sigle,
  n:tous.filter(x=>x.l.sigle===l.sigle).length}));
 [...new Set(tous.map(x=>x.e.ville||x.v.ville))].forEach(c=>L.push({type:'Ville',fr:c,ville:c,n:tous.filter(x=>(x.e.ville||x.v.ville)===c).length}));
 L.forEach(s=>{s.cle=s.type+':'+s.fr;s.txt=sansAccent(s.fr+' '+(s.en||''));s.n??=s.eqs?.size});
 return SUGG=L.filter(s=>s.n||s.fiche)}
const ORDRE_T=['Secteur','Domaine','Thème','Équipe','Laboratoire','Ville'];
function chercher(q){q=sansAccent(q.trim());const mots=q.split(/\s+/).filter(Boolean);if(!mots.length)return [];
 const res=suggestions().filter(s=>!FILTRES.some(f=>f.cle===s.cle)).map(s=>{const ws=s.txt.split(/[^a-z0-9]+/);
  if(!mots.every(m=>ws.some(w=>w.startsWith(m))||s.txt.includes(m)))return null;
  const r=s.txt.startsWith(q)?0:mots.every(m=>ws.some(w=>w.startsWith(m)))?1:2;return {s,r}}).filter(Boolean);
 res.sort((a,b)=>a.r-b.r||ORDRE_T.indexOf(a.s.type)-ORDRE_T.indexOf(b.s.type)||(b.s.n||0)-(a.s.n||0));
 const par={};return res.filter(({s})=>(par[s.type]=(par[s.type]||0)+1)<=4).slice(0,10).map(x=>x.s)}
function accueil(){const S=suggestions();
 return [...S.filter(s=>s.type==='Secteur').sort((a,b)=>b.n-a.n).slice(0,6),...S.filter(s=>s.type==='Domaine').sort((a,b)=>b.n-a.n).slice(0,4)]
  .filter(s=>!FILTRES.some(f=>f.cle===s.cle))}
function garde(e,l,v){return FILTRES.every(f=>f.eqs?f.eqs.has(e.fiche):f.labo?l.sigle===f.labo:f.ville?(e.ville||v.ville)===f.ville:true)}
function raison(e){const r=FILTRES.filter(f=>f.eqs&&f.eqs.has(e.fiche));if(!r.length)return '';
 return `<p class="raison">${r.map(f=>{const p=f.eqs.get(e.fiche);return `<span>${esc(f.fr)}${p?` : ${pct(p)}${f.type==='Domaine'?' de son activité':' des publications'}`:' : thème de la fiche'}</span>`}).join('')}</p>`}
function filtresRendre(){$('#ann-filtres').innerHTML=FILTRES.map((f,i)=>`<span class="filtre"><small>${esc(f.type)}</small> ${esc(f.fr)}<button data-retire="${i}" aria-label="Retirer le filtre ${esc(f.fr)}">×</button></span>`).join('')
  +(FILTRES.length>1?'<button class="filtre-tout" data-retire="tout">tout effacer</button>':'');
 $('#ann-filtres').querySelectorAll('[data-retire]').forEach(b=>b.onclick=()=>{b.dataset.retire==='tout'?FILTRES.splice(0):FILTRES.splice(+b.dataset.retire,1);filtresRendre();annuaireRendre();$('#ann-q').focus()})}
(()=>{const q=$('#ann-q'),lst=$('#ann-sugg');let items=[],act=-1;
 const fermer=()=>{lst.hidden=true;q.setAttribute('aria-expanded','false');q.removeAttribute('aria-activedescendant');act=-1};
 const ouvrir=()=>{items=q.value.trim()?chercher(q.value):accueil();act=-1;q.removeAttribute('aria-activedescendant');
  if(!items.length){fermer();return}
  let t='';lst.innerHTML=(q.value.trim()?'':'<li class="sugg-titre" role="presentation">Suggestions</li>')+items.map((s,i)=>{const h=s.type!==t?`<li class="sugg-type" role="presentation">${esc(s.type==='Secteur'?'Secteurs d\'application':s.type==='Domaine'?'Domaines':s.type==='Thème'?'Thèmes':s.type==='Équipe'?'Équipes':s.type==='Laboratoire'?'Laboratoires':'Villes')}</li>`:'';t=s.type;
   return h+`<li role="option" id="sg-${i}" data-i="${i}" title="${esc(s.aide||s.en||'')}"><span>${esc(s.fr)}</span>${s.fiche?'<small>fiche</small>':`<small>${s.n} équipe${s.n>1?'s':''}</small>`}</li>`}).join('');
  lst.hidden=false;q.setAttribute('aria-expanded','true');
  lst.querySelectorAll('[data-i]').forEach(li=>li.onmousedown=ev=>{ev.preventDefault();choisir(items[+li.dataset.i])})};
 const marquer=()=>{lst.querySelectorAll('[role=option]').forEach(li=>li.setAttribute('aria-selected',+li.dataset.i===act));
  if(act>=0){q.setAttribute('aria-activedescendant','sg-'+act);lst.querySelector('#sg-'+act).scrollIntoView({block:'nearest'})}};
 const choisir=s=>{fermer();if(s.fiche){fiche(s.fiche);return}FILTRES.push(s);q.value='';filtresRendre();annuaireRendre()};
 q.addEventListener('input',()=>{annuaireRendre();ouvrir()});q.addEventListener('focus',ouvrir);q.addEventListener('blur',()=>setTimeout(fermer,100));
 q.addEventListener('keydown',ev=>{if(ev.key==='ArrowDown'||ev.key==='ArrowUp'){if(lst.hidden)ouvrir();if(!items.length)return;ev.preventDefault();
   const n=items.length;act=(act+1+(ev.key==='ArrowDown'?1:-1)+n+1)%(n+1)-1;marquer()}
  else if(ev.key==='Enter'&&!lst.hidden&&act>=0){ev.preventDefault();choisir(items[act])}
  else if(ev.key==='Escape'){fermer()}
  else if(ev.key==='Backspace'&&!q.value&&FILTRES.length){FILTRES.pop();filtresRendre();annuaireRendre()}})})();
// texte cherché pour une équipe : annuaire, synthèse, thèmes et secteurs de la fiche (français et anglais)
const TXT_EQ=new Map();
function texteEq(e){if(!TXT_EQ.has(e)){const f=EQ.find(x=>x.id===e.fiche);
 TXT_EQ.set(e,sansAccent([e.sigle,e.nom,e.themes,e.correspondant,e.ville,f?.synthese,f?.pour_entreprises,...(f?f.themes.flatMap(x=>[T[x.id]?.fr,T[x.id]?.en]):[]),
  ...(f?f.applications.flatMap(a=>[A[a]?.fr,A[a]?.en]):[])].join(' ')))}return TXT_EQ.get(e)}
function annuaireRendre(){const q=sansAccent($('#ann-q').value.trim());let nE=0;const nL=new Set(),vis=[];
 const html=ANN.map(v=>{const labos=v.labos.map(l=>{const txtL=sansAccent([v.ville,l.sigle,l.nom,l.ville,...l.equipes.map(e=>e.ville)].join(' '));
   const eqs=l.equipes.filter(e=>garde(e,l,v)&&(!q||txtL.includes(q)||texteEq(e).includes(q)));
   if((q||FILTRES.length)&&!eqs.length&&!(l.equipes.length===0&&!FILTRES.length&&txtL.includes(q)))return '';
   nL.add(l.sigle);nE+=eqs.length;
   return `<article class="labo">
    <header class="labo-t"><div class="labo-id">${lien(l.url,l.sigle)}${l.umr?`<span class="badge badge-umr">UMR ${esc(l.umr)}</span>`:''}</div>
     <p class="labo-n">${esc(l.nom)}</p>${l.site||l.ville_aff?`<p class="labo-site">${esc(l.site||l.ville_aff)}</p>`:''}</header>
    ${l.equipes.length?`<ul class="equipes">${eqs.map(e=>tuile(e,v,l)).join('')}</ul>`:(l.correspondant?`<p class="labo-vide">Correspondant : ${corr(l.correspondant,l.correspondant_site)}</p>`:'')}
   </article>`}).join('');
  if(!labos)return '';vis.push(v.ville);
  return `<div class="ville" id="${ancre(v.ville)}">${v.villes.map(c=>`<span class="ancre-ville" id="${ancre(c)}"></span>`).join('')}<h3>${esc(v.ville)}</h3><div class="labos">${labos}</div></div>`}).join('');
 $('#ann-liste').innerHTML=html||'<p class="meta">Aucune équipe ne correspond.</p>';bind($('#ann-liste'));
 $('#ann-villes').innerHTML=vis.map(v=>`<a href="#${ancre(v)}">${esc(v)}</a>`).join('');
 $('#ann-resume').textContent=(q||FILTRES.length)?`${nE} équipe${nE>1?'s':''} sur ${ANN.reduce((s,v)=>s+v.labos.reduce((t,l)=>t+l.equipes.length,0),0)} correspondent, dans ${nL.size} laboratoire${nL.size>1?'s':''} et ${vis.length} ville${vis.length>1?'s':''}.`:`${nE} équipes, ${nL.size} laboratoires, ${vis.length} villes. Clic sur le sigle : fiche de l'équipe.`}
section(['#ann-liste'],annuaireRendre);
section([],ficheDepuisAncre);
// carte des domaines : chaque équipe est placée selon la répartition de ses publications entre les domaines
// (part de ses publications par thème, ramenée aux domaines du thème : premier domaine 1, second 0,5),
// à l'intérieur d'un cercle de domaines ordonné pour rapprocher ceux que les mêmes équipes partagent.
// « IA pour le graphique » n'est pas sur la roue (méthode transversale, pas un domaine d'application : décision de
// Damien, 2026-11-08) ; ses thèmes comptent pour leur autre domaine s'ils en ont un
const HORS_ROUE=['ia'];
const CARTE=(()=>{const W=1000,H=760,cx=500,cy=380,R=300,tous=VOC.domaines.map(d=>d.id),ids=tous.filter(d=>!HORS_ROUE.includes(d));
 const prof=(e,ids)=>{const w=Object.fromEntries(ids.map(d=>[d,0]));
  Object.entries(e.st).forEach(([t,x])=>(T[t]?.domaines||[]).forEach((d,i)=>{if(d in w)w[d]+=x.p*(i?.5:1)}));
  const s=Object.values(w).reduce((a,b)=>a+b,0)||1;ids.forEach(d=>w[d]/=s);return w};
 const P=Object.fromEntries(EQ.map(e=>[e.id,prof(e,ids)])), PT=Object.fromEntries(EQ.map(e=>[e.id,prof(e,tous)]));  // PT : tous les domaines (recherche)
 // similarité entre domaines (cosinus sur les équipes), puis ordre circulaire : plus proche voisin + 2-opt
 const vec=d=>EQ.map(e=>P[e.id][d]),nrm=v=>Math.hypot(...v)||1;
 const sim=(a,b)=>{const va=vec(a),vb=vec(b);return va.reduce((s,x,i)=>s+x*vb[i],0)/(nrm(va)*nrm(vb))};
 const S=ids.map(a=>ids.map(b=>sim(a,b))),n=ids.length,tour=o=>o.reduce((s,x,i)=>s+S[x][o[(i+1)%n]],0);
 let best=null;for(let s0=0;s0<n;s0++){const o=[s0],r=new Set(ids.map((_,i)=>i));r.delete(s0);
  while(r.size){const l=o[o.length-1];let m=null;r.forEach(j=>{if(m===null||S[l][j]>S[l][m])m=j});o.push(m);r.delete(m)}
  let ok=true;while(ok){ok=false;for(let i=1;i<n-1;i++)for(let j=i+1;j<n;j++){const c=[...o.slice(0,i),...o.slice(i,j+1).reverse(),...o.slice(j+1)];if(tour(c)>tour(o)+1e-9){o.splice(0,n,...c);ok=true}}}
  if(!best||tour(o)>tour(best))best=o}
 // choix éditorial (Damien, 2026-11-08) : Fabrication numérique entre Traitement de géométrie et Capture (maillages,
 // microstructures), bien que l'ordre calculé la place entre Animation et Modélisation ; appliqué si ces deux voisins se suivent
 const PLACER={fabrication:['geometrie','capture']};
 Object.entries(PLACER).forEach(([d,[a,b]])=>{const id=k=>ids.indexOf(k),i=best.indexOf(id(d));if(i<0)return;best.splice(i,1);
  const m=best.length,ia=best.indexOf(id(a)),ib=best.indexOf(id(b));
  if(best[(ia+1)%m]===id(b))best.splice(ia+1,0,id(d));
  else if(best[(ib+1)%m]===id(a))best.splice(ib+1,0,id(d));
  else best.splice(i,0,id(d))});
 const ordre=best.map(k=>ids[k]);
 const ancre={};best.forEach((k,i)=>{const a=-Math.PI/2+2*Math.PI*i/n;ancre[ids[k]]={x:cx+R*Math.cos(a),y:cy+R*Math.sin(a),a}});
 // position cible : barycentre des domaines, parts accentuées (puissance 2,5) pour séparer les équipes spécialisées
 const cible=EQ.map(e=>{const w=P[e.id],q=ids.map(d=>w[d]**2.5),s=q.reduce((a,b)=>a+b,0)||1;
  return {e,x:ids.reduce((t,d,i)=>t+q[i]/s*ancre[d].x,0),y:ids.reduce((t,d,i)=>t+q[i]/s*ancre[d].y,0)}});
 const rmax=Math.max(...cible.map(c=>Math.hypot(c.x-cx,c.y-cy)))||1,k=.86*R/rmax;
 // étiquettes de même taille pour toutes les équipes (sigle seul, largeur mesurée)
 const TAILLES=[{fs:11.5,h:20,min:0,lib:'1 à 3'},{fs:13.5,h:24,min:4,lib:'4 à 7'},{fs:16,h:28,min:8,lib:'8 et plus'}];
 const classe=()=>1;
 const ctx=document.createElement('canvas').getContext('2d');
 const nd=cible.map(c=>{const x=cx+(c.x-cx)*k,y=cy+(c.y-cy)*k,t=classe(c.e),{fs,h}=TAILLES[t];
  ctx.font=`650 ${fs}px system-ui,-apple-system,"Segoe UI",sans-serif`;
  return {e:c.e,tx:x,ty:y,x,y,t,fs,h,w:Math.ceil(ctx.measureText(c.e.sigle).width+fs*1.3)}});
 // anti-chevauchement des étiquettes, déterministe : répulsion des boîtes + rappel vers la position cible
 for(let it=0;it<400;it++){for(let i=0;i<nd.length;i++)for(let j=i+1;j<nd.length;j++){const a=nd[i],b=nd[j];
   const dx=b.x-a.x,dy=b.y-a.y,ox=(a.w+b.w)/2+4-Math.abs(dx),oy=(a.h+b.h)/2+3-Math.abs(dy);
   if(ox>0&&oy>0){if(ox/a.w<oy/a.h){const s=(dx>=0?1:-1)*ox/2;a.x-=s;b.x+=s}else{const s=(dy>=0?1:-1)*oy/2;a.y-=s;b.y+=s}}}
  const rappel=it<340?.03:0;  // dernières passes sans rappel : on finit de séparer les étiquettes
  nd.forEach(a=>{a.x+=(a.tx-a.x)*rappel;a.y+=(a.ty-a.y)*rappel;
   // contrainte : l'étiquette entière reste à l'intérieur du cercle (marge de 10), en la ramenant vers le centre
   const dx=a.x-cx,dy=a.y-cy,cx2=Math.abs(dx)+a.w/2,cy2=Math.abs(dy)+a.h/2,m=Math.hypot(cx2,cy2),lim=R-10;
   if(m>lim){const r=Math.hypot(dx,dy)||1,s=Math.max(0,r-(m-lim))/r;a.x=cx+dx*s;a.y=cy+dy*s}})}
 return {W,H,cx,cy,R,ids,ordre,P,PT,ancre,nd,TAILLES}})();
const etatC={region:null,epingle:null};
function carteRendre(){const {W,H,cx,cy,R,ids,ordre,P,ancre,nd,TAILLES}=CARTE,el=$('#carte'),pan=$('#c-panneau');
 const tactile=matchMedia('(hover: none)').matches,SEUIL=.15,pct=v=>Math.round(100*v)+' %',visible=e=>!etatC.region||e.region===etatC.region;
 const parts=id=>ids.map(d=>[d,P[id][d]]).filter(x=>x[1]>=.05).sort((a,b)=>b[1]-a[1]);
 const eqsDe=d=>nd.filter(n=>visible(n.e)&&P[n.e.id][d]>=SEUIL).sort((a,b)=>P[b.e.id][d]-P[a.e.id][d]);
 const perm=e=>{const p=e.stats?.permanents_ig||0;return p?`${p} permanent${p>1?'s':''} en IG`:'effectif non renseigné'};
 // libellé de domaine coupé en deux lignes au blanc le plus proche du milieu
 const lignes=s=>{if(s.length<=19)return [s];let b=-1;[...s].forEach((c,i)=>{if(c===' '&&(b<0||Math.abs(i-s.length/2)<Math.abs(b-s.length/2)))b=i});return [s.slice(0,b),s.slice(b+1)]};
 const lab=d=>{const a=ancre[d],c=Math.cos(a.a),s=Math.sin(a.a),L=lignes(D[d].fr),lh=17,anc=c>.2?'start':c<-.2?'end':'middle';
  const x=a.x+c*16,y0=s<-.8?a.y-16-(L.length-1)*lh:s>.8?a.y+26:a.y+s*14+5-(L.length-1)*lh/2;
  const tw=Math.max(...L.map(l=>l.length))*8.4,x0=anc==='start'?x:anc==='end'?x-tw:x-tw/2;
  const hx=Math.min(x0,a.x-10),hy=Math.min(y0-15,a.y-10),hw=Math.max(x0+tw,a.x+10)-hx,hh=Math.max(y0+(L.length-1)*lh+6,a.y+10)-hy;
  return `<g class="c-dom" data-dom="${d}" tabindex="0" role="button" aria-label="Domaine ${esc(D[d].fr)} : ${eqsDe(d).length} équipe(s) y consacrent au moins 15 % de leurs publications">
   <rect class="c-hit" x="${hx-6}" y="${hy-4}" width="${hw+12}" height="${hh+8}" rx="8"/><circle cx="${a.x}" cy="${a.y}" r="7"/>
   <text text-anchor="${anc}">${L.map((l,i)=>`<tspan x="${x}" y="${y0+i*lh}">${esc(l)}</tspan>`).join('')}</text></g>`};
 const ariaEq=n=>`${n.e.sigle}, ${n.e.labo}, ${n.e.ville}. ${perm(n.e)}. `+parts(n.e.id).slice(0,4).map(([d,v])=>`${D[d].fr} ${pct(v)}`).join(', ');
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Carte des équipes selon leurs domaines de publication. Tabulation pour parcourir, Entrée pour ouvrir une fiche, Échap pour effacer.">
  <circle class="c-centre" cx="${cx}" cy="${cy}" r="${R*.38}"/>
  ${ordre.map(d=>`<line class="c-rayon" x1="${cx}" y1="${cy}" x2="${ancre[d].x}" y2="${ancre[d].y}"/>`).join('')}
  <circle class="c-cercle" cx="${cx}" cy="${cy}" r="${R}"/><g id="c-liens"></g>${ordre.map(lab).join('')}
  ${[...nd].sort((a,b)=>a.t-b.t).map(n=>`<g class="c-eq t${n.t}" data-eqc="${n.e.id}" tabindex="0" role="button" aria-label="${esc(ariaEq(n))}" transform="translate(${n.x.toFixed(1)},${n.y.toFixed(1)})"><rect x="${(-n.w/2).toFixed(1)}" y="${-n.h/2}" width="${n.w}" height="${n.h}" rx="${n.h/2}"/><text y="${(n.fs*.36).toFixed(1)}" text-anchor="middle" font-size="${n.fs}">${esc(n.e.sigle)}</text></g>`).join('')}
 </svg>`;
 const svg=el.querySelector('svg'),liens=$('#c-liens');
 // cadrage serré sur le contenu : les marges vides du viewBox fixe sont rendues à la carte
 const bb=svg.getBBox();svg.setAttribute('viewBox',`${(bb.x-10).toFixed(0)} ${(bb.y-10).toFixed(0)} ${(bb.width+20).toFixed(0)} ${(bb.height+20).toFixed(0)}`);
 const pos=id=>nd.find(n=>n.e.id===id);
 const trace=paires=>liens.innerHTML=paires.map(([n,d,w])=>`<line x1="${n.x}" y1="${n.y}" x2="${ancre[d].x}" y2="${ancre[d].y}" stroke-width="${(1+10*w).toFixed(1)}"/>`).join('');
 const appliquer=actifs=>svg.querySelectorAll('.c-eq').forEach(g=>{const e=pos(g.dataset.eqc).e;g.classList.toggle('pale',!visible(e)||(!!actifs&&!actifs.has(e.id)));g.classList.toggle('actif',!!actifs&&actifs.has(e.id))});
 const doms=f=>svg.querySelectorAll('.c-dom').forEach(x=>{const on=f(x.dataset.dom);x.classList.toggle('actif',on===true);x.classList.toggle('pale',on===false)});
 const barre=(v,m)=>`<i style="width:${Math.max(2,Math.round(56*v/m))}px"></i>`;
 const legende=`<div class="c-leg"><div><h3>Lire la carte</h3><p class="c-aide">${tactile?'Touchez une équipe ou un domaine pour voir ses parts ; touchez à nouveau une équipe pour ouvrir sa fiche. Faites glisser la carte de côté.':'Survolez ou parcourez au clavier une équipe ou un domaine. Clic sur un domaine : le garder affiché. Clic sur une équipe : sa fiche.'}</p></div>
  <div><h4>Position</h4><svg class="c-schema" viewBox="0 0 250 92" aria-hidden="true"><circle class="s-c" cx="58" cy="46" r="38"/><circle class="s-d" cx="58" cy="8" r="4"/><circle class="s-d" cx="94" cy="58" r="4"/><circle class="s-d" cx="22" cy="58" r="4"/>
   <rect x="47" y="17" width="22" height="9" rx="4.5"/><rect x="47" y="42" width="22" height="9" rx="4.5"/><text x="108" y="25">près d'un domaine :</text><text x="108" y="38">équipe spécialisée</text><text x="108" y="60">au centre : plusieurs</text><text x="108" y="73">domaines à parts égales</text></svg></div>
  <div><h4>Cercle</h4><p class="c-aide">Domaines voisins : partagés par les mêmes équipes.</p></div></div>`;
 const montrerEq=id=>{const n=pos(id),e=n.e,top=parts(id);trace(top.map(([d,v])=>[n,d,v]));appliquer(new Set([id]));doms(d=>top.some(t=>t[0]===d));
  pan.innerHTML=`<h3>${esc(e.sigle)}</h3><p class="sous">${esc(e.labo)}, ${esc(e.ville)} · ${esc(perm(e))}</p><ul>${top.slice(0,6).map(([d,v])=>`<li><span>${esc(D[d].fr)}</span>${barre(v,top[0][1])}<b>${pct(v)}</b></li>`).join('')}</ul><p class="c-aide">Part des publications par domaine.</p><button class="c-fiche" type="button" data-fiche="${e.id}">Voir la fiche de l'équipe →</button>`;
  pan.querySelector('[data-fiche]').onclick=()=>fiche(e.id)};
 const montrerDom=d=>{const eqs=eqsDe(d);trace(eqs.map(n=>[n,d,P[n.e.id][d]]));appliquer(new Set(eqs.map(n=>n.e.id)));doms(x=>x===d);
  const m=eqs.length?P[eqs[0].e.id][d]:1;
  pan.innerHTML=`<h3>${esc(D[d].fr)}</h3><p class="sous">${esc(D[d].description)}</p><p class="c-aide">${eqs.length} équipe${eqs.length>1?'s':''} y consacre${eqs.length>1?'nt':''} au moins 15 % de ${eqs.length>1?'leurs':'ses'} publications${etatC.region?' ('+esc(etatC.region)+')':''} :</p><ul>${eqs.map(n=>`<li><span>${esc(n.e.sigle)} <small style="color:var(--muted)">${esc(n.e.ville)}</small></span>${barre(P[n.e.id][d],m)}<b>${pct(P[n.e.id][d])}</b></li>`).join('')}</ul>${etatC.epingle?.id===d?'<p class="c-aide">Échap ou nouveau clic : relâcher.</p>':''}`};
 const repos=()=>{const p=etatC.epingle;if(p){p.type==='eq'?montrerEq(p.id):montrerDom(p.id);return}
  liens.innerHTML='';doms(()=>null);appliquer(null);pan.innerHTML=legende};
 svg.querySelectorAll('.c-eq').forEach(g=>{const id=g.dataset.eqc;
  g.addEventListener('mouseenter',()=>montrerEq(id));g.addEventListener('focus',()=>montrerEq(id));g.addEventListener('mouseleave',repos);g.addEventListener('blur',repos);
  // tactile : premier toucher = détail, second = fiche
  g.addEventListener('click',()=>{if(tactile&&etatC.epingle?.id!==id){etatC.epingle={type:'eq',id};repos();return}fiche(id)});
  g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();fiche(id)}})});
 svg.querySelectorAll('.c-dom').forEach(g=>{const d=g.dataset.dom,basculer=()=>{etatC.epingle=etatC.epingle?.id===d?null:{type:'dom',id:d};repos()};
  g.addEventListener('mouseenter',()=>montrerDom(d));g.addEventListener('focus',()=>montrerDom(d));g.addEventListener('mouseleave',repos);g.addEventListener('blur',repos);
  g.addEventListener('click',basculer);g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();basculer()}})});
 el.onkeydown=ev=>{if(ev.key==='Escape'){etatC.epingle=null;repos()}};
 const regs=[...new Set(EQ.map(e=>e.region))].sort((a,b)=>a.localeCompare(b,'fr'));
 $('#carte-reg').innerHTML=`<button class="chip" data-reg="" aria-pressed="${!etatC.region}">Toutes</button>`+regs.map(r=>`<button class="chip" data-reg="${esc(r)}" aria-pressed="${etatC.region===r}">${esc(r)}</button>`).join('');
 $('#carte-reg').querySelectorAll('[data-reg]').forEach(b=>b.onclick=()=>{etatC.region=b.dataset.reg||null;carteRendre()});
 // version texte, équivalente à la carte (lecteur d'écran, mobile, impression)
 $('#carte-liste').innerHTML=`<dl>${ordre.map(d=>{const eqs=eqsDe(d);return `<dt>${esc(D[d].fr)}</dt><dd>${eqs.length?eqs.map(n=>`${esc(n.e.sigle)} ${pct(P[n.e.id][d])}`).join(', '):'aucune équipe au-dessus de 15 %'}</dd>`}).join('')}</dl>`;
 repos();
 if(el.scrollWidth>el.clientWidth&&!el.dataset.centre){el.scrollLeft=(el.scrollWidth-el.clientWidth)/2;el.dataset.centre=1}}
section(['#carte'],carteRendre);
</script>
</body>
</html>
"""


def main():
    voc, equipes, ann = charger()
    js = lambda x: json.dumps(x, ensure_ascii=False).replace('</', '<\\/')  # pas de « </script> » dans les données
    per = json.loads((CARTO / 'periode.json').read_text()) if (CARTO / 'periode.json').exists() else {'debut': 2016, 'fin': 2026}
    page = PAGE.replace('__VOC__', js(voc)).replace('__EQ__', js(equipes)).replace('__ANN__', js(ann)).replace('__DEBUT__', str(per['debut'])).replace('__FIN__', str(per['fin']))
    CHEMINS['sortie'].parent.mkdir(parents=True, exist_ok=True)
    CHEMINS['sortie'].write_text(page, encoding='utf-8')
    print(f'{len(equipes)} équipes -> {CHEMINS["sortie"]} ({len(page) // 1024} Ko)')
    sans_coord = [e['sigle'] + ' (' + e['ville'] + ')' for e in equipes if not e['coord']]
    if sans_coord:
        print('sans coordonnées :', sans_coord)


if __name__ == '__main__':
    main()
