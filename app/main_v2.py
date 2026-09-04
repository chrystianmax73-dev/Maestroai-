from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager, NoTransition
from kivy.uix.widget import Widget

from maestro import Action, ActionType, HeuristicAgent, MaestroGridEnv
from maestro.vision.capture_controller import CaptureController

BG=(.025,.031,.040,1); PANEL=(.055,.067,.083,1); PANEL2=(.075,.090,.110,1)
TEXT=(.94,.96,.98,1); MUTED=(.52,.58,.65,1); GREEN=(.20,.82,.55,1)
BLUE=(.20,.56,.95,1); RED=(.92,.30,.32,1); YELLOW=(.96,.76,.22,1)
FIELD=(.045,.27,.16,1); WHITE=(.88,.94,.90,.55)

class Card(BoxLayout):
    def __init__(self, fill=PANEL, radius=16, **kwargs):
        super().__init__(**kwargs); self.fill=fill; self.radius=radius
        self.padding=dp(14); self.spacing=dp(8); self.bind(pos=self._draw,size=self._draw); self._draw()
    def _draw(self,*_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.fill); RoundedRectangle(pos=self.pos,size=self.size,radius=[dp(self.radius)])

class ActionButton(Button):
    def __init__(self,text,**kwargs):
        super().__init__(text=text,**kwargs); self.background_normal=""; self.background_color=PANEL2
        self.color=TEXT; self.bold=True; self.font_size=dp(12); self.bind(state=self._state)
    def _state(self,*_): self.background_color=GREEN if self.state=="down" else PANEL2

class FieldView(Widget):
    state=ObjectProperty(None,allownone=True)
    def __init__(self,**kwargs): super().__init__(**kwargs); self.bind(pos=self.draw,size=self.draw,state=self.draw)
    def _cell_center(self,cell):
        if not self.state: return self.center
        cw=self.width/self.state.grid_cols; ch=self.height/self.state.grid_rows
        return self.x+(cell[0]+.5)*cw, self.y+self.height-(cell[1]+.5)*ch
    def draw(self,*_):
        self.canvas.clear()
        if not self.state: return
        cols,rows=self.state.grid_cols,self.state.grid_rows; cw,ch=self.width/cols,self.height/rows
        with self.canvas:
            Color(*FIELD); RoundedRectangle(pos=self.pos,size=self.size,radius=[dp(14)])
            Color(*WHITE); Line(rectangle=(self.x,self.y,self.width,self.height),width=1.1)
            mx=self.x+self.width/2; Line(points=[mx,self.y,mx,self.y+self.height],width=1)
            Line(circle=(mx,self.y+self.height/2,min(self.width,self.height)*.11),width=1)
            Color(1,1,1,.07)
            for c in range(1,cols):
                x=self.x+c*cw; Line(points=[x,self.y,x,self.y+self.height],width=.45)
            for r in range(1,rows):
                y=self.y+r*ch; Line(points=[self.x,y,self.x+self.width,y],width=.45)
            radius=min(cw,ch)*.28
            for p in self.state.team_a: self._player(p.cell,BLUE,radius)
            for p in self.state.team_b: self._player(p.cell,RED,radius)
            bx,by=self._cell_center(self.state.ball.cell); Color(*YELLOW)
            Ellipse(pos=(bx-radius*.42,by-radius*.42),size=(radius*.84,radius*.84))
    def _player(self,cell,color,radius):
        x,y=self._cell_center(cell); Color(*color); Ellipse(pos=(x-radius,y-radius),size=(radius*2,radius*2))
        Color(1,1,1,.7); Line(circle=(x,y,radius),width=.8)

class Home(Screen):
    def __init__(self,app,**kwargs):
        super().__init__(**kwargs); root=BoxLayout(orientation="vertical",padding=[dp(22),dp(26),dp(22),dp(20)],spacing=dp(14)); self.add_widget(root)
        root.add_widget(Label(text="MAESTRO",color=TEXT,bold=True,font_size=dp(34),size_hint_y=None,height=dp(48),halign="left"))
        root.add_widget(Label(text="FOOTBALL INTELLIGENCE LAB",color=GREEN,bold=True,font_size=dp(11),size_hint_y=None,height=dp(22),halign="left"))
        root.add_widget(Label(text="Simulação local • visão de tela • agente autônomo",color=MUTED,font_size=dp(13),size_hint_y=None,height=dp(42),halign="left",valign="middle"))
        status=Card(orientation="vertical",size_hint_y=None,height=dp(128)); status.add_widget(Label(text="SISTEMA OFFLINE",color=GREEN,bold=True,font_size=dp(11),size_hint_y=None,height=dp(22),halign="left")); status.add_widget(Label(text="Simulador local",color=TEXT,bold=True,font_size=dp(17),size_hint_y=None,height=dp(28),halign="left")); status.add_widget(Label(text="Nenhuma conta, servidor ou conexão externa é necessária.",color=MUTED,font_size=dp(11),halign="left",valign="middle")); root.add_widget(status)
        b=ActionButton("ABRIR LABORATÓRIO",size_hint_y=None,height=dp(58)); b.bind(on_release=lambda *_:app.show_lab()); root.add_widget(b)
        b=ActionButton("TESTAR VISÃO E CAPTURA",size_hint_y=None,height=dp(48)); b.bind(on_release=lambda *_:app.show_lab(focus_capture=True)); root.add_widget(b)
        root.add_widget(Widget()); root.add_widget(Label(text="v0.4 • LAB BUILD",color=MUTED,font_size=dp(9),size_hint_y=None,height=dp(18),halign="left"))

class Lab(Screen):
    def __init__(self,app,**kwargs):
        super().__init__(**kwargs); self.app=app; self.env=MaestroGridEnv(seed=42); self.state,_=self.env.reset(); self.agent=HeuristicAgent(seed=42); self.autoplay=False; self.capture=CaptureController(self._notice)
        root=BoxLayout(orientation="vertical",padding=[dp(12),dp(10),dp(12),dp(10)],spacing=dp(9)); self.add_widget(root)
        head=BoxLayout(size_hint_y=None,height=dp(52),spacing=dp(8)); back=ActionButton("‹",size_hint_x=None,width=dp(44)); back.bind(on_release=lambda *_:app.show_home()); head.add_widget(back)
        title=BoxLayout(orientation="vertical"); title.add_widget(Label(text="MAESTRO LAB",color=TEXT,bold=True,font_size=dp(17),halign="left")); self.mode=Label(text="MANUAL • SIMULADOR",color=GREEN,font_size=dp(9),halign="left"); title.add_widget(self.mode); head.add_widget(title)
        self.vision_chip=ActionButton("VISION OFF",size_hint_x=None,width=dp(106)); self.vision_chip.bind(on_release=lambda *_:app.toggle_capture()); head.add_widget(self.vision_chip); root.add_widget(head)
        score=Card(orientation="horizontal",size_hint_y=None,height=dp(66)); self.score=Label(text="A  0  ×  0  B",color=TEXT,bold=True,font_size=dp(21),halign="left"); score.add_widget(self.score); self.clock=Label(text="POSSE A\nT=0",color=MUTED,font_size=dp(10),halign="right",valign="middle"); score.add_widget(self.clock); root.add_widget(score)
        field=Card(orientation="vertical",padding=dp(7),size_hint_y=.46); self.field=FieldView(size_hint=(1,1),state=self.state); field.add_widget(self.field); root.add_widget(field)
        info=Card(orientation="vertical",size_hint_y=None,height=dp(72)); self.notice=Label(text="Pronto. Selecione uma ação.",color=MUTED,font_size=dp(11),halign="left",valign="middle"); info.add_widget(self.notice); self.owner=Label(text="DONO DA BOLA: —",color=TEXT,bold=True,font_size=dp(11),halign="left"); info.add_widget(self.owner); root.add_widget(info)
        controls=GridLayout(cols=3,spacing=dp(7),size_hint_y=None,height=dp(104)); actions=[("PASSE",self.pass_action),("DRIBLE",self.dribble_action),("LANÇAMENTO",self.launch_action),("CRUZAMENTO",self.cross_action),("FINALIZAR",self.finish_action),("NOVO JOGO",self.reset_game)]
        for label,fn in actions:
            b=ActionButton(label); b.bind(on_release=lambda _,fn=fn:fn()); controls.add_widget(b)
        root.add_widget(controls)
        bottom=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(7)); self.ai_button=ActionButton("INICIAR IA"); self.ai_button.bind(on_release=lambda *_:app.toggle_ai()); bottom.add_widget(self.ai_button); b=ActionButton("DIAGNÓSTICO"); b.bind(on_release=lambda *_:app.open_diagnostics()); bottom.add_widget(b); root.add_widget(bottom)
    def refresh(self):
        self.field.state=self.state; o=self.state.owner(); self.owner.text=f"DONO DA BOLA: {o.id if o else '—'} • TIME {o.team if o else '—'}"; self.clock.text=f"POSSE {self.state.possession}\nT={self.state.time_step}"; self.mode.text="AUTÔNOMO • SELF-PLAY" if self.autoplay else "MANUAL • SIMULADOR"; self.ai_button.text="PARAR IA" if self.autoplay else "INICIAR IA"; cap=self.capture.status(); self.vision_chip.text="VISION ON" if cap.active else "VISION OFF"; self.vision_chip.background_color=GREEN if cap.active else PANEL2
    def step(self,action):
        if not action:return
        self.state,reward,done,info=self.env.step(action); label=info.get("action",action.type.name); result="OK" if info.get("success") else "FALHOU"; self.notice.text=f"{label} • {result} • recompensa {reward:.2f}"; self.refresh()
        if info.get("goal"): self.notice.text=f"⚽ GOL! • {label}"
        if done: self.autoplay=False; self.notice.text="PARTIDA ENCERRADA • NOVO JOGO para reiniciar"
    def _owner(self): return self.state.owner()
    def pass_action(self):
        o=self._owner(); teammates=[p for p in self.state.team_of(o.id) if p.id!=o.id] if o else []; self.step(Action(type=ActionType.PASSE,actor_id=o.id,target_id=teammates[0].id) if teammates else None)
    def dribble_action(self):
        o=self._owner()
        if not o:return
        d=1 if o.team=="A" else -1; occupied={p.cell for p in self.state.all_players()}; targets=[(o.cell[0]+d,o.cell[1]),(o.cell[0],o.cell[1]-1),(o.cell[0],o.cell[1]+1),(o.cell[0]-d,o.cell[1])]
        target=next((c for c in targets if 0<=c[0]<self.state.grid_cols and 0<=c[1]<self.state.grid_rows and c not in occupied),targets[0]); self.step(Action(type=ActionType.DRIBLE,actor_id=o.id,target_cell=target))
    def launch_action(self):
        o=self._owner()
        if o:
            d=1 if o.team=="A" else -1; tc=max(0,min(self.state.grid_cols-1,o.cell[0]+3*d)); self.step(Action(type=ActionType.LANCAMENTO,actor_id=o.id,target_cell=(tc,o.cell[1])))
    def cross_action(self):
        o=self._owner(); teammates=[p for p in self.state.team_of(o.id) if p.id!=o.id] if o else []; self.step(Action(type=ActionType.CRUZAMENTO,actor_id=o.id,target_id=teammates[0].id) if teammates else None)
    def finish_action(self):
        o=self._owner(); self.step(Action(type=ActionType.FINALIZAR,actor_id=o.id) if o else None)
    def reset_game(self): self.autoplay=False; self.state,_=self.env.reset(); self.notice.text="Novo jogo iniciado • seed 42"; self.refresh()
    def tick_ai(self,*_):
        if self.autoplay:
            a=self.agent.decide(self.state,self.env)
            if a:self.step(a)
    def _notice(self,text): self.notice.text=text

class Diagnostics(Screen):
    def __init__(self,app,**kwargs):
        super().__init__(**kwargs); self.app=app; root=BoxLayout(orientation="vertical",padding=dp(18),spacing=dp(10)); self.add_widget(root); root.add_widget(Label(text="MAESTRO VISION",color=TEXT,bold=True,font_size=dp(23),size_hint_y=None,height=dp(38),halign="left")); self.body=Label(text="Lendo estado da captura…",color=MUTED,font_size=dp(12),halign="left",valign="top"); root.add_widget(self.body); b=ActionButton("VOLTAR AO LABORATÓRIO",size_hint_y=None,height=dp(52)); b.bind(on_release=lambda *_:app.show_lab()); root.add_widget(b)
    def refresh(self):
        s=self.app.lab.capture.status(); self.body.text=f"CAPTURA: {'ATIVA' if s.active else 'DESLIGADA'}\nFPS: {s.fps:.1f}\nRESOLUÇÃO: {s.width} × {s.height}\nCENÁRIO: {s.scene_confidence:.0%}\nBOLA: {s.ball_confidence:.0%}\nINCERTEZA: {'SIM' if s.uncertain else 'NÃO'}\nAGENTE: {s.agent_state}\n\nERRO: {s.error or 'nenhum'}"

class MaestroMobileApp(App):
    def build(self):
        Window.clearcolor=BG; self.sm=ScreenManager(transition=NoTransition()); self.home=Home(self,name="home"); self.lab=Lab(self,name="lab"); self.diag=Diagnostics(self,name="diagnostics"); self.sm.add_widget(self.home); self.sm.add_widget(self.lab); self.sm.add_widget(self.diag); Clock.schedule_interval(self._poll,.5); Clock.schedule_interval(self.lab.tick_ai,.35); return self.sm
    def _poll(self,*_):
        if self.sm.current=="lab": self.lab.refresh()
        elif self.sm.current=="diagnostics": self.diag.refresh()
    def show_home(self): self.sm.current="home"
    def show_lab(self,focus_capture=False): self.sm.current="lab"; self.lab.refresh();
    def toggle_ai(self): self.lab.autoplay=not self.lab.autoplay; (self.lab.capture.start_agent() if self.lab.autoplay else self.lab.capture.stop_agent()); self.lab.refresh()
    def toggle_capture(self):
        if self.lab.capture.status().active:self.lab.capture.stop()
        else:self.lab.capture.request_capture()
        self.lab.refresh()
    def open_diagnostics(self): self.sm.current="diagnostics"; self.diag.refresh()
    def on_stop(self):
        try:self.lab.capture.close()
        except Exception:pass

if __name__=="__main__": MaestroMobileApp().run()
