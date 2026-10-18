import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GroupBox {
    id: panel
    required property Controller controller
    title: qsTr("Feature weights")
    ColumnLayout {
        anchors.fill: parent
        spacing: 12
        SettingSlider {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "rgb_weight"
            label: qsTr("RGB histogram")
            description: qsTr("Overall red, green, and blue color mix.")
        }
        SettingSlider {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "hsv_weight"
            label: qsTr("HSV histogram")
            description: qsTr("Hue, saturation, and color brightness.")
        }
        SettingSlider {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "spatial_weight"
            label: qsTr("Spatial color")
            description: qsTr("Where colors appear within the image.")
        }
        SettingSlider {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "texture_weight"
            label: qsTr("Texture")
            description: qsTr("Edges, patterns, and variations in detail.")
        }
        SettingSlider {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "brightness_weight"
            label: qsTr("Brightness and contrast")
            description: qsTr("Lightness, darkness, and tonal range.")
        }
        SettingSlider {
            Layout.fillWidth: true
            controller: panel.controller
            settingKey: "aspect_ratio_weight"
            label: qsTr("Aspect ratio")
            increment: 0.05
            description: qsTr("Portrait, square, and landscape proportions.")
        }
    }
}
