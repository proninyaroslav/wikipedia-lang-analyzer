# Copyright (C) 2019 Yaroslav Pronin <proninyaroslav@mail.ru>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import requests
import wikitextparser as wtp
import re
import json
import sys
import argparse

_URL_API = 'https://en.wikipedia.org/w/api.php'


class Language:
    def __init__(self, name, influenced_by):
        self.name = name
        self.influenced_by = influenced_by

    def __repr__(self):
        return "Language[name=" + self.name.__repr__() + \
            ", influenced_by=" + self.influenced_by.__repr__() + "]"


def get_langs_titles(session):
    languages = []
    params = {
        'action': 'query',
        'format': 'json',
        'titles': 'List of programming languages',
        'prop': 'links',
        'pllimit': '500'
    }
    plcontinue = None

    while True:
        if plcontinue is not None:
            params['plcontinue'] = plcontinue
        res = session.get(url=_URL_API, params=params)
        content = res.json()

        pages = content['query']['pages']
        page_key = sorted(pages.keys())[-1]
        for langs in pages[page_key]['links']:
            if langs['ns'] == 0:
                languages.append(langs['title'].replace('_', ' '))

        if 'continue' not in content:
            break
        plcontinue = content['continue']['plcontinue']

    return languages


def get_lang_by_title(session, title):
    res = session.get(url=_URL_API, params={
        'action': 'query',
        'prop': 'revisions',
        'rvprop': 'content',
        'format': 'json',
        'titles': title,
        'rvsextion': '0'
    })
    pages = res.json()['query']['pages']
    page_key = sorted(pages.keys())[-1]
    wikitext = pages[page_key]['revisions'][0]['*']

    return Language(title, parse_influence_langs(wikitext))


def parse_influence_langs(wikitext):
    parsed = wtp.parse(wikitext)
    infobox = list(filter(lambda template:
                          'Infobox programming language' in template,
                          parsed.templates))
    if not infobox:
        return []

    template = infobox[0]
    args = [
        template.get_arg('influenced by'),
        template.get_arg('influenced_by'),
    ]

    for arg in args:
        if not arg:
            continue
        arg.value = re.sub(r'(<ref>.*?<\/ref>)', '', arg.value)

    return list({wikilink.title.replace('_', ' ')
        for arg in args if arg for wikilink in arg.wikilinks})


def clean_lang_name(name): return re.sub(r'( \(.*\))', '', name)


def calc_influential_lang_map():
    influence_map = {}

    s = requests.Session()
    for title in get_langs_titles(s):
        lang = get_lang_by_title(s, title)
        influenced_lang_name = clean_lang_name(lang.name)

        for influencing_lang in lang.influenced_by:
            name = clean_lang_name(influencing_lang)
            if name in influence_map:
                influence_map[name]['langs'].append(influenced_lang_name)
                influence_map[name]['count'] += 1
            else:
                influence_map[name] = {'count': 0, 'langs': []}

    return influence_map


def calc_influenced_lang_map():
    influence_map = {}

    s = requests.Session()
    for title in get_langs_titles(s):
        lang = get_lang_by_title(s, title)

        influenced_lang_name = clean_lang_name(lang.name)
        influenced_by = [clean_lang_name(name) for name in lang.influenced_by]
        influence_map[influenced_lang_name] = {
            'count': len(influenced_by),
            'langs': influenced_by
        }

    return influence_map


def main(argv):
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--influential',
        help='List of programming languages that have most influenced the development of other languages',
        action='store_true')
    group.add_argument('--influenced',
        help='List of programming languages that are most influenced by other languages',
        action='store_true')
    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    influence_map = {}

    if args.influential:
        influence_map = calc_influential_lang_map()
    elif args.influenced:
        influence_map = calc_influenced_lang_map()
    else:
        parser.print_help()
        sys.exit(1)

    sorted_influence_map = sorted(influence_map.items(),
                                  key=lambda item: item[1]['count'],
                                  reverse=True)
    print(json.dumps(sorted_influence_map, indent=2, separators=(',', ': ')))


if __name__ == "__main__":
    main(sys.argv)
