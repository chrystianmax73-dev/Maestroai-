from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT))
from maestro.vision.screen_perception import ScreenPerception

def synthetic_scene(width=960,height=540):
    def pixel(x,y):
        if 120<x<840 and 70<y<490:
            if abs(x-480)<3 or abs(y-280)<3:return (235,235,235)
            if 735<x<752 and 260<y<277:return (245,245,245)
            if 260<x<300 and 180<y<235:return (205,45,35)
            if 650<x<690 and 330<y<385:return (35,75,205)
            return (42,145,62)
        return (28,30,34)
    return width,height,pixel

def test_detects_field_and_scene():
    w,h,p=synthetic_scene(); r=ScreenPerception().analyze(w,h,p); assert r.field_confidence>.55 and r.scene_confidence>.45 and r.white_line_ratio>0 and not r.uncertain

def test_detects_two_uniform_color_signals():
    w,h,p=synthetic_scene(); r=ScreenPerception().analyze(w,h,p); assert r.team_color_a>0 and r.team_color_b>0

def test_non_scene():
    r=ScreenPerception().analyze(960,540,lambda x,y:(35,35,40)); assert r.field_confidence==0 and r.ball_confidence==0 and r.uncertain

def test_deterministic():
    w,h,p=synthetic_scene(); assert ScreenPerception().analyze(w,h,p).to_dict()==ScreenPerception().analyze(w,h,p).to_dict()

def test_rgba_adapter():
    w,h=32,18; raw=bytearray()
    for y in range(h):
        for x in range(w): raw.extend((42,145,62,255) if x<28 and y>2 else (20,20,20,255))
    r=ScreenPerception().analyze_rgba_bytes(w,h,raw); assert r.width==w and r.height==h and r.field_confidence>0

if __name__=="__main__":
    test_detects_field_and_scene(); test_detects_two_uniform_color_signals(); test_non_scene(); test_deterministic(); test_rgba_adapter(); print("=== TODOS OS TESTES DE PERCEPÇÃO PASSARAM ===")
