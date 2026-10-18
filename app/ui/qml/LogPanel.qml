import Spectra
import QtQuick
import QtQuick.Controls

GroupBox {
    id: panel
    required property Controller controller
    title: qsTr("Activity")
    ScrollView {
        anchors.fill: parent
        TextArea {
            id: log
            objectName: "activityLog"
            readOnly: true
            selectByMouse: true
            wrapMode: TextEdit.Wrap
            textFormat: TextEdit.PlainText
            text: qsTr("Ready. Choose a media folder to begin.")
            Accessible.name: qsTr("Activity log")
        }
    }
    Connections {
        target: panel.controller
        function onLogMessage(message) {
            log.append(message);
        }
        function onClearLog() {
            log.clear();
        }
    }
}
