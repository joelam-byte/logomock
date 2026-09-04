"""Fetch the official Inkscape mirror archive in verified byte ranges for local QA."""
import concurrent.futures
import hashlib
from pathlib import Path
import time
import urllib.request

URL = 'https://twds.dl.sourceforge.net/project/inkscape/inkscape-1.4.2_2025-05-13_f4327f4-x64.7z'
SIZE = 97306337
DEST = Path(__file__).parent / 'inkscape-1.4.2.7z'
PARTS = Path(__file__).parent / 'inkscape-download-parts'
PARTS.mkdir(exist_ok=True)
CHUNK = 1024 * 1024


def fetch(index):
    start = index * CHUNK
    end = min(SIZE - 1, start + CHUNK - 1)
    path = PARTS / f'{index:04}.part'
    if path.exists() and path.stat().st_size == end-start+1:
        return path
    for attempt in range(10):
        try:
            req = urllib.request.Request(URL, headers={'Range':f'bytes={start}-{end}','User-Agent':'LogoMock-Local-QA'})
            with urllib.request.urlopen(req, timeout=90) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{SIZE}':
                    raise ValueError('Mirror did not honor exact byte range')
                payload = response.read()
            if len(payload) != end-start+1:
                raise ValueError('Incomplete download')
            path.write_bytes(payload)
            print(f'part {index + 1}/{(SIZE + CHUNK - 1)//CHUNK}', flush=True)
            return path
        except Exception:
            if attempt == 9:
                raise
            time.sleep(1 + attempt)


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(fetch,range((SIZE + CHUNK - 1)//CHUNK)))
    with DEST.open('wb') as output:
        for path in paths:
            output.write(path.read_bytes())
    assert DEST.stat().st_size == SIZE
    assert DEST.read_bytes()[:6] == b'7z\xbc\xaf\x27\x1c'
    print(DEST, hashlib.sha256(DEST.read_bytes()).hexdigest(), flush=True)
