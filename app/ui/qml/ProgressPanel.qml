import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: panel
    required property Controller controller
    RowLayout {
        Label {
            Layout.fillWidth: true
            text: panel.controller.status
            elide: Text.ElideMiddle
        }
        Label {
            text: panel.controller.metrics
        }
        Label {
            text: panel.controller.indeterminate ? qsTr("Working…") : qsTr("%1%").arg(Math.round(panel.controller.fraction * 100))
        }
    }
    ProgressBar {
        Layout.fillWidth: true
        value: panel.controller.fraction
        indeterminate: panel.controller.indeterminate
        Accessible.name: qsTr("Current stage progress")
    }
}
