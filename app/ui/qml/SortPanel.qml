import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: panel
    required property Controller controller
    readonly property var options: panel.controller.settings
    signal browseRequested
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: panel.availableWidth
        enabled: !panel.controller.busy
        spacing: 16
        GroupBox {
            title: qsTr("Media")
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                SettingText {
                    Layout.fillWidth: true
                    controller: panel.controller
                    settingKey: "folder_path"
                    label: qsTr("Media folder")
                }
                RowLayout {
                    Button {
                        text: qsTr("Browse…")
                        onClicked: panel.browseRequested()
                    }
                    Button {
                        text: qsTr("Open Folder")
                        enabled: panel.options["folder_path"].length > 0
                        onClicked: panel.controller.openFolder()
                    }
                }
            }
        }
        GroupBox {
            title: qsTr("Clusters")
            Layout.fillWidth: true
            ColumnLayout {
                anchors.fill: parent
                CheckBox {
                    text: qsTr("Auto-determine threshold")
                    checked: panel.options["auto_determine"]
                    onToggled: panel.controller.setSetting("auto_determine", checked)
                }
                SettingText {
                    Layout.fillWidth: true
                    controller: panel.controller
                    settingKey: "similarity_threshold"
                    label: qsTr("Similarity threshold")
                    numeric: true
                    enabled: !panel.options["auto_determine"]
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Lower values create tighter clusters. Typical range: 0.005–0.05.")
                    wrapMode: Text.WordWrap
                }
            }
        }
        RenamePanel {
            Layout.fillWidth: true
            controller: panel.controller
        }
        WeightsPanel {
            Layout.fillWidth: true
            controller: panel.controller
        }
        GroupBox {
            title: qsTr("Video")
            Layout.fillWidth: true
            SettingSlider {
                anchors.fill: parent
                controller: panel.controller
                settingKey: "video_frame_percentage"
                label: qsTr("Frame position (%)")
                description: qsTr("Applies to newly extracted frames. Existing cached frames are reused.")
                maximum: 100
                increment: 1
                enabled: panel.options["include_videos"]
            }
        }
    }
}
