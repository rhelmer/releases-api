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
Run scraper (e.g. every 5 minutes from cron or similar):
```
 ./scraper.py > static/releases.json
```

Run web UI:
```
 ./web.py
```
