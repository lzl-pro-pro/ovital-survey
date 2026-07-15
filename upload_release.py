# -*- coding: utf-8 -*-
"""上传发布到GitHub"""
import urllib.request, json, os

TOKEN_FILE = ".github_token"
VERSION_FILE = "version.txt"

if not os.path.exists(TOKEN_FILE):
    print("Put your GitHub token in .github_token file")
    exit(1)

token = open(TOKEN_FILE, encoding="utf-8").read().strip()
version = open(VERSION_FILE, encoding="utf-8").read().strip()
tag = "v" + version

# 读取发布说明
notes = ""
try:
    info = json.load(open("version.json", encoding="utf-8"))
    notes = info.get("notes", "")
except:
    pass

data = json.dumps({
    "tag_name": tag,
    "name": tag,
    "body": notes,
    "draft": False
}).encode("utf-8")

print("Creating release " + tag + "...")
req = urllib.request.Request(
    "https://api.github.com/repos/lzl-pro-pro/ovital-survey/releases",
    data=data,
    headers={"Authorization": "token " + token, "Accept": "application/vnd.github.v3+json"}
)
try:
    resp = urllib.request.urlopen(req)
    release = json.loads(resp.read())
except urllib.error.HTTPError as e:
    err = json.loads(e.read())
    if "already_exists" in str(err):
        print("Release exists, fetching...")
        req2 = urllib.request.Request(
            "https://api.github.com/repos/lzl-pro-pro/ovital-survey/releases/tags/" + tag,
            headers={"Authorization": "token " + token, "Accept": "application/vnd.github.v3+json"}
        )
        release = json.loads(urllib.request.urlopen(req2).read())
    else:
        raise

print("Release ID: " + str(release["id"]))

# Upload exe
exe_path = "dist/OvitalSurvey.exe"
size = os.path.getsize(exe_path)
print("Uploading " + str(round(size/1024/1024, 1)) + " MB...")

upload_url = release["upload_url"].replace("{?name,label}", "?name=OvitalSurvey.exe")
with open(exe_path, "rb") as f:
    exe_data = f.read()

req3 = urllib.request.Request(
    upload_url, data=exe_data,
    headers={"Authorization": "token " + token, "Content-Type": "application/octet-stream"}
)
resp3 = urllib.request.urlopen(req3)
result = json.loads(resp3.read())
print("Upload OK: " + result["browser_download_url"])
print("DONE - Users can auto-update to " + tag + "!")
