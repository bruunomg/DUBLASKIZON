from types import SimpleNamespace
from unittest.mock import patch
import personalized_dubbing_tab as module
keys=['CAP01/Sally/a','CAP02/Sally/a','CAP02/Sally/sub/b','CAP03/Outro/a','CAP03/Sally2/a','CAP03/Outro/Sally','CAP04/sally/c']
assert module.filter_personalized_scenes(keys,names=['SALLY'])==[keys[i] for i in (0,1,2,6)]
assert module.filter_personalized_scenes(keys,folders=['CAP02/Sally'])==keys[1:3]
assert module.filter_personalized_scenes(keys,folders=['CAP02/Sally','CAP02/Sally/sub'],names=['sally'])==[keys[i] for i in (0,1,2,6)]
assert module.filter_personalized_scenes(keys,folders=['.'])==keys
assert module.filter_personalized_scenes(keys,names=['missing'])==[]
a=module.PersonalizedDubbingApp.__new__(module.PersonalizedDubbingApp)
a.audio_by_stem={k:k for k in keys};a.text_by_stem={k:k for k in keys[:-1]};a.scope_folders={'CAP02/Sally'};a.scope_names={'Sally'}
a.running=False;a.scene_review=None;a.populate_scenes=lambda:None;selected=[];a.scene_list=SimpleNamespace(selection_set=lambda *args:selected.append(args),selection_clear=lambda *args:selected.clear());a.scope_status=SimpleNamespace(set=lambda value:None)
a._apply_scene_scope(True);assert a.stems==keys[:3] and selected
# Reload reapplies the same scope; newly discovered matching scenes join it.
a.audio_by_stem['CAP05/Sally/new']='wav';a.text_by_stem['CAP05/Sally/new']='txt';a._apply_scene_scope();assert a.stems==keys[:3]+['CAP05/Sally/new']
a.clear_scene_scope();assert len(a.stems)==7 and not a.scope_names and not a.scope_folders
print('OK: folder subtree, repeated character names across chapters, exact case-insensitive names, no duplicate scenes, TXT pairing, persistent reload scope and clear filter.')
