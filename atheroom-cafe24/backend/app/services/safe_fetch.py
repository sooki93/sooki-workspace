"""Bounded HTTPS-only image download, public-IP validation and DNS pinning."""
import http.client, socket, ssl, ipaddress
from urllib.parse import urlparse,urljoin
MAX=5*1024*1024
class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,ip): super().__init__(host,timeout=12,context=ssl.create_default_context());self.ip=ip
    def connect(self):
        sock=socket.create_connection((self.ip,443),self.timeout)
        self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
def fetch_image(url):
    if url.startswith('//'): url='https:'+url
    for _ in range(3):
        parsed=urlparse(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (443,None): raise ValueError('unsafe URL')
        addresses={a[4][0] for a in socket.getaddrinfo(parsed.hostname,443,type=socket.SOCK_STREAM)}
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses): raise ValueError('nonpublic host')
        conn=PinnedHTTPS(parsed.hostname,sorted(addresses)[0])
        try:
            conn.request('GET',(parsed.path or '/')+('?' + parsed.query if parsed.query else ''),headers={'User-Agent':'AttheroomStudio/1.0','Accept':'image/*'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308): url=urljoin(url,response.getheader('Location',''));continue
            if response.status!=200 or not response.getheader('Content-Type','').lower().startswith('image/'): raise ValueError('not image')
            raw=response.read(MAX+1)
            if len(raw)>MAX: raise ValueError('too large')
            return raw
        finally: conn.close()
    raise ValueError('redirect limit')
