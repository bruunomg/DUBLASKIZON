"""Trechos PCM de uma cena; posições em frames, sem mistura ou reamostragem."""
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class AudioClip:
    id: int
    start: int
    pcm: bytes

    def end(self, frame_bytes):
        return self.start + len(self.pcm) // frame_bytes


def split_clip(clips, position, frame_bytes):
    for index, clip in enumerate(clips):
        if clip.start < position < clip.end(frame_bytes):
            offset = (position - clip.start) * frame_bytes
            new_id = max(c.id for c in clips) + 1
            return tuple(clips[:index]) + (replace(clip, pcm=clip.pcm[:offset]), AudioClip(new_id, position, clip.pcm[offset:])) + tuple(clips[index + 1:])
    raise ValueError('Clique dentro de um trecho do DUBLADO, fora das bordas e dos espaços vazios.')


def move_clip(clips, clip_id, position, frame_bytes):
    selected = next(c for c in clips if c.id == clip_id)
    position = max(0, int(position))
    if position == selected.start:
        return tuple(clips)
    others = sorted((c for c in clips if c.id != clip_id), key=lambda c: c.start)
    moving_right = position > selected.start
    leading_edge = position + len(selected.pcm) / frame_bytes if moving_right else position
    def insert_before(clip):
        midpoint = (clip.start + clip.end(frame_bytes)) / 2
        return leading_edge < midpoint if moving_right else leading_edge <= midpoint
    index = next((i for i, c in enumerate(others) if insert_before(c)), len(others))
    start = max(position, others[index-1].end(frame_bytes) if index else 0)
    moved = replace(selected, start=start)
    result = others[:index] + [moved]
    cursor = moved.end(frame_bytes)
    for clip in others[index:]:
        clip = replace(clip, start=max(clip.start, cursor))
        result.append(clip)
        cursor = clip.end(frame_bytes)
    return tuple(result)


def move_clip_group(clips, ids, delta, frame_bytes):
    """Translate selected clips rigidly; displace collisions without mixing PCM."""
    chosen=[c for c in clips if c.id in ids]
    if not chosen:return tuple(clips)
    delta=max(round(delta),-min(c.start for c in chosen))
    if not delta:return tuple(clips)
    moved=sorted((replace(c,start=c.start+delta) for c in chosen),key=lambda c:c.start)
    remaining=[];cursor=0
    for clip in sorted((c for c in clips if c.id not in ids),key=lambda c:c.start):
        start=max(cursor,clip.start);length=len(clip.pcm)//frame_bytes
        for obstacle in moved:
            if start<obstacle.end(frame_bytes) and start+length>obstacle.start:
                start=obstacle.end(frame_bytes)
        item=replace(clip,start=start);remaining.append(item);cursor=item.end(frame_bytes)
    return tuple(sorted(moved+remaining,key=lambda c:c.start))


def render_clips(clips, frame_bytes, sample_width, minimum_frames=0, maximum_bytes=256*1024*1024):
    end = max([minimum_frames] + [c.end(frame_bytes) for c in clips])
    if end * frame_bytes > maximum_bytes:
        raise ValueError('Esse deslocamento criaria um áudio muito grande. Use um intervalo menor.')
    silence = b'\x80' if sample_width == 1 else b'\x00'
    result = bytearray(silence * (end * frame_bytes))
    previous_end = 0
    for clip in sorted(clips, key=lambda c: c.start):
        if clip.start < previous_end or len(clip.pcm) % frame_bytes:
            raise ValueError('Trechos sobrepostos ou PCM desalinhado.')
        result[clip.start * frame_bytes:clip.end(frame_bytes) * frame_bytes] = clip.pcm
        previous_end = clip.end(frame_bytes)
    return bytes(result)


def paste_clip(clips, start, stop, pcm, frame_bytes):
    """Substitui a seleção sem unir os trechos restantes; a colagem é um novo trecho."""
    if start < 0 or stop < start or len(pcm) % frame_bytes:
        raise ValueError("Colagem ou seleção PCM inválida.")
    inserted_frames = len(pcm) // frame_bytes
    delta = inserted_frames - (stop - start)
    next_id = max((c.id for c in clips), default=0) + 1
    result = []
    for clip in clips:
        end = clip.end(frame_bytes)
        if end <= start:
            result.append(clip)
        elif clip.start >= stop:
            result.append(replace(clip, start=clip.start + delta))
        else:
            has_left = clip.start < start
            if has_left:
                result.append(replace(clip, pcm=clip.pcm[:(start - clip.start) * frame_bytes]))
            if end > stop:
                identifier = next_id if has_left else clip.id
                if has_left:
                    next_id += 1
                result.append(AudioClip(identifier, stop + delta, clip.pcm[(stop - clip.start) * frame_bytes:]))
    if pcm:
        result.append(AudioClip(next_id, start, bytes(pcm)))
    return tuple(sorted(result, key=lambda c: c.start))
