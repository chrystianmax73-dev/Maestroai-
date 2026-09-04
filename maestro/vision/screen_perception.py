"""Percepção visual determinística e leve para frames de futebol."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Callable, Dict, Tuple

@dataclass(frozen=True)
class PerceptionResult:
    width:int; height:int; field_confidence:float; field_bbox:Tuple[float,float,float,float]
    white_line_ratio:float; bright_blob_ratio:float; dark_blob_ratio:float
    team_color_a:float; team_color_b:float; ball_x:float; ball_y:float
    ball_confidence:float; scene_confidence:float; uncertain:bool
    def to_dict(self)->Dict[str,object]:
        d=asdict(self); d["field_bbox"]=list(self.field_bbox); return d

class ScreenPerception:
    def __init__(self,sample_cols=48,sample_rows=27):
        self.sample_cols=max(8,int(sample_cols)); self.sample_rows=max(8,int(sample_rows))
    @staticmethod
    def _green(r,g,b): return g>=65 and g>r*1.10 and g>b*1.08 and g-r>=12
    @staticmethod
    def _white(r,g,b): return min(r,g,b)>=190 and max(r,g,b)-min(r,g,b)<=42
    @staticmethod
    def _bright(r,g,b): return min(r,g,b)>=205
    @staticmethod
    def _dark(r,g,b): return max(r,g,b)<=55
    @staticmethod
    def _color_a(r,g,b): return r>=115 and r>g*1.28 and r>b*1.20
    @staticmethod
    def _color_b(r,g,b): return b>=105 and b>r*1.18 and b>g*1.08

    def analyze(self,width,height,pixel_at:Callable[[int,int],Tuple[int,int,int]]):
        width=max(1,int(width)); height=max(1,int(height)); green=white=bright=dark=a=b=0; samples=0; bright_points=[]; green_points=[]
        for gy in range(self.sample_rows):
            y=min(height-1,int((gy+.5)*height/self.sample_rows))
            for gx in range(self.sample_cols):
                x=min(width-1,int((gx+.5)*width/self.sample_cols)); r,g,bv=pixel_at(x,y); samples+=1
                if self._green(r,g,bv): green+=1; green_points.append((x,y))
                if self._white(r,g,bv): white+=1
                if self._bright(r,g,bv): bright+=1; bright_points.append((x,y))
                if self._dark(r,g,bv): dark+=1
                if self._color_a(r,g,bv): a+=1
                if self._color_b(r,g,bv): b+=1
        q=lambda n:n/float(max(1,samples)); field=min(1.0,q(green)*1.55); wr=q(white); br=q(bright); dr=q(dark); ar=q(a); bb=q(b)
        bbox=(0,0,0,0)
        if green_points:
            xs=[p[0] for p in green_points]; ys=[p[1] for p in green_points]; bbox=(min(xs)/width,min(ys)/height,max(xs)/width,max(ys)/height)
        bx=by=bc=0.0
        if bright_points and field>=.35:
            best=None; radius=max(1,width//12)
            for x,y in bright_points:
                neighbors=sum(1 for ox,oy in bright_points if abs(x-ox)<=radius and abs(y-oy)<=max(1,height//12))
                score=(1/max(1,neighbors))*(.35+field*.65)
                if best is None or score>best[0]: best=(score,x,y)
            if best: bc=min(1.0,best[0]*2.2); bx=best[1]/width; by=best[2]/height
        scene=min(1.0,field*.75+min(1,wr*8)*.15+min(1,(ar+bb)*8)*.10)
        return PerceptionResult(width,height,round(field,4),tuple(round(v,4) for v in bbox),round(wr,4),round(br,4),round(dr,4),round(ar,4),round(bb,4),round(bx,4),round(by,4),round(bc,4),round(scene,4),scene<.45 or field<.30)

    def analyze_rgba_bytes(self,width,height,data,row_stride=None,pixel_stride=4):
        raw=bytes(data); width=int(width); height=int(height); stride=int(row_stride or width*pixel_stride); ps=max(3,int(pixel_stride))
        def px(x,y):
            i=y*stride+x*ps
            if i+2>=len(raw): return (0,0,0)
            return (raw[i],raw[i+1],raw[i+2])
        return self.analyze(width,height,px)

    def analyze_bitmap(self,buffer,width,height,row_stride=None,pixel_stride=4):
        return self.analyze_rgba_bytes(width,height,buffer,row_stride,pixel_stride).to_dict()
