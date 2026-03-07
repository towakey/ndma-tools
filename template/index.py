import sys
import io

import cgi
import cgitb

cgitb.enable()
form = cgi.FieldStorage()

mode=form.getfirst("mode","")

# これを使用しないと日本語が文字化けする
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

if __name__ == '__main__':
    # WEB表示
    print("Content-Type: text/html; charset=utf-8\n\n")
    print("日本語")

    # ファイルとして出力してダウンロードさせる
    # ShiftJIS化
    sys.stdin.reconfigure(encoding="cp932")
    sys.stdout.reconfigure(encoding="cp932")
    sys.stderr.reconfigure(encoding="cp932")
    print ("Content-Type: application/octet-stream; ")

    print ("Content-Disposition: attachment; filename=download_file.txt\n")
    print ("ここにダウンロードさせたいもの")