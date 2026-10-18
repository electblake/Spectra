import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: bar
    required property Controller controller
    readonly property var options: bar.controller.settings
    signal startRequested
    RowLayout {
        enabled: !bar.controller.busy
        CheckBox {
            text: qsTr("Include videos")
            checked: bar.options["include_videos"]
            onToggled: bar.controller.setSetting("include_videos", checked)
        }
        CheckBox {
            text: qsTr("Dry run (preview)")
            checked: bar.options["dry_run"]
            onToggled: bar.controller.setSetting("dry_run", checked)
        }
        CheckBox {
            text: qsTr("Create backup")
            checked: bar.options["backup"]
            onToggled: bar.controller.setSetting("backup", checked)
        }
    }
    RowLayout {
        Button {
            objectName: "startButton"
            text: qsTr("Start Sorting")
            highlighted: true
            enabled: !bar.controller.busy && bar.options["folder_path"].length > 0
            onClicked: bar.startRequested()
        }
        Button {
            objectName: "stopButton"
            text: qsTr("Stop")
            enabled: bar.controller.cancellable
            onClicked: bar.controller.stop()
        }
        Item {
            Layout.fillWidth: true
        }
        Button {
            text: qsTr("Save Settings")
            enabled: !bar.controller.busy
            onClicked: bar.controller.saveSettings()
        }
        Button {
            text: qsTr("Restore Defaults")
            enabled: !bar.controller.busy
            onClicked: bar.controller.restoreDefaults()
        }
    }
}
