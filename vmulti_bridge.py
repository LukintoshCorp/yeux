import hid
import time

TARGET_USAGE_PAGE = 0xFF00

device_info = None

for d in hid.enumerate():
    usage_page = d.get("usage_page")
    product = d.get("product_string")

    if usage_page == TARGET_USAGE_PAGE:
        print("FOUND:", product)
        device_info = d
        break

if not device_info:
    print("VMulti device not found")
    exit()

h = hid.device()
h.open_path(device_info["path"])

print("Connected!")

# mouse report:
# [reportId, buttons, x, y, wheel]
#
# x/y = signed byte (-127 a 127)

while True:
    # move diagonal
    report = [1, 0, 5, 5, 0]

    try:
        h.write(report)
        print("sent", report)
    except Exception as e:
        print("write failed:", e)

    time.sleep(0.01)