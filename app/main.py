"""
Maestro Mobile — Vertical Slice (Kivy)
======================================
Interface mobile que consome MaestroGridEnv sem alterar sua lógica.

Arquitetura preparada para cursor futuro:
- `controlled_player_id` existe no estado da UI e é independente de
  `ball.owner_id`. Na v1, ações são sempre executadas pelo dono da bola
  (exigência atual do ambiente). No futuro, o cursor poderá selecionar
  qualquer jogador do time controlado sem quebrar a interface.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o pacote maestro seja encontrado tanto no desktop quanto no APK
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kivy.app import App
from kivy.clock import Clock
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

from maestro import Action, ActionType, MaestroGridEnv


# ---------------------------------------------------------------------------
# Constantes de UI
# ---------------------------------------------------------------------------
TEAM_A_COLOR = (0.12, 0.45, 0.85, 1.0)   # azul
TEAM_B_COLOR = (0.85, 0.20, 0.20, 1.0)   # vermelho
BALL_COLOR = (1.0, 0.92, 0.15, 1.0)      # amarelo
FIELD_COLOR = (0.18, 0.55, 0.28, 1.0)    # verde
ZONE_COLOR = (0.15, 0.40, 0.20, 0.45)
GRID_LINE = (1, 1, 1, 0.25)
CURSOR_RING = (1.0, 1.0, 0.3, 0.9)       # reservado para cursor futuro


class FieldWidget(Widget):
    """Desenha a grade, jogadores, bola e (futuro) anel de cursor."""

    state = ObjectProperty(None, allownone=True)
    controlled_player_id = NumericProperty(-1)  # prepara cursor futuro

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(
            size=self._redraw,
            pos=self._redraw,
            state=self._redraw,
            controlled_player_id=self._redraw,
        )

    def _cell_size(self):
        if not self.state:
            return 1.0, 1.0
        cols = self.state.grid_cols
        rows = self.state.grid_rows
        return self.width / cols, self.height / rows

    def _cell_center(self, col: int, row: int):
        cw, ch = self._cell_size()
        # row 0 no topo (como no overlay ASCII)
        x = self.x + (col + 0.5) * cw
        y = self.y + self.height - (row + 0.5) * ch
        return x, y

    def _redraw(self, *args):
        self.canvas.clear()
        if not self.state:
            return

        cols = self.state.grid_cols
        rows = self.state.grid_rows
        cw, ch = self._cell_size()

        with self.canvas:
            # Campo
            Color(*FIELD_COLOR)
            Rectangle(pos=self.pos, size=self.size)

            # Zonas de finalização
            factor = 10 / 12
            Color(*ZONE_COLOR)
            zone_w = (1 - factor) * self.width
            Rectangle(pos=(self.x, self.y), size=(zone_w, self.height))  # zona B
            Rectangle(
                pos=(self.x + factor * self.width, self.y),
                size=(self.width * (1 - factor), self.height),
            )  # zona A

            # Linhas da grade
            Color(*GRID_LINE)
            for c in range(cols + 1):
                x = self.x + c * cw
                Line(points=[x, self.y, x, self.y + self.height], width=1)
            for r in range(rows + 1):
                y = self.y + r * ch
                Line(points=[self.x, y, self.x + self.width, y], width=1)

            # Jogadores
            radius = min(cw, ch) * 0.32
            for p in self.state.team_a:
                self._draw_player(p, TEAM_A_COLOR, radius)
            for p in self.state.team_b:
                self._draw_player(p, TEAM_B_COLOR, radius)

            # Bola
            bc, br = self.state.ball.cell
            bx, by = self._cell_center(bc, br)
            Color(*BALL_COLOR)
            bradius = radius * 0.45
            Ellipse(
                pos=(bx - bradius, by - bradius),
                size=(bradius * 2, bradius * 2),
            )

            # Anel de cursor (reservado — só desenha se controlled != owner)
            if self.controlled_player_id >= 0:
                try:
                    cp = self.state.player_by_id(int(self.controlled_player_id))
                    cx, cy = self._cell_center(*cp.cell)
                    Color(*CURSOR_RING)
                    Line(
                        circle=(cx, cy, radius * 1.35),
                        width=dp(2),
                    )
                except KeyError:
                    pass

    def _draw_player(self, player, color, radius):
        x, y = self._cell_center(*player.cell)
        Color(*color)
        Ellipse(pos=(x - radius, y - radius), size=(radius * 2, radius * 2))
        # número
        # (texto é desenhado via Label overlay no layout principal)


class PlayerLabelOverlay(Widget):
    """Labels de número dos jogadores posicionados sobre o FieldWidget."""

    state = ObjectProperty(None, allownone=True)

    def __init__(self, field: FieldWidget, **kwargs):
        super().__init__(**kwargs)
        self.field = field
        self._labels: dict[int, Label] = {}
        self.bind(size=self._reposition, pos=self._reposition)
        field.bind(state=self._on_state)

    def _on_state(self, *args):
        self._rebuild_labels()
        self._reposition()

    def _rebuild_labels(self):
        for lab in self._labels.values():
            self.remove_widget(lab)
        self._labels.clear()
        if not self.field.state:
            return
        for p in self.field.state.all_players():
            lab = Label(
                text=str(p.id),
                font_size=dp(12),
                bold=True,
                color=(1, 1, 1, 1),
                size_hint=(None, None),
                size=(dp(24), dp(24)),
            )
            self._labels[p.id] = lab
            self.add_widget(lab)

    def _reposition(self, *args):
        if not self.field.state:
            return
        for pid, lab in self._labels.items():
            try:
                p = self.field.state.player_by_id(pid)
                x, y = self.field._cell_center(*p.cell)
                lab.center = (x, y)
            except KeyError:
                pass


class MaestroMobileApp(App):
    title = "Maestro Grid"

    def build(self):
        from kivy.uix.floatlayout import FloatLayout

        self.env = MaestroGridEnv(seed=42, max_steps=300)
        self.state = None
        self.last_info: dict = {}
        # Preparado para cursor futuro: controlado pelo usuário, independente da bola
        self.controlled_player_id: int = -1
        self.user_team = "A"  # time que o usuário comanda nesta vertical slice

        root = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(4))

        # --- Header: placar + status ---
        self.header = Label(
            text="Maestro — toque em INICIAR",
            size_hint_y=None,
            height=dp(36),
            font_size=dp(15),
            bold=True,
            color=(1, 1, 1, 1),
        )
        root.add_widget(self.header)

        self.status = Label(
            text="",
            size_hint_y=None,
            height=dp(48),
            font_size=dp(12),
            color=(0.9, 0.9, 0.7, 1),
            halign="left",
            valign="middle",
        )
        self.status.bind(size=self.status.setter("text_size"))
        root.add_widget(self.status)

        # --- Campo (FieldWidget + overlay de números) ---
        field_container = FloatLayout(size_hint_y=0.50)
        self.field = FieldWidget()
        self.field.size_hint = (1, 1)
        field_container.add_widget(self.field)
        self.overlay = PlayerLabelOverlay(self.field)
        self.overlay.size_hint = (1, 1)
        field_container.add_widget(self.overlay)
        root.add_widget(field_container)

        # --- Ações ---
        actions_label = Label(
            text="Ações (ator = dono da bola)",
            size_hint_y=None,
            height=dp(22),
            font_size=dp(12),
            color=(0.8, 0.8, 0.8, 1),
        )
        root.add_widget(actions_label)

        self.action_grid = GridLayout(
            cols=3, size_hint_y=None, height=dp(100), spacing=dp(4)
        )
        for name, atype in [
            ("PASSE", ActionType.PASSE),
            ("DRIBLE", ActionType.DRIBLE),
            ("LANÇAR", ActionType.LANCAMENTO),
            ("CRUZAR", ActionType.CRUZAMENTO),
            ("FINALIZAR", ActionType.FINALIZAR),
            ("RESET", None),
        ]:
            btn = Button(text=name, font_size=dp(13))
            if atype is None:
                btn.bind(on_press=self.on_reset)
            else:
                btn.bind(on_press=lambda b, t=atype: self.on_action_type(t))
            self.action_grid.add_widget(btn)
        root.add_widget(self.action_grid)

        # --- Alvos (aparecem quando necessário) ---
        self.target_scroll = ScrollView(size_hint_y=None, height=dp(70))
        self.target_box = BoxLayout(
            orientation="horizontal", size_hint_x=None, spacing=dp(4)
        )
        self.target_box.bind(minimum_width=self.target_box.setter("width"))
        self.target_scroll.add_widget(self.target_box)
        root.add_widget(self.target_scroll)

        # Log curto
        self.log = Label(
            text="",
            size_hint_y=None,
            height=dp(56),
            font_size=dp(11),
            color=(0.75, 0.85, 0.75, 1),
            halign="left",
            valign="top",
        )
        self.log.bind(size=self.log.setter("text_size"))
        root.add_widget(self.log)

        # Inicia automaticamente
        Clock.schedule_once(lambda dt: self.on_reset(None), 0.3)
        return root

    # ------------------------------------------------------------------
    # Estado / UI
    # ------------------------------------------------------------------

    def _refresh_ui(self):
        if not self.state:
            return
        self.field.state = self.state
        # Cursor futuro: por enquanto acompanha o dono da bola do time do usuário
        owner = self.state.owner()
        if owner and owner.team == self.user_team:
            self.controlled_player_id = owner.id
        self.field.controlled_player_id = self.controlled_player_id

        metrics = self.env.evaluation_metrics()
        ga = metrics["gols_marcados"]
        gb = metrics["gols_sofridos"]
        self.header.text = (
            f"A {ga}  x  {gb} B   |   t={self.state.time_step}   "
            f"posse={self.state.possession}"
        )

        info = self.last_info
        lines = []
        if info.get("valid") is False:
            lines.append(f"⚠ INVÁLIDA: {info.get('reason', '?')}")
        else:
            act = info.get("action", "—")
            succ = info.get("success")
            if succ is True:
                lines.append(f"✓ {act} OK")
            elif succ is False:
                lines.append(f"✗ {act} falhou")
            else:
                lines.append(f"{act}")
            if info.get("goal"):
                lines.append(f"GOL DO TIME {info['goal']}!")
            if info.get("turnover"):
                lines.append("turnover")
            if "success_probability" in info:
                lines.append(f"p={info['success_probability']:.2f}")
        self.status.text = "  |  ".join(lines) if lines else "Pronto"

        # Log das últimas ações
        self.log.text = self._format_log(info)

    def _format_log(self, info: dict) -> str:
        if not info:
            return ""
        parts = [f"ação={info.get('action')}"]
        if "actor" in info:
            parts.append(f"ator={info['actor']}")
        if "target" in info:
            parts.append(f"alvo={info['target']}")
        if "target_cell" in info:
            parts.append(f"célula={info['target_cell']}")
        if info.get("valid") is False:
            parts.append(f"motivo={info.get('reason')}")
        return "  ".join(parts)

    def _clear_targets(self):
        self.target_box.clear_widgets()

    def _show_teammate_targets(self, action_type: ActionType):
        self._clear_targets()
        owner = self.state.owner()
        if not owner:
            return
        teammates = [p for p in self.state.team_of(owner.id) if p.id != owner.id]
        for tm in teammates:
            btn = Button(
                text=f"→ {tm.team}{tm.id} ({tm.cell[0]},{tm.cell[1]})",
                size_hint_x=None,
                width=dp(120),
                font_size=dp(12),
            )
            btn.bind(
                on_press=lambda b, t=tm, at=action_type: self._execute(
                    Action(type=at, actor_id=owner.id, target_id=t.id)
                )
            )
            self.target_box.add_widget(btn)

    def _show_dribble_targets(self):
        self._clear_targets()
        owner = self.state.owner()
        if not owner:
            return
        oc, or_ = owner.cell
        directions = [
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),           (1, 0),
            (-1, 1),  (0, 1),  (1, 1),
        ]
        for dc, dr in directions:
            tc, tr = oc + dc, or_ + dr
            if 0 <= tc < self.state.grid_cols and 0 <= tr < self.state.grid_rows:
                dist = self.state.cell_distance(owner.cell, (tc, tr))
                if dist <= self.env.MAX_DRIBBLE_DISTANCE:
                    btn = Button(
                        text=f"→ ({tc},{tr})",
                        size_hint_x=None,
                        width=dp(80),
                        font_size=dp(12),
                    )
                    btn.bind(
                        on_press=lambda b, cell=(tc, tr): self._execute(
                            Action(
                                type=ActionType.DRIBLE,
                                actor_id=owner.id,
                                target_cell=cell,
                            )
                        )
                    )
                    self.target_box.add_widget(btn)

    def _show_lancamento_targets(self):
        self._clear_targets()
        owner = self.state.owner()
        if not owner:
            return
        # Células à frente (até 4 colunas) na direção de ataque
        direction = 1 if owner.team == "A" else -1
        oc, or_ = owner.cell
        for reach in range(2, 5):
            tc = oc + direction * reach
            for dr in (-1, 0, 1):
                tr = or_ + dr
                if 0 <= tc < self.state.grid_cols and 0 <= tr < self.state.grid_rows:
                    btn = Button(
                        text=f"→ ({tc},{tr})",
                        size_hint_x=None,
                        width=dp(80),
                        font_size=dp(12),
                    )
                    btn.bind(
                        on_press=lambda b, cell=(tc, tr): self._execute(
                            Action(
                                type=ActionType.LANCAMENTO,
                                actor_id=owner.id,
                                target_cell=cell,
                            )
                        )
                    )
                    self.target_box.add_widget(btn)

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def on_reset(self, _btn):
        self.state, info = self.env.reset()
        self.last_info = info
        self.controlled_player_id = (
            self.state.owner().id if self.state.owner() else -1
        )
        self._clear_targets()
        self._refresh_ui()
        self.status.text = "Partida iniciada (seed=42)"

    def on_action_type(self, action_type: ActionType):
        if not self.state:
            return
        owner = self.state.owner()
        if not owner:
            self.status.text = "Sem dono da bola"
            return

        if action_type == ActionType.FINALIZAR:
            self._execute(Action(type=ActionType.FINALIZAR, actor_id=owner.id))
        elif action_type in (ActionType.PASSE, ActionType.CRUZAMENTO):
            self._show_teammate_targets(action_type)
            self.status.text = f"Escolha o alvo para {action_type.value}"
        elif action_type == ActionType.DRIBLE:
            self._show_dribble_targets()
            self.status.text = "Escolha a célula do drible"
        elif action_type == ActionType.LANCAMENTO:
            self._show_lancamento_targets()
            self.status.text = "Escolha a célula do lançamento"

    def _execute(self, action: Action):
        self._clear_targets()
        self.state, reward, done, info = self.env.step(action)
        self.last_info = info
        self._refresh_ui()
        if done:
            self.status.text += "  |  FIM DE PARTIDA"


if __name__ == "__main__":
    MaestroMobileApp().run()
