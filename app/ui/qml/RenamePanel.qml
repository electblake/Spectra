import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    required property Controller controller
    readonly property var options: panel.controller.settings
    title: qsTr("Renaming")
    ColumnLayout {
        anchors.fill: parent
        spacing: 8
        SettingText {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "file_prefix"
            label: qsTr("Prefix (used exactly as entered)")
        }
        Label {
            text: qsTr("Start counting at")
        }
        SpinBox {
            objectName: "count_start"
            from: 0
            to: 2147483647
            editable: true
            value: panel.options["count_start"]
            Accessible.name: qsTr("Start counting at")
            onValueModified: panel.controller.setSetting("count_start", value)
        }
        CheckBox {
            text: qsTr("Parse file dates")
            checked: panel.options["parse_dates"]
            onToggled: panel.controller.setSetting("parse_dates", checked)
        }
        SettingText {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "date_pattern"
            label: qsTr("Date pattern (regular expression)")
            enabled: panel.options["parse_dates"]
        }
        Button {
            text: qsTr("Update examples")
            enabled: panel.options["parse_dates"]
            onClicked: panel.controller.updateExamples()
        }
        Label {
            Layout.fillWidth: true
            text: panel.controller.examples
            wrapMode: Text.WordWrap
        }
        SettingText {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "separator"
            label: qsTr("Separator before parsed date")
        }
    }
}
