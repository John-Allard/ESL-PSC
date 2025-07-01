from __future__ import annotations

"""A simple QGraphicsView-based viewer for phylogenetic trees."""

from typing import Dict
from PyQt6.QtWidgets import (
    QWidget,
    QGraphicsView,
    QGraphicsScene,
    QVBoxLayout,
    QGraphicsTextItem,
)
from PyQt6.QtGui import QPainter, QPen
from PyQt6.QtCore import Qt
from Bio.Phylo.Newick import Tree, Clade


class _ZoomableGraphicsView(QGraphicsView):
    """Graphics view that supports wheel-based zooming."""

    def wheelEvent(self, event):
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self.scale(factor, factor)


class TreeViewer(QWidget):
    """Window displaying a Newick phylogenetic tree."""

    def __init__(self, tree: Tree, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Phylogenetic Tree")
        self.resize(1000, 1000)
        layout = QVBoxLayout(self)

        self.view = _ZoomableGraphicsView()
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )

        layout.addWidget(self.view)
        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)

        self._draw_tree(tree)

    # ------------------------------------------------------------------
    def _y_positions(self, tree: Tree, step: int = 30) -> Dict[Clade, float]:
        """Assign y positions to all nodes based on tip order."""
        y: Dict[Clade, float] = {}
        for idx, leaf in enumerate(tree.get_terminals()):
            y[leaf] = idx * step

        def set_internal(clade: Clade) -> float:
            if clade.is_terminal():
                return y[clade]
            vals = [set_internal(c) for c in clade.clades]
            y[clade] = sum(vals) / len(vals)
            return y[clade]

        set_internal(tree.root)
        return y

    # ------------------------------------------------------------------
    def _depths(self, tree: Tree) -> Dict[Clade, float]:
        """Return cumulative branch lengths with missing lengths treated as 1."""
        depths: Dict[Clade, float] = {tree.root: 0.0}
        for clade in tree.find_clades(order="preorder"):
            parent_depth = depths.get(clade, 0.0)
            for child in clade.clades:
                bl = child.branch_length if child.branch_length is not None else 1.0
                depths[child] = parent_depth + bl
        return depths

    # ------------------------------------------------------------------
    def _draw_tree(self, tree: Tree) -> None:
        """Render the tree to the graphics scene."""
        depths = self._depths(tree)
        max_depth = max(depths.values()) if depths else 1
        y_pos = self._y_positions(tree)

        tree_width = 800
        label_offset = 10
        scale = tree_width / max_depth

        x_scaled = {clade: d * scale for clade, d in depths.items()}

        pen = QPen(Qt.GlobalColor.black)
        for clade in tree.find_clades(order="preorder"):
            x_parent, y_parent = x_scaled.get(clade, 0), y_pos.get(clade, 0)
            for child in clade.clades:
                x_child, y_child = x_scaled.get(child, 0), y_pos.get(child, 0)
                # Horizontal from child to parent's x
                self.scene.addLine(x_child, y_child, x_parent, y_child, pen)
                # Vertical up to parent
                self.scene.addLine(x_parent, y_parent, x_parent, y_child, pen)

        for leaf in tree.get_terminals():
            y_leaf = y_pos.get(leaf, 0)
            label = QGraphicsTextItem(leaf.name or "")
            self.scene.addItem(label)
            label.setPos(tree_width + label_offset, y_leaf - label.boundingRect().height() / 2)

        total_height = len(tree.get_terminals()) * 30 + 20
        self.scene.setSceneRect(0, -10, tree_width + 150, total_height)

