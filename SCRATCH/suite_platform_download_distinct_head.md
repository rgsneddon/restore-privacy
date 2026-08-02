# Suite platform links — distinct responses (HEAD + GET)

Date: 2026-08-02

## Symptom
"The response is the same for all platform links."

## Live GET (already correct)
`GET /suite/download?platform={plat}&free_direct=1` → 302 to distinct Helsinki filenames:

| platform | Content-Length | magic | filename |
|----------|----------------|-------|----------|
| windows  | 38859788 | MZ (PE) | restore-privacy-client-1.0.8-windows-x64-setup.exe |
| android  | 85170634 | PK (zip/apk) | restore-privacy-client-1.0.8-android.apk |
| macos    | 27765505 | PK (zip) | restore-privacy-client-1.0.8-macos.zip |
| ios      | 13202044 | PK (zip) | restore-privacy-client-1.0.8-ios.zip |
| linux    | 14636754 | 1f8b (gzip) | restore-privacy-client-1.0.8-linux-x64.tar.gz |

## Bug: HEAD was identical 501 for every platform
Status host (`status_page/app.py`) only implemented `do_GET`. Python BaseHTTP
returns **501 Unsupported method** for HEAD — same body for windows/android/macos/ios/linux.
`curl -I` and many link checkers therefore looked like “same response for all platforms.”

Helsinki `node/serve_paid_assets.py` had the same gap (HEAD → 501 after redirect).

## Fix
- `status_page/app.py`: `do_HEAD` → `do_GET`; `_write_body` / stream paths skip body on HEAD
- `node/serve_paid_assets.py`: `do_HEAD` → `do_GET`; `_send_file` / `_send_json` skip body on HEAD
- Tests: `tests/test_suite_download_head_per_platform.py`
- Structural: `tests/test_host_delivery.py` asserts do_HEAD present

## Verify
```
python3 -m unittest tests.test_suite_download_head_per_platform tests.test_host_delivery -v
```

After Render redeploy + Helsinki serve restart, `curl -I` per platform should 302
with distinct `Location` basenames (status) and 200 + distinct `Content-Disposition`
(Helsinki signed URL).
