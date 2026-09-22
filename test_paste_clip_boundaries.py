from audio_clip_timeline import AudioClip, paste_clip, render_clips
import random

# Every insertion/replacement across clips and gaps must match PCM splice exactly.
rng=random.Random(41)
for width in (1,2,3,4):
 for channels in (1,2):
  fb=width*channels
  clips=(AudioClip(1,2,b'a'*4*fb),AudioClip(2,8,b'b'*6*fb),AudioClip(3,14,b'c'*3*fb))
  raw=render_clips(clips,fb,width,20)
  for _ in range(300):
   start=rng.randrange(21);stop=rng.randrange(start,21)
   pcm=b'd'*rng.randrange(1,7)*fb
   result=paste_clip(clips,start,stop,pcm,fb)
   expected=raw[:start*fb]+pcm+raw[stop*fb:]
   assert render_clips(result,fb,width,len(expected)//fb)==expected
   assert len(set(c.id for c in result))==len(result)
   for original in clips:
    if original.end(fb)<=start or original.start>=stop:
     kept=next(c for c in result if c.id==original.id)
     assert kept.pcm==original.pcm
# An insertion inside a clip preserves both sides and all following boundaries.
clips=(AudioClip(1,0,b'aaaa'),AudioClip(2,4,b'bbbb'),AudioClip(3,8,b'cccc'))
result=paste_clip(clips,2,2,b'XX',1)
assert [c.pcm for c in result]==[b'aa',b'XX',b'aa',b'bbbb',b'cccc']
assert [c.start for c in result]==[0,2,4,6,10]
assert [c.id for c in result][-2:]==[2,3]
print('OK: 2400 PCM splices, gaps, selection replacement, stereo/8-32bit, preserved boundaries and unique clip IDs.')
