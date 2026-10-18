import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: field
    required property Controller controller
    required property string settingKey
    required property string label
    property bool numeric: false
    spacing: 4
    Label {
        text: field.label
    }
    TextField {
        objectName: field.settingKey
        Layout.fillWidth: true
        text: String(field.controller.settings[field.settingKey])
        Accessible.name: field.label
        selectByMouse: true
        onTextEdited: {
            if (!field.numeric)
                field.controller.setSetting(field.settingKey, text);
        }
        onEditingFinished: {
            if (field.numeric)
                field.controller.setSetting(field.settingKey, text);
        }
    }
}
