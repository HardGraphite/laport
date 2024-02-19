#!/usr/bin/env python3

"""
LAN Portal
"""

import argparse
import dataclasses
import enum
import http.server
import os
import random
import re
import sys


@enum.unique
class PortalType(enum.Enum):
    FILE_SEND = 0
    FILE_RECV = 1
    TEXT_SEND = 2
    TEXT_RECV = 3


@dataclasses.dataclass
class PortalParam:
    type: PortalType
    data: str
    path: str


class HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    sys_version = '/0'
    server_version = 'LaPort/0.1'

    @staticmethod
    def make_handler_class(portal_param: PortalParam):
        def _class(request, client_address, server):
            return HTTPRequestHandler(request, client_address, server, portal_param)
        return _class

    def __init__(self, request, client_address, server, portal_param: PortalParam):
        self.portal_param = portal_param
        super().__init__(request, client_address, server)

    def do_GET(self):
        if self.path.lower() != self.portal_param.path.lower():
            self.send_error(404)
            return
        match self.portal_param.type:
            case PortalType.FILE_SEND:
                self.page_download_file()
            case PortalType.FILE_RECV:
                self.page_upload_file()
            case PortalType.TEXT_SEND:
                self.page_copy_text()
            case PortalType.TEXT_RECV:
                self.page_paste_text()

    def do_POST(self):
        if self.path.lower() != self.portal_param.path.lower():
            self.send_error(404)
            return
        match self.portal_param.type:
            case PortalType.FILE_RECV:
                self.page_upload_file_handle_post()
            case PortalType.TEXT_RECV:
                self.page_paste_text_handle_post()
            case _:
                self.send_error(403)

    def page_download_file(self):
        self.send_file(self.portal_param.data)

    def page_upload_file(self):
        self.send_html(b'''
<!DOCTYPE html>
<html>
<head>
    <title>LaPort - Upload</title>
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no" />
</head>
<body style="text-align: center; margin: 30vh 0 0;">
    <form enctype="multipart/form-data" method="post">
        <input name="file" type="file"/>
        <input type="submit"/>
    </form>
</body>
</html>''')

    def page_upload_file_handle_post(self):
        result = self.save_post_file(self.portal_param.data)
        if result:
            self.page_ok()

    def page_copy_text(self):
        self.send_text(self.portal_param.data)

    def page_paste_text(self):
        self.send_html(b'''
<!DOCTYPE html>
<html>
<head>
    <title>LaPort - Paste</title>
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no" />
</head>
<body style="margin: 10vh 15% 0;">
    <form enctype="multipart/form-data" method="post">
        <textarea name="text" required style="resize: none; height: 50vh; width: 100%;"></textarea>

        <div style="text-align: right; margin: 15px;"><input type="submit"/></div>
    </form>
</body>
</html>''')

    def page_paste_text_handle_post(self):
        out = sys.stdout
        log = sys.stderr # http.server log stream
        sep_line = '=' * 72 + '\n'
        log.write(sep_line)
        ok = self.dump_post_text(out)
        out.flush()
        log.write(sep_line)
        if ok:
            self.page_ok()
        else:
            log.write('!!! FAILED\n')

    def page_ok(self):
        self.send_html(b'''
<!DOCTYPE html>
<html>
<head>
    <title>LaPort</title>
    <meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no" />
</head>
<body style="text-align: center; margin: 30vh 0 0;">
    <div style="font-size: 120px; font-weight: bold; color: darkgreen;">
        &check;
    </div>
</body>
</html>''')

    def send_text(self, text: str | bytes, text_type='plain'):
        if isinstance(text, str):
            text = text.encode()
        self.send_response(200)
        self.send_header('Content-type', f'text/{text_type}; charset=utf-8')
        self.send_header('Content-Length', str(len(text)))
        self.end_headers()
        self.wfile.write(text)

    def send_html(self, html_code: str | bytes):
        self.send_text(html_code, 'html')

    def send_file(self, file_path: str):
        try:
            f = open(file_path, 'rb')
        except Exception:
            self.send_error(500)
            return
        import mimetypes
        import shutil
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        file_type = mimetypes.guess_type(file_path, False)[0] or ''
        self.send_response(200)
        self.send_header('Content-type', file_type)
        self.send_header('Content-Disposition', f'attachment; filename="{file_name}"')
        self.send_header('Content-Length', str(file_size))
        self.end_headers()
        try:
            shutil.copyfileobj(f, self.wfile)
        finally:
            f.close()

    def save_post_file(self, save_to_dir: str) -> str | None:
        content_type = self.headers['Content-Type']
        if not content_type:
            self.send_error(400)
            return
        boundary = content_type.split('=')[1].encode()
        remainbytes = int(self.headers['Content-Length'])
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            self.send_error(400)
            return
        line = self.rfile.readline()
        remainbytes -= len(line)
        filename = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line.decode())
        if not filename or len(filename) == 0:
            self.send_error(400, 'filename is unknown')
            return
        filename = os.path.basename(filename[0])
        out_file_path = os.path.join(save_to_dir, filename)
        line = self.rfile.readline()
        remainbytes -= len(line)
        line = self.rfile.readline()
        remainbytes -= len(line)
        try:
            out = open(out_file_path, 'wb')
        except IOError:
            self.send_error(500)
            return
        preline = self.rfile.readline()
        remainbytes -= len(preline)
        while remainbytes > 0:
            if remainbytes <= 0:
                self.send_error(400)
                return
            line = self.rfile.readline()
            remainbytes -= len(line)
            if boundary in line:
                preline = preline[0:-1]
                if preline.endswith(b'\r'):
                    preline = preline[0:-1]
                out.write(preline)
                break
            else:
                out.write(preline)
                preline = line
        out.close()
        return filename

    def dump_post_text(self, out) -> bool | None:
        content_type = self.headers['Content-Type']
        if not content_type:
            self.send_error(400)
            return
        boundary = content_type.split('=')[1].encode()
        remainbytes = int(self.headers['Content-Length'])
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            self.send_error(400)
            return
        line = self.rfile.readline()
        remainbytes -= len(line)
        line = self.rfile.readline()
        remainbytes -= len(line)
        preline = self.rfile.readline()
        remainbytes -= len(preline)
        while remainbytes > 0:
            if remainbytes <= 0:
                self.send_error(400)
                return
            line = self.rfile.readline()
            remainbytes -= len(line)
            if boundary in line:
                preline = preline[0:-1]
                if preline.endswith(b'\r'):
                    preline = preline[0:-1]
                out.write(preline.decode())
                if not preline.endswith(b'\n'):
                    out.write('\n')
                break
            else:
                out.write(preline.decode())
                preline = line
        return True


def show_qr_code(data: str):
    try:
        import pyqrcode
        code = pyqrcode.create(data.upper(), error='L', mode='alphanumeric')
        print(code.terminal(quiet_zone=1))
        return
    except Exception:
        pass
    print('(QR code not available)')


def show_service_url(host: str , port: int, path: str):
    url = f'http://{host}:{port}{path}'
    print('Visit:', url, ', or scan the QR code:')
    show_qr_code(url)


def run_server(portal_param: PortalParam, host: str , port: int):
    show_service_url(host, port, portal_param.path)
    server = http.server.HTTPServer(
        (host, port),
        HTTPRequestHandler.make_handler_class(portal_param)
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


def random_path(n: int) -> str:
    chars = ['/']
    for _ in range(n):
        chars.append(random.choice('0123456789abcdefghijklmnopqrstuvwxyz'))
    return ''.join(chars)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    ap.add_argument(
        '--addr', default='0.0.0.0',
        help='server address'
    )
    ap.add_argument(
        '--port', type=int, default=random.randint(10000, 65535),
        help='sever port'
    )
    ap.add_argument(
        '--path', default=random_path(4),
        help='service path'
    )
    g.add_argument(
        '-f', '--send-file', metavar='FILE',
        help='send (share) a file',
    )
    g.add_argument(
        '-d', '--recv-file', metavar='DIR',
        help='receive files to the directory',
    )
    g.add_argument(
        '-t', '--send-text', metavar='TEXT',
        help='send text from comannd-line or stdin (-)',
    )
    g.add_argument(
        '-p', '--recv-text', action='store_true',
        help='receive text and write to stdout',
    )
    args = ap.parse_args()
    srv_addr = args.addr
    srv_port = args.port
    srv_path = args.path
    if args.send_file:
        pp_type = PortalType.FILE_SEND
        pp_data = args.send_file
    elif args.recv_file:
        pp_type = PortalType.FILE_RECV
        pp_data = args.recv_file
    elif args.send_text:
        pp_type = PortalType.TEXT_SEND
        pp_data = sys.stdin.read() if args.send_text == '-' else args.send_text
    else:
        pp_type = PortalType.TEXT_RECV
        pp_data = ''
    del ap, g, args
    run_server(
        PortalParam(type=pp_type, data=pp_data, path=srv_path),
        srv_addr, srv_port,
    )


if __name__ == '__main__':
    main()
