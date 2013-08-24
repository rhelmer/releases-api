REST+JSON service to return information about Mozilla builds.

Data is retreived from the http://ftp.mozilla.org/pub/mozilla.org/

--
Install:
```
 virtualenv env
 . env/bin/activate
 pip install -r requirements.txt
```

--  
Run scraper:
```
 ./scraper.py > static/releases.json
```

Run web UI:
```
 ./web.py
```
