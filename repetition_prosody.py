"""Original-derived accents for bounded recovery of repeated words.

Embedded in the inference subprocess; no neural dependencies in the GUI.
"""
PROFILE_CODE = r'''
def reference_repetition_profile(reference, count, start_fraction=0., end_fraction=1.):
    import numpy as np
    neutral=[{'gain':1.,'rate':1.,'pause':.15} for _ in range(count)]
    if reference is None or count<1:return neutral
    try:
        import soundfile as sf
        pcm,sr=sf.read(reference,always_2d=True,dtype='float32')
        pcm=pcm.mean(axis=1)
        pcm=pcm[round(len(pcm)*start_fraction):round(len(pcm)*end_fraction)]
        hop=max(1,round(sr*.02))
        levels=np.array([np.sqrt(np.mean(pcm[i:i+hop]**2)) for i in range(0,len(pcm),hop)])
        if len(levels)<3 or not np.isfinite(levels).all() or levels.max()<1e-5:return neutral
        # A low gate preserves softer accents; isolated samples never set the gate.
        threshold=max(1e-6,float(np.percentile(levels,90))*.12)
        mask=levels>threshold
        # Bridge small phonetic gaps, not actual pauses.
        for i in range(1,len(mask)-1):
            if mask[i-1] and mask[i+1]:mask[i]=True
        edges=np.diff(np.r_[False,mask,False].astype(int))
        spans=[(a,b) for a,b in zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)) if b-a>=2]
        if not spans:return neutral
        durations=np.array([(b-a)*.02 for a,b in spans])
        strengths=np.array([np.sqrt(np.mean(levels[a:b]**2)) for a,b in spans])
        pauses=np.array([max(0.,(spans[i+1][0]-b)*.02) if i+1<len(spans) else .08 for i,(a,b) in enumerate(spans)])
        positions=np.linspace(0,len(spans)-1,count)
        # Map the progression, rather than claim word-level alignment in another language.
        gain=np.clip(np.interp(positions,np.arange(len(spans)),strengths)/max(float(np.median(strengths)),1e-6),.65,1.35)
        length=np.clip(np.interp(positions,np.arange(len(spans)),durations)/max(float(np.median(durations)),.04),.8,1.25)
        pause=np.clip(np.interp(positions,np.arange(len(spans)),pauses),.05,.35)
        return [{'gain':float(g),'rate':float(1/l),'pause':float(p)} for g,l,p in zip(gain,length,pause)]
    except (OSError,ValueError,RuntimeError,ImportError):return neutral

def expressive_repetition_clips(takes, profile, sampling_rate):
    import numpy as np
    import librosa
    result=[]
    for index,accent in enumerate(profile):
        # Alternate independently generated takes. Stretch preserves vocal pitch.
        unit=np.asarray(takes[index%len(takes)],dtype=np.float32).copy()
        # Timestamp boundaries may include silence; trim only the very quiet
        # outer margins, preserving 30 ms around every audible sample.
        magnitude=np.abs(unit)
        active=np.flatnonzero(magnitude>max(1e-6,float(magnitude.max())*.01))
        if active.size:
            margin=round(sampling_rate*.03)
            unit=unit[max(0,int(active[0])-margin):min(len(unit),int(active[-1])+margin+1)]
        rate=accent['rate']
        if abs(rate-1.)>.015 and len(unit)>512:
            unit=librosa.effects.time_stretch(unit,rate=rate)
        unit*=accent['gain']
        peak=float(np.max(np.abs(unit)))
        if peak>.98:unit*=.98/peak
        if index:result.append(np.zeros(round(sampling_rate*profile[index-1]['pause']),dtype=np.float32))
        result.append(unit)
    return result
'''
exec(PROFILE_CODE)
