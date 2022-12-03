#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import csv
import sys
import random
import sqlite3

gateways = [
    'https://ipfs.io',
    'https://dweb.link',
    'https://gateway.ipfs.io',
    'https://gateway.pinata.cloud',
    'https://jorropo.net',
    'https://ipfs.best-practice.se',
    'https://ipfs.telos.miami',
    'https://crustwebsites.net',
    'https://ipfs.eth.aragon.network',
    'https://ipfs.lain.la',
    'https://storry.tv',
    'https://c4rex.co',
]

db = sqlite3.connect(sys.argv[1])
db.row_factory = sqlite3.Row
cur = db.cursor()

for mscz_id, ref in cur.execute("SELECT id, ref FROM mscz_files"):
    dirname = os.path.join(sys.argv[2], str(mscz_id % 20))
    fullname = os.path.join(dirname, '%s.mscz' % mscz_id)
    if os.path.isfile(fullname) and os.stat(fullname).st_size > 1:
        continue
    random.shuffle(gateways)
    print('\t'.join(gw + ref for gw in gateways))
    print("  out=" + fullname)
