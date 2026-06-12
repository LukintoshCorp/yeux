import onnx
import onnxruntime as ort
import numpy as np
from onnx import helper, TensorProto


MODEL_PATH = "directml_test.onnx"


def create_model():
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 4])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1, 4])
    z = helper.make_tensor_value_info("z", TensorProto.FLOAT, [1, 4])

    node = helper.make_node(
        "Add",
        inputs=["x", "y"],
        outputs=["z"],
    )

    graph = helper.make_graph(
        [node],
        "DirectMLTestGraph",
        [x, y],
        [z],
    )

    model = helper.make_model(
    graph,
    producer_name="YeuxDirectMLTest",
    opset_imports=[helper.make_operatorsetid("", 25)],
)

    model.ir_version = 10
    onnx.save(model, MODEL_PATH)


def main():
    create_model()

    print("Providers disponíveis:", ort.get_available_providers())

    session = ort.InferenceSession(
        MODEL_PATH,
        providers=["DmlExecutionProvider", "CPUExecutionProvider"],
    )

    print("Provider usado:", session.get_providers())

    x = np.array([[1, 2, 3, 4]], dtype=np.float32)
    y = np.array([[10, 20, 30, 40]], dtype=np.float32)

    result = session.run(None, {"x": x, "y": y})

    print("Resultado:", result[0])


if __name__ == "__main__":
    main()