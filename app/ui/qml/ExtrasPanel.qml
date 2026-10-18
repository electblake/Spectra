import Spectra
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ScrollView {
    id: panel
    required property Controller controller
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: panel.availableWidth
        enabled: !panel.controller.busy
        spacing: 16
        GroupBox {
            Layout.fillWidth: true
            title: qsTr("File Explorer")
            ColumnLayout {
                anchors.fill: parent
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Add Open in Spectra to right-click menus for folders, folder backgrounds, and drives.")
                    wrapMode: Text.WordWrap
                }
                Button {
                    text: qsTr("Install in File Explorer")
                    onClicked: panel.controller.installExplorer()
                }
            }
        }
        GroupBox {
            Layout.fillWidth: true
            title: qsTr("Updates")
            ColumnLayout {
                anchors.fill: parent
                Label {
                    Layout.fillWidth: true
                    text: panel.controller.updateStatus
                    wrapMode: Text.WordWrap
                }
                Button {
                    text: qsTr("Check for Updates")
                    onClicked: panel.controller.checkUpdates()
                }
                Button {
                    text: qsTr("View Releases")
                    onClicked: panel.controller.viewReleases()
                }
            }
        }
    }
}
