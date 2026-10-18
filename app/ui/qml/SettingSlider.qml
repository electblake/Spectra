import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: field
    required property Controller controller
    required property string settingKey
    required property string label
    property string description: ""
    property real maximum: 3
    property real increment: 0.1
    spacing: 4
    RowLayout {
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: field.label
        }
        Label {
            text: Number(field.controller.settings[field.settingKey]).toLocaleString(Qt.locale(), "f", field.increment < 0.1 ? 2 : 1)
        }
    }
    Slider {
        objectName: field.settingKey
        Layout.fillWidth: true
        from: 0
        to: field.maximum
        stepSize: field.increment
        value: field.controller.settings[field.settingKey]
        Accessible.name: field.label
        onMoved: field.controller.setSetting(field.settingKey, value)
    }
    Label {
        Layout.fillWidth: true
        text: field.description
        visible: text.length > 0
        wrapMode: Text.WordWrap
    }
}
