from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager, NoTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from maestro import Action, ActionType, HeuristicAgent, MaestroGridEnv

# NOTA DE ARQUITETURA: o módulo de captura de tela Android
# (maestro/vision/capture_controller.py, services/capture.py, android_src/)
# existe no repositório mas NÃO é importado nem empacotado nesta build.
# Ele fica isolado como ponto de integração futuro (ver README/ARCHITECTURE),
# sem nenhuma wiring ativa no app que é de fato compilado e distribuído.


# ---------------------------------------------------------------------------
# Visual system — designed for Maestro, not default Kivy controls.
# ---------------------------------------------------------------------------
BG = (0.031, 0.043, 0.055, 1)
PANEL = (0.063, 0.078, 0.096, 1)
PANEL_2 = (0.088, 0.106, 0.130, 1)
PANEL_BORDER = (1, 1, 1, 0.06)
TEXT = (0.94, 0.97, 0.99, 1)
MUTED = (0.55, 0.61, 0.68, 1)
ACCENT = (0.16, 0.85, 0.58, 1)      # verde Maestro — IA / positivo
ACCENT_2 = (0.22, 0.58, 0.97, 1)    # azul — navegação / time A
DANGER = (0.93, 0.32, 0.34, 1)
WARN = (0.97, 0.73, 0.24, 1)
TEAM_A = (0.22, 0.58, 0.97, 1)
TEAM_B = (0.93, 0.32, 0.34, 1)
BALL = (1.0, 0.85, 0.20, 1)
FIELD = (0.043, 0.24, 0.155, 1)
FIELD_LINE = (0.80, 0.94, 0.86, 0.32)
BRAND = (0.16, 0.85, 0.58, 1)


class Panel(Widget):
    radius = NumericProperty(14)
    fill = ObjectProperty(PANEL)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, fill=self._draw)
        self._draw()

    def _draw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.fill)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.radius)])


class MaestroButton(ButtonBehavior, Label):
    """Flat, high-contrast control used throughout the app."""
    active = BooleanProperty(False)
    fill = ObjectProperty(PANEL_2)
    active_fill = ObjectProperty(ACCENT)

    def __init__(self, **kwargs):
        self.font_size = kwargs.pop("font_size", dp(13))
        self.bold = kwargs.pop("bold", True)
        super().__init__(**kwargs)
        self.halign = "center"
        self.valign = "middle"
        self.bind(size=self._text_size, active=self._draw, pos=self._draw)
        self._draw()

    def _text_size(self, *args):
        self.text_size = self.size

    def _draw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*(self.active_fill if self.active else self.fill))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])


class StatusDot(Widget):
    active = BooleanProperty(False)
    color = ObjectProperty(MUTED)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._draw, size=self._draw, active=self._draw)
        self._draw()

    def _draw(self, *args):
        self.canvas.clear()
        with self.canvas:
            Color(*(ACCENT if self.active else self.color))
            Ellipse(pos=self.pos, size=self.size)


class FieldWidget(Widget):
    state = ObjectProperty(None, allownone=True)
    controlled_player_id = NumericProperty(-1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(size=self._redraw, pos=self._redraw, state=self._redraw,
                  controlled_player_id=self._redraw)

    def _cell_size(self):
        if not self.state:
            return 1.0, 1.0
        return self.width / self.state.grid_cols, self.height / self.state.grid_rows

    def _cell_center(self, col, row):
        cw, ch = self._cell_size()
        return self.x + (col + .5) * cw, self.y + self.height - (row + .5) * ch

    def _redraw(self, *args):
        self.canvas.clear()
        if not self.state:
            return
        cols, rows = self.state.grid_cols, self.state.grid_rows
        cw, ch = self._cell_size()
        with self.canvas:
            Color(*FIELD)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])

            # Textura sutil de listras do gramado (puramente decorativa)
            Color(1, 1, 1, .025)
            stripe_w = self.width / 10
            for i in range(0, 10, 2):
                Rectangle(pos=(self.x + i * stripe_w, self.y), size=(stripe_w, self.height))

            Color(*FIELD_LINE)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.3)
            mx = self.x + self.width / 2
            Line(points=[mx, self.y, mx, self.y + self.height], width=1.1)
            circle_r = min(self.width, self.height) * .13
            Line(circle=(mx, self.y + self.height / 2, circle_r), width=1.1)
            Ellipse(pos=(mx - dp(1.5), self.y + self.height / 2 - dp(1.5)), size=(dp(3), dp(3)))

            # Pequenas áreas junto às linhas de fundo (referência visual de gol)
            box_w = self.width * .07
            box_h = self.height * .34
            Line(rectangle=(self.x, self.y + (self.height - box_h) / 2, box_w, box_h), width=1.0)
            Line(rectangle=(self.x + self.width - box_w, self.y + (self.height - box_h) / 2, box_w, box_h), width=1.0)

            # grid kept subtle because the simulator is grid-based
            Color(1, 1, 1, .06)
            for c in range(1, cols):
                x = self.x + c * cw
                Line(points=[x, self.y, x, self.y + self.height], width=.6)
            for r in range(1, rows):
                y = self.y + r * ch
                Line(points=[self.x, y, self.x + self.width, y], width=.6)

            radius = min(cw, ch) * .31
            for p in self.state.team_a:
                self._player(p, TEAM_A, radius)
            for p in self.state.team_b:
                self._player(p, TEAM_B, radius)
            bc, br = self.state.ball.cell
            bx, by = self._cell_center(bc, br)
            # sombra sutil sob a bola, pra dar profundidade
            Color(0, 0, 0, .28)
            Ellipse(pos=(bx - radius*.40, by - radius*.52), size=(radius*.80, radius*.30))
            Color(*BALL)
            Ellipse(pos=(bx - radius*.42, by - radius*.42), size=(radius*.84, radius*.84))
            Color(0, 0, 0, .55)
            Line(circle=(bx, by, radius*.42), width=.7)

            if self.controlled_player_id >= 0:
                try:
                    cp = self.state.player_by_id(int(self.controlled_player_id))
                    cx, cy = self._cell_center(*cp.cell)
                    Color(*BALL)
                    Line(circle=(cx, cy, radius * 1.35), width=dp(2))
                except KeyError:
                    pass

    def _player(self, player, color, radius):
        x, y = self._cell_center(*player.cell)
        Color(0, 0, 0, .22)
        Ellipse(pos=(x-radius*.95, y-radius*1.05), size=(radius*1.9, radius*.55))
        Color(*color)
        Ellipse(pos=(x-radius, y-radius), size=(radius*2, radius*2))
        Color(1, 1, 1, .9)
        Line(circle=(x, y, radius), width=1.0)


class PlayerLabels(Widget):
    state = ObjectProperty(None, allownone=True)

    def __init__(self, field, **kwargs):
        super().__init__(**kwargs)
        self.field = field
        self.labels = {}
        field.bind(state=self._rebuild)
        self.bind(size=self._place, pos=self._place)

    def _rebuild(self, *args):
        for label in self.labels.values():
            self.remove_widget(label)
        self.labels.clear()
        if not self.field.state:
            return
        for p in self.field.state.all_players():
            lab = Label(text=str(p.id), color=(1,1,1,1), bold=True,
                        font_size=dp(9), size_hint=(None,None), size=(dp(22),dp(22)))
            self.labels[p.id] = lab
            self.add_widget(lab)
        self._place()

    def _place(self, *args):
        if not self.field.state:
            return
        for pid, lab in self.labels.items():
            try:
                p = self.field.state.player_by_id(pid)
                lab.center = self.field._cell_center(*p.cell)
            except KeyError:
                pass


class CaptureCard(Panel):
    """Cartão de status do módulo de Visão.

    Nesta build, o módulo de captura de tela Android não está incluído
    (ver nota no topo do arquivo) — o cartão só informa isso, sem
    oferecer nenhuma ação real de captura.
    """

    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(6))
        title = Label(text="MAESTRO VISION", color=TEXT, bold=True, font_size=dp(15),
                      halign="left", valign="middle", size_hint_y=None, height=dp(26))
        box.add_widget(title)
        self.state_label = Label(text="NÃO INCLUÍDO NESTA BUILD", color=MUTED, font_size=dp(12),
                                 halign="left", valign="middle", size_hint_y=None, height=dp(24))
        box.add_widget(self.state_label)
        row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(38))
        diag = MaestroButton(text="DIAGNÓSTICO", font_size=dp(11))
        diag.bind(on_release=lambda *_: app.open_diagnostics())
        row.add_widget(diag)
        box.add_widget(row)
        self.add_widget(box)

    def refresh(self, status):
        # Estático de propósito — sem módulo de captura não há status real
        # pra mostrar, e não colocamos números/estado inventado aqui.
        self.state_label.text = "NÃO INCLUÍDO NESTA BUILD"
        self.state_label.color = MUTED


class ModuleBadge(BoxLayout):
    """Linha 'nome do módulo — status', usada na Home para dar uma visão
    honesta do que está disponível nesta build."""

    def __init__(self, label, status, ok=True, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(22), spacing=dp(8), **kwargs)
        dot = StatusDot(active=ok, size_hint=(None, None), size=(dp(8), dp(8)),
                         pos_hint={"center_y": .5})
        self.add_widget(dot)
        self.add_widget(Label(text=label, color=TEXT, font_size=dp(12), bold=True,
                              halign="left", valign="middle", size_hint_x=.42))
        self.add_widget(Label(text=status, color=(ACCENT if ok else MUTED),
                              font_size=dp(11), halign="left", valign="middle"))


class HomeScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        root = FloatLayout()
        self.add_widget(root)
        root.add_widget(Panel(pos_hint={"x":0,"y":0}, size_hint=(1,1), fill=BG, radius=0))

        content = BoxLayout(orientation="vertical", padding=[dp(26),dp(30),dp(26),dp(26)], spacing=dp(16),
                            size_hint=(1,.86), pos_hint={"x":0,"y":.06})
        root.add_widget(content)

        brand_row = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(64), spacing=dp(2))
        brand = Label(text="MAESTRO", color=TEXT, bold=True, font_size=dp(34),
                      size_hint_y=None, height=dp(42), halign="left", valign="bottom")
        brand.bind(size=lambda w,*_: setattr(w, "text_size", w.size))
        brand_row.add_widget(brand)
        sub = Label(text="LABORATÓRIO DE FUTEBOL  •  OFFLINE", color=ACCENT, bold=True,
                    font_size=dp(11.5), size_hint_y=None, height=dp(20), halign="left")
        sub.bind(size=lambda w,*_: setattr(w, "text_size", w.size))
        brand_row.add_widget(sub)
        content.add_widget(brand_row)

        card = Panel(size_hint_y=None, height=dp(132), radius=16)
        info = BoxLayout(orientation="vertical", padding=[dp(16),dp(14)], spacing=dp(7))
        info.add_widget(Label(text="ESTADO DOS MÓDULOS", color=MUTED, font_size=dp(10), bold=True,
                              size_hint_y=None, height=dp(16), halign="left"))
        info.add_widget(ModuleBadge("SIMULADOR", "PRONTO", ok=True))
        info.add_widget(ModuleBadge("AGENTE (IA)", "PRONTO", ok=True))
        info.add_widget(ModuleBadge("VISÃO", "NÃO INCLUÍDA NESTA BUILD", ok=False))
        card.add_widget(info)
        content.add_widget(card)

        content.add_widget(Widget(size_hint_y=None, height=dp(2)))

        enter = MaestroButton(text="ENTRAR NO LABORATÓRIO", font_size=dp(15), active=True,
                              size_hint_y=None, height=dp(58))
        enter.bind(on_release=lambda *_: app.show_lab())
        content.add_widget(enter)
        vision = MaestroButton(text="VER DIAGNÓSTICO DE VISÃO", font_size=dp(12.5), fill=PANEL_2,
                               size_hint_y=None, height=dp(46))
        vision.bind(on_release=lambda *_: app.show_lab(focus_capture=True))
        content.add_widget(vision)
        content.add_widget(Widget())
        footer = Label(text="MAESTRO v0.4  •  100% LOCAL  •  SEM CONEXÃO EXTERNA", color=MUTED,
                       font_size=dp(9), size_hint_y=None, height=dp(20), halign="left")
        footer.bind(size=lambda w,*_: setattr(w, "text_size", w.size))
        content.add_widget(footer)


class LabScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        root = FloatLayout()
        self.add_widget(root)
        root.add_widget(Panel(pos_hint={"x":0,"y":0}, size_hint=(1,1), fill=BG, radius=0))

        top = BoxLayout(orientation="horizontal", padding=[dp(14),dp(10)], spacing=dp(8),
                        size_hint=(1,None), height=dp(58), pos_hint={"x":0,"top":1})
        root.add_widget(top)
        back = MaestroButton(text="‹", font_size=dp(25), size_hint_x=None, width=dp(46))
        back.bind(on_release=lambda *_: app.show_home())
        top.add_widget(back)
        title_box = BoxLayout(orientation="vertical")
        title_box.add_widget(Label(text="MAESTRO", color=TEXT, bold=True, font_size=dp(17), halign="left"))
        self.mode = Label(text="LABORATÓRIO • MANUAL", color=ACCENT, font_size=dp(9), halign="left")
        title_box.add_widget(self.mode)
        top.add_widget(title_box)
        self.capture_chip = MaestroButton(text="● VISÃO N/D", font_size=dp(9), size_hint_x=None, width=dp(110))
        self.capture_chip.bind(on_release=lambda *_: app.toggle_capture())
        top.add_widget(self.capture_chip)

        body = BoxLayout(orientation="vertical", padding=[dp(12),0,dp(12),dp(10)], spacing=dp(8),
                         size_hint=(1,.89), pos_hint={"x":0,"y":0})
        root.add_widget(body)

        score = Panel(size_hint_y=None, height=dp(64), radius=12)
        sb = BoxLayout(orientation="horizontal", padding=[dp(16),dp(8)], spacing=dp(10))
        team_a_dot = StatusDot(active=True, color=TEAM_A, size_hint=(None,None), size=(dp(10),dp(10)))
        sb.add_widget(team_a_dot)
        self.score = Label(text="0   ×   0", color=TEXT, bold=True, font_size=dp(22), halign="left",
                           size_hint_x=None, width=dp(90))
        sb.add_widget(self.score)
        team_b_dot = StatusDot(active=True, color=TEAM_B, size_hint=(None,None), size=(dp(10),dp(10)))
        sb.add_widget(team_b_dot)
        sb.add_widget(Widget())
        self.clock = Label(text="t=0", color=MUTED, font_size=dp(12), halign="right")
        sb.add_widget(self.clock)
        score.add_widget(sb)
        body.add_widget(score)

        field_panel = Panel(size_hint_y=.44, radius=14)
        fp = FloatLayout()  # FloatLayout não tem propriedade `padding` — causava TypeError no build()
        field_panel.add_widget(fp)
        self.field = FieldWidget(size_hint=(1,1), pos_hint={"x":0,"y":0})
        fp.add_widget(self.field)
        self.labels = PlayerLabels(self.field, size_hint=(1,1))
        fp.add_widget(self.labels)
        body.add_widget(field_panel)

        status_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(7))
        self.status = Panel(radius=10)
        status_box = BoxLayout(orientation="vertical", padding=[dp(10),dp(5)])
        self.status_title = Label(text="PRONTO", color=ACCENT, bold=True, font_size=dp(11), halign="left")
        self.status_detail = Label(text="Partida pronta para teste.", color=MUTED, font_size=dp(9), halign="left")
        status_box.add_widget(self.status_title); status_box.add_widget(self.status_detail)
        self.status.add_widget(status_box)
        status_row.add_widget(self.status)
        self.capture_card = CaptureCard(app, size_hint_x=.72, radius=10)
        status_row.add_widget(self.capture_card)
        body.add_widget(status_row)

        controls = BoxLayout(orientation="vertical", size_hint_y=.32, spacing=dp(4))
        controls.add_widget(Label(text="CONTROLE DA PARTIDA", color=MUTED, bold=True, font_size=dp(9),
                                  size_hint_y=None, height=dp(15), halign="left"))
        main_row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(42))
        self.play = MaestroButton(text="▶  JOGAR SOZINHO", active=True, font_size=dp(12))
        self.play.bind(on_release=lambda *_: app.toggle_ai())
        main_row.add_widget(self.play)
        self.pause = MaestroButton(text="Ⅱ  PAUSAR", font_size=dp(12))
        self.pause.bind(on_release=lambda *_: app.toggle_pause())
        main_row.add_widget(self.pause)
        reset = MaestroButton(text="↻  NOVO JOGO", font_size=dp(12))
        reset.bind(on_release=lambda *_: app.reset_game())
        main_row.add_widget(reset)
        controls.add_widget(main_row)

        controls.add_widget(Label(text="AÇÃO MANUAL", color=MUTED, bold=True, font_size=dp(9),
                                  size_hint_y=None, height=dp(15), halign="left"))
        action_row = GridLayout(cols=5, spacing=dp(5), size_hint_y=None, height=dp(40))
        self.action_buttons = {}
        for label, typ in [("PASSE",ActionType.PASSE),("DRIBLE",ActionType.DRIBLE),
                           ("LANÇAMENTO",ActionType.LANCAMENTO),("CRUZAMENTO",ActionType.CRUZAMENTO),
                           ("FINALIZAR",ActionType.FINALIZAR)]:
            b = MaestroButton(text=label, font_size=dp(9), fill=PANEL_2)
            b.bind(on_release=lambda _, t=typ: app.on_action_type(t))
            self.action_buttons[typ] = b
            action_row.add_widget(b)
        controls.add_widget(action_row)
        self.target_scroll = ScrollView(size_hint_y=None, height=dp(38), do_scroll_y=False)
        self.target_box = BoxLayout(orientation="horizontal", spacing=dp(5), size_hint_x=None)
        self.target_box.bind(minimum_width=self.target_box.setter("width"))
        self.target_scroll.add_widget(self.target_box)
        controls.add_widget(self.target_scroll)
        body.add_widget(controls)

        nav = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(5))
        for text, cb in [("◎  VISÃO", app.open_diagnostics), ("⚙  AGENTE", app.open_agent_panel)]:
            b = MaestroButton(text=text, font_size=dp(10), fill=PANEL_2)
            b.bind(on_release=lambda *_x, c=cb: c())
            nav.add_widget(b)
        body.add_widget(nav)


class MaestroMobileApp(App):
    title = "Maestro"
    BASE_AI_INTERVAL = .6
    SPEEDS = (.5, 1, 2, 4)

    def build(self):
        Window.clearcolor = BG
        self.env = MaestroGridEnv(seed=42, max_steps=300)
        self.state = None
        self.last_info = {}
        self.agent = HeuristicAgent(seed=42)
        self.autonomous = False
        self.paused = False
        self.speed = 1.0
        self.ai_event = None
        self.pending_type: Optional[ActionType] = None
        # Sem módulo de captura nesta build: capture_status fica sempre vazio,
        # e a UI mostra isso honestamente em vez de inventar números.
        self.capture_status = {}

        self.sm = ScreenManager(transition=NoTransition())
        self.home = HomeScreen(self, name="home")
        self.lab = LabScreen(self, name="lab")
        self.sm.add_widget(self.home); self.sm.add_widget(self.lab)
        Clock.schedule_once(lambda *_: self.reset_game(), .15)
        return self.sm

    def show_home(self):
        self.stop_ai(); self.sm.current = "home"

    def show_lab(self, focus_capture=False):
        self.sm.current = "lab"
        if focus_capture:
            self.set_status("VISÃO", "Módulo de captura de tela não incluído nesta build.")

    def reset_game(self):
        self.stop_ai()
        self.paused = False
        self.state, _ = self.env.reset()
        self.last_info = {}
        self.lab.mode.text = "LABORATÓRIO • MANUAL"
        self.lab.pause.text = "Ⅱ  PAUSAR"
        self._refresh_ui()

    def toggle_ai(self):
        if self.autonomous:
            self.stop_ai()
            return
        self.autonomous = True
        self.paused = False
        self.lab.play.text = "■  PARAR IA"
        self.lab.play.active = True
        self.lab.mode.text = f"LABORATÓRIO • IA {self.speed:g}x"
        self.schedule_ai()
        self.set_status("IA AUTÔNOMA", "O agente está decidindo pelo estado do simulador.")

    def stop_ai(self):
        self.autonomous = False
        if self.ai_event is not None:
            self.ai_event.cancel(); self.ai_event = None
        if hasattr(self, "lab"):
            self.lab.play.text = "▶  JOGAR SOZINHO"
            self.lab.play.active = True
            self.lab.mode.text = "LABORATÓRIO • MANUAL"

    def toggle_pause(self):
        self.paused = not self.paused
        self.lab.pause.text = "▶  CONTINUAR" if self.paused else "Ⅱ  PAUSAR"
        if self.paused:
            self.set_status("PAUSADO", "Simulação congelada. A captura pode continuar ativa.")
        elif self.autonomous:
            self.set_status("IA AUTÔNOMA", "Agente retomado.")

    def schedule_ai(self):
        if self.ai_event is not None:
            self.ai_event.cancel()
        self.ai_event = Clock.schedule_interval(self.ai_tick, self.BASE_AI_INTERVAL / self.speed)

    def ai_tick(self, _dt):
        if not self.autonomous or self.paused or not self.state:
            return
        action = self.agent.decide(self.state, self.env)
        if action is not None:
            self.execute(action)
        if self.state.time_step >= 300:
            self.stop_ai()

    def on_action_type(self, action_type):
        if self.autonomous or self.paused or not self.state:
            return
        self.pending_type = action_type
        self.rebuild_targets(action_type)
        if action_type == ActionType.FINALIZAR:
            owner = self.state.owner()
            if owner: self.execute(Action(type=action_type, actor_id=owner.id))

    def rebuild_targets(self, action_type):
        self.lab.target_box.clear_widgets()
        owner = self.state.owner() if self.state else None
        if not owner or action_type == ActionType.FINALIZAR:
            return
        if action_type in (ActionType.PASSE, ActionType.CRUZAMENTO):
            targets = [p for p in self.state.team_of(owner.id) if p.id != owner.id]
            for p in targets:
                b = MaestroButton(text=f"JOGADOR {p.id}", font_size=dp(9), size_hint_x=None, width=dp(92))
                b.bind(on_release=lambda _, pid=p.id: self.execute(Action(type=self.pending_type, actor_id=owner.id, target_id=pid)))
                self.lab.target_box.add_widget(b)
        else:
            direction = 1 if owner.team == "A" else -1
            for dc, dr in [(direction,0),(direction,-1),(direction,1),(0,-1),(0,1)]:
                cell=(owner.cell[0]+dc, owner.cell[1]+dr)
                if 0 <= cell[0] < self.state.grid_cols and 0 <= cell[1] < self.state.grid_rows:
                    b=MaestroButton(text=f"{cell[0]},{cell[1]}", font_size=dp(9), size_hint_x=None, width=dp(62))
                    b.bind(on_release=lambda _, c=cell: self.execute(Action(type=self.pending_type, actor_id=owner.id, target_cell=c)))
                    self.lab.target_box.add_widget(b)

    def execute(self, action):
        try:
            self.state, reward, done, info = self.env.step(action)
            self.last_info = info
            self.lab.target_box.clear_widgets()
            self.pending_type = None
            self._refresh_ui()
            if done:
                self.stop_ai()
                self.set_status("FIM", "Partida encerrada. Use NOVO JOGO para reiniciar.")
        except Exception as exc:
            self.set_status("ERRO", str(exc))

    def _refresh_ui(self):
        if not self.state: return
        self.lab.field.state = self.state
        owner = self.state.owner()
        if owner and owner.team == "A":
            self.lab.field.controlled_player_id = owner.id
        metrics = self.env.evaluation_metrics()
        self.lab.score.text = f"{metrics['gols_marcados']}   ×   {metrics['gols_sofridos']}"
        self.lab.clock.text = f"t={self.state.time_step:03d}   posse={self.state.possession}"
        info = self.last_info
        act = info.get("action")
        if info.get("valid") is False:
            self.set_status("AÇÃO INVÁLIDA", str(info.get("reason", "motivo desconhecido")))
        elif info.get("goal"):
            self.set_status("GOL", f"Time {info['goal']} marcou.")
        elif act:
            self.set_status("ÚLTIMA AÇÃO", f"{act} • {'sucesso' if info.get('success') else 'falha'}")

    def set_status(self, title, detail):
        if not hasattr(self, "lab"): return
        self.lab.status_title.text = title
        self.lab.status_detail.text = detail
        colors = {
            "AÇÃO INVÁLIDA": DANGER, "ERRO": DANGER,
            "GOL": WARN, "FIM": WARN,
            "IA AUTÔNOMA": ACCENT, "PRONTO": ACCENT,
        }
        self.lab.status_title.color = colors.get(title, TEXT)

    # ------------------------------------------------------------------
    # Vision status. Nesta build o módulo de captura de tela Android não
    # está incluído/empacotado (ver nota no topo do arquivo) — estes
    # métodos só informam esse estado honestamente, sem simular captura.
    # ------------------------------------------------------------------
    def toggle_capture(self):
        self.set_status("VISÃO", "Módulo de captura de tela não incluído nesta build.")

    def on_stop(self):
        super().on_stop()

    def open_diagnostics(self):
        metrics = self.env.evaluation_metrics() if self.state else {}
        rows = [
            ("ENGINE", "READY", ACCENT),
            ("SIMULATOR", "READY", ACCENT),
            ("AGENT", "RUNNING" if self.autonomous else "IDLE", ACCENT if self.autonomous else MUTED),
            ("VISION", "NÃO INCLUÍDO NESTA BUILD", MUTED),
            ("CAPTURE", "N/D", MUTED),
            ("FPS", "--", MUTED),
            ("FIELD", "--", MUTED),
            ("BALL", "--", MUTED),
            ("SCENE", "--", MUTED),
            ("UNCERTAINTY", "N/D", MUTED),
            ("GOLS A/B", f"{metrics.get('gols_marcados',0)} / {metrics.get('gols_sofridos',0)}", TEXT),
            ("ERROR", "NONE", ACCENT),
        ]
        self._open_stat_popup("MAESTRO • DIAGNÓSTICO", rows)

    def open_agent_panel(self):
        rows = [
            ("MODO", "IA AUTÔNOMA" if self.autonomous else "MANUAL", ACCENT if self.autonomous else MUTED),
            ("VELOCIDADE", f"{self.speed:g}x", TEXT),
            ("PASSOS", str(self.state.time_step if self.state else 0), TEXT),
        ]
        if self.state:
            metrics = self.env.evaluation_metrics()
            rows.append(("GOLS A/B", f"{metrics.get('gols_marcados',0)} / {metrics.get('gols_sofridos',0)}", TEXT))
        self._open_stat_popup(
            "MAESTRO AGENT", rows,
            footer="O agente decide usando somente o estado público\ndo simulador (MaestroGridEnv) — nada externo ao jogo.",
        )

    def _open_stat_popup(self, title, rows, footer=None):
        from kivy.uix.popup import Popup
        body = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(4))
        for label, value, color in rows:
            row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(26))
            row.add_widget(Label(text=label, color=MUTED, bold=True, font_size=dp(11),
                                 halign="left", valign="middle", size_hint_x=.5))
            row.add_widget(Label(text=str(value), color=color, bold=True, font_size=dp(12),
                                 halign="right", valign="middle", size_hint_x=.5))
            body.add_widget(row)
        if footer:
            foot = Label(text=footer, color=MUTED, font_size=dp(10), halign="left", valign="top",
                        size_hint_y=None, height=dp(40))
            foot.bind(size=lambda w,*_: setattr(w, "text_size", w.size))
            body.add_widget(Widget(size_hint_y=None, height=dp(6)))
            body.add_widget(foot)
        Popup(title=title, title_color=TEXT, separator_color=ACCENT,
              content=body, size_hint=(.9, None), height=dp(44 + 30 * len(rows) + (56 if footer else 0))
              ).open()


if __name__ == "__main__":
    MaestroMobileApp().run()
