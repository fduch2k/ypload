#!/usr/bin/python
import os
import sys
sys.path.append(
    os.path.join(
        os.path.dirname(sys.argv[0]),
        'lib/python2.7/'))
import mimetypes
import webbrowser

YD_APP_ID = 'cb76e6135dc34947bcf7620e1ab62e54'
YD_APP_SECRET = 'e4dba0141d734e1d89a5333c26a44f46'
KEY_FILE = os.path.expanduser('~/.ypload-key')

#!/usr/bin/env python

import requests
import urlparse
import BaseHTTPServer
XMLin = None


class YploadRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse.parse_qs(urlparse.urlparse(self.path).query)
        if "code" in parsed:
            YploadRequestHandler._code = parsed["code"][0]
        self.wfile.write("HTTP/1.0 200 OK")
        self.send_header("Date", self.date_time_string())
        self.send_header("Server", self.version_string())
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write("<html><body>\n")
        self.wfile.write("<script>var win = window.open('', '_self');win.close();</script>\n")
        self.wfile.write("Your code is %s" % YploadRequestHandler._code)
        self.wfile.write("</body></html>\n")
        self.finish()


class FileInfo(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    def fromJSON(self, j):
        self.href = j['d:href']
        prop = j['d:propstat']['d:prop']
        self.name = prop['d:displayname']
        self.length = prop['d:getcontentlength']
        self.modified = dateparse(prop['d:getlastmodified'])
        self.created = dateparse(prop['d:creationdate'])
        return self

    def json(self):
        return dict(
            name=self.name,
            length=self.length,
            modified=self.modified.strftime('%s')
        )

    def __str__(self):
        return '%(name)s (%(href)s) - %(length)s bytes' % self

    __repr__ = __str__


def getKey(YD_APP_ID, YD_APP_SECRET, keyfile):
    if os.path.isfile(keyfile):
        return open(keyfile, 'r').read()
    import webbrowser
    webbrowser.open_new('https://oauth.yandex.ru/authorize?response_type=code&client_id=' + YD_APP_ID)

    YploadRequestHandler._code = None
    httpd = BaseHTTPServer.HTTPServer(('', 8714), YploadRequestHandler)
    httpd.handle_request()

    if YploadRequestHandler._code:
        code = YploadRequestHandler._code
    else:
        code = raw_input('Input your code: ').strip()

    res = requests.post('https://oauth.yandex.ru/token', data=dict(
        grant_type='authorization_code',
        code=code,
        client_id=YD_APP_ID, client_secret=YD_APP_SECRET
    ), verify=False)
    if res.status_code != 200:
        raise Exception('Wrong code')
    key = res.json['access_token']
    with open(keyfile, 'w') as fl:
        fl.write(key)
    return key


class LoginAPI:
    MP = "https://login.yandex.ru/info?format=json"

    def __init__(self, key):
        self.key = "OAuth " + key

    def getInfo(self):
        rq = requests.get(self.MP, headers={
          'Authorization': self.key,
        }, verify=False)
        return rq.json


class DiskAPI:
    MP = 'https://webdav.yandex.ru'

    def __init__(self, key):
        self.key = "OAuth " + key

    def url(self, d):
        return self.MP + d

    def ls(self, directory='/'):
        if not XMLin:
            raise Exception('You need to install pyxml2obj and dateutil')
        rq = requests.request('PROPFIND', self.url(directory), headers={
            'Authorization': self.key,
            'Accept': '*/*',
            'Depth': '1'
        }, verify=False)
        res = []
        for line in XMLin(rq.text)['d:response']:
            res.append(FileInfo().fromJSON(line))
        return res

    def mkdir(self, path):
        rq = requests.request('MKCOL', self.url(path), headers={
            'Authorization': self.key,
            'Accept': '*/*',
        }, verify=False)
        return rq.status_code == 201

    def put(self, path, data, tp='application/binary'):
        rq = requests.request('PUT', self.url(path), data=data, headers={
            'Authorization': self.key,
            'Accept': '*/*',
            'Expect': '100-continue',
            'Content-Type': tp,
        }, verify=False)
        return rq.status_code == 201

    def publish(self, path):
        rq = requests.post(self.url(path) + '?publish', allow_redirects=False, headers={
            'Authorization': self.key,
            'Accept': '*/*'
        }, verify=False)
        if rq.status_code != 302:
            raise Exception('Wtf?')
        return rq.headers['location']


key = getKey(YD_APP_ID, YD_APP_SECRET, KEY_FILE)
api = DiskAPI(key)
api.mkdir('/JustShared')
api.mkdir('/JustShared/screenshots')


from Foundation import NSObject, NSLog
from AppKit import NSApplication, NSApp, NSWorkspace
from Cocoa import (NSEvent,
                   NSKeyDown, NSKeyDownMask, NSKeyUpMask,
                   NSCommandKeyMask)
from PyObjCTools import AppHelper

def screenshot():
    global api
    import tempfile, datetime
    handle, fname = tempfile.mkstemp(suffix='.png', prefix=datetime.datetime.now().isoformat())
    os.close(handle)
    os.system('screencapture -d -i ' + fname + '>/dev/null 2>&1')

    if os.path.isfile(fname) and os.path.getsize(fname) > 15:
        newname = '/JustShared/screenshots/' + os.path.basename(fname)
        try:
            tp, enc = mimetypes.guess_type(fname)
            if not tp:
                tp = 'application/facepalm'
            api.put(newname, open(fname, 'r').read(), tp=tp)
            durl = api.publish(newname)
            os.system('echo ' + durl + '| pbcopy')
            webbrowser.open(durl)
        except Exception, e:
            sys.stderr.write('Something wrong with %s\n%s\n' % (fname, e))
    else:
        sys.stderr.write('No such file %s\n' % fname)
    os.unlink(fname)

class SniffCocoa:
    def __init__(self):
        pass

    def createAppDelegate (self) :
        sc = self
        class AppDelegate(NSObject):
            def applicationDidFinishLaunching_(self, notification):
                mask = (NSKeyDownMask
                        | NSKeyUpMask)
                NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(mask, sc.handler)
        return AppDelegate

    def run(self):
        NSApplication.sharedApplication()
        delegate = self.createAppDelegate().alloc().init()
        NSApp().setDelegate_(delegate)
        self.workspace = NSWorkspace.sharedWorkspace()
        AppHelper.runEventLoop()

    def cancel(self):
        AppHelper.stopEventLoop()

    def handler(self, event):
        try:
            if event.type() == NSKeyDown:
                flags = event.modifierFlags()
                if (flags & NSCommandKeyMask) and \
                   event.keyCode() == 23 and \
                   event.charactersIgnoringModifiers() == u'%':
                   screenshot()
        except (Exception, KeyboardInterrupt) as e:
            NSLog(e);
            AppHelper.stopEventLoop()

if __name__ == '__main__':
    sc = SniffCocoa()
    sc.run()
