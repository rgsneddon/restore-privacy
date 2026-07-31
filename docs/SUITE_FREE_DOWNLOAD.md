# Suite free download

Restore Privacy Suite **v1.0.0** installers are free. Residual Connect still
needs a KEYGEN — monthly licence from **£3.00** on the live site.

Download links sit on the public homepage (and on the open `public_site/` Pages
export). After checkout, paste the KEYGEN from your fulfilment email, then
Connect.

Live free route on the status host: `/suite/download?platform=…`  
Public Pages point those buttons at restoreprivacy.online so binaries stay
on the fulfilment host.

Operators building packages:

```bash
python3 scripts/build_suite_1.0.0.py
python3 scripts/host_paid_assets_vps.py --stage --upload --version 1.0.0 --force
python3 scripts/build_public_pages.py
```
