from PyQt5 import QtCore, QtGui, QtWidgets

class PhotoViewer(QtWidgets.QGraphicsView):
    photoClicked = QtCore.pyqtSignal(QtCore.QPoint)

    def __init__(self, parent):
        super(PhotoViewer, self).__init__(parent)
        self._zoom = 0
        self._empty = True

        self._scene = QtWidgets.QGraphicsScene(self)
        
        self.setScene(self._scene)
        
        self.pixmap=None

        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30)))
        self.setFrameShape(QtWidgets.QFrame.NoFrame)

    def hasPhoto(self):
        return not self._empty

    def fitInView(self, scale=True):
        px =  self.pixmap
        px = px.scaled(QtCore.QSize(self.width(), self.height()), QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
        self.m_pixmapItem.setPixmap(px)
        self._scene.setSceneRect(QtCore.QRectF(px.rect()))

    def fitInView2(self, scale=True):
        px = self.pixmap
        
        px = px.scaled(QtCore.QSize(self.width()*self._zoom, self.height()*self._zoom),
                       QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
        self.m_pixmapItem.setPixmap(px)
        self._scene.setSceneRect(QtCore.QRectF(px.rect()))


    def setPhoto(self, pixmap=None):
        self._zoom = 0
        if pixmap and not pixmap.isNull():
            self.pixmap =pixmap
            self._empty = False
            self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
            self.m_pixmapItem = self._scene.addPixmap(pixmap)
            self._scene.setSceneRect(QtCore.QRectF(pixmap.rect()))
            #self.centerOn(self.m_pixmapItem)
            self.setAlignment(QtCore.Qt.AlignTop)
        else:
            self._empty = True
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
        self.fitInView()     

    def wheelEvent(self, event):
        if self.hasPhoto():
            if event.angleDelta().y() > 0:
                factor = 1.25
                self._zoom += 1
                route = -1
            else:
                factor = 0.8
                self._zoom -= 1
                route = 1
            if self._zoom > 1:
                self.scale(factor, factor)
                self.fitInView2()
                mousePoint = self.mapToScene(event.pos()).toPoint()
                if self._zoom + route > 0:
                    col, row = int(int(mousePoint.x()) * ((self._zoom)/(self._zoom+route))), int(
                        int(mousePoint.y())*((self._zoom)/(self._zoom+route)))
                else:
                    col, row = int(mousePoint.x()) * \
                        (self._zoom), int(mousePoint.y())*(self._zoom)
                self.centerOn(QtCore.QPointF(col, row))
            elif self._zoom == 1:
                self.fitInView()
                self.resetTransform()
            else:
                self._zoom = 1

