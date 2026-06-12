import onnxruntime as ort

MODEL = r"models\MediaPipeFaceLandmarkDetector.onnx"

session = ort.InferenceSession(
    MODEL,
    providers=["DmlExecutionProvider", "CPUExecutionProvider"],
)

print("Providers:", session.get_providers())
print("Inputs:")
for i in session.get_inputs():
    print(i.name, i.shape, i.type)

print("Outputs:")
for o in session.get_outputs():
    print(o.name, o.shape, o.type)