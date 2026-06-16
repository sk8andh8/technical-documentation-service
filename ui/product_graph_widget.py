"""Представление структуры изделия в виде графа (без дублирования узлов).

В отличие от дерева, каждый элемент отображается ровно один раз, даже если
он применяется в нескольких местах (первичная + заимствованные связи).
Узлы раскладываются по слоям (расстояние от корня), рёбра рисуются между
узлами: сплошная линия — первичная применяемость, пунктир — заимствование.

Реализация не требует внешних зависимостей (только PyQt6): простой послойный
layout + QGraphicsView для отрисовки, масштабирования и панорамирования.
"""

import html

from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QColor, QPen, QBrush, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsRectItem,
    QGraphicsTextItem, QGraphicsPathItem, QMenu,
)

from repository.item_repository import ItemRepository
from repository.parent_child_repository import ParentChildRepository

NODE_W = 190
NODE_H = 38
H_GAP = 70
V_GAP = 34


class _NodeItem(QGraphicsRectItem):
    """Прямоугольный узел графа с обозначением элемента."""

    def __init__(self, item_id: int, designation: str, is_root: bool):
        super().__init__(0, 0, NODE_W, NODE_H)
        self.item_id = item_id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        fill = QColor("#1D4ED8") if is_root else QColor("#FFFFFF")
        border = QColor("#1D4ED8") if is_root else QColor("#94A3B8")
        self.setBrush(QBrush(fill))
        self.setPen(QPen(border, 2))
        self.setZValue(1)

        text_color = "#FFFFFF" if is_root else "#1E293B"
        label = QGraphicsTextItem(self)
        display = designation if len(designation) <= 42 else designation[:39] + "…"
        display = html.escape(display)
        label.setHtml(
            f'<div style="color:{text_color}; font-size:11px;">'
            f'<b>{display}</b></div>'
        )
        label.setTextWidth(NODE_W - 16)
        label.setPos(8, 8)

    def center_bottom(self) -> QPointF:
        return QPointF(self.pos().x() + NODE_W / 2, self.pos().y() + NODE_H)

    def center_top(self) -> QPointF:
        return QPointF(self.pos().x() + NODE_W / 2, self.pos().y())


class _GraphView(QGraphicsView):
    """QGraphicsView с зумом колесом мыши и панорамированием."""

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class ProductGraphWidget(QWidget):
    """Виджет вкладки «Граф изделия»."""

    edit_requested = pyqtSignal(int)
    view_file_requested = pyqtSignal(int)
    add_child_requested = pyqtSignal(int)

    def __init__(self, db_session, parent=None):
        super().__init__(parent)
        self.repo = ItemRepository(db_session)
        self.pc_repo = ParentChildRepository(db_session)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #3B82F6; color: white; padding: 6px 14px; "
            "border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #2563EB; }"
        )
        toolbar.addWidget(self.btn_refresh)

        self.btn_fit = QPushButton("Вписать в окно")
        self.btn_fit.clicked.connect(self._fit_view)
        self.btn_fit.setStyleSheet(
            "QPushButton { padding: 6px 14px; border-radius: 4px; "
            "background-color: #F1F5F9; color: #475569; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        toolbar.addWidget(self.btn_fit)

        self.btn_reset = QPushButton("Масштаб 1:1")
        self.btn_reset.clicked.connect(self._reset_zoom)
        self.btn_reset.setStyleSheet(
            "QPushButton { padding: 6px 14px; border-radius: 4px; "
            "background-color: #F1F5F9; color: #475569; }"
            "QPushButton:hover { background-color: #E2E8F0; }"
        )
        toolbar.addWidget(self.btn_reset)

        toolbar.addStretch()

        legend = QLabel(
            '<span style="color:#1D4ED8;">━━</span> первичная применяемость&nbsp;&nbsp;'
            '<span style="color:#9333EA;">┅┅</span> заимствование'
        )
        legend.setStyleSheet("color: #64748B; font-size: 12px;")
        toolbar.addWidget(legend)

        layout.addLayout(toolbar)

        self.scene = QGraphicsScene()
        self.view = _GraphView(self.scene)
        self.view.setStyleSheet(
            "QGraphicsView { background-color: #F8FAFC; border: 1px solid #CBD5E1; "
            "border-radius: 4px; }"
        )
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.view, stretch=1)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #64748B; font-style: italic;")
        layout.addWidget(self.lbl_info)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Построение графа
    # ------------------------------------------------------------------
    def refresh(self):
        self.scene.clear()

        items = {it.id: it for it in self.repo.get_latest_versions()}
        relations = self.pc_repo.get_all()

        # Только связи между существующими элементами
        edges = [
            (r.parent_id, r.child_id, r.is_primary)
            for r in relations
            if r.parent_id in items and r.child_id in items
        ]

        children = {}
        has_parent = set()
        for pid, cid, _ in edges:
            children.setdefault(pid, []).append(cid)
            has_parent.add(cid)

        layer = self._assign_layers(items.keys(), children, has_parent)

        # Группируем по слоям, узлы сортируем по ID для стабильности
        by_layer: dict[int, list[int]] = {}
        for item_id, lvl in layer.items():
            by_layer.setdefault(lvl, []).append(item_id)

        node_items: dict[int, _NodeItem] = {}
        max_width = 0
        for lvl in sorted(by_layer):
            row = sorted(by_layer[lvl])
            y = lvl * (NODE_H + V_GAP)
            for col, item_id in enumerate(row):
                x = col * (NODE_W + H_GAP)
                it = items[item_id]
                designation = it.designation or it.name
                node = _NodeItem(
                    item_id, designation, is_root=item_id not in has_parent
                )
                node.setPos(x, y)
                self.scene.addItem(node)
                node_items[item_id] = node
            max_width = max(max_width, len(row) * (NODE_W + H_GAP))

        # Рёбра
        for pid, cid, is_primary in edges:
            self._draw_edge(node_items[pid], node_items[cid], is_primary)

        rect = self.scene.itemsBoundingRect()
        self.scene.setSceneRect(rect.adjusted(-40, -40, 40, 40))
        self._fit_view()

        n_borrowed = sum(1 for _, _, p in edges if not p)
        self.lbl_info.setText(
            f"Узлов: {len(items)}  |  Связей: {len(edges)}  "
            f"(первичных: {len(edges) - n_borrowed}, заимствований: {n_borrowed})"
        )

    def _assign_layers(self, all_ids, children, has_parent) -> dict[int, int]:
        """Слой узла = самый длинный путь от любого корня (longest-path layering).

        Гарантирует, что Заим. примен. всегда ниже всех своих родителей.
        """
        layer = {item_id: 0 for item_id in all_ids}
        # Итеративная релаксация (граф ацикличен — БД запрещает циклы)
        for _ in range(len(layer) + 1):
            changed = False
            for pid, kids in children.items():
                for cid in kids:
                    if layer[cid] < layer[pid] + 1:
                        layer[cid] = layer[pid] + 1
                        changed = True
            if not changed:
                break
        return layer

    def _draw_edge(self, parent_node: _NodeItem, child_node: _NodeItem, is_primary: bool):
        start = parent_node.center_bottom()
        end = child_node.center_top()

        path = QPainterPath(start)
        mid_y = (start.y() + end.y()) / 2
        path.cubicTo(
            QPointF(start.x(), mid_y),
            QPointF(end.x(), mid_y),
            end,
        )

        edge = QGraphicsPathItem(path)
        if is_primary:
            pen = QPen(QColor("#1D4ED8"), 2)
        else:
            pen = QPen(QColor("#9333EA"), 2, Qt.PenStyle.DashLine)
        edge.setPen(pen)
        edge.setZValue(0)
        self.scene.addItem(edge)

        # Стрелка на конце ребра
        self._draw_arrow_head(end, edge.pen().color())

    def _draw_arrow_head(self, tip: QPointF, color: QColor):
        size = 7
        path = QPainterPath()
        path.moveTo(tip.x(), tip.y())
        path.lineTo(tip.x() - size / 2, tip.y() - size)
        path.lineTo(tip.x() + size / 2, tip.y() - size)
        path.closeSubpath()
        head = QGraphicsPathItem(path)
        head.setBrush(QBrush(color))
        head.setPen(QPen(color))
        head.setZValue(0)
        self.scene.addItem(head)

    # ------------------------------------------------------------------
    # Взаимодействие
    # ------------------------------------------------------------------
    def _node_at(self, view_pos) -> _NodeItem | None:
        scene_pos = self.view.mapToScene(view_pos)
        for it in self.scene.items(scene_pos):
            if isinstance(it, _NodeItem):
                return it
            if isinstance(it, QGraphicsTextItem) and isinstance(it.parentItem(), _NodeItem):
                return it.parentItem()
        return None

    def _show_context_menu(self, pos):
        node = self._node_at(pos)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { padding: 4px; background-color: white; border: 1px solid #E2E8F0; }"
            "QMenu::item { padding: 6px 20px; border-radius: 3px; }"
            "QMenu::item:selected { background-color: #DBEAFE; }"
        )

        if node is not None:
            item_id = node.item_id
            action_add = menu.addAction("Добавить связь")
            action_add.triggered.connect(lambda: self.add_child_requested.emit(item_id))
            menu.addSeparator()
            action_edit = menu.addAction("Редактировать элемент")
            action_edit.triggered.connect(lambda: self.edit_requested.emit(item_id))

            item = self.repo.get_by_id_and_version(
                item_id, self.repo.get_max_version(item_id)
            )
            if item is not None and item.file_data is not None:
                action_view = menu.addAction("Просмотреть файл")
                action_view.triggered.connect(
                    lambda: self.view_file_requested.emit(item_id)
                )
        else:
            action_refresh = menu.addAction("Обновить")
            action_refresh.triggered.connect(self.refresh)

        menu.exec(self.view.viewport().mapToGlobal(pos))

    def _fit_view(self):
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _reset_zoom(self):
        self.view.resetTransform()
