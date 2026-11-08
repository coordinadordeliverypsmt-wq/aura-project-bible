import sys, time, numpy as np, openvino as ov
VOZ="/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"; dev=sys.argv[1]
T=time.perf_counter
def p(*a): print(f"[{T()-t0:7.1f}s]",*a,flush=True)
t0=T(); c=ov.Core(); m=c.read_model(VOZ); p("read", [(i.get_any_name(), i.get_partial_shape()) for i in m.inputs])
cm=c.compile_model(m, dev, {"PERFORMANCE_HINT":"LATENCY"}); p("compiled")
r=cm.create_infer_request()
ids=np.array([[1,0,20,0,59,0,120,0,2]],dtype=np.int64)
for k in range(3):
    t=T(); r.infer({"input":ids,"input_lengths":np.array([ids.shape[1]],dtype=np.int64),"scales":np.array([0.667,1,0.8],dtype=np.float32)})
    p(f"infer{k} {1000*(T()-t):.0f} ms out={r.get_output_tensor(0).shape}")
