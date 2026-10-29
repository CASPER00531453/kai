"""Explorer file drops onto the island window."""

from __future__ import annotations

import pythoncom
import win32con
from win32com.shell import shell


class FileDrop:
    _public_methods_ = ["DragEnter", "DragOver", "DragLeave", "Drop"]
    _com_interfaces_ = [pythoncom.IID_IDropTarget]

    def __init__(self, on_enter, on_leave, on_drop) -> None:
        self.on_enter = on_enter
        self.on_leave = on_leave
        self.on_drop = on_drop

    def _files(self, data_object) -> list[str]:
        fmt = (win32con.CF_HDROP, None, pythoncom.DVASPECT_CONTENT, -1, pythoncom.TYMED_HGLOBAL)
        try:
            medium = data_object.GetData(fmt)
        except pythoncom.com_error:
            return []
        try:
            found = shell.DragQueryFile(medium.data_handle)
        except Exception:
            return []
        if isinstance(found, str):
            return [found]
        return [path for path in found if path]

    def DragEnter(self, data_object, key_state, point, effect):
        files = self._files(data_object)
        if files:
            self.on_enter()
            return pythoncom.DROPEFFECT_COPY
        return pythoncom.DROPEFFECT_NONE

    def DragOver(self, key_state, point, effect):
        return pythoncom.DROPEFFECT_COPY

    def DragLeave(self):
        self.on_leave()

    def Drop(self, data_object, key_state, point, effect):
        files = self._files(data_object)
        if files:
            self.on_drop(files)
            return pythoncom.DROPEFFECT_COPY
        return pythoncom.DROPEFFECT_NONE


def attach(hwnd: int, on_enter, on_leave, on_drop):
    pythoncom.OleInitialize()
    target = FileDrop(on_enter, on_leave, on_drop)
    wrapped = pythoncom.WrapObject(target, pythoncom.IID_IDropTarget, pythoncom.IID_IDropTarget)
    pythoncom.RegisterDragDrop(int(hwnd), wrapped)
    return wrapped


def detach(hwnd: int) -> None:
    try:
        pythoncom.RevokeDragDrop(int(hwnd))
    except Exception:
        pass
