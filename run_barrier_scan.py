import sys, numpy as np, pandas as pd, math
sys.path.insert(0,"/home/user/trading")

d = pd.read_csv("data/crypto/btc_15m.csv.gz", index_col=0, parse_dates=True)
o,h,l,c,v = (d[k].to_numpy(float) for k in ("open","high","low","close","volume"))
n=len(d)

def atr(h,l,c,w=14):
    tr=np.maximum(h[1:]-l[1:], np.maximum(abs(h[1:]-c[:-1]), abs(l[1:]-c[:-1])))
    a=np.full(len(c),np.nan); a[1:]=pd.Series(tr).rolling(w).mean().to_numpy()
    return a
A=atr(h,l,c)

def barriers(stop_abs, rr, H=96):
    """0=perte, 1=gain, -1=non resolu. Stop d'abord si la meme barre touche les deux."""
    sl=c-stop_abs; tp=c+rr*stop_abs
    BIG=10**9
    hl=np.full(n,BIG); hw=np.full(n,BIG)
    idx=np.arange(n)
    for m in range(1,H+1):
        j=idx+m; ok=j<n
        jj=np.where(ok,j,0)
        loss= ok & (l[jj]<=sl) & (hl==BIG)
        hl[loss]=m
        win = ok & (h[jj]>=tp) & (hw==BIG)
        hw[win]=m
    out=np.full(n,-1,dtype=int)
    out[(hl<hw)]=0
    out[(hw<hl)]=1
    return out

# stop = 1.0 x ATR(14) M15, plus realiste qu'un % fixe
STOP=A.copy()
roll=lambda a,k: pd.Series(a).shift(k).to_numpy()
ema=lambda a,s: pd.Series(a).ewm(span=s).mean().to_numpy()
rsi14=(lambda:
   (lambda up,dn: 100-100/(1+up/np.where(dn==0,1e-12,dn)))(
     pd.Series(np.maximum(np.diff(c,prepend=c[0]),0)).ewm(alpha=1/14).mean().to_numpy(),
     pd.Series(np.maximum(-np.diff(c,prepend=c[0]),0)).ewm(alpha=1/14).mean().to_numpy()))()
rng=h-l; body=np.abs(c-o); lw=np.minimum(o,c)-l; uw=h-np.maximum(o,c)
hi20=pd.Series(h).rolling(20).max().shift(1).to_numpy()
lo20=pd.Series(l).rolling(20).min().shift(1).to_numpy()
e20=ema(c,20); e50=ema(c,50)

T={
 "baseline (toutes)":        np.ones(n,bool),
 "pin / rejet":              (rng>0)&(lw>=0.55*rng)&(c>=l+0.55*rng),
 "englobante":               (c>o)&(body>=0.5*rng)&(c>=np.maximum(roll(o,1),roll(c,1)))&(o<=np.minimum(roll(o,1),roll(c,1))),
 "balayage bas 20":          (l<lo20)&(c>lo20),
 "cassure haut 20":          (c>hi20),
 "RSI<30":                   (rsi14<30),
 "RSI<25":                   (rsi14<25),
 "RSI>70":                   (rsi14>70),
 "3 baisses d'affilee":      (c<roll(c,1))&(roll(c,1)<roll(c,2))&(roll(c,2)<roll(c,3)),
 "3 hausses d'affilee":      (c>roll(c,1))&(roll(c,1)>roll(c,2))&(roll(c,2)>roll(c,3)),
 "sous EMA20 + rebond":      (c<e20)&(c>roll(c,1)),
 "EMA20>EMA50 + repli":      (e20>e50)&(c<e20),
 "grande bougie (>2 ATR)":   (rng>2*A),
 "compression (<0.5 ATR)":   (rng<0.5*A),
 "pin + EMA20>EMA50":        (rng>0)&(lw>=0.55*rng)&(c>=l+0.55*rng)&(e20>e50),
 "balayage + EMA20>EMA50":   (l<lo20)&(c>lo20)&(e20>e50),
 "RSI<30 + EMA20>EMA50":     (rsi14<30)&(e20>e50),
}
split=int(n*0.65)
print(f"BTC M15  {n} barres  {d.index[0]:%Y-%m-%d} -> {d.index[-1]:%Y-%m-%d}")
print(f"IS = {d.index[0]:%Y-%m}..{d.index[split]:%Y-%m}  |  OOS = {d.index[split]:%Y-%m}..{d.index[-1]:%Y-%m}\n")

for rr in (3.0,4.0):
    res=barriers(STOP,rr)
    ok=(res>=0)&np.isfinite(A)&(A>0)
    base=res[ok & T["baseline (toutes)"]].mean()
    # frais: stop median en % -> levier a 2% de risque -> palier
    sp=np.nanmedian(STOP[ok]/c[ok]); lev=0.02/sp
    fee=0.0005 if lev<10 else (0.0006 if lev<25 else 0.0007)
    fir=2*fee/sp; be=(1+fir)/(1+rr)
    print(f"{'='*96}\nRR {rr:.0f}:1  stop=1xATR(14) median {sp*100:.3f}%  levier {lev:.0f}x  "
          f"frais {fee*100:.3f}%/cote = {fir:.2f}R  SEUIL {be:.1%}   (hasard {1/(1+rr):.1%}, marche {base:.1%})")
    print(f"{'declencheur':>26} {'n_IS':>7} {'P_IS':>7} {'n_OOS':>7} {'P_OOS':>7} {'vs marche OOS':>14} {'t_OOS':>7} {'net R':>8}")
    rows=[]
    for lab,m in T.items():
        if lab=="baseline (toutes)": continue
        mi=m&ok; a=mi.copy(); a[split:]=False; b=mi.copy(); b[:split]=False
        if a.sum()<200 or b.sum()<200: continue
        pi=res[a].mean(); po=res[b].mean(); nb=b.sum()
        base_o=res[ok&(np.arange(n)>=split)].mean()
        se=math.sqrt(base_o*(1-base_o)/nb)
        t=(po-base_o)/se
        net=po*rr-(1-po)*1-fir
        rows.append((net,lab,a.sum(),pi,nb,po,base_o,t))
    for net,lab,ni,pi,nb,po,bo,t in sorted(rows,reverse=True):
        print(f"{lab:>26} {ni:7d} {pi:6.1%} {nb:7d} {po:6.1%} {(po-bo)*100:+13.1f}pt {t:+7.2f} {net:+8.3f}")
    print()
