#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Import musescore-dataset metadata.
"""


import os
import io
import csv
import json
import sqlite3
import contextlib


def make_insert(d):
    keys, values = zip(*(('"%s"' % k, v) for k, v in d.items()))
    qs = tuple('?' for x in keys)
    return ','.join(keys), ','.join(qs), values

cstr = lambda s: None if s == '' else s
cint = lambda s: None if s == '' or s is None else int(s)


print('Creating schema')
db = sqlite3.connect('musescore.com.db')
db.row_factory = sqlite3.Row
cur = db.cursor()
cur.execute(
    'CREATE TABLE IF NOT EXISTS mscz_files ('
    'id INTEGER PRIMARY KEY,'
    'ref TEXT,'
    'path TEXT'
')')
cur.execute(
    'CREATE TABLE IF NOT EXISTS score ('
    'revisionId INTEGER PRIMARY KEY,'
    'id INTEGER,'
    'authorUserId INTEGER,'
    'title TEXT,'
    'duration INTEGER,'
    'pagesCount INTEGER,'
    'instrumentsCount INTEGER,'
    'partsCount INTEGER,'
    'instrumentsNames TEXT,'
    'partsNames TEXT,'
    'musicxmlInstruments TEXT,'
    'summary TEXT,'
    'description TEXT,'
    'timeCreated TEXT,'
    'timeUpdated TEXT,'
    'url TEXT'
')')
cur.execute("CREATE INDEX IF NOT EXISTS idx_score_id ON score (id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_score_author_id ON score (authorUserId)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_score_updated ON score (timeUpdated DESC)")
cur.execute(
    'CREATE TABLE IF NOT EXISTS user ('
    'id INTEGER PRIMARY KEY,'
    'name TEXT,'
    'plan TEXT,'
    'permalink TEXT,'
    'avatar TEXT,'
    'avatarCid TEXT'
')')
db.commit()

if os.path.isfile('mscz-files.csv'):
    print('Importing mscz-files.csv')
    with open('mscz-files.csv', 'rb') as f:
        wrapper = io.TextIOWrapper(f, encoding='utf-8', newline='')
        csv_reader = csv.reader(wrapper)
        next(csv_reader)
        for row in csv_reader:
            db.execute("INSERT OR IGNORE INTO mscz_files VALUES (?,?,?)", (
                cint(row[0]), cstr(row[1]), cstr(row[2])
            ))
    db.commit()
if os.path.isfile('score.jsonl'):
    print('Importing score.jsonl')
    with open('score.jsonl', 'rb') as f:
        wrapper = io.TextIOWrapper(f, encoding='utf-8', newline='')
        for ln in wrapper:
            d = json.loads(ln)
            for key, value in d.items():
                if isinstance(value, list):
                    d[key] = json.dumps(value)
                elif key in (
                    'id', 'revisionId', 'duration', 'pagesCount',
                    'instrumentsCount', 'partsCount', 'authorUserId'
                ):
                    d[key] = cint(value)
                else:
                    d[key] = cstr(value)
                if key == '__error__' and not value:
                    d[key] = None
            if '__error__' in d:
                if d['__error__']:
                    continue
                del d['__error__']
            with contextlib.suppress(KeyError):
                del d['__key__']
            with contextlib.suppress(KeyError):
                del d['__has_error__']
            if d.get('id') is None:
                continue
            keys, qs, values = make_insert(d)
            row = db.execute("SELECT * FROM score WHERE revisionId=?",
                (d['revisionId'],)).fetchone()
            if d['revisionId'] == 0:
                print(ln.strip())
            try:
                if row:
                    if d['timeUpdated'] >= row['timeUpdated']:
                        db.execute(
                            "REPLACE INTO score ({}) VALUES ({})".format(keys, qs),
                            values)
                else:
                    db.execute("INSERT INTO score ({}) VALUES ({})".format(keys, qs), values)
            except sqlite3.DatabaseError:
                print(ln)
                raise
    db.commit()
if os.path.isfile('user.jsonl'):
    print('Importing user.jsonl')
    with open('user.jsonl', 'rb') as f:
        wrapper = io.TextIOWrapper(f, encoding='utf-8', newline='')
        for ln in wrapper:
            d = json.loads(ln)
            for key, value in d.items():
                if key == id:
                    d[key] = cint(value)
                else:
                    d[key] = cstr(value)
            keys, qs, values = make_insert(d)
            try:
                db.execute("REPLACE INTO user ({}) VALUES ({})".format(keys, qs),
                    values)
            except sqlite3.DatabaseError:
                print(ln)
                raise
    db.commit()
cur.execute(
    "CREATE VIRTUAL TABLE fts_score USING fts5 ("
    "title, summary, description, content='score', content_rowid='revisionId', prefix=2"
    ")"
)
cur.execute(
    "INSERT INTO fts_score(rowid, title, summary, description) "
    "SELECT revisionId, title, summary, description FROM score"
)
cur.execute('ANALYZE')
db.commit()
cur.execute('VACUUM')
db.commit()
print('Done.')
