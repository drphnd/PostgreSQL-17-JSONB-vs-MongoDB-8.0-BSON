import sys
prev=None; n=0; gaps=[]; jumps=[]
for l in open(sys.argv[1]):
    p=l.split()
    if len(p)!=2: continue
    w,m=float(p[0]),float(p[1]); n+=1
    if prev:
        dm=m-prev[1]; dw=w-prev[0]
        if dm>1.0: gaps.append((round(prev[0]),round(dm,2)))
        if abs(dw-dm)>0.5: jumps.append((round(w),round(dw-dm,2)))
    prev=(w,m)
print("baris:",n,"| jeda proses >1 s:",len(gaps),"| lompatan jam dinding >0.5 s:",len(jumps))
print("jeda:",gaps[:10]); print("lompatan:",jumps[:10])
