#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import sys
import json
import sqlite3

import xattr

re_paren = re.compile(r'\(.+?\)')
re_word = re.compile(r'\w+')
re_ws = re.compile(r'\s+')

db = sqlite3.connect(sys.argv[1])
db.row_factory = sqlite3.Row
cur = db.cursor()
cur.execute("""
SELECT s.id, s.authorUserId, u.name, s.title, s.partsNames, s.instrumentsNames
FROM score s
LEFT JOIN user u ON u.id=s.authorUserId
""")

def names_to_list(s):
    if not s:
        return ''
    l = json.loads(s)
    seen = set()
    results = []
    for item in l:
        item = re_ws.sub(' ', re_paren.sub('', item).strip())
        if re_word.search(item) and item not in seen:
            results.append(item)
            seen.add(item)
    return ', '.join(results)


for mscz_id, user_id, user_name, title, partsNames, instrumentsNames in cur:
    dirname = os.path.join(sys.argv[2], str(mscz_id % 20))
    fullname = os.path.join(dirname, '%s.mscz' % mscz_id)
    if not os.path.isfile(fullname):
        continue
    if b'dublincore.title' in xattr.list(fullname, namespace=xattr.NS_USER):
        continue
    print(mscz_id, title)
    subject = names_to_list(instrumentsNames) or names_to_list(partsNames)
    xattr.set(fullname, "user.dublincore.title", title.strip())
    if user_name:
        creator = '%s. %s' % (user_id, user_name.strip())
    else:
        creator = str(user_id)
    xattr.set(fullname, "user.dublincore.creator", creator)
    if subject:
        xattr.set(fullname, "user.dublincore.subject", subject)
