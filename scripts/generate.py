import os, sys
import yaml
import json
import urllib.request, urllib.error
import argparse
import tqdm


meta = {
    'filename_yaml': 'data.yaml',
    'filename_json_out': 'json/data.json',
    'filename_md_out': 'README.md'
}
root_path = os.path.join(os.path.dirname(__file__))



def yaml_read_file(pathname):
    assert os.path.isfile(pathname)
    with open(pathname, 'r') as fid:
        content = yaml.safe_load(fid)
    return content



def recursive_url_get(data, all_urls):
    if isinstance(data, dict):
        labels = list(data.keys())
        for label in labels:
            if label=='URL' or label.startswith('URL-'):
                url = data[label]
                all_urls.append(url)
        for element in data:
            recursive_url_get(data[element], all_urls)
    if isinstance(data, list):
        for element in data:
            recursive_url_get(element, all_urls)


def get_all_urls(data):
    all_urls = []
    recursive_url_get(data, all_urls)
    return all_urls


def is_url_valid(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        url_open = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return True
        print(f'Warning: URL seems down {url}')
        print('Error code: ', e.code)
        return False
    except urllib.error.URLError as e:
        print(f'Warning: URL seems wrong: {url}')
        print('Reason: ', e.reason)
        return False
    except Exception as e:
        print(f'Warning: URL issue {url}')
        print('Error: ', e)
        return False
    else:
        return True


def check_urls(urls, exitOnError=False, exceptions=set()):
    success = True
    print('Check urls ...')
    for url in tqdm.tqdm(urls):
        if url not in exceptions:
            ret = is_url_valid(url)
            if ret != True:
                success = False
    if exitOnError and not success:
        print("Exit due to Error")
        exit(1)


def get_optional(key, data):
    if key in data:
        return str(data[key])
    return ''


def prettyMD_equipe(equipe_name, equipe):
    out = ''
    url = equipe.get('URL', '')
    nom = equipe.get('Nom', '')

    if url:
        out += f'  * **[{equipe_name}]({url})**'
    else:
        out += f'  * **{equipe_name}**'

    if nom:
        out += f' - {nom}'
    out += ' \n'

    if 'Correspondant' in equipe:
        out += f'    * Correspondant: {equipe["Correspondant"]} \n'
    if 'Thèmes' in equipe:
        out += f'    * Thèmes: _{equipe["Thèmes"]}_ \n'
    if 'Ville' in equipe:
        out += f'    * Ville: {equipe["Ville"]} \n'
    if 'Inria' in equipe:
        out += f'    * _Equipe commune Inria_ \n'

    return out


def prettyMD(data):

    out = '# Equipes de recherche en Informatique Graphique \n\n'

    out += '## Compléter/Modifier les informations \n'
    out += '  - Envoyez un email à contact[at]asso-afig.fr avec vos informations\n'
    out += '  - Ou faites un push-request sur le dépot.\n'
    out += '\n'
    out += 'Rem. Le fichier README.md est généré automatiquement à partir du fichier data.yaml. Ne pas modifier directement le fichier README.md.\n'
    out += '\n\n'

    # --- Summary ---
    out += '## Résumé \n\n'

    lab_names = sorted(data.keys())
    for lab_name in lab_names:
        lab = data[lab_name]
        lab_url = lab.get('URL', '')
        ville = lab.get('Ville', '')

        line = f'[**{lab_name}**]({lab_url})'
        if 'Equipes' in lab:
            equipe_names = sorted(lab['Equipes'].keys())
            teams = ', '.join([f'[{e}]({lab["Equipes"][e].get("URL","")})' for e in equipe_names])
            line += f' : {teams}'

        # For Inria, also list joint teams from other labs
        if lab_name == 'Inria':
            joint_teams = []
            for other_lab_name in lab_names:
                if other_lab_name != 'Inria' and 'Equipes' in data[other_lab_name]:
                    for team_name, team in data[other_lab_name]['Equipes'].items():
                        if 'Inria' in team:
                            joint_teams.append(f'[{team_name}]({team.get("URL","")})')
            if joint_teams:
                line += ', ' + ', '.join(joint_teams)

        if ville:
            line += f' ({ville})'

        out += f'- {line} \n'

    out += '\n\n'

    # --- Detailed listing grouped by city ---
    out += '## Listing détaillé \n\n'

    # Group labs by city
    labs_by_city = {}
    for lab_name in lab_names:
        lab = data[lab_name]
        ville = lab.get('Ville', 'Autre')
        if ville not in labs_by_city:
            labs_by_city[ville] = []
        labs_by_city[ville].append(lab_name)

    cities = sorted([c for c in labs_by_city.keys() if c != 'Autre'], key=str.lower)
    if 'Autre' in labs_by_city:
        cities.append('Autre')
    for city in cities:
        out += f'### {city} \n\n'

        for lab_name in sorted(labs_by_city[city]):
            lab = data[lab_name]
            lab_url = lab.get('URL', '')
            lab_nom = lab.get('Nom', '')
            lab_umr = get_optional('UMR', lab)

            out += f'* **[{lab_name}]({lab_url})**'
            if lab_nom:
                out += f' - {lab_nom}'
            out += ' \n'

            if lab_umr:
                out += f'  * CNRS UMR-{lab_umr} \n'

            if 'Correspondant' in lab:
                out += f'  * Correspondant: {lab["Correspondant"]} \n'
            if 'Thèmes' in lab:
                out += f'  * Thèmes: _{lab["Thèmes"]}_ \n'

            if 'Equipes' in lab:
                equipe_names = sorted(lab['Equipes'].keys())
                for equipe_name in equipe_names:
                    equipe = lab['Equipes'][equipe_name]
                    out += prettyMD_equipe(equipe_name, equipe)

            # For Inria: also list joint teams from other labs
            if lab_name == 'Inria':
                joint_entries = []
                for other_lab_name in lab_names:
                    if other_lab_name != 'Inria' and 'Equipes' in data[other_lab_name]:
                        for team_name, team in data[other_lab_name]['Equipes'].items():
                            if 'Inria' in team:
                                joint_entries.append((team_name, team, other_lab_name))
                if joint_entries:
                    for team_name, team, other_lab_name in joint_entries:
                        url = team.get('URL', '')
                        out += f'  * **[{team_name}]({url})** - _Equipe commune avec {other_lab_name}_ \n'

            out += '\n'

        out += '\n'

    return out


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Generate Listing Equipes de Recherche')
    parser.add_argument('-c', '--checkURL', help='Check url validity', action='store_true')
    parser.add_argument('-C', '--checkURLwithFailure', help='Check url validity and fails if some are unreachable', action='store_true')
    args = parser.parse_args()

    is_check_url = args.checkURL or args.checkURLwithFailure
    exit_on_failure = args.checkURLwithFailure

    filename_yaml = root_path + '/../' + meta['filename_yaml']
    filename_json_out = root_path + '/../' + meta['filename_json_out']
    filename_md_out = root_path + '/../' + meta['filename_md_out']

    data = yaml_read_file(filename_yaml)

    if is_check_url:
        urls = get_all_urls(data)
        check_urls(urls, exitOnError=exit_on_failure)

    # export json
    print('[Export JSON]')
    with open(filename_json_out, 'w') as json_fid:
        json.dump(data, json_fid, indent=4, ensure_ascii=False)

    # export pretty md
    print('[Export README.md]')
    with open(filename_md_out, 'w') as md_fid:
        mdTXT = prettyMD(data)
        md_fid.write(mdTXT)

    print('Done.')
