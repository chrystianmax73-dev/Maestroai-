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
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from maestro import Action, ActionType, HeuristicAgent, MaestroGridEnv, TacticalEngine
from maestro.vision.capture_controller import CaptureController

BG = (0.025, 0.033, 0.043, 1)
PANEL = (0.055, 0.068, 0.084, 1)
PANEL_2 = (0.080, 0.098, 0.120, 1)
TEXT = (0.94, 0.97, 0.99, 1)
MUTED = (0.48, 0.55, 0.63, 1)
ACCENT = (0.16, 0.85, 0.58, 1)
BLUE = (0.22, 0.58, 0.97, 1)
RED = (0.93, 0.32, 0.34, 1)
WARN = (0.97, 0.73, 0.24, 1)
FIELD = (0.035, 0.22, 0.14, 1)
FIELD_LINE = (0.82, 0.94, 0.86, 0.35)
BALL = (1.0, 0.84, 0.18, 1)


class Panel(Widget):
    radius = NumericProperty(12)
    fill = ObjectProperty(PANEL)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw, fill=self.draw)
        self.draw()

    def draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.fill)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.radius)])


class MaestroButton(ButtonBehavior, Label):
    active = BooleanProperty(False)
    fill = ObjectProperty(PANEL_2)
    active_fill = ObjectProperty(ACCENT)

    def __init__(self, **kwargs):
        self.font_size = kwargs.pop("font_size", dp(12))
        self.bold = kwargs.pop("bold", True)
        super().__init__(**kwargs)
        self.halign = "center"
        self.valign = "middle"
        self.bind(size=self._text, pos=self.draw, active=self.draw)
        self.draw()

    def _text(self, *_):
        self.text_size = self.size

    def draw(self, *_):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*(self.active_fill if self.active else self.fill))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])


class FieldWidget(Widget):
    state = ObjectProperty(None, allownone=True)
    selected_id = NumericProperty(-1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.draw, size=self.draw, state=self.draw, selected_id=self.draw)

    def center(self, cell):
        if not self.state:
            return self.center
        cw = self.width / self.state.grid_cols
        ch = self.height / self.state.grid_rows
        col, row = cell
        return self.x + (col + .5) * cw, self.y + self.height - (row + .5) * ch

    def draw(self, *_):
        self.canvas.clear()
        if not self.state:
            return
        cols, rows = self.state.grid_cols, self.state.grid_rows
        cw, ch = self.width / cols, self.height / rows
        with self.canvas:
            Color(*FIELD)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
            Color(1, 1, 1, .025)
            stripe = self.width / 10
            for i in range(0, 10, 2):
                Rectangle(pos=(self.x + i * stripe, self.y), size=(stripe, self.height))
            Color(*FIELD_LINE)
            Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)
            mx = self.x + self.width / 2
            Line(points=[mx, self.y, mx, self.y + self.height], width=1)
            Line(circle=(mx, self.y + self.height / 2, min(self.width, self.height) * .13), width=1)
            for c in range(1, cols):
                x = self.x + c * cw
                Line(points=[x, self.y, x, self.y + self.height], width=.45)
            for r in range(1, rows):
                y = self.y + r * ch
                Line(points=[self.x, y, self.x + self.width, y], width=.45)
            radius = min(cw, ch) * .30
            for p in self.state.team_a:
                self._player(p, BLUE, radius)
            for p in self.state.team_b:
                self._player(p, RED, radius)
            bx, by = self.center(self.state.ball.cell)
            Color(*BALL)
            Ellipse(pos=(bx - radius * .42, by - radius * .42), size=(radius * .84, radius * .84))
            if self.selected_id >= 0:
                try:
                    p = self.state.player_by_id(int(self.selected_id))
                    x, y = self.center(p.cell)
                    Color(*BALL)
                    Line(circle=(x, y, radius * 1.35), width=dp(2))
                except KeyError:
                    pass

    def _player(self, player, color, radius):
        x, y = self.center(player.cell)
        Color(0, 0, 0, .24)
        Ellipse(pos=(x-radius, y-radius*.8), size=(radius*2, radius*.45))
        Color(*color)
        Ellipse(pos=(x-radius, y-radius), size=(radius*2, radius*2))
        Color(1, 1, 1, .85)
        Line(circle=(x, y, radius), width=.8)


class PlayerLabels(Widget):
    def __init__(self, field, **kwargs):
        super().__init__(**kwargs)
        self.field = field
        self.labels = {}
        field.bind(state=self.rebuild)
        self.bind(pos=self.place, size=self.place)

    def rebuild(self, *_):
        for child in list(self.children):
            self.remove_widget(child)
        self.labels.clear()
        if not self.field.state:
            return
        for p in self.field.state.all_players():
            label = Label(text=str(p.id), color=(1, 1, 1, 1), bold=True,
                          font_size=dp(8), size_hint=(None, None), size=(dp(18), dp(18)))
            self.labels[p.id] = label
            self.add_widget(label)
        self.place()

    def place(self, *_):
        if not self.field.state:
            return
        for pid, label in self.labels.items():
            try:
                label.center = self.field.center(self.field.state.player_by_id(pid).cell)
            except KeyError:
                pass


class CandidateRow(Panel):
    def __init__(self, candidate, rank, on_select, **kwargs):
        super().__init__(size_hint_y=None, height=dp(56), radius=9, **kwargs)
        box = BoxLayout(orientation="horizontal", padding=[dp(10), dp(5)], spacing=dp(8))
        box.add_widget(Label(text=f"{rank:02d}", color=MUTED, bold=True, font_size=dp(10), size_hint_x=.10))
        label = candidate.label
        if candidate.action.target_id is not None:
            label += f" → P{candidate.action.target_id}"
        elif candidate.action.target_cell is not None:
            label += f" → {candidate.action.target_cell[0]},{candidate.action.target_cell[1]}"
        box.add_widget(Label(text=label, color=TEXT, bold=True, font_size=dp(11), halign="left", size_hint_x=.38))
        box.add_widget(Label(text=f"{candidate.score:.2f}", color=ACCENT if candidate.score >= .65 else WARN,
                             bold=True, font_size=dp(14), size_hint_x=.18))
        why = Label(text=candidate.rationale, color=MUTED, font_size=dp(8.5), halign="left", size_hint_x=.34)
        why.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        box.add_widget(why)
        self.add_widget(box)
        self._callback = on_select
        self._candidate = candidate

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._callback(self._candidate)
            return True
        return super().on_touch_down(touch)


class LabScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        root = BoxLayout(orientation="vertical", padding=[dp(10), dp(8), dp(10), dp(8)], spacing=dp(7))
        self.add_widget(root)

        header = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(7))
        back = MaestroButton(text="‹", font_size=dp(24), size_hint_x=None, width=dp(40))
        back.bind(on_release=lambda *_: app.show_home())
        header.add_widget(back)
        title = BoxLayout(orientation="vertical")
        title.add_widget(Label(text="MAESTRO / TACTICAL LAB", color=TEXT, bold=True, font_size=dp(15), halign="left"))
        self.subtitle = Label(text="SIMULADOR • DECISÃO • EXECUÇÃO CONTROLADA", color=ACCENT, font_size=dp(8.5), halign="left")
        title.add_widget(self.subtitle)
        header.add_widget(title)
        self.run_chip = MaestroButton(text="● IDLE", font_size=dp(9), size_hint_x=None, width=dp(76))
        header.add_widget(self.run_chip)
        root.add_widget(header)

        telemetry = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        self.t_posse = self.metric(telemetry, "POSSE")
        self.t_step = self.metric(telemetry, "STEP")
        self.t_owner = self.metric(telemetry, "BALL OWNER")
        self.t_pressure = self.metric(telemetry, "PRESSÃO")
        self.t_action = self.metric(telemetry, "DECISÃO")
        root.add_widget(telemetry)

        body = BoxLayout(spacing=dp(7))
        left = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=.58)
        field_panel = Panel(radius=12)
        fp = BoxLayout(padding=dp(7))
        field_panel.add_widget(fp)
        self.field = FieldWidget()
        fp.add_widget(self.field)
        self.labels = PlayerLabels(self.field)
        fp.add_widget(self.labels)
        left.add_widget(field_panel)

        controls = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
        self.play = MaestroButton(text="▶  IA AUTÔNOMA", active=True, font_size=dp(11))
        self.play.bind(on_release=lambda *_: app.toggle_ai())
        controls.add_widget(self.play)
        self.pause = MaestroButton(text="Ⅱ", font_size=dp(11))
        self.pause.bind(on_release=lambda *_: app.toggle_pause())
        controls.add_widget(self.pause)
        reset = MaestroButton(text="↻ NOVO", font_size=dp(11))
        reset.bind(on_release=lambda *_: app.reset_game())
        controls.add_widget(reset)
        left.add_widget(controls)
        body.add_widget(left)

        right = BoxLayout(orientation="vertical", spacing=dp(6), size_hint_x=.42)
        tactical = Panel(radius=12)
        tbox = BoxLayout(orientation="vertical", padding=dp(9), spacing=dp(5))
        head = BoxLayout(size_hint_y=None, height=dp(31))
        head.add_widget(Label(text="DECISÕES CANDIDATAS", color=TEXT, bold=True, font_size=dp(11), halign="left"))
        analyze = MaestroButton(text="ANALISAR", font_size=dp(8.5), size_hint_x=None, width=dp(75), active=True)
        analyze.bind(on_release=lambda *_: app.analyze())
        head.add_widget(analyze)
        tbox.add_widget(head)
        self.candidate_scroll = ScrollView(do_scroll_x=False)
        self.candidate_box = BoxLayout(orientation="vertical", spacing=dp(4), size_hint_y=None)
        self.candidate_box.bind(minimum_height=self.candidate_box.setter("height"))
        self.candidate_scroll.add_widget(self.candidate_box)
        tbox.add_widget(self.candidate_scroll)
        tactical.add_widget(tbox)
        right.add_widget(tactical)

        log_panel = Panel(size_hint_y=None, height=dp(116), radius=12)
        logbox = BoxLayout(orientation="vertical", padding=[dp(9), dp(6)], spacing=dp(3))
        logbox.add_widget(Label(text="EVENT STREAM", color=MUTED, bold=True, font_size=dp(9), halign="left", size_hint_y=None, height=dp(17)))
        self.log = Label(text="[000] sessão iniciada", color=TEXT, font_size=dp(8.5), halign="left", valign="top")
        self.log.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        logbox.add_widget(self.log)
        log_panel.add_widget(logbox)
        right.add_widget(log_panel)
        body.add_widget(right)
        root.add_widget(body)

        actions = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(5))
        for name, typ in (("PASSE", ActionType.PASSE), ("DRIBLE", ActionType.DRIBLE),
                          ("LANÇAMENTO", ActionType.LANCAMENTO), ("CRUZAMENTO", ActionType.CRUZAMENTO),
                          ("FINALIZAR", ActionType.FINALIZAR)):
            b = MaestroButton(text=name, font_size=dp(8.5))
            b.bind(on_release=lambda _, t=typ: app.manual_action(t))
            actions.add_widget(b)
        root.add_widget(actions)

    @staticmethod
    def metric(parent, name):
        panel = Panel(radius=8)
        box = BoxLayout(orientation="vertical", padding=[dp(6), dp(3)])
        box.add_widget(Label(text=name, color=MUTED, bold=True, font_size=dp(7.5), size_hint_y=.45))
        value = Label(text="--", color=TEXT, bold=True, font_size=dp(11), size_hint_y=.55, halign="left")
        box.add_widget(value)
        panel.add_widget(box)
        parent.add_widget(panel)
        return value


class HomeScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=[dp(24), dp(28)], spacing=dp(14))
        self.add_widget(root)
        root.add_widget(Label(text="MAESTRO", color=TEXT, bold=True, font_size=dp(34), halign="left", size_hint_y=None, height=dp(45)))
        root.add_widget(Label(text="TACTICAL LAB  /  OFFLINE SIMULATION", color=ACCENT, bold=True, font_size=dp(11), halign="left", size_hint_y=None, height=dp(22)))
        intro = Panel(size_hint_y=None, height=dp(175), radius=16)
        ib = BoxLayout(orientation="vertical", padding=dp(17), spacing=dp(7))
        ib.add_widget(Label(text="O cérebro do Maestro", color=TEXT, bold=True, font_size=dp(17), halign="left", size_hint_y=None, height=dp(28)))
        body = Label(text="Percepção → GameState → avaliação tática → decisão → execução no simulador.\n\nAs alternativas são calculadas e pontuadas antes da ação. O laboratório registra a decisão, o resultado e o estado seguinte.", color=MUTED, font_size=dp(11), halign="left", valign="top")
        body.bind(size=lambda w, *_: setattr(w, "text_size", w.size))
        ib.add_widget(body)
        intro.add_widget(ib)
        root.add_widget(intro)
        enter = MaestroButton(text="ABRIR SALA TÁTICA", active=True, font_size=dp(15), size_hint_y=None, height=dp(58))
        enter.bind(on_release=lambda *_: app.show_lab())
        root.add_widget(enter)
        capture = MaestroButton(text="ATIVAR CAPTURA ANDROID", active=False, font_size=dp(11), size_hint_y=None, height=dp(42))
        capture.bind(on_release=lambda *_: app.request_capture())
        root.add_widget(capture)
        root.add_widget(Label(text="SIMULADOR LOCAL  •  SEM CONTROLE DE APLICATIVOS EXTERNOS  •  v0.5", color=MUTED, font_size=dp(9), halign="left", size_hint_y=None, height=dp(20)))
        root.add_widget(Widget())


class MaestroMobileApp(App):
    title = "Maestro Tactical Lab"
    INTERVAL = .55

    def build(self):
        Window.clearcolor = BG
        self.env = MaestroGridEnv(seed=42, max_steps=300)
        self.agent = HeuristicAgent(seed=42)
        self.tactics = TacticalEngine(self.env)
        self.state = None
        self.last_info = {}
        self.autonomous = False
        self.paused = False
        self.ai_event = None
        self.history_text = []
        self.capture = CaptureController(self.append_log)
        self.sm = ScreenManager(transition=NoTransition())
        self.home = HomeScreen(self, name="home")
        self.lab = LabScreen(self, name="lab")
        self.sm.add_widget(self.home)
        self.sm.add_widget(self.lab)
        Clock.schedule_once(lambda *_: self.reset_game(), .15)
        return self.sm

    def show_home(self):
        self.stop_ai()
        self.sm.current = "home"

    def show_lab(self):
        self.sm.current = "lab"
        self.analyze()

    def request_capture(self):
        """Inicia MediaProjection somente após ação e consentimento do usuário."""
        if not self.capture.request_capture():
            self.append_log("captura Android indisponível ou aguardando permissão")

    def reset_game(self):
        self.stop_ai()
        self.paused = False
        self.state, _ = self.env.reset()
        self.last_info = {}
        self.history_text = ["[000] novo jogo / estado inicial"]
        self.refresh()
        self.analyze()

    def toggle_ai(self):
        if self.autonomous:
            self.stop_ai()
            return
        self.autonomous = True
        self.paused = False
        self.lab.play.text = "■  PARAR IA"
        self.lab.run_chip.text = "● RUN"
        self.lab.subtitle.text = "SIMULADOR • IA AUTÔNOMA • LOOP TÁTICO"
        self.schedule_ai()
        self.append_log("IA iniciada / melhor candidato será executado")

    def stop_ai(self):
        self.autonomous = False
        if self.ai_event is not None:
            self.ai_event.cancel()
            self.ai_event = None
        if hasattr(self, "lab"):
            self.lab.play.text = "▶  IA AUTÔNOMA"
            self.lab.run_chip.text = "● IDLE"
            self.lab.subtitle.text = "SIMULADOR • DECISÃO • EXECUÇÃO CONTROLADA"

    def toggle_pause(self):
        self.paused = not self.paused
        self.lab.pause.text = "▶" if self.paused else "Ⅱ"
        self.append_log("loop pausado" if self.paused else "loop retomado")

    def schedule_ai(self):
        if self.ai_event is not None:
            self.ai_event.cancel()
        self.ai_event = Clock.schedule_interval(self.ai_tick, self.INTERVAL)

    def ai_tick(self, _dt):
        if not self.autonomous or self.paused or not self.state:
            return
        best = self.tactics.best(self.state, self.env)
        if best is None:
            self.stop_ai()
            return
        self.execute(best.action, source=f"IA {best.label} {best.score:.2f}")

    def analyze(self):
        if not self.state:
            return
        candidates = self.tactics.evaluate(self.state, self.env)
        self.lab.candidate_box.clear_widgets()
        for i, candidate in enumerate(candidates[:7], 1):
            self.lab.candidate_box.add_widget(CandidateRow(candidate, i, self.select_candidate))
        if candidates:
            best = candidates[0]
            self.lab.t_action.text = f"{best.label} {best.score:.2f}"

    def select_candidate(self, candidate):
        if not self.state or self.autonomous or self.paused:
            return
        owner = self.state.owner()
        self.lab.field.selected_id = owner.id if owner else -1
        self.execute(candidate.action, source=f"MANUAL CANDIDATO {candidate.label} {candidate.score:.2f}")

    def manual_action(self, action_type):
        if self.autonomous or self.paused or not self.state:
            return
        owner = self.state.owner()
        if owner is None:
            return
        if action_type == ActionType.FINALIZAR:
            self.execute(Action(type=action_type, actor_id=owner.id), source="MANUAL FINALIZAR")
            return
        candidates = [c for c in self.tactics.evaluate(self.state, self.env) if c.action.type == action_type]
        if candidates:
            self.execute(candidates[0].action, source=f"MANUAL {action_type.value}")
        else:
            self.append_log(f"sem candidato válido para {action_type.value}")

    def execute(self, action, source="EXEC"):
        try:
            self.state, reward, done, info = self.env.step(action)
            self.last_info = info
            valid = bool(info.get("valid", False))
            act = info.get("action", action.type.value)
            result = "OK" if valid else "INVALID"
            if info.get("goal"):
                result = f"GOL {info['goal']}"
            self.append_log(f"[{self.state.time_step:03d}] {source} → {act} / {result} / r={reward:.2f}")
            self.refresh()
            self.analyze()
            if done:
                self.stop_ai()
                self.append_log("partida encerrada")
        except Exception as exc:
            self.append_log(f"ERRO {type(exc).__name__}: {exc}")

    def refresh(self):
        if not self.state:
            return
        self.lab.field.state = self.state
        owner = self.state.owner()
        self.lab.field.selected_id = owner.id if owner else -1
        pressure = self.state.pressure_on(owner.id) if owner else 0.0
        self.lab.t_posse.text = self.state.possession
        self.lab.t_step.text = f"{self.state.time_step:03d}"
        self.lab.t_owner.text = f"P{owner.id}" if owner else "--"
        self.lab.t_pressure.text = f"{pressure:.2f}"
        self.lab.t_action.text = self.last_info.get("action", "ANALISANDO")
        self.lab.log.text = "\n".join(self.history_text[-7:])

    def append_log(self, text):
        self.history_text.append(text)
        if hasattr(self, "lab"):
            self.lab.log.text = "\n".join(self.history_text[-7:])

    def on_stop(self):
        self.stop_ai()
        self.capture.close()
        super().on_stop()


if __name__ == "__main__":
    MaestroMobileApp().run()
