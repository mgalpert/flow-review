import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/flow-review-canvas'
spec=importlib.util.spec_from_file_location('builder',SKILL/'scripts/build_canvas.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class BuilderTests(unittest.TestCase):
    def setUp(self):self.model=json.loads((SKILL/'assets/example.json').read_text())
    def test_independent_flow_count_and_connections(self):
        model=builder.validate(self.model)
        self.assertEqual(len(model['flows']),3)
        ids={s['id'] for f in model['flows'] for s in f['steps']}
        self.assertTrue(all(e['from'] in ids and e['to'] in ids for e in model['edges']))
    def test_dangling_feedback_is_preserved_as_an_error(self):
        self.model['annotations']=[{'id':'comment-1','type':'comment','text':'Keep my feedback','screenId':'removed-screen'}]
        with self.assertRaisesRegex(ValueError,'missing screen'):builder.validate(self.model)
    def test_bad_wire_and_duplicate_screen_are_rejected(self):
        invalid=copy.deepcopy(self.model);invalid['edges'][0]['to']='missing'
        with self.assertRaisesRegex(ValueError,'unknown screen'):builder.validate(invalid)
        self.model['flows'][1]['steps'][0]['id']='welcome'
        with self.assertRaisesRegex(ValueError,'unique'):builder.validate(self.model)
    def test_embedded_script_text_remains_data_and_output_is_protected(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);source=d/'model.json';out=d/'board.html'
            self.model['flows'][0]['steps'][0]['title']='A literal </script><script>not code</script>'
            source.write_text(json.dumps(self.model))
            args=[sys.executable,str(SKILL/'scripts/build_canvas.py'),'--model',str(source),'--out',str(out)]
            subprocess.run(args,check=True,capture_output=True)
            self.assertEqual(builder.embedded(out.read_text(),'data')['flows'][0]['steps'][0]['title'],self.model['flows'][0]['steps'][0]['title'])
            before=out.read_bytes();result=subprocess.run(args,capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertEqual(out.read_bytes(),before)
    def test_returned_notes_and_geometry_survive_rebuild(self):
        model=builder.validate(self.model);model['positions']['welcome']={'x':333,'y':444,'w':350}
        model['annotations']=[{'id':'note-1','type':'note','text':'Do not lose this','x':10,'y':20}]
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);source=d/'feedback.json';out=d/'revision.html';source.write_text(json.dumps(model))
            subprocess.run([sys.executable,str(SKILL/'scripts/build_canvas.py'),'--model',str(source),'--out',str(out)],check=True,capture_output=True)
            result=builder.embedded(out.read_text(),'data')
            self.assertEqual(result['annotations'],model['annotations']);self.assertEqual(result['positions']['welcome'],model['positions']['welcome'])
    def test_icons_embed_without_external_files(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'example.png').write_bytes(b'image bytes')
            self.assertEqual(builder.icon_data({'Example':'example.png'},d)['Example'],'data:image/png;base64,aW1hZ2UgYnl0ZXM=')

if __name__=='__main__':unittest.main()
