import time, numpy as np, openvino as ov
try:
    import openvino.opset13 as op
except ImportError:
    import openvino.runtime.opset13 as op
x = op.parameter([1, 192, 400], np.float32, name="x")
w = op.constant(np.random.rand(192, 192, 3).astype(np.float32))
y = op.convolution(x, w, [1], [3], [3], [3])   # conv1d dilatada, como en HiFi-GAN
m = ov.Model([op.relu(y)], [x]); c = ov.Core()
for dev in ("CPU", "GPU"):
    try:
        cm = c.compile_model(m, dev); r = cm.create_infer_request(); a = np.random.rand(1,192,400).astype(np.float32)
        r.infer({"x": a}); t = time.perf_counter()
        for _ in range(20): r.infer({"x": a})
        print(dev, "OK", round((time.perf_counter()-t)/20*1000, 2), "ms/infer", flush=True)
    except Exception as e: print(dev, "FALLA", str(e).splitlines()[-1][:160], flush=True)
