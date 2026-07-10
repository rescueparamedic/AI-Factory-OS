from .runtime import RealWorkerRuntime
def run_demo(root,request,**kwargs): return RealWorkerRuntime(root).run(request,**kwargs)
