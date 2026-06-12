import hid
import time

devices = [d for d in hid.enumerate() if d.get("usage_page") == 0xFF00]

for idx, d in enumerate(devices):
    print(idx, d.get("product_string"), d.get("usage_page"), d.get("usage"))

for idx in [3, 4, 5]:
    d = devices[idx]
    print("TESTANDO UGEE", idx)

    h = hid.device()
    h.open_path(d["path"])

    for report_id in range(0, 8):
        report = [report_id, 0, 30, 0, 0]
        h.write(report)
        print("sent", report)
        time.sleep(0.5)

    h.close()