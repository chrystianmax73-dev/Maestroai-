from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# Visual system — designed for Maestro, not default Kivy controls.
# ---------------------------------------------------------------------------
BG = (0.035, 0.047, 0.060, 1)
PANEL = (0.065, 0.080, 0.098, 1)
PANEL_2 = (0.085, 0.102, 0.125, 1)
TEXT = (0.93, 0.96, 0.98, 1)
MUTED = (0.54, 0.60, 0.66, 1)
ACCENT = (0.18, 0.82, 0.56, 1)
ACCENT_2 = (0.18, 0.55, 0.95, 1)
DANGER = (0.92, 0.30, 0.30, 1)
WARN = (0.96, 0.72, 0.22, 1)
TEAM_A = (0.18, 0.55, 0.95, 1)
TEAM_B = (0.92, 0.28, 0.30, 1)
BALL = (1.0, 0.84, 0.18, 1)
FIELD = (0.055, 0.30, 0.19, 1)
FIELD_LINE = (0.75, 0.92, 0.82, 0.35)


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
            Color(*FIELD_LINE)
            # outer lines and midfield
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)
            mx = self.x + self.width / 2
            Line(points=[mx, self.y, mx, self.y + self.height], width=1)
            Ellipse(pos=(mx - min(self.width, self.height) * .12,
                         self.y + self.height / 2 - min(self.width, self.height) * .12),
                    size=(min(self.width, self.height) * .24, min(self.width, self.height) * .24),
                    angle_start=0, angle_end=360)
            # grid kept subtle because the simulator is grid-based
            Color(1, 1, 1, .08)
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
            Color(*BALL)
            Ellipse(pos=(bx - radius*.42, by - radius*.42), size=(radius*.84, radius*.84))

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
        Color(*color)
        Ellipse(pos=(x-radius, y-radius), size=(radius*2, radius*2))
        Color(1, 1, 1, .85)
        Line(circle=(x, y, radius), width=.8)


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
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        box = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(6))
        title = Label(text="MAESTRO VISION", color=TEXT, bold=True, font_size=dp(15),
                      halign="left", valign="middle", size_hint_y=None, height=dp(26))
        box.add_widget(title)
        self.state_label = Label(text="CAPTURA DESLIGADA", color=MUTED, font_size=dp(12),
                                 halign="left", valign="middle", size_hint_y=None, height=dp(24))
        box.add_widget(self.state_label)
        row = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(38))
        self.toggle = MaestroButton(text="ATIVAR CAPTURA", font_size=dp(11))
        self.toggle.bind(on_release=lambda *_: app.toggle_capture())
        row.add_widget(self.toggle)
        diag = MaestroButton(text="DIAGNÓSTICO", font_size=dp(11))
        diag.bind(on_release=lambda *_: app.open_diagnostics())
        row.add_widget(diag)
        box.add_widget(row)
        self.add_widget(box)

    def refresh(self, status):
        active = bool(status.get("active"))
        self.state_label.text = "CAPTURA ATIVA • OVERLAY ONLINE" if active else "CAPTURA DESLIGADA"
        self.state_label.color = ACCENT if active else MUTED
        self.toggle.text = "DESATIVAR CAPTURA" if active else "ATIVAR CAPTURA"
        self.toggle.active = active


class HomeScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        root = FloatLayout()
        self.add_widget(root)
        root.add_widget(Panel(pos_hint={"x":0,"y":0}, size_hint=(1,1), fill=BG, radius=0))

        content = BoxLayout(orientation="vertical", padding=[dp(24),dp(28),dp(24),dp(28)], spacing=dp(14),
                            size_hint=(1,.82), pos_hint={"x":0,"y":.08})
        root.add_widget(content)
        brand = Label(text="MAESTRO", color=TEXT, bold=True, font_size=dp(30),
                      size_hint_y=None, height=dp(46), halign="left", valign="middle")
        content.add_widget(brand)
        sub = Label(text="LABORATÓRIO DE FUTEBOL • OFFLINE", color=ACCENT, bold=True,
                    font_size=dp(11), size_hint_y=None, height=dp(24), halign="left")
        content.add_widget(sub)
        desc = Label(text="Ambiente de teste para simulação, visão e agente autônomo.",
                     color=MUTED, font_size=dp(13), size_hint_y=None, height=dp(46),
                     halign="left", valign="middle")
        desc.bind(size=lambda *_: setattr(desc, "text_size", desc.size))
        content.add_widget(desc)

        card = Panel(size_hint_y=None, height=dp(110), radius=16)
        info = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(4))
        info.add_widget(Label(text="AMBIENTE", color=MUTED, font_size=dp(10), bold=True,
                              size_hint_y=None, height=dp(20), halign="left"))
        info.add_widget(Label(text="Simulador local + percepção de tela + agente", color=TEXT,
                              font_size=dp(14), size_hint_y=None, height=dp(28), halign="left"))
        info.add_widget(Label(text="Nenhuma conexão externa é necessária.", color=MUTED,
                              font_size=dp(11), size_hint_y=None, height=dp(20), halign="left"))
        card.add_widget(info)
        content.add_widget(card)

        enter = MaestroButton(text="ENTRAR NO LABORATÓRIO", font_size=dp(15), active=True,
                              size_hint_y=None, height=dp(58))
        enter.bind(on_release=lambda *_: app.show_lab())
        content.add_widget(enter)
        vision = MaestroButton(text="TESTAR VISÃO / CAPTURA", font_size=dp(13),
                               size_hint_y=None, height=dp(46))
        vision.bind(on_release=lambda *_: app.show_lab(focus_capture=True))
        content.add_widget(vision)
        content.add_widget(Widget())
        footer = Label(text="MAESTRO v0.3 LAB • DIAGNÓSTICO LOCAL", color=MUTED,
                       font_size=dp(9), size_hint_y=None, height=dp(20), halign="left")
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
        self.capture_chip = MaestroButton(text="● CAPTURA OFF", font_size=dp(9), size_hint_x=None, width=dp(110))
        self.capture_chip.bind(on_release=lambda *_: app.toggle_capture())
        top.add_widget(self.capture_chip)

        body = BoxLayout(orientation="vertical", padding=[dp(12),0,dp(12),dp(10)], spacing=dp(8),
                         size_hint=(1,.89), pos_hint={"x":0,"y":0})
        root.add_widget(body)

        score = Panel(size_hint_y=None, height=dp(58), radius=12)
        sb = BoxLayout(orientation="horizontal", padding=[dp(14),dp(7)], spacing=dp(10))
        self.score = Label(text="A  0   ×   0  B", color=TEXT, bold=True, font_size=dp(18), halign="left")
        sb.add_widget(self.score)
        self.clock = Label(text="t=0", color=MUTED, font_size=dp(11), halign="right")
        sb.add_widget(self.clock)
        score.add_widget(sb)
        body.add_widget(score)

        field_panel = Panel(size_hint_y=.48, radius=14)
        fp = FloatLayout(padding=dp(8))
        field_panel.add_widget(fp)
        self.field = FieldWidget(size_hint=(1,1), pos_hint={"x":0,"y":0})
        fp.add_widget(self.field)
        self.labels = PlayerLabels(self.field, size_hint=(1,1))
        fp.add_widget(self.labels)
        body.add_widget(field_panel)

        status_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(7))
        self.status = Panel(radius=10)
        status_box = BoxLayout(orientation="vertical", padding=[dp(10),dp(5)])
        self.status_title = Label(text="PRONTO", color=TEXT, bold=True, font_size=dp(11), halign="left")
        self.status_detail = Label(text="Partida pronta para teste.", color=MUTED, font_size=dp(9), halign="left")
        status_box.add_widget(self.status_title); status_box.add_widget(self.status_detail)
        self.status.add_widget(status_box)
        status_row.add_widget(self.status)
        self.capture_card = CaptureCard(app, size_hint_x=.72, radius=10)
        status_row.add_widget(self.capture_card)
        body.add_widget(status_row)

        controls = BoxLayout(orientation="vertical", size_hint_y=.28, spacing=dp(6))
        main_row = BoxLayout(spacing=dp(6))
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

        action_row = GridLayout(cols=5, spacing=dp(5))
        self.action_buttons = {}
        for label, typ in [("PASSE",ActionType.PASSE),("DRIBLE",ActionType.DRIBLE),
                           ("LANÇAMENTO",ActionType.LANCAMENTO),("CRUZAMENTO",ActionType.CRUZAMENTO),
                           ("FINALIZAR",ActionType.FINALIZAR)]:
            b = MaestroButton(text=label, font_size=dp(9))
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

        nav = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(5))
        for text, cb in [("VISÃO", app.open_diagnostics), ("AGENTE", app.open_agent_panel)]:
            b = MaestroButton(text=text, font_size=dp(9)); b.bind(on_release=lambda *_x, c=cb: c()); nav.add_widget(b)
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
        self.capture_status = {}

        self.sm = ScreenManager(transition=NoTransition())
        self.home = HomeScreen(self, name="home")
        self.lab = LabScreen(self, name="lab")
        self.sm.add_widget(self.home); self.sm.add_widget(self.lab)
        Clock.schedule_once(lambda *_: self.reset_game(), .15)
        Clock.schedule_interval(self.poll_capture, 1.0)
        return self.sm

    def show_home(self):
        self.stop_ai(); self.sm.current = "home"

    def show_lab(self, focus_capture=False):
        self.sm.current = "lab"
        if focus_capture:
            self.set_status("VISÃO", "Ative a captura para iniciar o diagnóstico de tela.")

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
        self.lab.score.text = f"A  {metrics['gols_marcados']}   ×   {metrics['gols_sofridos']}  B"
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

    # ------------------------------------------------------------------
    # Capture / vision control. Read-only observation; no input injection.
    # ------------------------------------------------------------------
    def _capture_broadcast(self, action):
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            intent = Intent(action)
            intent.setPackage(PythonActivity.mActivity.getPackageName())
            PythonActivity.mActivity.sendBroadcast(intent)
            return True
        except Exception as exc:
            self.set_status("CAPTURA", f"Não foi possível enviar o comando: {exc}")
            return False

    def toggle_capture(self):
        active = bool(self.capture_status.get("active"))
        self._capture_broadcast("org.maestro.CAPTURE_STOP" if active else "org.maestro.CAPTURE_REQUEST")
        self.set_status("CAPTURA", "Solicitação enviada; aguardando status do Android.")

    def poll_capture(self, _dt):
        try:
            path = Path(self.user_data_dir) / "maestro_capture_status.json"
            if path.exists():
                self.capture_status = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not hasattr(self, "lab"): return
        self.lab.capture_card.refresh(self.capture_status)
        active = bool(self.capture_status.get("active"))
        self.lab.capture_chip.text = "● CAPTURA ON" if active else "● CAPTURA OFF"
        self.lab.capture_chip.active = active
        if active:
            p = self.capture_status.get("perception") or {}
            scene = float(p.get("scene_confidence", 0))
            self.lab.status_detail.text = f"Visão {scene:.0%} • {self.capture_status.get('fps',0):.1f} FPS • leitura somente"

    def open_diagnostics(self):
        status = self.capture_status
        p = status.get("perception") or {}
        text = (
            f"CAPTURA: {'ATIVA' if status.get('active') else 'INATIVA'}\n"
            f"TELA: {status.get('width','—')} × {status.get('height','—')}\n"
            f"FPS: {status.get('fps',0)}\n"
            f"CAMPO: {float(p.get('field_confidence',0)):.0%}\n"
            f"BOLA: {float(p.get('ball_confidence',0)):.0%}\n"
            f"CENA: {float(p.get('scene_confidence',0)):.0%}\n"
            f"INCERTO: {'SIM' if p.get('uncertain') else 'NÃO'}\n"
            f"ERRO: {status.get('error') or 'nenhum'}"
        )
        from kivy.uix.popup import Popup
        Popup(title="MAESTRO VISION • DIAGNÓSTICO", content=Label(text=text, color=TEXT,
              halign="left", valign="top"), size_hint=(.88,.62)).open()

    def open_agent_panel(self):
        from kivy.uix.popup import Popup
        metrics = self.env.evaluation_metrics() if self.state else {}
        text = (
            f"MODO: {'IA AUTÔNOMA' if self.autonomous else 'MANUAL'}\n"
            f"VELOCIDADE: {self.speed:g}x\n"
            f"PASSOS: {self.state.time_step if self.state else 0}\n"
            f"GOLS A/B: {metrics.get('gols_marcados',0)} / {metrics.get('gols_sofridos',0)}\n\n"
            "O agente usa somente o estado público do simulador.\n"
            "A captura é observação e diagnóstico; não injeta comandos."
        )
        Popup(title="MAESTRO AGENT", content=Label(text=text, color=TEXT, halign="left", valign="top"),
              size_hint=(.88,.52)).open()


if __name__ == "__main__":
    MaestroMobileApp().run()
