#!/usr/bin/env python

import os
import simplejson
from flask import Flask, Response, render_template
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/releases')
def releases():
    try:
        with open('static/releases.json') as f:
            contents = f.read()
        return Response(response=contents, mimetype='application/json')
    except IOError, e:
        return Response('No results (yet) %s' % e)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
