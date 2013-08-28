#!/usr/bin/env python
import os, site

wsgidir = os.path.dirname(__file__)
site.addsitedir(os.path.abspath(os.path.join(wsgidir, './')))

from web import app as application
