#!/usr/bin/env python

import re
import urllib2
import lxml.html
import json
import os
import sys
import datetime
import logging

logging.basicConfig()
logger = logging.getLogger('scraper')
logger.setLevel(logging.DEBUG)

"""
 Socket timeout to prevent FTP from hanging indefinitely
 Picked a 2 minute timeout as a generous allowance,
 given the entire script takes about that much time to run.
"""
import socket
socket.setdefaulttimeout(120)

#==============================================================================

def urljoin(*parts):
    url = parts[0]
    for part in parts[1:]:
        if not url.endswith('/'):
            url += '/'
        if part.startswith('/'):
            part = part[1:]
        url += part
    return url


def getLinks(url, startswith=None, endswith=None):

    html = ''
    results = []
    try:
        page = urllib2.urlopen(url)
        html = lxml.html.document_fromstring(page.read())
        page.close()
    except urllib2.HTTPError, err:
        if err.code == 404:
            return results
        else:
            raise

    for element, attribute, link, pos in html.iterlinks():
        if startswith:
            if link.startswith(startswith):
                results.append(link)
        elif endswith:
            if link.endswith(endswith):
                results.append(link)
    return results


def parseInfoFile(url, nightly=False):
    infotxt = urllib2.urlopen(url)
    content = infotxt.read()
    contents = content.splitlines()
    infotxt.close()
    results = {}
    bad_lines = []
    if nightly:
        results = {'buildID': contents[0], 'rev': contents[1]}
        if len(contents) > 2:
            results['altrev'] = contents[2]
    elif contents:
        results = {}
        for line in contents:
            if line == '':
                continue
            try:
                key, value = line.split('=')
                results[key] = value
            except ValueError:
                bad_lines.append(line)

    return results, bad_lines

def parseB2GFile(url, nightly=False, logger=None):
    """
      Parse the B2G manifest JSON file
      Example: {"buildid": "20130125070201", "update_channel": "nightly", "version": "18.0"}
      TODO handle exception if file does not exist
    """
    infotxt = urllib2.urlopen(url)
    results = json.load(infotxt)
    infotxt.close()

    # bug 869564: Return None if update_channel is 'default'
    if results['update_channel'] == 'default':
        logger.warning("Found default update_channel for buildid: %s. Skipping.", results['buildid'])
        return None

    # Default 'null' channels to nightly
    results['build_type'] = results['update_channel'] or 'nightly'

    # Default beta_number to 1 for beta releases
    if results['update_channel'] == 'beta':
        results['beta_number'] = results.get('beta_number', 1)

    return results


def getRelease(dirname, url):
    candidate_url = urljoin(url, dirname)
    builds = getLinks(candidate_url, startswith='build')
    if not builds:
        logger.info('No build dirs in %s' % candidate_url)
        return

    latest_build = builds.pop()
    build_url = urljoin(candidate_url, latest_build)
    info_files = getLinks(build_url, endswith='_info.txt')

    for f in info_files:
        info_url = urljoin(build_url, f)
        kvpairs, bad_lines = parseInfoFile(info_url)

        platform = f.split('_info.txt')[0]

        version = dirname.split('-candidates')[0]
        build_number = latest_build.strip('/')

        yield (platform, version, build_number, kvpairs, bad_lines)


def getNightly(dirname, url):
    nightly_url = urljoin(url, dirname)

    info_files = getLinks(nightly_url, endswith='.txt')
    for f in info_files:
        if 'en-US' in f:
            pv, platform = re.sub('\.txt$', '', f).split('.en-US.')
        elif 'multi' in f:
            pv, platform = re.sub('\.txt$', '', f).split('.multi.')
        else:
            ##return
            continue

        version = pv.split('-')[-1]
        info_url = urljoin(nightly_url, f)
        kvpairs, bad_lines = parseInfoFile(info_url, nightly=True)

        yield (platform, version, kvpairs, bad_lines)

def getB2G(dirname, url, backfill_date=None, logger=None):
    """
     Last mile of B2G scraping, calls parseB2G on .json
     Files look like:  socorro_unagi-stable_2013-01-25-07.json
    """
    url = '%s/%s' % (url, dirname)
    info_files = getLinks(url, endswith='.json')
    platform = None
    version = None
    repository = 'b2g-release'
    for f in info_files:
        # Pull platform out of the filename
        jsonfilename = os.path.splitext(f)[0].split('_')

        # Skip if this file isn't for socorro!
        if jsonfilename[0] != 'socorro':
            continue
        platform = jsonfilename[1]

        info_url = '%s/%s' % (url, f)
        kvpairs = parseB2GFile(info_url, nightly=True, logger=logger)

        # parseB2GFile() returns None when a file is
        #    unable to be parsed or we ignore the file
        if kvpairs is None:
            continue
        version = kvpairs['version']

        yield (platform, repository, version, kvpairs)


#==============================================================================
products = ['b2g', 'firefox', 'mobile', 'thunderbird', 'seamonkey']
base_url = 'http://ftp.mozilla.org/pub/mozilla.org'

class Scraper():

    def run(self, date):
        # record_associations
        results = {
            'releases': [],
            'nightly': [],
        }

        for product_name in products:
            logger.debug('scraping %s releases for date %s',
                product_name, date)
            if product_name == 'b2g':
                # FIXME seems to have moved
                continue
                #results['nightly'].append(self.scrapeB2G(product_name, date))
            else:
                results['releases'].append(self.scrapeReleases(product_name))
                results['nightly'].append(
                    self.scrapeNightlies(product_name, date))

        return results


    def scrapeReleases(self, product_name):
        results = {product_name: []}
        prod_url = urljoin(base_url, product_name, '')
        # releases are sometimes in nightly, sometimes in candidates dir.
        # look in both.
        for directory in ('nightly', 'candidates'):
            if not getLinks(prod_url, startswith=directory):
                logger.debug('Dir %s not found for %s',
                             directory, product_name)
                continue

            url = urljoin(base_url, product_name, directory, '')
            releases = getLinks(url, endswith='-candidates/')
            for release in releases:
                for info in getRelease(release, url):
                    platform, version, build_number, kvpairs, bad_lines = info
                    build_type = 'Release'
                    beta_number = None
                    repository = 'mozilla-release'
                    if 'b' in version:
                        build_type = 'Beta'
                        version, beta_number = version.split('b')
                        repository = 'mozilla-beta'
                    for bad_line in bad_lines:
                        logger.warning(
                            "Bad line for %s on %s (%r)",
                            release, url, bad_line
                        )
                    if kvpairs.get('buildID'):
                        build_id = kvpairs['buildID']

                        # TODO store data somewhere
                        results[product_name].append({
                            'version': version,
                            'platform': platform,
                            'build_id': build_id,
                            'build_type': build_type,
                            'beta_number': beta_number,
                            'repository': repository,
                        })
        return results

    def scrapeNightlies(self, product_name, date):
        results = {product_name: []}
        nightly_url = urljoin(base_url, product_name, 'nightly',
                              date.strftime('%Y'),
                              date.strftime('%m'),
                              '')
        dir_prefix = date.strftime('%Y-%m-%d')
        nightlies = getLinks(nightly_url, startswith=dir_prefix)
        for nightly in nightlies:
            for info in getNightly(nightly, nightly_url):
                platform, version, kvpairs, bad_lines = info
                for bad_line in bad_lines:
                    logger.warning(
                        "Bad line for %s (%r)",
                        nightly, bad_line
                    )
                build_type = 'Nightly'
                if version.endswith('a2'):
                    build_type = 'Aurora'
                if kvpairs.get('rev'):
                    repository = '/'.join(kvpairs['rev'].split('/')[:-2])
                    revision = kvpairs['rev'].split('/')[-1:][0]
                else:
                    repository = revision = None
                if kvpairs.get('buildID'):
                    build_id = kvpairs['buildID']
                    results[product_name].append({
                        'version': version,
                        'platform': platform,
                        'build_id': build_id,
                        'build_type': build_type,
                        'repository': repository,
                        'revision': revision,
                    })
        return results

    def scrapeB2G(self, product_name, date):
        results = {product_name: []}

        if not product_name == 'b2g':
            return
        b2g_manifests = urljoin(base_url, product_name,
                            'manifests')

        dir_prefix = date.strftime('%Y-%m-%d')
        version_dirs = getLinks(b2g_manifests, startswith='1.')
        for version_dir in version_dirs:
            prod_url = urljoin(b2g_manifests, version_dir,
                               date.strftime('%Y'), date.strftime('%m'))
            nightlies = getLinks(prod_url, startswith=dir_prefix)

            for nightly in nightlies:
                for info in getB2G(nightly, prod_url, backfill_date=None, logger=logger):
                    (platform, repository, version, kvpairs) = info
                    build_id = kvpairs['buildid']
                    build_type = kvpairs['build_type']
                    results[product_name].append({
                        'version': version,
                        'platform': platform,
                        'build_id': build_id,
                        'build_type': build_type,
                        'beta_number': kvpairs.get('beta_number', None),
                        'repository': repository,
                    })
                        

def main():
    scraper = Scraper()
    print json.dumps(scraper.run(datetime.date.today()))

if __name__ == '__main__':
    sys.exit(main())
