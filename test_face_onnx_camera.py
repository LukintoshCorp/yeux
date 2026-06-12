import time
import cv2
import numpy as np
import onnxruntime as ort

MODEL = r"models\MediaPipeFaceLandmarkDetector.onnx"

session = ort.InferenceSession(
    MODEL,
    providers=["DmlExecutionProvider", "CPUExecutionProvider"],
)

input_name = session.get_inputs()[0].name

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
cap.set(cv2.CAP_PROP_FPS, 30)

print("ONNX DirectML draw test. Aperte Q para sair.")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    h, w = frame.shape[:2]

    img = cv2.resize(frame, (192, 192))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2, 0, 1))
    img = np.expand_dims(img, axis=0)

    start = time.perf_counter()
    scores, landmarks = session.run(None, {input_name: img})
    latency_ms = (time.perf_counter() - start) * 1000

    score = float(scores[0])
    pts = landmarks[0]

    # desenha alguns landmarks
    for p in pts[::6]:
        x = int(p[0] * w)
        y = int(p[1] * h)

        if 0 <= x < w and 0 <= y < h:
            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)

    cv2.putText(
        frame,
        f"Score: {score:.3f} | ONNX: {latency_ms:.2f} ms",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
    )

    cv2.imshow("Yeux ONNX DirectML Landmarks", frame)

    if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
        break

cap.release()
cv2.destroyAllWindows()