import sys, time, numpy as np, openvino as ov, collections
VOZ="/media/majo1230/AURORA_EXT/piper_voices/es_MX-ald-medium.onnx"; dev=sys.argv[1]
T=time.perf_counter
c=ov.Core(); cm=c.compile_model(c.read_model(VOZ), dev, {"PERFORMANCE_HINT":"LATENCY","PERF_COUNT":True})
r=cm.create_infer_request(); ids=np.array([[1,0,20,0,59,0,120,0,2]],dtype=np.int64)
for k in range(3):
    t=T(); r.infer({"input":ids,"input_lengths":np.array([9],dtype=np.int64),"scales":np.array([0.0,1,0.0],dtype=np.float32)})
    print(f"infer{k} {1000*(T()-t):.0f} ms out={r.get_output_tensor(0).shape}",flush=True)
agg=collections.Counter()
for pi in r.get_profiling_info(): agg[(pi.node_type, pi.exec_type)] += pi.real_time.total_seconds()*1000
for (nt,et),ms in agg.most_common(8): print(f"  {ms:9.1f} ms  {nt:22s} {et}")
