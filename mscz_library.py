import os
import re
import sys
import json
import glob
import shutil
import sqlite3
import tempfile
import subprocess

import zhconv
import jinja2
import bottle
import markupsafe

script_path = os.path.abspath(os.path.dirname(__file__))

re_paren = re.compile(r'\(.+?\)')
re_word = re.compile(r'\w+')
re_ws = re.compile(r'\s+')
re_paragraph = re.compile(r'(?:\r\n|\r(?!\n)|\n){2,}')

MIMETYPES = {
    'ogg': 'audio/ogg',
    'pdf': 'application/pdf',
    'mscz': 'application/x-musescore3',
    'png': 'image/png',
}
CONFIG = {}

application = app = bottle.Bottle()

@jinja2.pass_eval_context
def nl2br(eval_ctx, value):
    result = u'\n\n'.join(
        u'<p>%s</p>' % p.replace('\n', markupsafe.Markup('<br>\n'))
        for p in re_paragraph.split(markupsafe.escape(value))
    )
    if eval_ctx.autoescape:
        result = markupsafe.Markup(result)
    return result


def time_format(sec):
    return '%02d:%02d' % divmod(sec, 60)


def names_to_list(s):
    if not s:
        return ''
    l = json.loads(s)
    results = []
    for item in l:
        item = re_ws.sub(' ', re_paren.sub('', item).strip())
        if re_word.search(item):
            results.append(item)
    return ', '.join(results)


def instruments(instruments, parts):
    return names_to_list(instruments) or names_to_list(parts)


jinjaenv = jinja2.Environment(loader=jinja2.FileSystemLoader(
    os.path.join(script_path, 'templates')), autoescape=True)
jinjaenv.filters['nl2br'] = nl2br
jinjaenv.filters['time_format'] = time_format
jinjaenv.filters['instruments'] = instruments


def render_mscz(inputfile, outputfile, title):
    environ = os.environ.copy()
    if 'display' in CONFIG:
        environ['DISPLAY'] = CONFIG['display']
    if title:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpinput = os.path.join(
                tmpdir, title + os.path.splitext(inputfile)[1])
            shutil.copyfile(inputfile, tmpinput)
            subprocess.run(['mscore3', '-m', '-o', outputfile, tmpinput], env=environ)
    else:
        subprocess.run(['mscore3', '-m', '-o', outputfile, inputfile], env=environ)


def render_thumbnail(inputfile, outputfile):
    with tempfile.TemporaryDirectory() as tmpdir:
        render_mscz(inputfile, os.path.join(tmpdir, 'thumb.png'), '')
        for filename in sorted(glob.glob(os.path.join(tmpdir, 'thumb*.png'))):
            shutil.copyfile(filename, outputfile)
            break


def render_page(where, values, title):
    db = sqlite3.connect(CONFIG['db'])
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    sql = """
    SELECT s.id, s.authorUserId,
      coalesce(u.name, CAST(s.authorUserId AS TEXT)) author,
      s.title, s.partsCount, s.pagesCount, s.duration,
      s.partsNames, s.instrumentsNames, s.timeUpdated,
      s.summary, s.description,
      CASE WHEN s.url LIKE 'https://%' THEN s.url
      ELSE 'https://musescore.com' || s.url END url
    FROM score s
    LEFT JOIN user u ON u.id=s.authorUserId
    """
    if where:
        sql += where
    cur.execute(sql, values or ())
    template = jinjaenv.get_template("template.html")
    return template.render(title=title, scores=cur.fetchall())


def get_title(score_id, ext):
    db = sqlite3.connect(CONFIG['db'])
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    row = cur.execute("SELECT title FROM score WHERE id=?", (score_id,)).fetchone()
    if row and row[0]:
        return '%d.%s.%s' % (score_id, row[0].strip(), ext)
    else:
        return '%d.%s' % (score_id, ext)


def get_path(id, ext):
    root = CONFIG.get('path/' + ext, CONFIG['path/mscz'])
    relpath = os.path.join(str(id % 20), '%s.%s' % (id, ext))
    return root, relpath


@app.route('/pdfjs/<path:path>')
def pdfjs(path):
    return bottle.static_file(path, root=os.path.join(script_path, 'pdfjs'))


@app.route('/download/<id:int>.<ext>')
def download(id, ext):
    db = sqlite3.connect(CONFIG['db'])
    db.row_factory = sqlite3.Row
    cur = db.cursor()
    row = cur.execute("SELECT title FROM score WHERE id=?", (id,)).fetchone()
    title = None
    download_name = str(id)
    if row and row[0]:
        title = row[0]
        download_name += '.' + title

    root, relpath = get_path(id, ext)
    fullname = os.path.join(root, relpath)
    if os.path.isfile(fullname):
        return bottle.static_file(
            relpath, root=root, mimetype=MIMETYPES.get(ext),
            download=('%s.%s' % (download_name, ext) if ext != 'png' else None))
    if ext == 'mscz':
        bottle.abort(404, "%s not found" % id)
    msczpath = os.path.join(*get_path(id, "mscz"))
    if not os.path.isfile(msczpath):
        bottle.abort(404, "%s not found" % id)
    if ext == 'png':
        render_thumbnail(msczpath, fullname)
        return bottle.static_file(
            relpath, root=root, mimetype=MIMETYPES.get(ext))
    else:
        render_mscz(msczpath, fullname, title)
        return bottle.static_file(
            relpath, root=root, mimetype=MIMETYPES.get(ext),
            download='%s.%s' % (download_name, ext))


@app.route('/user/<id:int>')
def user_list(id):
    return render_page("""
        WHERE s.authorUserId=?
        ORDER BY s.pagesCount DESC NULLS LAST, s.timeUpdated DESC,
          s.revisionId DESC
    """, (id,), "User %d" % id)


@app.route('/')
def index():
    search = bottle.request.params.get('q', '').encode('latin1').decode('utf-8')
    if search:
        search_kwds = set((
            search, zhconv.convert(search, 'zh-hans'),
            zhconv.convert(search, 'zh-hant')
        ))
        search_fts = ' OR '.join('"%s"*' % x.replace('"', '""') for x in search_kwds)
        # search_where = []
        # search_values = []
        # for kwd in search_kwds:
            # search_where.extend(('s.title LIKE ?', 's.description LIKE ?'))
            # search_values.extend((kwd,)*2)
        return render_page("""
            WHERE revisionId IN (SELECT ROWID FROM fts_score WHERE fts_score MATCH ?)
            ORDER BY s.partsCount ASC NULLS LAST,
              s.pagesCount DESC NULLS LAST, s.id DESC
        """, (search_fts,), "Search result for: " + search)
    else:
        # return render_page("""
            # ORDER BY s.id DESC
            # LIMIT 20
        # """, (), "Last Updated")
        return render_page("""
            ORDER BY random()
            LIMIT 20
        """, (), "Random selection")


def load_config(root):
    CONFIG['db'] = os.path.join(root, 'mscz/musescore.com.db')
    CONFIG['display'] = os.environ.get("DISPLAY", ":9")
    CONFIG['path/mscz'] = os.path.join(root, 'mscz')
    CONFIG['path/pdf'] = os.path.join(root, 'pdf')
    CONFIG['path/ogg'] = os.path.join(root, 'ogg')
    CONFIG['path/png'] = os.path.join(root, 'png')

# change this to data directory
load_config('.')

if __name__ == '__main__':
    host = '127.0.0.1'
    port = 8084
    if len(sys.argv) > 1:
        srvhost = sys.argv[1]
        spl = srvhost.rsplit(":", 1)
        if spl[1].isnumeric():
            host = spl[0].lstrip('[').rstrip(']')
            port = int(spl[1])
        else:
            host = srvhost.lstrip('[').rstrip(']')
    app.run(host=host, port=port, server='auto')
