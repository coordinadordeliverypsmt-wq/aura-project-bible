"""Adaptador experimental: expone un modelo OpenVINO con la interfaz `session.run(None, args)` de onnxruntime."""
import time
import openvino as ov

class OVSession:
    def __init__(self, onnx_path, device="CPU", precision=None, cache_dir=None):
        core = ov.Core()
        if cache_dir: core.set_property({"CACHE_DIR": cache_dir})
        cfg = {"PERFORMANCE_HINT": "LATENCY"}
        if precision: cfg["INFERENCE_PRECISION_HINT"] = precision
        t = time.perf_counter()
        self.model = core.read_model(onnx_path)
        self.compiled = core.compile_model(self.model, device, cfg)
        self.compile_ms = round((time.perf_counter() - t) * 1000, 1)
        self.req = self.compiled.create_infer_request()
        self.inputs = [i.get_any_name() for i in self.compiled.inputs]
    def run(self, _names, args):
        feed = {k: v for k, v in args.items() if k in self.inputs}
        self.req.infer(feed)
        return [self.req.get_output_tensor(i).data.copy() for i in range(len(self.compiled.outputs))]
