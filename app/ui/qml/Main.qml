import Spectra
import QtQuick
import QtQuick.Controls

ApplicationWindow {
    id: window
    required property Controller controller
    width: 1440
    height: 960
    minimumWidth: 760
    minimumHeight: 600
    visible: true
    title: window.controller.title
    font.pointSize: 12
    onClosing: close => {
        close.accepted = window.controller.requestClose();
    }

    Workspace {
        anchors.fill: parent
        controller: window.controller
        onQuitRequested: window.close()
    }
}
