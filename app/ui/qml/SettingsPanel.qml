import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: panel
    required property Controller controller
    readonly property var options: panel.controller.settings
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: panel.availableWidth
        enabled: !panel.controller.busy
        spacing: 16
        GroupBox {
            Layout.fillWidth: true
            title: qsTr("Performance")
            ColumnLayout {
                anchors.fill: parent
                Label {
                    text: qsTr("Image feature workers")
                }
                SpinBox {
                    objectName: "feature_workers"
                    from: 1
                    to: 64
                    value: panel.options["feature_workers"]
                    Accessible.name: qsTr("Image feature workers")
                    onValueModified: panel.controller.setSetting("feature_workers", value)
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Extraction threads. More workers use more memory. Default: 4.")
                    wrapMode: Text.WordWrap
                }
                Label {
                    text: qsTr("Video frame workers")
                }
                SpinBox {
                    objectName: "video_workers"
                    from: 1
                    to: 64
                    value: panel.options["video_workers"]
                    Accessible.name: qsTr("Video frame workers")
                    onValueModified: panel.controller.setSetting("video_workers", value)
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("One video per worker process. Default: 1.")
                    wrapMode: Text.WordWrap
                }
            }
        }
        GroupBox {
            Layout.fillWidth: true
            title: qsTr("Image processing")
            ColumnLayout {
                anchors.fill: parent
                Label {
                    text: qsTr("PNG compression level")
                }
                SpinBox {
                    objectName: "png_compress_level"
                    from: 0
                    to: 9
                    value: panel.options["png_compress_level"]
                    Accessible.name: qsTr("PNG compression level")
                    onValueModified: panel.controller.setSetting("png_compress_level", value)
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Video frames only. 0: uncompressed; 9: smallest files. Pixels are unchanged. Default: 1.")
                    wrapMode: Text.WordWrap
                }
                Label {
                    text: qsTr("Resize optimization")
                }
                ComboBox {
                    objectName: "resize_optimization"
                    model: ["Default", "Low", "Medium", "High"]
                    currentIndex: model.indexOf(panel.options["resize_optimization"])
                    Accessible.name: qsTr("Resize optimization")
                    onActivated: panel.controller.setSetting("resize_optimization", currentText)
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Analysis remains 100 × 100 pixels. Stronger optimization is faster and may change similarity results; originals are unchanged.")
                    wrapMode: Text.WordWrap
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: qsTr("Use Save Settings to keep these values for the next launch.")
            wrapMode: Text.WordWrap
        }
    }
}
