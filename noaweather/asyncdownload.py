import threading
import Queue
import urllib2
import zlib
import os
import subprocess

class AsyncDownload():
    '''
    Asyncronous download
    '''
    def __init__(self, conf, url, cachefile, callback = False, min_size = 500):
        
        self.callback = callback
        self.q = Queue.Queue()
        self.dirsep = conf.dirsep[:]
        cachepath = conf.cachepath[:]
        self.wgrib2bin = conf.wgrib2bin[:]
        self.cancel = threading.Event()
        self.min_size = min_size
        
        self.t = threading.Thread(target = self.run, args = (url, cachepath, cachefile))
        self.t.start()
        
    def run(self, url, cachepath, cachefile):
        filepath = os.sep.join([cachepath, cachefile])
        tempfile = filepath + '.tmp'
        
        print "Dowloading: %s" % (url)
        
        # Request gzipped file
        request = urllib2.Request(url)
        request.add_header('Accept-encoding', 'gzip,deflate')
        
        try:
            response = urllib2.urlopen(request)
        except urllib2.URLError:
            return
        
        # Check for gzziped file
        isGzip = response.headers.get('content-encoding', '').find('gzip') >= 0
        gz = zlib.decompressobj(16+zlib.MAX_WBITS)
        of = open(tempfile, 'w')
        
        try:
            while True:
                if self.cancel.isSet():
                    raise Exception()
                data = response.read(1024*128)
                if not data:
                    break
                if isGzip:
                    data = gz.decompress(data)
                of.write(data)
        except Exception:
            if os.path.exists(tempfile):
                os.remove(tempfile)
            self.q.put(False)
        
        of.close()
        
        if os.path.exists(tempfile) and os.path.getsize(tempfile) > self.min_size:
            # Downloaded
            if filepath.split('.')[-1] == 'grib2':
                # Uncompress grib2 file
                subprocess.call([self.wgrib2bin, tempfile, '-set_grib_type', 'simple', '-grib_out', filepath])
                os.remove(tempfile)
            else:
                os.rename(tempfile, filepath)    
           
            # Call callback if defined otherwise put the file on the queue
            if self.callback:
                self.callback(cachefile)
            else:
                self.q.put(cachefile)
        else:
            # File to small, remove file.
            if os.path.exists(tempfile):
                os.remove(tempfile)
            self.q.put(False)

    def die(self):
        if self.t.is_alive():
            self.cancel.set()
            self.t.join()
