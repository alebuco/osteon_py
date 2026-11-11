"""Visualizador 3D com VTK: renderização volumétrica (ray casting) do volume
e exibição de malhas (vtkPolyData). Embute o QVTKRenderWindowInteractor no Qt."""
from __future__ import annotations

# Força o backend Qt do VTK para PySide6 antes de importar o widget.
import vtkmodules.qt
vtkmodules.qt.PyQtImpl = "PySide6"
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor  # noqa: E402
import vtk  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from ..core import mesh as meshmod  # noqa: E402


class VolumeView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.vtk_widget = QVTKRenderWindowInteractor(self)
        self.ren = vtk.vtkRenderer()
        self.ren.SetBackground(0.02, 0.03, 0.04)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.ren)
        self.iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.vtk_widget)

        self._volume_actor = None
        self._mesh_actors = []
        self._started = False

    def start(self):
        if not self._started:
            self.iren.Initialize()
            self._started = True

    # -- volume -------------------------------------------------------------
    def show_volume(self, vol):
        self.clear()
        img = meshmod.build_vtk_image(vol)
        mapper = vtk.vtkGPUVolumeRayCastMapper()
        mapper.SetInputData(img)

        color = vtk.vtkColorTransferFunction()
        color.AddRGBPoint(-1000, 0.0, 0.0, 0.0)
        color.AddRGBPoint(-200, 0.55, 0.37, 0.28)
        color.AddRGBPoint(150, 0.78, 0.62, 0.45)
        color.AddRGBPoint(400, 0.93, 0.87, 0.78)
        color.AddRGBPoint(1500, 1.0, 1.0, 0.98)

        opacity = vtk.vtkPiecewiseFunction()
        opacity.AddPoint(-1000, 0.0)
        opacity.AddPoint(120, 0.0)
        opacity.AddPoint(300, 0.15)
        opacity.AddPoint(800, 0.75)
        opacity.AddPoint(1500, 0.9)

        prop = vtk.vtkVolumeProperty()
        prop.SetColor(color)
        prop.SetScalarOpacity(opacity)
        prop.ShadeOn()
        prop.SetInterpolationTypeToLinear()
        prop.SetAmbient(0.3)
        prop.SetDiffuse(0.7)
        prop.SetSpecular(0.2)

        actor = vtk.vtkVolume()
        actor.SetMapper(mapper)
        actor.SetProperty(prop)
        self.ren.AddVolume(actor)
        self._volume_actor = actor
        self.ren.ResetCamera()
        self.render()

    # -- malhas -------------------------------------------------------------
    def show_meshes(self, items):
        """items: lista de (polydata, (r,g,b), opacity)."""
        self.clear()
        for poly, color, op in items:
            m = vtk.vtkPolyDataMapper()
            m.SetInputData(poly)
            m.ScalarVisibilityOff()
            a = vtk.vtkActor()
            a.SetMapper(m)
            a.GetProperty().SetColor(*color)
            a.GetProperty().SetOpacity(op)
            a.GetProperty().SetInterpolationToPhong()
            self.ren.AddActor(a)
            self._mesh_actors.append(a)
        self.ren.ResetCamera()
        self.render()

    def clear(self):
        if self._volume_actor is not None:
            self.ren.RemoveVolume(self._volume_actor)
            self._volume_actor = None
        for a in self._mesh_actors:
            self.ren.RemoveActor(a)
        self._mesh_actors = []

    def render(self):
        self.vtk_widget.GetRenderWindow().Render()
